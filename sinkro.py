#!/usr/bin/env python3
"""Erregistroa fitxategi bidez trukatzea.

Ez dago sarerik, portu-rik ez zerbitzaririk: erregistroa fitxategi batera
esportatzen da, nahi duzun bidetik bidaltzen duzu (Telegram, posta, USB), eta
besteak inportatu egiten du. Aplikazioak ez du inoiz konexiorik irekitzen.

Fitxategia JSON arrunta da, edozein editorerekin irakurgarria::

    {
      "formatua": "root-erregistroa",
      "bertsioa": 2,
      "sortzailea": "Mahaigainekoa",
      "gertaerak": [ … ]
    }

Inportatzeak ez du EZER ezabatzen: gertaerak gehitu baino ez du egiten. Horrek
esan nahi du bi erregistro batzeak ez duela inoiz daturik galtzen, eta fitxategi
bera bi aldiz inportatzeak ez duela ezer bikoizten.
"""

import json
import sqlite3
import time

import gertaerak
import konfig

FORMATUA = "root-erregistroa"
BERTSIOA = 2

GEHIENEZ_GERTAERA = 50_000
# Bertsio zaharreko fitxategi zifratuen hasiera. Ez dira jada irakurtzen, baina
# errore ulertezin bat eman beharrean, zer den esaten zaio erabiltzaileari.
ZAHARRAREN_MAGIA = b"ROOTSYNC1"


class SinkroErrorea(Exception):
    """Fitxategia ezin da erabili."""


# ─── Esportatu ──────────────────────────────────────────────────────────────


def fitxategira_esportatu(konn: sqlite3.Connection) -> bytes:
    """Erregistro osoa fitxategi batean. Babeskopia eramangarri gisa ere balio du."""
    edukia = {
        "formatua": FORMATUA,
        "bertsioa": BERTSIOA,
        "sortzailea": konfig.gailu_izena(),
        "gailu_id": konfig.gailu_id(),
        "sortze_data": time.strftime("%Y-%m-%d %H:%M"),
        "gertaerak": gertaerak.esportatu(konn),
    }
    return json.dumps(edukia, ensure_ascii=False, indent=1).encode("utf-8")


# ─── Inportatu ──────────────────────────────────────────────────────────────


def fitxategia_irakurri(byteak: bytes) -> tuple:
    """Fitxategia irakurri eta egiaztatu, datu-basea ukitu gabe.

    Aplikatzetik bereizita dago: horrela fitxategia ona dela jakin dezakegu
    ezer aldatu aurretik (adib. babeskopia bat egiteko).
    """
    if byteak.startswith(ZAHARRAREN_MAGIA):
        raise SinkroErrorea(
            "Bertsio zaharreko fitxategi zifratua da; bertsio honek ezin du ireki"
        )

    try:
        edukia = json.loads(byteak)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise SinkroErrorea("Fitxategia ez da baliozko JSON bat") from e

    if not isinstance(edukia, dict) or edukia.get("formatua") != FORMATUA:
        raise SinkroErrorea("Ez da Root Erregistroa fitxategi bat")
    if not isinstance(edukia.get("bertsioa"), int):
        raise SinkroErrorea("Formatu bertsio baliogabea")

    zerrenda = edukia.get("gertaerak")
    if not isinstance(zerrenda, list):
        raise SinkroErrorea("Gertaera-zerrenda baliogabea")
    if len(zerrenda) > GEHIENEZ_GERTAERA:
        raise SinkroErrorea("Gertaera gehiegi fitxategi bakarrean")

    return edukia, zerrenda


def fitxategitik_inportatu(konn: sqlite3.Connection, byteak: bytes, aurretik=None) -> dict:
    """Fitxategi bat inportatu eta uneko erregistroarekin bateratu.

    `aurretik` emanez gero, fitxategia ona dela egiaztatu ONDOREN eta datuak
    aplikatu AURRETIK deitzen da (babeskopia bat egiteko).
    """
    edukia, zerrenda = fitxategia_irakurri(byteak)
    if aurretik:
        aurretik()

    emaitza = gertaerak.gehitu(konn, zerrenda)
    _gailua_erregistratu(konn, edukia.get("gailu_id"), edukia.get("sortzailea"))

    return {
        "berriak": emaitza["berriak"],
        "baztertuak": emaitza["baztertuak"],
        "guztira": len(zerrenda),
        "iturria": edukia.get("sortzailea") or "?",
        "sortze_data": edukia.get("sortze_data"),
    }


def _gailua_erregistratu(konn: sqlite3.Connection, gailu_id, izena) -> None:
    """Nondik datozen datuak gogoratu, interfazean erakusteko."""
    if not isinstance(gailu_id, str) or not gertaerak.ID_ERED.match(gailu_id):
        return
    if not isinstance(izena, str) or len(izena) > 60:
        izena = None
    konn.execute(
        "INSERT INTO gailuak (gailu_id, izena, azken_ikusia) VALUES (?,?,?) "
        "ON CONFLICT(gailu_id) DO UPDATE SET azken_ikusia = excluded.azken_ikusia, "
        "izena = COALESCE(excluded.izena, gailuak.izena)",
        (gailu_id, izena, int(time.time())),
    )
    konn.commit()


# ─── Egoera ─────────────────────────────────────────────────────────────────


def egoera(konn: sqlite3.Connection) -> dict:
    gailu_lerroak = konn.execute(
        "SELECT gailu_id, izena, azken_ikusia FROM gailuak ORDER BY azken_ikusia DESC"
    ).fetchall()
    return {
        "gailu_id": konfig.gailu_id(),
        "gailu_izena": konfig.gailu_izena(),
        # Bi ordenagailuk hatz-marka bera badute, erregistro berbera dute.
        "hatz_marka": gertaerak.egoeraren_hatz_marka(konn),
        "gertaerak": konn.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0],
        "gailuak": [dict(l) for l in gailu_lerroak],
    }
