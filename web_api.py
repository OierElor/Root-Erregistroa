#!/usr/bin/env python3
"""APIaren logika, HTTPtik aske.

Hemen dago backend-aren logika osoa, Flask-en mendekotasunik gabe: `deitu()`-ri
bide bat, metodo bat eta gorputza ematen zaizkio, eta hiztegi bat itzultzen du.

Bi frontend-ek geruza hau erabiltzen dute:

* `app.py` — mahaigaineko Flask zerbitzaria (127.0.0.1).
* Nabigatzailean Pyodide bidez exekutatzen den bertsioa (mobila), non ez dagoen
  HTTPrik: JavaScript-ek `deitu()`-ri zuzenean deitzen dio.

Zergatik geruza bakarra: jokalarien identifikatzaileak, Lamport erlojua eta
gertaeren ordena zehatz-mehatz berdinak izan behar dira bi frontend-etan, bestela
`.rootsync` fitxategiak bateratzean datuak zatituko lirateke. Logika bakarra
edukita, bateragarritasuna ez da mantendu beharreko zerbait: definizioz dator.
"""

import sqlite3
import time
import uuid

import babeskopiak
import db
import estatistikak
import gertaerak
import konfig
import sinkro


class Fitxategia:
    """Erantzun bat fitxategi gisa: esportatzeak JSON hutsa itzultzen du, ez hiztegia."""

    def __init__(self, byteak: bytes, izena: str, mota: str = "application/json"):
        self.byteak = byteak
        self.izena = izena
        self.mota = mota


class BideErrorea(Exception):
    """Bide edo metodo ezezaguna."""


class Eskaera:
    """Eskaera baten datuak, jatorria edozein izanik (HTTP edo Pyodide dei bat)."""

    def __init__(self, konn: sqlite3.Connection, gorputza=None, kontsulta=None, byteak=None):
        self.k = konn
        self._gorputza = gorputza
        self.kontsulta = kontsulta or {}
        self.byteak = byteak

    def json(self) -> dict:
        if not isinstance(self._gorputza, dict):
            raise ValueError("JSON objektu bat espero zen")
        return self._gorputza


# Katalogo guztiek egitura bera dute; taula-izena kodean dago finkatuta, ez
# eskaeran (ikus `KATALOGOAK`), beraz ez dago SQL injekziorako biderik.
_KATALOGO_KONTSULTA = (
    "SELECT kodea, izena, hedapena FROM %s WHERE ezabatuta = 0 "
    "ORDER BY hedapena, izena"
)

# Katalogoen izen publikoa → (gorde gertaera, ezabatu gertaera, kolorea du?)
KATALOGOAK = {
    "fakzioak":      ("fakzioa_gorde", "fakzioa_ezabatu", True),
    "mertzenarioak": ("mertzenarioa_gorde", "mertzenarioa_ezabatu", False),
    "leku-bereziak": ("lekua_gorde", "lekua_ezabatu", False),
    "arloteak":      ("arlotea_gorde", "arlotea_ezabatu", False),
}


# ─── Katalogoak eta hasierako datuak ────────────────────────────────────────


def hasiera(esk: Eskaera) -> dict:
    k = esk.k
    return dict(
        laburpena=estatistikak.laburpena(k),
        jokalariak=[
            dict(l) for l in k.execute(
                "SELECT id, izena, ezizena FROM jokalariak WHERE ezabatuta = 0 "
                "ORDER BY izena COLLATE NOCASE"
            )
        ],
        fakzioak=[
            dict(l) for l in k.execute(
                "SELECT kodea, izena, hedapena, kolorea, arlotea FROM fakzioak "
                "WHERE ezabatuta = 0 ORDER BY hedapena, izena"
            )
        ],
        mertzenarioak=[dict(l) for l in k.execute(_KATALOGO_KONTSULTA % "mertzenarioak")],
        leku_bereziak=[dict(l) for l in k.execute(_KATALOGO_KONTSULTA % "leku_bereziak")],
        arloteak=[dict(l) for l in k.execute(_KATALOGO_KONTSULTA % "arloteak")],
        mapak=[dict(l) for l in k.execute("SELECT * FROM mapak ORDER BY izena")],
        karta_sortak=[dict(l) for l in k.execute("SELECT * FROM karta_sortak")],
        garaipen_motak=[
            {"kodea": kodea, "izena": izena} for kodea, izena in db.GARAIPEN_MOTAK
        ],
        sinkro=sinkro.egoera(k),
        ezarpenak=konfig.ezarpenak(),
    )


# ─── Jokalariak ─────────────────────────────────────────────────────────────


def _jokalaria_ziurtatu(k, izena: str) -> str:
    """Izen bat jokalari-id bihurtu, behar bada jokalaria sortuz.

    Identifikatzailea izenetik eratortzen da, beraz bi ordenagailutan jokalari
    bera sartzeak ez du bikoizturik sortzen sinkronizatzean.
    """
    izena = (izena or "").strip()
    if not izena:
        raise ValueError("Jokalariaren izena hutsik dago")

    # Lehenik izenez: jokalariari izena aldatu bazaio, ez sortu berri bat.
    lerroa = k.execute(
        "SELECT id FROM jokalariak WHERE izena = ? COLLATE NOCASE AND ezabatuta = 0",
        (izena,),
    ).fetchone()
    if lerroa:
        return lerroa["id"]

    jokalari_id = gertaerak.jokalari_id_izenetik(izena)
    if k.execute("SELECT 1 FROM jokalariak WHERE id = ?", (jokalari_id,)).fetchone():
        # Badago (izena aldatuta edo ezabatuta): ez berridatzi isilean.
        return jokalari_id

    gertaerak.gertaera_berria(k, "jokalaria_gorde", {"id": jokalari_id, "izena": izena})
    return jokalari_id


def jokalaria_gorde(esk: Eskaera) -> dict:
    datuak = esk.json()
    karga = {
        "id": datuak.get("id") or gertaerak.jokalari_id_izenetik(datuak.get("izena", "")),
        "izena": datuak.get("izena"),
        "ezizena": datuak.get("ezizena"),
    }
    gertaerak.gertaera_berria(esk.k, "jokalaria_gorde", karga)
    return dict(ok=True, id=karga["id"])


def jokalaria_ezabatu(esk: Eskaera, jokalari_id: str) -> dict:
    gertaerak.gertaera_berria(esk.k, "jokalaria_ezabatu", {"id": jokalari_id})
    return dict(ok=True)


# ─── Partidak ───────────────────────────────────────────────────────────────


def partidak_zerrendatu(esk: Eskaera) -> dict:
    iragazkia = {
        "jokalari_id": esk.kontsulta.get("jokalari_id"),
        "fakzio_kodea": esk.kontsulta.get("fakzio_kodea"),
        "mapa_kodea": esk.kontsulta.get("mapa_kodea"),
    }
    muga = str(esk.kontsulta.get("muga") or "50")
    return dict(
        partidak=estatistikak.azken_partidak(
            esk.k, int(muga) if muga.isdigit() else 50, iragazkia
        )
    )


def partida_gorde(esk: Eskaera) -> dict:
    datuak = esk.json()
    k = esk.k

    parte_hartzaileak = datuak.get("jokalariak")
    if not isinstance(parte_hartzaileak, list):
        raise ValueError("jokalariak: zerrenda bat behar da")

    prestatuak = []
    for sarrera in parte_hartzaileak:
        if not isinstance(sarrera, dict):
            raise ValueError("jokalari sarrera baliogabea")
        jokalari_id = sarrera.get("jokalari_id") or _jokalaria_ziurtatu(
            k, sarrera.get("izena", "")
        )
        prestatuak.append({**sarrera, "jokalari_id": jokalari_id})

    karga = {
        "id": datuak.get("id") or uuid.uuid4().hex,
        "data": datuak.get("data") or time.strftime("%Y-%m-%d"),
        "mapa_kodea": datuak.get("mapa_kodea"),
        "karta_sorta": datuak.get("karta_sorta"),
        "oharrak": datuak.get("oharrak"),
        "jokalariak": prestatuak,
        "mertzenarioak": datuak.get("mertzenarioak"),
        "leku_bereziak": datuak.get("leku_bereziak"),
    }
    gertaerak.gertaera_berria(k, "partida_gorde", karga)
    return dict(ok=True, id=karga["id"])


def partida_ezabatu(esk: Eskaera, partida_id: str) -> dict:
    gertaerak.gertaera_berria(esk.k, "partida_ezabatu", {"id": partida_id})
    return dict(ok=True)


# ─── Katalogoak ─────────────────────────────────────────────────────────────


def katalogoa_gorde(esk: Eskaera, katalogoa: str) -> dict:
    """Katalogo bateko sarrera bat gehitu edo izena aldatu.

    Gertaera bat denez, aldaketa ordenagailu guztietara sinkronizatzen da; eta
    `azken_lamport` mugitzen duenez, hurrengo abioan hazi-datuek ez dute
    berridazten (ikus `db.hasieratu`).
    """
    if katalogoa not in KATALOGOAK:
        raise ValueError("Katalogo ezezaguna")
    gorde_mota, _, kolorea_du = KATALOGOAK[katalogoa]

    datuak = esk.json()
    karga = {
        "kodea": datuak.get("kodea"),
        "izena": datuak.get("izena"),
        "hedapena": datuak.get("hedapena") or "Norberarena",
    }
    if kolorea_du:
        karga["kolorea"] = datuak.get("kolorea") or "#888888"

    gertaerak.gertaera_berria(esk.k, gorde_mota, karga)
    return dict(ok=True, kodea=karga["kodea"])


def katalogoa_ezabatu(esk: Eskaera, katalogoa: str, kodea: str) -> dict:
    if katalogoa not in KATALOGOAK:
        raise ValueError("Katalogo ezezaguna")
    gertaerak.gertaera_berria(esk.k, KATALOGOAK[katalogoa][1], {"kodea": kodea})
    return dict(ok=True)


# ─── Estatistikak ───────────────────────────────────────────────────────────


def estatistikak_ikusi(esk: Eskaera) -> dict:
    k = esk.k
    return dict(
        laburpena=estatistikak.laburpena(k),
        jokalariak=estatistikak.jokalarien_sailkapena(k),
        fakzioak=estatistikak.fakzioen_estatistikak(k),
        matrizea=estatistikak.jokalari_fakzio_matrizea(k),
        bilakaera=estatistikak.bilakaera(k),
        arloteak=estatistikak.arloteen_estatistikak(k),
        **estatistikak.osagarrien_erabilera(k),
    )


# ─── Fitxategi bidezko trukea ───────────────────────────────────────────────


def sinkro_egoera(esk: Eskaera) -> dict:
    return dict(**sinkro.egoera(esk.k))


def sinkro_esportatu(esk: Eskaera) -> Fitxategia:
    return Fitxategia(
        sinkro.fitxategira_esportatu(esk.k),
        f"root-erregistroa-{time.strftime('%Y%m%d-%H%M%S')}.rootsync",
    )


def sinkro_inportatu(esk: Eskaera) -> dict:
    if not esk.byteak:
        raise ValueError("Fitxategia hutsik dago")
    k = esk.k
    # Babeskopia fitxategia ona dela egiaztatu ondoren, datuak ukitu aurretik.
    return dict(
        babeskopia=True,
        **sinkro.fitxategitik_inportatu(
            k, esk.byteak, lambda: babeskopiak.kopia_egin(k, "inportazio")
        ),
    )


# ─── Babeskopiak ────────────────────────────────────────────────────────────


def babeskopia_zerrenda(esk: Eskaera) -> dict:
    return dict(kopiak=babeskopiak.zerrenda(), karpeta=str(babeskopiak.KOPIA_DIR))


def babeskopia_egin(esk: Eskaera) -> dict:
    bidea = babeskopiak.kopia_egin(esk.k, "eskuz")
    ezabatuak = babeskopiak.garbitu(konfig.ezarpenak()["babeskopia_gehienez"])
    return dict(ok=True, izena=bidea.name, ezabatuak=ezabatuak)


def babeskopia_leheneratu(esk: Eskaera) -> dict:
    izena = esk.json().get("izena", "")
    return dict(ok=True, **babeskopiak.leheneratu(esk.k, izena))


# ─── Ezarpenak eta mantentze-lanak ──────────────────────────────────────────


def ezarpenak_gorde(esk: Eskaera) -> dict:
    return dict(ezarpenak=konfig.ezarpenak_gorde(esk.json()))


def gailua_izendatu(esk: Eskaera) -> dict:
    konfig.gailua_izendatu(esk.json().get("izena", ""))
    return dict(ok=True, izena=konfig.gailu_izena())


def birsortu(esk: Eskaera) -> dict:
    """Proiekzioak gertaera-erregistrotik berreraiki (konponketa)."""
    return dict(ok=True, entitateak=gertaerak.birsortu(esk.k))


# ─── Bideak ─────────────────────────────────────────────────────────────────

# (metodoa, bidea, funtzioa). `*` bide-zati bat harrapatzen du, eta funtzioari
# argumentu gisa pasatzen zaio.
BIDEAK = (
    ("GET",    "/api/hasiera",                hasiera),
    ("POST",   "/api/jokalariak",             jokalaria_gorde),
    ("DELETE", "/api/jokalariak/*",           jokalaria_ezabatu),
    ("GET",    "/api/partidak",               partidak_zerrendatu),
    ("POST",   "/api/partidak",               partida_gorde),
    ("DELETE", "/api/partidak/*",             partida_ezabatu),
    ("POST",   "/api/katalogoak/*",           katalogoa_gorde),
    ("DELETE", "/api/katalogoak/*/*",         katalogoa_ezabatu),
    ("GET",    "/api/estatistikak",           estatistikak_ikusi),
    ("GET",    "/api/sinkro/egoera",          sinkro_egoera),
    ("GET",    "/api/sinkro/esportatu",       sinkro_esportatu),
    ("POST",   "/api/sinkro/inportatu",       sinkro_inportatu),
    ("GET",    "/api/babeskopiak",            babeskopia_zerrenda),
    ("POST",   "/api/babeskopiak",            babeskopia_egin),
    ("POST",   "/api/babeskopiak/leheneratu", babeskopia_leheneratu),
    ("POST",   "/api/ezarpenak",              ezarpenak_gorde),
    ("POST",   "/api/gailua",                 gailua_izendatu),
    ("POST",   "/api/birsortu",               birsortu),
)


def _bat_egin(bidea: str, metodoa: str):
    """Bide bat funtzio batekin lotu, harrapatutako zatiak itzuliz."""
    zatiak = bidea.strip("/").split("/")
    for onartua, eredua, funtzioa in BIDEAK:
        if onartua != metodoa:
            continue
        eredu_zatiak = eredua.strip("/").split("/")
        if len(eredu_zatiak) != len(zatiak):
            continue
        harrapatuak = []
        for eredu_zatia, zatia in zip(eredu_zatiak, zatiak):
            if eredu_zatia == "*":
                harrapatuak.append(zatia)
            elif eredu_zatia != zatia:
                break
        else:
            return funtzioa, harrapatuak
    raise BideErrorea(f"Bide ezezaguna: {metodoa} {bidea}")


def deitu(
    konn: sqlite3.Connection,
    bidea: str,
    metodoa: str = "GET",
    gorputza=None,
    kontsulta=None,
    byteak=None,
):
    """APIari deitu HTTPrik gabe.

    `sinkro/esportatu`-k `Fitxategia` bat itzultzen du; besteek hiztegia.
    """
    funtzioa, harrapatuak = _bat_egin(bidea, metodoa.upper())
    esk = Eskaera(konn, gorputza=gorputza, kontsulta=kontsulta, byteak=byteak)
    return funtzioa(esk, *harrapatuak)
