#!/usr/bin/env python3
"""LAN sinkronizazioa: kideen aurkikuntza eta trukea.

Bi zati:

* **Aurkikuntza** — UDP multicast bidezko seinale bat 5 segundoro. Seinaleak
  taldearen *marka* darama (gakoaren hash-a, ez gakoa), beraz talde bereko
  gailuek elkar aurkitzen dute inolako zerbitzaririk gabe.
* **Trukea** — HTTP entzule minimo bat, `POST /sync` bakarrik onartzen duena.
  Gorputz guztiak `.rootsync` fardel zifratuak dira; deszifratzen ez den oro
  isilean baztertzen da.

Interfaze grafikoa EZ da hemendik zerbitzatzen: hura 127.0.0.1-en bakarrik
entzuten du (`app.py`). Kanpora zabalik dagoen azalera bakarra `POST /sync` da.
"""

import json
import os
import socket
import struct
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import db
import konfig
import kripto
import sinkro

MULTICAST_TALDEA = "239.255.42.77"
AURKIKUNTZA_PORTUA = int(os.environ.get("AURKIKUNTZA_PORTUA", "47777"))
SYNC_PORTUA = int(os.environ.get("SYNC_PORT", "47778"))

SEINALE_TARTEA = 5          # segundo
SINKRO_TARTEA = 20          # segundo
KIDE_IRAUNGITZEA = 60       # segundo seinalerik gabe → kidea ahaztu
ESKAERA_MUGA = 30           # eskaera minutuko IP bakoitzeko
GEHIENEZ_SEINALEA = 1024

_egoera_giltza = threading.Lock()
_kideak: dict = {}
_azken_sinkro: dict = {"noiz": None, "emaitza": None, "errorea": None}


# ─── Egoera partekatua ──────────────────────────────────────────────────────


def kideak() -> list:
    orain = time.time()
    with _egoera_giltza:
        return [
            {**k, "duela": int(orain - k["azken_ikusia"])}
            for k in _kideak.values()
            if orain - k["azken_ikusia"] < KIDE_IRAUNGITZEA
        ]


def azken_sinkro() -> dict:
    with _egoera_giltza:
        return dict(_azken_sinkro)


def _sinkro_emaitza_gorde(emaitza=None, errorea=None) -> None:
    with _egoera_giltza:
        _azken_sinkro.update(
            {"noiz": int(time.time()), "emaitza": emaitza, "errorea": errorea}
        )


# ─── Entzulea (kide rola) ───────────────────────────────────────────────────


class _SyncKudeatzailea(BaseHTTPRequestHandler):
    server_version = "RootErregistroa"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, formatua, *argumentuak):  # zaratarik ez
        pass

    def _erantzun(self, kodea: int, gorputza: bytes = b"") -> None:
        self.send_response(kodea)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(gorputza)))
        self.end_headers()
        if gorputza:
            self.wfile.write(gorputza)

    def do_POST(self):  # noqa: N802
        if self.path != "/sync":
            return self._erantzun(404)
        if not _muga_onartzen_du(self.client_address[0]):
            return self._erantzun(429)

        try:
            luzera = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._erantzun(400)
        if not 0 < luzera <= kripto.GEHIENEZ_FARDELA:
            return self._erantzun(413)

        gorputza = self.rfile.read(luzera)
        konn = db.konexioa()
        try:
            erantzuna = sinkro.eskaera_erantzun(konn, gorputza)
            self._erantzun(200, erantzuna)
        except (kripto.KriptoErrorea, sinkro.SinkroErrorea, ValueError):
            # Xehetasunik ez: erantzun desberdinek erasotzaile bati zer den
            # baliozkoa asmatzen lagunduko liokete.
            self._erantzun(400)
        except Exception:
            self._erantzun(500)
        finally:
            konn.close()


_eskaera_kontagailua: dict = {}


def _muga_onartzen_du(ip: str) -> bool:
    orain = time.time()
    with _egoera_giltza:
        marka = [t for t in _eskaera_kontagailua.get(ip, []) if orain - t < 60]
        if len(marka) >= ESKAERA_MUGA:
            _eskaera_kontagailua[ip] = marka
            return False
        marka.append(orain)
        _eskaera_kontagailua[ip] = marka
        return True


# ─── Aurkikuntza ────────────────────────────────────────────────────────────


def _seinalea_bidali(hargailua: socket.socket) -> None:
    marka = sinkro.talde_marka()
    if not marka:
        return
    seinalea = json.dumps(
        {
            "talde_marka": marka,
            "gailu_id": konfig.gailu_id(),
            "izena": konfig.gailu_izena(),
            "portua": SYNC_PORTUA,
        }
    ).encode()
    try:
        hargailua.sendto(seinalea, (MULTICAST_TALDEA, AURKIKUNTZA_PORTUA))
    except OSError:
        pass  # sarerik gabe: hurrengoan saiatuko da


def _seinalea_prozesatu(datuak: bytes, helbidea) -> None:
    if len(datuak) > GEHIENEZ_SEINALEA:
        return
    try:
        seinalea = json.loads(datuak)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(seinalea, dict):
        return
    if seinalea.get("talde_marka") != sinkro.talde_marka():
        return  # beste talde batekoa
    gailu_id = seinalea.get("gailu_id")
    if not isinstance(gailu_id, str) or gailu_id == konfig.gailu_id():
        return
    portua = seinalea.get("portua")
    if not isinstance(portua, int) or not 1 <= portua <= 65535:
        return

    with _egoera_giltza:
        _kideak[gailu_id] = {
            "gailu_id": gailu_id,
            "izena": str(seinalea.get("izena", ""))[:60],
            "helbidea": helbidea[0],
            "portua": portua,
            "azken_ikusia": time.time(),
        }


def _aurkikuntza_haria(gelditu: threading.Event) -> None:
    hargailua = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    hargailua.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    hargailua.settimeout(1.0)
    try:
        hargailua.bind(("", AURKIKUNTZA_PORTUA))
        mreq = struct.pack(
            "4sl", socket.inet_aton(MULTICAST_TALDEA), socket.INADDR_ANY
        )
        hargailua.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        hargailua.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    except OSError as e:
        print(f"[sarea] Aurkikuntza ezin da abiarazi: {e}")
        return

    azkena = 0.0
    while not gelditu.is_set():
        if time.time() - azkena > SEINALE_TARTEA:
            _seinalea_bidali(hargailua)
            azkena = time.time()
        try:
            datuak, helbidea = hargailua.recvfrom(GEHIENEZ_SEINALEA + 1)
            _seinalea_prozesatu(datuak, helbidea)
        except socket.timeout:
            continue
        except OSError:
            time.sleep(1)
    hargailua.close()


# ─── Trukea (bezero rola) ───────────────────────────────────────────────────


def _bidali(kidea: dict, gorputza: bytes) -> bytes:
    eskaera = urllib.request.Request(
        f"http://{kidea['helbidea']}:{kidea['portua']}/sync",
        data=gorputza,
        headers={"Content-Type": "application/octet-stream"},
        method="POST",
    )
    with urllib.request.urlopen(eskaera, timeout=10) as erantzuna:
        return erantzuna.read(kripto.GEHIENEZ_FARDELA + 1)


def kidearekin_sinkronizatu(konn, kidea: dict) -> dict:
    """Truke osoa kide batekin: jaso eta bidali."""
    erantzuna = _bidali(kidea, sinkro.eskaera_sortu(konn))
    emaitza = sinkro.erantzuna_prozesatu(konn, erantzuna)

    if emaitza.get("bultzada"):
        _bidali(kidea, emaitza["bultzada"])

    return {
        "kidea": kidea.get("izena") or kidea["gailu_id"][:8],
        "jasoak": emaitza["jasoak"],
        "bidaliak": emaitza["bidaltzekoak"],
    }


def orain_sinkronizatu() -> dict:
    """Kide guztiekin sinkronizatu. Interfazeko botoiak eta hariak deitzen dute."""
    zerrenda = kideak()
    if not zerrenda:
        _sinkro_emaitza_gorde(errorea="Ez da kiderik aurkitu sare lokalean")
        return {"kideak": 0, "emaitzak": []}

    konn = db.konexioa()
    emaitzak, akatsak = [], []
    try:
        for kidea in zerrenda:
            try:
                emaitzak.append(kidearekin_sinkronizatu(konn, kidea))
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                akatsak.append(f"{kidea.get('izena', '?')}: konexio arazoa ({e})")
            except (kripto.KriptoErrorea, sinkro.SinkroErrorea) as e:
                akatsak.append(f"{kidea.get('izena', '?')}: {e}")
    finally:
        konn.close()

    _sinkro_emaitza_gorde(emaitza=emaitzak, errorea="; ".join(akatsak) or None)
    return {"kideak": len(zerrenda), "emaitzak": emaitzak, "akatsak": akatsak}


def _sinkro_haria(gelditu: threading.Event) -> None:
    while not gelditu.wait(SINKRO_TARTEA):
        if not konfig.ezarpenak().get("sync_auto", True):
            continue
        if not konfig.talderik_badago():
            continue
        try:
            orain_sinkronizatu()
        except Exception as e:  # hariak ez du inoiz hil behar
            _sinkro_emaitza_gorde(errorea=str(e))


# ─── Abiaraztea ─────────────────────────────────────────────────────────────


class Zerbitzua:
    def __init__(self):
        self.gelditu = threading.Event()
        self.zerbitzaria = None
        self.hariak = []

    def abiarazi(self) -> None:
        if not konfig.talderik_badago():
            print("[sarea] Talderik gabe: LAN sinkronizazioa itzalita.")
            return
        try:
            self.zerbitzaria = ThreadingHTTPServer(("0.0.0.0", SYNC_PORTUA), _SyncKudeatzailea)
        except OSError as e:
            print(f"[sarea] {SYNC_PORTUA} portua ezin da ireki: {e}")
            return

        for helburua in (
            lambda: self.zerbitzaria.serve_forever(poll_interval=1),
            lambda: _aurkikuntza_haria(self.gelditu),
            lambda: _sinkro_haria(self.gelditu),
        ):
            haria = threading.Thread(target=helburua, daemon=True)
            haria.start()
            self.hariak.append(haria)
        print(f"[sarea] LAN sinkronizazioa martxan (portua {SYNC_PORTUA})")

    def gelditu_dena(self) -> None:
        self.gelditu.set()
        if self.zerbitzaria:
            self.zerbitzaria.shutdown()
