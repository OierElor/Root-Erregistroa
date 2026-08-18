"""Fitxategi bidezko trukearen testak.

Bi ordenagailu simulatzen dira prozesu berean: bakoitzak bere datu-basea eta
bere gailu-identitatea. "Sinkronizatzea" fitxategi bat batetik bestera pasatzea
da, USB batean edo Telegram bidez egingo litzatekeen bezala.
"""

import contextlib
import json
import uuid

import pytest

import db
import gertaerak
import sinkro


@contextlib.contextmanager
def gailua_bezala(monkeypatch, gailu_id):
    with monkeypatch.context() as m:
        m.setenv("GAILU_ID", gailu_id)
        m.setenv("GAILU_IZENA", gailu_id)
        yield


def datu_basea(tmp_path, izena):
    bidea = tmp_path / f"{izena}.db"
    db.hasieratu(bidea)
    return db.konexioa(bidea)


def partida(jokalaria, puntuak=30, partida_id=None, **gehigarriak):
    return {
        "id": partida_id or uuid.uuid4().hex,
        "data": "2026-03-14",
        "mapa_kodea": "negua",
        "karta_sorta": "estandarra",
        "oharrak": None,
        "jokalariak": [
            {"jokalari_id": jokalaria, "fakzio_kodea": "eyrie", "puntuak": puntuak,
             "irabazlea": True, "garaipen_mota": "puntuak"}
        ],
        **gehigarriak,
    }


def pasatu(monkeypatch, iturria, helburua, nork="gailua-a", nori="gailua-b"):
    """Fitxategi bat esportatu batean eta inportatu bestean."""
    with gailua_bezala(monkeypatch, nork):
        fitxategia = sinkro.fitxategira_esportatu(iturria)
    with gailua_bezala(monkeypatch, nori):
        return fitxategia, sinkro.fitxategitik_inportatu(helburua, fitxategia)


# ─── Oinarrizko trukea ──────────────────────────────────────────────────────


def test_esportatu_eta_inportatu(tmp_path, monkeypatch):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        gertaerak.gertaera_berria(ka, "partida_gorde", partida("j1"))

    _, emaitza = pasatu(monkeypatch, ka, kb)

    assert emaitza["berriak"] == 2
    assert emaitza["iturria"] == "gailua-a"
    assert gertaerak.egoeraren_hatz_marka(ka) == gertaerak.egoeraren_hatz_marka(kb)


def test_fitxategia_json_irakurgarria_da(tmp_path, monkeypatch):
    ka = datu_basea(tmp_path, "a")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        fitxategia = sinkro.fitxategira_esportatu(ka)

    edukia = json.loads(fitxategia)
    assert edukia["formatua"] == "root-erregistroa"
    assert edukia["bertsioa"] == sinkro.BERTSIOA
    assert len(edukia["gertaerak"]) == 1
    assert "Oier" in fitxategia.decode("utf-8")   # testu laua da


def test_bi_aldiz_inportatzeak_ez_du_bikoizten(tmp_path, monkeypatch):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})

    fitxategia, lehena = pasatu(monkeypatch, ka, kb)
    with gailua_bezala(monkeypatch, "gailua-b"):
        bigarrena = sinkro.fitxategitik_inportatu(kb, fitxategia)

    assert (lehena["berriak"], bigarrena["berriak"]) == (1, 0)
    assert kb.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0] == 1


def test_norberak_esportatutakoa_berriro_inportatu_daiteke(tmp_path, monkeypatch):
    """Babeskopia eramangarri gisa erabiltzeko funtsezkoa da."""
    ka = datu_basea(tmp_path, "a")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        fitxategia = sinkro.fitxategira_esportatu(ka)
        emaitza = sinkro.fitxategitik_inportatu(ka, fitxategia)

    assert emaitza["berriak"] == 0
    assert ka.execute("SELECT COUNT(*) FROM jokalariak").fetchone()[0] == 1


def test_bi_norabideak_eta_offline_aldaketak(tmp_path, monkeypatch):
    """Biek partida bana sartzen dute konexiorik gabe, gero fitxategiak trukatu."""
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_gorde", partida("j1", 31))
    with gailua_bezala(monkeypatch, "gailua-b"):
        gertaerak.gertaera_berria(kb, "partida_gorde", partida("j2", 27))

    pasatu(monkeypatch, ka, kb, "gailua-a", "gailua-b")   # A → B
    pasatu(monkeypatch, kb, ka, "gailua-b", "gailua-a")   # B → A

    for k in (ka, kb):
        assert k.execute("SELECT COUNT(*) FROM partidak").fetchone()[0] == 2
    assert gertaerak.egoeraren_hatz_marka(ka) == gertaerak.egoeraren_hatz_marka(kb)


def test_partida_bera_bietan_editatuta_bat_datoz(tmp_path, monkeypatch):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    partida_id = uuid.uuid4().hex

    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_gorde", partida("j1", 30, partida_id))
    pasatu(monkeypatch, ka, kb)

    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_gorde", partida("j1", 31, partida_id))
    with gailua_bezala(monkeypatch, "gailua-b"):
        gertaerak.gertaera_berria(kb, "partida_gorde", partida("j1", 25, partida_id))

    pasatu(monkeypatch, ka, kb, "gailua-a", "gailua-b")
    pasatu(monkeypatch, kb, ka, "gailua-b", "gailua-a")

    assert (ka.execute("SELECT puntuak FROM partida_jokalariak").fetchone()[0]
            == kb.execute("SELECT puntuak FROM partida_jokalariak").fetchone()[0])
    assert gertaerak.egoeraren_hatz_marka(ka) == gertaerak.egoeraren_hatz_marka(kb)


def test_ezabatzea_ez_da_berpizten(tmp_path, monkeypatch):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    partida_id = uuid.uuid4().hex

    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_gorde", partida("j1", 30, partida_id))
    pasatu(monkeypatch, ka, kb)
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_ezabatu", {"id": partida_id})
    pasatu(monkeypatch, ka, kb)
    pasatu(monkeypatch, kb, ka, "gailua-b", "gailua-a")

    for k in (ka, kb):
        assert k.execute("SELECT ezabatuta FROM partidak").fetchone()[0] == 1


def test_datu_guztiak_bidaiatzen_dute(tmp_path, monkeypatch):
    """Mertzenarioak, lekuak, Vagabond pertsonaia eta katalogoak barne."""
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    partida_id = uuid.uuid4().hex

    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_gorde", {
            "id": partida_id, "data": "2026-04-01", "mapa_kodea": "aintzira",
            "jokalariak": [
                {"jokalari_id": "j1", "fakzio_kodea": "vagabond",
                 "arlote_kodea": "harrier", "puntuak": 30, "irabazlea": True},
            ],
            "mertzenarioak": ["forest-patrol", "flame-bearers"],
            "leku_bereziak": ["tower"],
        })
        gertaerak.gertaera_berria(ka, "mertzenarioa_gorde", {
            "kodea": "forest-patrol", "izena": "Forest Patrol (zuzendua)"})

    pasatu(monkeypatch, ka, kb)

    assert kb.execute(
        "SELECT arlote_kodea FROM partida_jokalariak").fetchone()[0] == "harrier"
    assert {l[0] for l in kb.execute(
        "SELECT mertzenario_kodea FROM partida_mertzenarioak")} == {
        "forest-patrol", "flame-bearers"}
    assert [l[0] for l in kb.execute("SELECT leku_kodea FROM partida_lekuak")] == ["tower"]
    assert kb.execute(
        "SELECT izena FROM mertzenarioak WHERE kodea = 'forest-patrol'"
    ).fetchone()[0] == "Forest Patrol (zuzendua)"


def test_iturriko_gailua_gogoratzen_da(tmp_path, monkeypatch):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
    pasatu(monkeypatch, ka, kb)

    lerroa = kb.execute("SELECT gailu_id, izena FROM gailuak").fetchone()
    assert lerroa["gailu_id"] == "gailua-a"


# ─── Fitxategi okerrak ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "edukia,zatia",
    [
        (b"hau ez da json", "JSON"),
        (b'{"beste": "app"}', "Root Erregistroa"),
        (b'["zerrenda"]', "Root Erregistroa"),
        (b'{"formatua": "root-erregistroa", "bertsioa": "bi"}', "bertsio"),
        (b'{"formatua": "root-erregistroa", "bertsioa": 2}', "zerrenda"),
        (b'{"formatua": "root-erregistroa", "bertsioa": 2, "gertaerak": {}}', "zerrenda"),
    ],
)
def test_fitxategi_okerrak_baztertzen_dira(tmp_path, monkeypatch, edukia, zatia):
    kb = datu_basea(tmp_path, "b")
    with pytest.raises(sinkro.SinkroErrorea, match=zatia):
        sinkro.fitxategitik_inportatu(kb, edukia)
    assert kb.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0] == 0


def test_formatu_zaharrak_mezu_argia_ematen_du(tmp_path):
    kb = datu_basea(tmp_path, "b")
    zaharra = b"ROOTSYNC1" + b"\x00\x01\x02 zifratutako zaborra"
    with pytest.raises(sinkro.SinkroErrorea, match="zifratua"):
        sinkro.fitxategitik_inportatu(kb, zaharra)


def test_gertaera_baliogabeak_iragazten_dira(tmp_path, monkeypatch):
    """Fitxategi bat eskuz uki daiteke; gertaerak banaka balidatzen dira."""
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        fitxategia = sinkro.fitxategira_esportatu(ka)

    edukia = json.loads(fitxategia)
    edukia["gertaerak"].append({"mota": "asmatutakoa", "karga": {"id": "x"}})
    edukia["gertaerak"].append({"gertaera_id": "y", "mota": "jokalaria_gorde",
                                "entitate_id": "j2", "gailu_id": "gailua-a",
                                "lamport": 1, "unix_ordua": 0,
                                "karga": {"id": "j2", "izena": "x" * 500}})
    hondatua = json.dumps(edukia).encode()

    with gailua_bezala(monkeypatch, "gailua-b"):
        emaitza = sinkro.fitxategitik_inportatu(kb, hondatua)

    assert emaitza["berriak"] == 1
    assert len(emaitza["baztertuak"]) == 2
    assert kb.execute("SELECT COUNT(*) FROM jokalariak").fetchone()[0] == 1


def test_gertaera_gehiegi_dituen_fitxategia(tmp_path):
    kb = datu_basea(tmp_path, "b")
    edukia = json.dumps({
        "formatua": "root-erregistroa", "bertsioa": 2,
        "gertaerak": [{} for _ in range(sinkro.GEHIENEZ_GERTAERA + 1)],
    }).encode()
    with pytest.raises(sinkro.SinkroErrorea, match="gehiegi"):
        sinkro.fitxategitik_inportatu(kb, edukia)


def test_inportatu_aurretik_babeskopia_deitzen_da(tmp_path, monkeypatch):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        fitxategia = sinkro.fitxategira_esportatu(ka)

    deiak = []
    sinkro.fitxategitik_inportatu(kb, fitxategia, aurretik=lambda: deiak.append(1))
    assert deiak == [1]

    # Fitxategia txarra bada, EZ da babeskopiarik egiten.
    deiak.clear()
    with pytest.raises(sinkro.SinkroErrorea):
        sinkro.fitxategitik_inportatu(kb, b"zaborra", aurretik=lambda: deiak.append(1))
    assert deiak == []


# ─── Egoera ─────────────────────────────────────────────────────────────────


def test_egoerak_hatz_marka_ematen_du(tmp_path, monkeypatch):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        egoera_a = sinkro.egoera(ka)

    assert egoera_a["gertaerak"] == 1
    assert egoera_a["gailu_izena"] == "gailua-a"
    with gailua_bezala(monkeypatch, "gailua-b"):
        assert sinkro.egoera(kb)["hatz_marka"] != egoera_a["hatz_marka"]

    pasatu(monkeypatch, ka, kb)
    with gailua_bezala(monkeypatch, "gailua-b"):
        assert sinkro.egoera(kb)["hatz_marka"] == egoera_a["hatz_marka"]
