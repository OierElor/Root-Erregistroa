#!/usr/bin/env python3
"""Taldearen kudeaketa eta sinkronizazio-protokoloa.

Garraioa (LAN edo fitxategia) axola gabe, dena `.rootsync` fardel zifratuen
truke bat da. Hemen dago protokoloaren logika; `sarea.py`-k sarera eramaten du
eta `app.py`-k fitxategietara.

Protokoloa (bi eskaera, biak zifratuta)
---------------------------------------
    A → B   eskaera   {ezagunak: [A-ren gertaera-idak]}
    B → A   erantzuna {gertaerak: A-ri falta zaizkionak, ezagunak: B-renak}
    A → B   bultzada  {gertaerak: B-ri falta zaizkionak}

Bi norabideetan sinkronizatzen da eskaera bakar batekin. Ez dago zerbitzari
zentralik: gailu bakoitzak berdin-berdin jokatzen du bi rolotan.
"""

import base64
import sqlite3
import time

import db
import gertaerak
import konfig
import kripto

GEHIENEZ_GERTAERA_FARDELEAN = 20_000
GEHIENEZ_ID_ZERRENDAN = 200_000
NONCE_BIZITZA = 2 * kripto.DENBORA_LEIHOA


class SinkroErrorea(Exception):
    pass


# ─── Taldea ─────────────────────────────────────────────────────────────────
#
# Gatza taldearen izenetik eratortzen da, ez ausaz. Horri esker gailu berri
# batek taldera elkartzeko bi datu besterik ez ditu behar, ahoz eman
# daitezkeenak: taldearen izena eta pasaesaldia. Talde bakoitzak bere gatza du
# (izena desberdina bada), beraz talde guztientzako aurrez kalkulatutako taula
# bakar batek ez du balio.


def _gatza_izenetik(talde_izena: str) -> bytes:
    import hashlib

    normalizatua = " ".join(talde_izena.split()).lower()
    return hashlib.blake2b(
        f"root-erregistroa:{normalizatua}".encode(), digest_size=kripto.GATZ_LUZERA
    ).digest()


def taldea_konfiguratu(talde_izena: str, pasaesaldia: str) -> dict:
    """Taldea sortu edo talde batera elkartu — eragiketa bera da.

    Bi gailuk izen eta pasaesaldi berak erabiltzen badituzte, gako bera lortzen
    dute eta elkar ulertzen dute. Ez dago zerbitzarian erregistratu beharrik.
    """
    talde_izena = (talde_izena or "").strip()
    if not 3 <= len(talde_izena) <= 60:
        raise SinkroErrorea("Taldearen izenak 3 eta 60 karaktere artean izan behar ditu")

    gatza = _gatza_izenetik(talde_izena)
    gakoa = kripto.gakoa_eratorri(pasaesaldia, gatza)
    datuak = {
        "izena": talde_izena,
        "gatza": base64.b64encode(gatza).decode(),
        "gakoa": base64.b64encode(gakoa).decode(),
        "talde_marka": kripto.talde_marka(gakoa),
    }
    konfig.taldea_gorde(datuak)
    return {"izena": talde_izena, "talde_marka": datuak["talde_marka"]}


def gakoa() -> bytes:
    datuak = konfig.taldea()
    if not datuak or not datuak.get("gakoa"):
        raise SinkroErrorea("Ez dago talderik konfiguratuta")
    return base64.b64decode(datuak["gakoa"])


def talde_marka() -> str | None:
    datuak = konfig.taldea()
    return datuak.get("talde_marka") if datuak else None


# ─── Fardelak ───────────────────────────────────────────────────────────────


def fardela_sortu(edukia: dict, mota: str = "sync") -> bytes:
    return kripto.fardela_sortu(gakoa(), edukia, konfig.gailu_id(), mota)


def fardela_ireki(konn: sqlite3.Connection, byteak: bytes) -> tuple:
    """Fardela ireki, eta sinkronizazio-fardela bada errepikapenak baztertu."""
    sinkronizazioa = kripto.goiburua_irakurri(byteak).get("mota") == "sync"
    goiburua, edukia = kripto.fardela_ireki(
        gakoa(), byteak, denbora_egiaztatu=sinkronizazioa
    )

    # Errepikapenen kontrola sinkronizazioan bakarrik: babeskopia bat bi aldiz
    # inportatu ahal izan behar da.
    if sinkronizazioa:
        _nonce_erregistratu(konn, goiburua["nonce"])

    if goiburua.get("gailu_id") == konfig.gailu_id():
        raise SinkroErrorea("Norberak sortutako fardela da")

    return goiburua, edukia


def _nonce_erregistratu(konn: sqlite3.Connection, nonce: str) -> None:
    """Nonce bat behin bakarrik onartu (errepikapenen aurkako babesa).

    Zifratzeak berak ez du errepikapenik saihesten: erasotzaile batek fardel
    zahar bat oso-osorik birbidal lezake. Denbora-leihoak eta nonce-en
    erregistroak batera hori eragozten dute.
    """
    orain = int(time.time())
    konn.execute("DELETE FROM ikusitako_nonceak WHERE noiz < ?", (orain - NONCE_BIZITZA,))
    kurtsorea = konn.execute(
        "INSERT OR IGNORE INTO ikusitako_nonceak (nonce, noiz) VALUES (?, ?)",
        (nonce, orain),
    )
    konn.commit()
    if kurtsorea.rowcount == 0:
        raise SinkroErrorea("Fardel hau lehen ere jaso da (errepikapena)")


def _gertaerak_atera(edukia: dict) -> list:
    zerrenda = edukia.get("gertaerak") or []
    if not isinstance(zerrenda, list):
        raise SinkroErrorea("Gertaera-zerrenda baliogabea")
    if len(zerrenda) > GEHIENEZ_GERTAERA_FARDELEAN:
        raise SinkroErrorea("Gertaera gehiegi fardel bakarrean")
    return zerrenda


def _idak_atera(edukia: dict) -> set:
    zerrenda = edukia.get("ezagunak") or []
    if not isinstance(zerrenda, list) or len(zerrenda) > GEHIENEZ_ID_ZERRENDAN:
        raise SinkroErrorea("Identifikatzaile-zerrenda baliogabea")
    return {x for x in zerrenda if isinstance(x, str) and len(x) <= 64}


# ─── Protokoloa ─────────────────────────────────────────────────────────────


def _nor_naizen() -> dict:
    """Fardel bakoitzean doan bisita-txartela: nor naizen eta non aurkitu.

    `sync_portua` funtsezkoa da: hartzaileak gu berriro deitzeko modua ematen
    dio, gure aurkikuntza-seinalea jaso ez badu ere (suebaki batek multicast-a
    norabide batean blokeatzea ohikoa da).
    """
    return {"gailu_izena": konfig.gailu_izena(), "sync_portua": konfig.SYNC_PORTUA}


def eskaera_sortu(konn: sqlite3.Connection) -> bytes:
    return fardela_sortu(
        {"mota": "eskaera", "ezagunak": gertaerak.id_guztiak(konn), **_nor_naizen()}
    )


def eskaera_erantzun(konn: sqlite3.Connection, byteak: bytes, kidea_ikusi=None) -> bytes:
    """Beste gailu batek bidalitako eskaera erantzun (zerbitzari rola).

    `kidea_ikusi` emanez gero, bidaltzailearen datuekin deitzen da: hala,
    guregana jo duen gailua kide ezagun bihurtzen da berehala.
    """
    goiburua, edukia = fardela_ireki(konn, byteak)
    mota = edukia.get("mota")

    if mota not in ("eskaera", "bultzada"):
        raise SinkroErrorea(f"Mezu mota ezezaguna: {mota!r}")

    _gailua_erregistratu(konn, goiburua, edukia.get("gailu_izena"))
    if kidea_ikusi:
        kidea_ikusi(
            {
                "gailu_id": goiburua.get("gailu_id"),
                "izena": edukia.get("gailu_izena"),
                "portua": edukia.get("sync_portua"),
            }
        )

    if mota == "eskaera":
        haienak = _idak_atera(edukia)
        return fardela_sortu(
            {
                "mota": "erantzuna",
                "gertaerak": gertaerak.esportatu(konn, haienak)[:GEHIENEZ_GERTAERA_FARDELEAN],
                "ezagunak": gertaerak.id_guztiak(konn),
                **_nor_naizen(),
            }
        )

    emaitza = gertaerak.gehitu(konn, _gertaerak_atera(edukia))
    return fardela_sortu({"mota": "onartuta", "berriak": emaitza["berriak"]})


def erantzuna_prozesatu(konn: sqlite3.Connection, byteak: bytes) -> dict:
    """Erantzuna aplikatu eta haiei falta zaizkien gertaerak prestatu."""
    goiburua, edukia = fardela_ireki(konn, byteak)
    if edukia.get("mota") != "erantzuna":
        raise SinkroErrorea("Espero ez zen erantzuna")

    emaitza = gertaerak.gehitu(konn, _gertaerak_atera(edukia))
    _gailua_erregistratu(konn, goiburua, edukia.get("gailu_izena"))

    haienak = _idak_atera(edukia)
    haiei_falta = gertaerak.esportatu(konn, haienak)[:GEHIENEZ_GERTAERA_FARDELEAN]

    bultzada = None
    if haiei_falta:
        bultzada = fardela_sortu(
            {"mota": "bultzada", "gertaerak": haiei_falta, **_nor_naizen()}
        )

    return {
        "jasoak": emaitza["berriak"],
        "baztertuak": emaitza["baztertuak"],
        "bidaltzekoak": len(haiei_falta),
        "bultzada": bultzada,
    }


def _gailua_erregistratu(konn: sqlite3.Connection, goiburua: dict, izena=None) -> None:
    gailu_id = goiburua.get("gailu_id")
    if not isinstance(gailu_id, str) or not gertaerak.ID_ERED.match(gailu_id):
        return
    if izena is not None and (not isinstance(izena, str) or len(izena) > 60):
        izena = None
    konn.execute(
        "INSERT INTO gailuak (gailu_id, izena, azken_ikusia) VALUES (?,?,?) "
        "ON CONFLICT(gailu_id) DO UPDATE SET azken_ikusia = excluded.azken_ikusia, "
        "izena = COALESCE(excluded.izena, gailuak.izena)",
        (gailu_id, izena, int(time.time())),
    )
    konn.commit()


# ─── Fitxategi bidezko trukea ───────────────────────────────────────────────


def fitxategira_esportatu(konn: sqlite3.Connection) -> bytes:
    """Erregistro osoa fardel zifratu batean. Babeskopietarako ere balio du."""
    return fardela_sortu(
        {
            "mota": "esportazioa",
            "gertaerak": gertaerak.esportatu(konn),
            "gailu_izena": konfig.gailu_izena(),
            "sortze_data": time.strftime("%Y-%m-%d %H:%M"),
        },
        mota="esportazioa",
    )


def fardela_deskodetu(byteak: bytes) -> tuple:
    """Fardel bat deszifratu eta egiaztatu, ezer aplikatu gabe.

    Aplikatzetik bereizita dago nahita: hala, deitzaileak fardela ona dela
    jakin dezake datu-basea ukitu aurretik (adib. babeskopia bat egiteko).
    """
    goiburua, edukia = kripto.fardela_ireki(gakoa(), byteak, denbora_egiaztatu=False)
    return goiburua, _gertaerak_atera(edukia)


def fitxategitik_inportatu(konn: sqlite3.Connection, byteak: bytes, aurretik=None) -> dict:
    """Fardel bat inportatu (esportazioa, babeskopia edo sinkronizazio-fardela).

    Ez du ezer ezabatzen: gertaerak gehitu baino ez du egiten, beraz bi
    erregistro bateratzeak ez du inoiz daturik galtzen.

    `aurretik` emanez gero, fardela ona dela egiaztatu ONDOREN eta datuak
    aplikatu AURRETIK deitzen da (babeskopia bat egiteko, adibidez).
    """
    goiburua, zerrenda = fardela_deskodetu(byteak)
    if aurretik:
        aurretik()
    emaitza = gertaerak.gehitu(konn, zerrenda)
    return {
        "berriak": emaitza["berriak"],
        "baztertuak": emaitza["baztertuak"],
        "iturria": goiburua.get("gailu_id", "?")[:8],
        "mota": goiburua.get("mota"),
    }


def egoera(konn: sqlite3.Connection) -> dict:
    talde_datuak = konfig.taldea() or {}
    gailu_lerroak = konn.execute(
        "SELECT gailu_id, izena, azken_ikusia FROM gailuak ORDER BY azken_ikusia DESC"
    ).fetchall()
    return {
        "taldea": talde_datuak.get("izena"),
        "talde_marka": talde_datuak.get("talde_marka"),
        "gailu_id": konfig.gailu_id(),
        "gailu_izena": konfig.gailu_izena(),
        "hatz_marka": gertaerak.egoeraren_hatz_marka(konn),
        "gertaerak": konn.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0],
        "gailuak": [dict(l) for l in gailu_lerroak],
    }
