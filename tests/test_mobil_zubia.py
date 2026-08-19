"""Mobileko zubiaren testak.

Zubia nabigatzailean exekutatzen da (Pyodide), baina Python hutsa denez,
mahaigainean proba daiteke. Hori da helburua: mobileko bidea ez da probatu gabeko
kode-adar bat.

Test erabakigarria `test_hatz_marka_berdina_bateratu_ondoren` da: mahaigainak eta
mobilak `.rootsync` bat trukatu ondoren erregistro **berbera** dutela frogatzen du.
"""

import contextlib
import json
import os

import pytest

import db
import gertaerak
import mobil_zubia
import web_api


@pytest.fixture
def zubia(tmp_path, monkeypatch):
    """Zubia datu-base huts batekin, mobil berri bat balitz bezala."""
    monkeypatch.setattr(db, "DB_FITX", tmp_path / "mobila.db")
    mobil_zubia.hasieratu()
    yield mobil_zubia
    if mobil_zubia._KONN is not None:
        mobil_zubia._KONN.close()
        mobil_zubia._KONN = None


def partida_datuak(izena="Oier", bigarrena="Maddi", puntuak=30):
    return {
        "data": "2026-05-01",
        "mapa_kodea": "udazkena",
        "jokalariak": [
            {"izena": izena, "fakzio_kodea": "marquise", "puntuak": puntuak,
             "irabazlea": True, "garaipen_mota": "puntuak"},
            {"izena": bigarrena, "fakzio_kodea": "eyrie", "puntuak": 24},
        ],
    }


@contextlib.contextmanager
def gailu_gisa(gailu_id: str):
    """Eragiketak beste gailu baten identitatearekin egin.

    Benetako bizitzan mobilak eta mahaigainak `gailu_id` desberdinak dituzte, eta
    hori da gertaerak berdinketan ordenatzeko erabiltzen den bigarren gakoa
    (`lamport, gailu_id, gertaera_id`). Testak hori islatu behar du, bestela
    ordena deterministikoa ez litzateke benetan probatuko.
    """
    zaharra = os.environ.get("GAILU_ID")
    os.environ["GAILU_ID"] = gailu_id
    try:
        yield
    finally:
        if zaharra is None:
            os.environ.pop("GAILU_ID", None)
        else:
            os.environ["GAILU_ID"] = zaharra


def deitu(zubia, bidea, metodoa="GET", gorputza=None, **kw):
    erantzuna = json.loads(zubia.deitu(
        bidea, metodoa,
        gorputza_json=json.dumps(gorputza) if gorputza is not None else None,
        **kw,
    ))
    return erantzuna


# ─── Erantzunen forma ───────────────────────────────────────────────────────


def test_hasieratzeak_gailu_datuak_ematen_ditu(zubia):
    datuak = json.loads(zubia.hasieratu())
    assert datuak["gailu_id"]
    assert datuak["gailu_izena"]


def test_erantzun_zuzena_ok_da(zubia):
    erantzuna = deitu(zubia, "/api/hasiera")
    assert erantzuna["ok"] is True
    assert "jokalariak" in erantzuna["datuak"]


def test_salbuespenak_ez_dira_igarotzen(zubia):
    """JavaScript-era ez da inoiz salbuespenik iristen: dena JSON erantzuna da."""
    erantzuna = deitu(zubia, "/api/partidak", "POST", {"jokalariak": "ez-zerrenda"})
    assert erantzuna["ok"] is False
    assert erantzuna["kodea"] == 400
    assert erantzuna["errorea"]


def test_bide_ezezaguna_404(zubia):
    erantzuna = deitu(zubia, "/api/asmatua")
    assert erantzuna == {"ok": False, "errorea": "Bide ezezaguna", "kodea": 404}


def test_json_baliogabea_ez_da_lehertzen(zubia):
    erantzuna = json.loads(zubia.deitu("/api/jokalariak", "POST", gorputza_json="{ ez json"))
    assert erantzuna["ok"] is False
    assert erantzuna["kodea"] == 400


def test_esportazioak_testua_ematen_du(zubia):
    deitu(zubia, "/api/partidak", "POST", partida_datuak())
    erantzuna = deitu(zubia, "/api/sinkro/esportatu")
    assert erantzuna["ok"] is True
    edukia = json.loads(erantzuna["fitxategia"]["testua"])
    assert edukia["formatua"] == "root-erregistroa"
    assert len(edukia["gertaerak"]) > 0


# ─── Mahaigainarekiko bateragarritasuna ─────────────────────────────────────


def test_hatz_marka_berdina_bateratu_ondoren(zubia, tmp_path):
    """Bi gailuk fitxategiak trukatuta, erregistro berbera dute.

    Hau da mobileko bertsioaren proba nagusia: hatz-marka berdina bada, bi
    aldeek gauza bera dute, eta beraz kalkulu berbera egiten dute.
    """
    # Mobila: partida bat, bere identitatearekin.
    with gailu_gisa("a" * 32):
        deitu(zubia, "/api/partidak", "POST", partida_datuak("Oier"))
        mobilaren_fitxategia = deitu(zubia, "/api/sinkro/esportatu")["fitxategia"]["testua"]

    # Mahaigaina: beste partida bat, datu-base eta gailu_id bereiziekin.
    mahaigaina = db.konexioa(tmp_path / "mahaigaina.db")
    db.hasieratu(tmp_path / "mahaigaina.db")
    try:
        with gailu_gisa("b" * 32):
            web_api.deitu(mahaigaina, "/api/partidak", "POST",
                          gorputza=partida_datuak("Ander", "Jon"))
            mahaigainaren_fitxategia = web_api.deitu(
                mahaigaina, "/api/sinkro/esportatu"
            ).byteak

        # Trukea: bakoitzak bestearena inportatzen du, bere identitateaz.
        with gailu_gisa("a" * 32):
            deitu(zubia, "/api/sinkro/inportatu", "POST",
                  byteak=mahaigainaren_fitxategia)
            mobilarena = deitu(zubia, "/api/sinkro/egoera")["datuak"]["hatz_marka"]
            mobileko_partidak = deitu(zubia, "/api/partidak")["datuak"]["partidak"]

        with gailu_gisa("b" * 32):
            web_api.deitu(mahaigaina, "/api/sinkro/inportatu", "POST",
                          byteak=mobilaren_fitxategia.encode("utf-8"))
            mahaigainarena = web_api.deitu(mahaigaina, "/api/sinkro/egoera")["hatz_marka"]
            mahaigaineko_partidak = web_api.deitu(mahaigaina, "/api/partidak")["partidak"]

        assert mobilarena == mahaigainarena

        # Eta bi partida berberak dituzte biek, ORDENA BEREAN: `azken_partidak`
        # (estatistikak.py) `azken_lamport`/`azken_gailua`-rekin ordenatzen du
        # berdinketetan (data bera denean), eta bi balio horiek sinkronizazio
        # osoak erabiltzen duen erloju logikotik datoz — beraz deterministikoak
        # dira bi gailuetan, `rowid` gailu bakoitzaren sartze-ordena lokala
        # litzatekeen bitartean.
        assert ([p["id"] for p in mobileko_partidak]
                == [p["id"] for p in mahaigaineko_partidak])
        assert len(mobileko_partidak) == 2
    finally:
        mahaigaina.close()


def test_jokalari_bera_ez_da_bikoizten(zubia, tmp_path):
    """Bi gailuetan "Oier" sartuta, bateratzean jokalari bakarra.

    Hau da JavaScript-era berridazteak hautsiko lukeena: identifikatzailea
    `blake2b(person=b"root-jokalari")`-rekin sortzen da, eta nabigatzaileak ez
    du hash hori. Kode bera exekutatuta, berdina da definizioz.
    """
    deitu(zubia, "/api/partidak", "POST", partida_datuak("Oier"))

    mahaigaina = db.konexioa(tmp_path / "mahaigaina.db")
    db.hasieratu(tmp_path / "mahaigaina.db")
    try:
        # Izen bera, idazkera desberdinarekin.
        web_api.deitu(mahaigaina, "/api/partidak", "POST",
                      gorputza=partida_datuak("  oier  "))
        fitxategia = web_api.deitu(mahaigaina, "/api/sinkro/esportatu").byteak
        deitu(zubia, "/api/sinkro/inportatu", "POST", byteak=fitxategia)
    finally:
        mahaigaina.close()

    izenak = [j["izena"].strip().casefold()
              for j in deitu(zubia, "/api/hasiera")["datuak"]["jokalariak"]]
    assert izenak.count("oier") == 1


def test_gertaera_ordena_berdina(zubia, tmp_path):
    """Gertaerak ordena berean daude bi aldeetan (Lamport + gailu_id)."""
    deitu(zubia, "/api/partidak", "POST", partida_datuak("Oier"))
    fitxategia = deitu(zubia, "/api/sinkro/esportatu")["fitxategia"]["testua"]

    mahaigaina = db.konexioa(tmp_path / "mahaigaina.db")
    db.hasieratu(tmp_path / "mahaigaina.db")
    try:
        web_api.deitu(mahaigaina, "/api/sinkro/inportatu", "POST",
                      byteak=fitxategia.encode("utf-8"))
        hangoak = gertaerak.esportatu(mahaigaina)
    finally:
        mahaigaina.close()

    hemengoak = json.loads(fitxategia)["gertaerak"]
    assert [g["gertaera_id"] for g in hangoak] == [g["gertaera_id"] for g in hemengoak]
