"""Bi gailuren arteko sinkronizazio osoa, sarerik gabe simulatuta.

`gailua_bezala` erabiliz prozesu berean bi gailu ordezkatzen dira: bakoitzak
bere datu-basea du, baina talde bera (gako bera).
"""

import contextlib
import time
import uuid

import pytest

import db
import gertaerak
import konfig
import kripto
import sinkro

TALDEA = "Aramaixoko basoa"
PASAESALDIA = "sagardoa-2026"


@contextlib.contextmanager
def gailua_bezala(monkeypatch, gailu_id):
    with monkeypatch.context() as m:
        m.setenv("GAILU_ID", gailu_id)
        m.setenv("GAILU_IZENA", gailu_id)
        yield


@pytest.fixture
def taldea():
    sinkro.taldea_konfiguratu(TALDEA, PASAESALDIA)
    yield
    konfig.taldea_ezabatu()


def datu_basea(tmp_path, izena):
    bidea = tmp_path / f"{izena}.db"
    db.hasieratu(bidea)
    return db.konexioa(bidea)


def partida(jokalaria, puntuak=30):
    return {
        "id": uuid.uuid4().hex,
        "data": "2026-03-14",
        "mapa_kodea": "negua",
        "karta_sorta": "estandarra",
        "oharrak": None,
        "jokalariak": [
            {"jokalari_id": jokalaria, "fakzio_kodea": "eyrie", "puntuak": puntuak,
             "irabazlea": True, "garaipen_mota": "puntuak"}
        ],
    }


def truke_osoa(monkeypatch, ka, kb):
    """A eta B-ren arteko sinkronizazio osoa (bi norabideak)."""
    with gailua_bezala(monkeypatch, "gailua-a"):
        eskaera = sinkro.eskaera_sortu(ka)
    with gailua_bezala(monkeypatch, "gailua-b"):
        erantzuna = sinkro.eskaera_erantzun(kb, eskaera)
    with gailua_bezala(monkeypatch, "gailua-a"):
        emaitza = sinkro.erantzuna_prozesatu(ka, erantzuna)
    if emaitza["bultzada"]:
        with gailua_bezala(monkeypatch, "gailua-b"):
            sinkro.eskaera_erantzun(kb, emaitza["bultzada"])
    return emaitza


# ─── Sinkronizazioa ─────────────────────────────────────────────────────────


def test_bi_norabideko_sinkronizazioa(tmp_path, monkeypatch, taldea):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")

    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        gertaerak.gertaera_berria(ka, "partida_gorde", partida("j1", 31))
    with gailua_bezala(monkeypatch, "gailua-b"):
        gertaerak.gertaera_berria(kb, "jokalaria_gorde", {"id": "j2", "izena": "Ander"})
        gertaerak.gertaera_berria(kb, "partida_gorde", partida("j2", 27))

    emaitza = truke_osoa(monkeypatch, ka, kb)

    assert emaitza["jasoak"] == 2
    assert gertaerak.egoeraren_hatz_marka(ka) == gertaerak.egoeraren_hatz_marka(kb)
    for k in (ka, kb):
        assert k.execute("SELECT COUNT(*) FROM partidak").fetchone()[0] == 2
        assert k.execute("SELECT COUNT(*) FROM jokalariak").fetchone()[0] == 2


def test_sinkronizazio_hutsa_idempotentea_da(tmp_path, monkeypatch, taldea):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})

    truke_osoa(monkeypatch, ka, kb)
    bigarrena = truke_osoa(monkeypatch, ka, kb)

    assert bigarrena["jasoak"] == 0
    assert bigarrena["bidaltzekoak"] == 0
    assert kb.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0] == 1


def test_offline_aldaketak_bateratzen_dira(tmp_path, monkeypatch, taldea):
    """Biek partida bera aldatzen dute konexiorik gabe: emaitza bat eta bakarra."""
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    partida_id = uuid.uuid4().hex

    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_gorde", {**partida("j1", 30), "id": partida_id})
    truke_osoa(monkeypatch, ka, kb)

    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_gorde", {**partida("j1", 31), "id": partida_id})
    with gailua_bezala(monkeypatch, "gailua-b"):
        gertaerak.gertaera_berria(kb, "partida_gorde", {**partida("j1", 25), "id": partida_id})

    truke_osoa(monkeypatch, ka, kb)
    truke_osoa(monkeypatch, ka, kb)  # bigarrena: biek dena dutela ziurtatzeko

    puntuak_a = ka.execute("SELECT puntuak FROM partida_jokalariak").fetchone()[0]
    puntuak_b = kb.execute("SELECT puntuak FROM partida_jokalariak").fetchone()[0]
    assert puntuak_a == puntuak_b
    assert gertaerak.egoeraren_hatz_marka(ka) == gertaerak.egoeraren_hatz_marka(kb)


def test_ezabatzea_ez_da_berpizten(tmp_path, monkeypatch, taldea):
    """Sinkronizazioak ezin du ezabatutako partida bat itzularazi."""
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    partida_id = uuid.uuid4().hex

    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_gorde", {**partida("j1"), "id": partida_id})
    truke_osoa(monkeypatch, ka, kb)
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "partida_ezabatu", {"id": partida_id})
    truke_osoa(monkeypatch, ka, kb)
    truke_osoa(monkeypatch, ka, kb)

    for k in (ka, kb):
        assert k.execute("SELECT ezabatuta FROM partidak").fetchone()[0] == 1


def test_jokalari_bera_bi_gailutan_ez_da_bikoizten(tmp_path, monkeypatch, taldea):
    """Bakoitzak bere ordenagailuan "Oier" sartzen du: jokalari BAT izan behar da.

    Identifikatzailea izenetik eratortzen denez, bi gailuek berdina kalkulatzen
    dute eta bateratzean bat egiten dute.
    """
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    jokalari_id = gertaerak.jokalari_id_izenetik("Oier")

    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": jokalari_id, "izena": "Oier"})
        gertaerak.gertaera_berria(ka, "partida_gorde", partida(jokalari_id, 30))
    with gailua_bezala(monkeypatch, "gailua-b"):
        gertaerak.gertaera_berria(
            kb, "jokalaria_gorde",
            {"id": gertaerak.jokalari_id_izenetik("  oier  "), "izena": "oier"},
        )
        gertaerak.gertaera_berria(kb, "partida_gorde", partida(jokalari_id, 25))

    truke_osoa(monkeypatch, ka, kb)

    for k in (ka, kb):
        assert k.execute("SELECT COUNT(*) FROM jokalariak").fetchone()[0] == 1
        assert k.execute(
            "SELECT COUNT(*) FROM partida_jokalariak WHERE jokalari_id = ?", (jokalari_id,)
        ).fetchone()[0] == 2


def test_eskaerak_bidaltzailea_kide_bihurtzen_du(tmp_path, monkeypatch, taldea):
    """Guregana jotzen duen gailua kide ezagun bihurtzen da berehala.

    Bestela sinkronizazioak norabide bakarrean funtzionatuko luke haren
    aurkikuntza-seinalea iritsi arte (edo inoiz ez, suebaki batek multicast-a
    norabide batean blokeatzen badu).
    """
    import sarea

    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        eskaera = sinkro.eskaera_sortu(ka)

    ikusitakoak = []
    with gailua_bezala(monkeypatch, "gailua-b"):
        sinkro.eskaera_erantzun(kb, eskaera, kidea_ikusi=ikusitakoak.append)

    assert len(ikusitakoak) == 1
    assert ikusitakoak[0]["gailu_id"] == "gailua-a"
    assert ikusitakoak[0]["portua"] == konfig.SYNC_PORTUA

    sarea._kideak.clear()
    sarea._kidea_gogoratu("gailua-a", "Ordenagailu-A", "192.168.1.40", konfig.SYNC_PORTUA)
    assert [k["helbidea"] for k in sarea.kideak()] == ["192.168.1.40"]


@pytest.mark.parametrize(
    "gailu_id,portua",
    [("gailua-a", 0), ("gailua-a", 99999), ("gailua-a", "47778"), ("../etc", 47778)],
)
def test_kide_datu_okerrak_baztertzen_dira(gailu_id, portua):
    import sarea

    sarea._kideak.clear()
    sarea._kidea_gogoratu(gailu_id, "izena", "192.168.1.40", portua)
    assert sarea.kideak() == []


# ─── Segurtasuna ────────────────────────────────────────────────────────────


def test_beste_taldeko_fardela_baztertu(tmp_path, monkeypatch, taldea):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        eskaera = sinkro.eskaera_sortu(ka)

    # Beste talde batek (beste pasaesaldi bat) ezin du fardela ireki.
    sinkro.taldea_konfiguratu("Beste taldea", "beste-pasaesaldia")
    with gailua_bezala(monkeypatch, "gailua-b"):
        with pytest.raises(kripto.KriptoErrorea):
            sinkro.eskaera_erantzun(kb, eskaera)
    assert kb.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0] == 0


def test_errepikapena_baztertu(tmp_path, monkeypatch, taldea):
    """Fardel oso bat berriro bidaltzea (replay) ez da onartzen."""
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        eskaera = sinkro.eskaera_sortu(ka)

    with gailua_bezala(monkeypatch, "gailua-b"):
        sinkro.eskaera_erantzun(kb, eskaera)
        with pytest.raises(sinkro.SinkroErrorea):
            sinkro.eskaera_erantzun(kb, eskaera)


def test_manipulatutako_fardela_ez_da_aplikatzen(tmp_path, monkeypatch, taldea):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        fardela = bytearray(sinkro.fardela_sortu(
            {"mota": "bultzada", "gertaerak": gertaerak.esportatu(ka)}
        ))
    fardela[-5] ^= 0xFF

    with gailua_bezala(monkeypatch, "gailua-b"):
        with pytest.raises(kripto.KriptoErrorea):
            sinkro.eskaera_erantzun(kb, bytes(fardela))
    assert kb.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0] == 0


def test_gertaera_baliogabeak_iragazten_dira_sinkronizazioan(tmp_path, monkeypatch, taldea):
    """Talde bereko gailu batek datu okerrak bidalita ere, ez dira onartzen."""
    kb = datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        fardela = sinkro.fardela_sortu({
            "mota": "bultzada",
            "gertaerak": [
                {"gertaera_id": "x1", "gailu_id": "gailua-a", "lamport": 1,
                 "unix_ordua": int(time.time()), "mota": "partida_gorde",
                 "entitate_id": "p1",
                 "karga": {"id": "p1", "data": "gaur", "jokalariak": []}},
            ],
        })
    with gailua_bezala(monkeypatch, "gailua-b"):
        sinkro.eskaera_erantzun(kb, fardela)
    assert kb.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0] == 0


def test_gertaera_gehiegi_dituen_fardela_baztertu(tmp_path, monkeypatch, taldea):
    kb = datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        fardela = sinkro.fardela_sortu({
            "mota": "bultzada",
            "gertaerak": [{} for _ in range(sinkro.GEHIENEZ_GERTAERA_FARDELEAN + 1)],
        })
    with gailua_bezala(monkeypatch, "gailua-b"):
        with pytest.raises(sinkro.SinkroErrorea):
            sinkro.eskaera_erantzun(kb, fardela)


# ─── Fitxategi bidezko trukea ───────────────────────────────────────────────


def test_esportatu_eta_inportatu(tmp_path, monkeypatch, taldea):
    ka, kb = datu_basea(tmp_path, "a"), datu_basea(tmp_path, "b")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
        gertaerak.gertaera_berria(ka, "partida_gorde", partida("j1"))
        fardela = sinkro.fitxategira_esportatu(ka)

    with gailua_bezala(monkeypatch, "gailua-b"):
        emaitza = sinkro.fitxategitik_inportatu(kb, fardela)
        # Berriro inportatzeak ez du ezer bikoizten (babeskopietan ohikoa da).
        berriro = sinkro.fitxategitik_inportatu(kb, fardela)

    assert emaitza["berriak"] == 2
    assert berriro["berriak"] == 0
    assert gertaerak.egoeraren_hatz_marka(ka) == gertaerak.egoeraren_hatz_marka(kb)


def test_esportazioa_ez_da_irakurgarria_pasaesaldirik_gabe(tmp_path, monkeypatch, taldea):
    ka = datu_basea(tmp_path, "a")
    with gailua_bezala(monkeypatch, "gailua-a"):
        gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "OierGaraiPuntua"})
        fardela = sinkro.fitxategira_esportatu(ka)
    assert b"OierGaraiPuntua" not in fardela
