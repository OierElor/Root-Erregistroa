#!/usr/bin/env python3
"""Nabigatzailearen eta APIaren arteko zubia (Pyodide).

Mobilean ez dago HTTPrik: Python bera nabigatzailearen barruan exekutatzen da
(Pyodide/WASM), eta JavaScript-ek hemengo funtzioei deitzen die zuzenean.
`app.py`-k HTTP geruzan egiten duena egiten du honek: eskaera bat `web_api`-ra
eraman, eta salbuespenak erantzun garbi bihurtu.

Dena JSON testu gisa igarotzen da JavaScript-era: horrela ez dago Python eta JS
arteko objektu-bihurketen mendekotasunik, eta erraz probatu daiteke mahaigainean
(ikus `tests/test_mobil_zubia.py`).

Zergatik Python nabigatzailean, eta ez JavaScript-en berridatzita: jokalarien
identifikatzaileak `blake2b`-rekin sortzen dira (`person=b"root-jokalari"`), eta
nabigatzaileak ez du hash hori. Berridatziz gero, kalkulu-desberdintasun txiki
batek jokalari bera bitan zatituko luke bi gailuak bateratzean. Kode bera
exekutatuta, bateragarritasuna ez da mantendu beharreko zerbait.
"""

import json
import sqlite3

import db
import gertaerak
import konfig
import sinkro
import web_api

_KONN: sqlite3.Connection | None = None


def _hutsa(balioa):
    """JavaScript-eko hutsuneak Python-en `None` bihurtu.

    Pyodide-k `undefined` bakarrik bihurtzen du `None`; `null`-ek `JsNull`
    objektu bat ematen du, eta hori ez da `None` ez eta hutsa ere. JavaScript
    aldeak `undefined` bidaltzen du, baina hemen ere onartzen da: zubi honek
    inoiz ez luke huts egin behar deitzeko modu txiki bategatik.
    """
    if balioa is None or type(balioa).__name__ == "JsNull":
        return None
    return balioa


def hasieratu() -> str:
    """Datu-basea prestatu eta konexioa ireki. Gailuaren datuak itzultzen ditu."""
    global _KONN
    db.hasieratu()
    _KONN = db.konexioa()
    return json.dumps({
        "gailu_id": konfig.gailu_id(),
        "gailu_izena": konfig.gailu_izena(),
        "datu_basea": str(db.DB_FITX),
    })


def _errorea(mezua: str, kodea: int) -> str:
    return json.dumps({"ok": False, "errorea": mezua, "kodea": kodea}, ensure_ascii=False)


def deitu(bidea: str, metodoa: str = "GET", gorputza_json=None,
          kontsulta_json=None, byteak=None) -> str:
    """APIari deitu eta erantzuna JSON testu gisa itzuli.

    Beti `{"ok": true, "datuak": …}` edo `{"ok": false, "errorea": …}` itzultzen
    du — inoiz ez du salbuespenik JavaScript-era pasatzen.

    Esportatzeak `{"ok": true, "fitxategia": {"izena": …, "testua": …}}` ematen du.
    """
    if _KONN is None:
        return _errorea("Datu-basea ez dago prest", 500)

    gorputza_json = _hutsa(gorputza_json)
    kontsulta_json = _hutsa(kontsulta_json)
    byteak = _hutsa(byteak)

    try:
        gorputza = json.loads(gorputza_json) if gorputza_json else None
        kontsulta = json.loads(kontsulta_json) if kontsulta_json else None
    except json.JSONDecodeError:
        return _errorea("JSON baliogabea", 400)

    try:
        emaitza = web_api.deitu(
            _KONN, bidea, metodoa,
            gorputza=gorputza,
            kontsulta=kontsulta,
            byteak=bytes(byteak) if byteak is not None else None,
        )
    except web_api.BideErrorea:
        return _errorea("Bide ezezaguna", 404)
    except (gertaerak.GertaeraErrorea, sinkro.SinkroErrorea, ValueError) as e:
        return _errorea(str(e), 400)
    except sqlite3.Error:
        return _errorea("Datu-basearen errorea", 500)

    if isinstance(emaitza, web_api.Fitxategia):
        # `.rootsync` UTF-8 JSON hutsa da, beraz testu gisa pasa daiteke.
        return json.dumps({
            "ok": True,
            "fitxategia": {"izena": emaitza.izena, "testua": emaitza.byteak.decode("utf-8")},
        }, ensure_ascii=False)

    return json.dumps({"ok": True, "datuak": emaitza}, ensure_ascii=False)


def gailua_izendatu(izena: str) -> str:
    """Gailuari izena jarri (lehen abioan, telefonoa bereizteko)."""
    konfig.gailua_izendatu(izena)
    return konfig.gailu_izena()
