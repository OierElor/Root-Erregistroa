"""APIaren testak, partidak editatzea barne.

Editatzea ez da eragiketa berezi bat: `id` bera duen `partida_gorde` gertaera
bat da. Testek horrek partida bikoizten EZ duela bermatzen dute.
"""

import pytest

import app as aplikazioa
import db

OSTALARIA = "127.0.0.1:3000"


@pytest.fixture
def bezeroa():
    db.hasieratu()
    konn = db.konexioa()
    konn.execute("DELETE FROM gertaerak")
    konn.execute("DELETE FROM partida_jokalariak")
    konn.execute("DELETE FROM partidak")
    konn.execute("DELETE FROM jokalariak")
    konn.commit()
    konn.close()

    aplikazioa.app.config.update(TESTING=True)
    with aplikazioa.app.test_client() as k:
        yield k


def eskaera(bezeroa, metodoa, bidea, datuak=None, tokena=True, **kw):
    goiburuak = {"Host": OSTALARIA}
    if tokena:
        goiburuak["X-Root-Token"] = aplikazioa.SAIO_TOKENA
    goiburuak.update(kw.pop("headers", {}))
    return getattr(bezeroa, metodoa)(bidea, json=datuak, headers=goiburuak, **kw)


def partida_datuak(**aldaketak):
    oinarria = {
        "data": "2026-05-01",
        "mapa_kodea": "udazkena",
        "karta_sorta": "estandarra",
        "oharrak": "Lehen bertsioa",
        "jokalariak": [
            {"izena": "Oier", "fakzio_kodea": "marquise", "puntuak": 30,
             "irabazlea": True, "garaipen_mota": "puntuak"},
            {"izena": "Ander", "fakzio_kodea": "eyrie", "puntuak": 24},
        ],
    }
    return {**oinarria, **aldaketak}


def partidak(bezeroa):
    return eskaera(bezeroa, "get", "/api/partidak").get_json()["partidak"]


# ─── Sortzea eta editatzea ──────────────────────────────────────────────────


def test_partida_sortu(bezeroa):
    erantzuna = eskaera(bezeroa, "post", "/api/partidak", partida_datuak())
    assert erantzuna.status_code == 200
    assert len(partidak(bezeroa)) == 1


def test_editatzeak_ez_du_partida_berririk_sortzen(bezeroa):
    partida_id = eskaera(bezeroa, "post", "/api/partidak", partida_datuak()).get_json()["id"]

    eskaera(bezeroa, "post", "/api/partidak", partida_datuak(
        id=partida_id, data="2026-05-02", mapa_kodea="negua", oharrak="Zuzenduta",
        jokalariak=[
            {"izena": "Oier", "fakzio_kodea": "marquise", "puntuak": 27},
            {"izena": "Ander", "fakzio_kodea": "eyrie", "puntuak": 30,
             "irabazlea": True, "garaipen_mota": "nagusitasuna"},
        ],
    ))

    zerrenda = partidak(bezeroa)
    assert len(zerrenda) == 1
    p = zerrenda[0]
    assert (p["id"], p["data"], p["mapa_kodea"], p["oharrak"]) == (
        partida_id, "2026-05-02", "negua", "Zuzenduta")
    irabazlea = [j for j in p["jokalariak"] if j["irabazlea"]]
    assert [j["jokalari_izena"] for j in irabazlea] == ["Ander"]
    assert {j["jokalari_izena"]: j["puntuak"] for j in p["jokalariak"]} == {"Oier": 27, "Ander": 30}


def test_editatzean_jokalaria_kendu_eta_gehitu(bezeroa):
    partida_id = eskaera(bezeroa, "post", "/api/partidak", partida_datuak()).get_json()["id"]

    eskaera(bezeroa, "post", "/api/partidak", partida_datuak(
        id=partida_id,
        jokalariak=[
            {"izena": "Oier", "fakzio_kodea": "marquise", "puntuak": 30, "irabazlea": True},
            {"izena": "Maddi", "fakzio_kodea": "alliance", "puntuak": 19},
        ],
    ))

    izenak = {j["jokalari_izena"] for j in partidak(bezeroa)[0]["jokalariak"]}
    assert izenak == {"Oier", "Maddi"}          # Ander kenduta
    # Anderrek jokalari gisa jarraitzen du: beste partidetako historia ez da ukitzen.
    hasiera = eskaera(bezeroa, "get", "/api/hasiera").get_json()
    assert "Ander" in {j["izena"] for j in hasiera["jokalariak"]}


def test_edizio_bakoitzak_gertaera_bat_uzten_du(bezeroa):
    """Editatzeak ez du historia ezabatzen: gertaerak metatu egiten dira.

    Horri esker beste ordenagailu batek jakin dezake zein den azken bertsioa.
    """
    partida_id = eskaera(bezeroa, "post", "/api/partidak", partida_datuak()).get_json()["id"]
    hasierako_gertaerak = eskaera(bezeroa, "get", "/api/hasiera").get_json()["laburpena"]["gertaerak"]

    eskaera(bezeroa, "post", "/api/partidak", partida_datuak(id=partida_id, oharrak="Bigarrena"))
    eskaera(bezeroa, "post", "/api/partidak", partida_datuak(id=partida_id, oharrak="Hirugarrena"))

    amaierako = eskaera(bezeroa, "get", "/api/hasiera").get_json()["laburpena"]["gertaerak"]
    assert amaierako == hasierako_gertaerak + 2
    assert partidak(bezeroa)[0]["oharrak"] == "Hirugarrena"


def test_ezabatutako_partida_editatzeak_berpizten_du(bezeroa):
    """Ustekabean ezabatu baduzu, editatzeak itzultzen du (gertaera berriagoa da)."""
    partida_id = eskaera(bezeroa, "post", "/api/partidak", partida_datuak()).get_json()["id"]
    eskaera(bezeroa, "delete", f"/api/partidak/{partida_id}")
    assert partidak(bezeroa) == []

    eskaera(bezeroa, "post", "/api/partidak", partida_datuak(id=partida_id, oharrak="Berreskuratua"))
    assert len(partidak(bezeroa)) == 1


def test_editatzean_datu_okerrak_baztertzen_dira(bezeroa):
    partida_id = eskaera(bezeroa, "post", "/api/partidak", partida_datuak()).get_json()["id"]

    erantzuna = eskaera(bezeroa, "post", "/api/partidak", partida_datuak(
        id=partida_id, data="bihar"))
    assert erantzuna.status_code == 400
    # Partida ukitu gabe geratzen da.
    assert partidak(bezeroa)[0]["data"] == "2026-05-01"


def test_partida_id_baliogabea_baztertu(bezeroa):
    erantzuna = eskaera(bezeroa, "post", "/api/partidak", partida_datuak(id="../../etc/passwd"))
    assert erantzuna.status_code == 400


# ─── Segurtasun-geruza ──────────────────────────────────────────────────────


def test_tokenik_gabe_ezin_da_idatzi(bezeroa):
    erantzuna = eskaera(bezeroa, "post", "/api/partidak", partida_datuak(), tokena=False)
    assert erantzuna.status_code == 403
    assert partidak(bezeroa) == []


def test_kanpoko_jatorria_baztertu(bezeroa):
    erantzuna = eskaera(bezeroa, "post", "/api/partidak", partida_datuak(),
                        headers={"Origin": "http://gaiztoa.eus"})
    assert erantzuna.status_code == 403


def test_ostalari_okerra_baztertu(bezeroa):
    erantzuna = bezeroa.get("/api/hasiera", headers={"Host": "gaiztoa.eus"})
    assert erantzuna.status_code == 403
