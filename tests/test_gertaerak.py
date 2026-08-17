"""Gertaera-erregistroaren testak.

Test garrantzitsuena `test_konbergentzia_ordena_edozein_delarik` da: hori da
sinkronizazio osoa zutik mantentzen duen propietatea.
"""

import random
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db          # noqa: E402
import gertaerak   # noqa: E402


@pytest.fixture
def konn(tmp_path, monkeypatch):
    monkeypatch.setenv("GAILU_ID", "gailua-a")
    bidea = tmp_path / "proba.db"
    db.hasieratu(bidea)
    k = db.konexioa(bidea)
    yield k
    k.close()


def partida_karga(jokalari_id, puntuak=30, data="2026-01-01", partida_id=None):
    return {
        "id": partida_id or uuid.uuid4().hex,
        "data": data,
        "mapa_kodea": "udazkena",
        "karta_sorta": "estandarra",
        "oharrak": "",
        "jokalariak": [
            {
                "jokalari_id": jokalari_id,
                "fakzio_kodea": "marquise",
                "puntuak": puntuak,
                "hasiera_ordena": 1,
                "irabazlea": True,
                "garaipen_mota": "puntuak",
            }
        ],
    }


def egoera_laburpena(konn):
    """Datu-basearen egoera konparagarria, ordena finkoan."""
    return {
        "jokalariak": [
            tuple(l) for l in konn.execute(
                "SELECT id, izena, ezizena, ezabatuta FROM jokalariak ORDER BY id"
            )
        ],
        "partidak": [
            tuple(l) for l in konn.execute(
                "SELECT id, data, mapa_kodea, oharrak, ezabatuta FROM partidak ORDER BY id"
            )
        ],
        "parte_hartzeak": [
            tuple(l) for l in konn.execute(
                "SELECT partida_id, jokalari_id, fakzio_kodea, puntuak, irabazlea "
                "FROM partida_jokalariak ORDER BY partida_id, jokalari_id"
            )
        ],
    }


# ─── Oinarrizkoa ────────────────────────────────────────────────────────────


def test_jokalaria_sortu_eta_proiektatu(konn):
    gertaerak.gertaera_berria(
        konn, "jokalaria_gorde", {"id": "j1", "izena": "Oier"}
    )
    lerroa = konn.execute("SELECT * FROM jokalariak WHERE id='j1'").fetchone()
    assert lerroa["izena"] == "Oier"
    assert lerroa["ezabatuta"] == 0


def test_partida_osoa_gorde(konn):
    gertaerak.gertaera_berria(konn, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
    karga = partida_karga("j1", puntuak=31)
    gertaerak.gertaera_berria(konn, "partida_gorde", karga)

    lerroa = konn.execute(
        "SELECT * FROM partida_jokalariak WHERE partida_id = ?", (karga["id"],)
    ).fetchone()
    assert lerroa["puntuak"] == 31
    assert lerroa["irabazlea"] == 1


def test_ezabatzea_tombstone_bat_da(konn):
    gertaerak.gertaera_berria(konn, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
    gertaerak.gertaera_berria(konn, "jokalaria_ezabatu", {"id": "j1"})

    lerroa = konn.execute("SELECT * FROM jokalariak WHERE id='j1'").fetchone()
    assert lerroa["ezabatuta"] == 1
    # Gertaerak erregistroan geratzen dira: bestela sinkronizazioan berpiztuko litzateke.
    assert konn.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0] == 2


def test_partida_editatzeak_jokalariak_ordezkatzen_ditu(konn):
    karga = partida_karga("j1", puntuak=30)
    gertaerak.gertaera_berria(konn, "partida_gorde", karga)
    karga["jokalariak"][0]["puntuak"] = 30
    karga["jokalariak"].append(
        {"jokalari_id": "j2", "fakzio_kodea": "eyrie", "puntuak": 22,
         "hasiera_ordena": 2, "irabazlea": False}
    )
    gertaerak.gertaera_berria(konn, "partida_gorde", karga)

    kopurua = konn.execute(
        "SELECT COUNT(*) FROM partida_jokalariak WHERE partida_id = ?", (karga["id"],)
    ).fetchone()[0]
    assert kopurua == 2


# ─── Bateratzea ─────────────────────────────────────────────────────────────


def test_bikoiztuak_baztertu(konn):
    gertaera = gertaerak.gertaera_berria(
        konn, "jokalaria_gorde", {"id": "j1", "izena": "Oier"}
    )
    emaitza = gertaerak.gehitu(konn, [gertaera, gertaera])
    assert emaitza["berriak"] == 0
    assert konn.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0] == 1


def test_konbergentzia_ordena_edozein_delarik(tmp_path, monkeypatch):
    """Gertaera multzo bera edozein ordenatan → egoera berbera.

    Hau da erregistro banatuaren funtsezko propietatea: sinkronizazioak zein
    ordenatan iristen diren ez du axola.
    """
    monkeypatch.setenv("GAILU_ID", "gailua-a")
    sortzailea = tmp_path / "sortzailea.db"
    db.hasieratu(sortzailea)
    ka = db.konexioa(sortzailea)

    partida_id = uuid.uuid4().hex
    gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
    gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j2", "izena": "Ander"})
    gertaerak.gertaera_berria(
        ka, "partida_gorde", partida_karga("j1", 30, partida_id=partida_id)
    )
    gertaerak.gertaera_berria(
        ka, "partida_gorde", partida_karga("j2", 25, partida_id=partida_id)
    )
    gertaerak.gertaera_berria(ka, "jokalaria_ezabatu", {"id": "j2"})
    guztiak = gertaerak.esportatu(ka)
    erreferentzia = egoera_laburpena(ka)
    ka.close()

    random.seed(20260817)
    for saioa in range(12):
        nahastuak = guztiak[:]
        random.shuffle(nahastuak)
        bidea = tmp_path / f"nahasia{saioa}.db"
        db.hasieratu(bidea)
        kb = db.konexioa(bidea)
        # Zatika sartu, sarearen bidez tantaka iritsiko balira bezala.
        for i in range(0, len(nahastuak), 2):
            gertaerak.gehitu(kb, nahastuak[i:i + 2])
        assert egoera_laburpena(kb) == erreferentzia, f"{saioa}. permutazioa"
        kb.close()


def test_birsortzeak_emaitza_bera_ematen_du(konn):
    gertaerak.gertaera_berria(konn, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
    gertaerak.gertaera_berria(konn, "partida_gorde", partida_karga("j1"))
    gertaerak.gertaera_berria(konn, "jokalaria_gorde", {"id": "j1", "izena": "Oier B."})
    aurretik = egoera_laburpena(konn)

    gertaerak.birsortu(konn)
    assert egoera_laburpena(konn) == aurretik


def test_ezabatzea_sorreraren_aurretik_iristea(tmp_path, monkeypatch):
    """Gertaerak alderantzizko ordenan iristea ez da arazo bat."""
    monkeypatch.setenv("GAILU_ID", "gailua-a")
    iturria = tmp_path / "iturria.db"
    db.hasieratu(iturria)
    ka = db.konexioa(iturria)
    sortu = gertaerak.gertaera_berria(ka, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
    ezabatu = gertaerak.gertaera_berria(ka, "jokalaria_ezabatu", {"id": "j1"})
    ka.close()

    helburua = tmp_path / "helburua.db"
    db.hasieratu(helburua)
    kb = db.konexioa(helburua)
    gertaerak.gehitu(kb, [ezabatu])          # ezabatzea lehenengo
    assert konn_lerroa(kb, "j1") is None     # oraindik ez dago ezer
    gertaerak.gehitu(kb, [sortu])            # sorrera gero
    lerroa = konn_lerroa(kb, "j1")
    assert lerroa is not None and lerroa["ezabatuta"] == 1
    kb.close()


def konn_lerroa(konn, jokalari_id):
    return konn.execute(
        "SELECT * FROM jokalariak WHERE id = ?", (jokalari_id,)
    ).fetchone()


def test_lamport_erlojua_aurreratzen_da(konn):
    kanpokoa = {
        "gertaera_id": uuid.uuid4().hex,
        "gailu_id": "urruneko-gailua",
        "lamport": 500,
        "unix_ordua": 1_700_000_000,
        "mota": "jokalaria_gorde",
        "entitate_id": "j9",
        "karga": {"id": "j9", "izena": "Urrunekoa"},
    }
    gertaerak.gehitu(konn, [kanpokoa])
    hurrengoa = gertaerak.gertaera_berria(
        konn, "jokalaria_gorde", {"id": "j1", "izena": "Oier"}
    )
    assert hurrengoa["lamport"] > 500


# ─── Balidazioa ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "aldaketa",
    [
        {"mota": "ezezaguna_da"},
        {"lamport": -1},
        {"lamport": "asko"},
        {"gertaera_id": "../../etc/passwd"},
        {"karga": {"id": "j1", "izena": "x" * 500}},
        {"karga": "testua"},
        {"entitate_id": "beste-bat"},
    ],
)
def test_gertaera_baliogabeak_baztertzen_dira(konn, aldaketa):
    oinarria = {
        "gertaera_id": uuid.uuid4().hex,
        "gailu_id": "urrunekoa",
        "lamport": 5,
        "unix_ordua": 1_700_000_000,
        "mota": "jokalaria_gorde",
        "entitate_id": "j1",
        "karga": {"id": "j1", "izena": "Oier"},
    }
    emaitza = gertaerak.gehitu(konn, [{**oinarria, **aldaketa}])
    assert emaitza["berriak"] == 0
    assert emaitza["baztertuak"]
    assert konn.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0] == 0


def test_gertaera_baliogabeak_ez_du_besteak_blokeatzen(konn):
    ona = {
        "gertaera_id": uuid.uuid4().hex,
        "gailu_id": "urrunekoa",
        "lamport": 5,
        "unix_ordua": 1_700_000_000,
        "mota": "jokalaria_gorde",
        "entitate_id": "j1",
        "karga": {"id": "j1", "izena": "Oier"},
    }
    txarra = {**ona, "gertaera_id": uuid.uuid4().hex, "mota": "etorkizuneko_mota"}
    emaitza = gertaerak.gehitu(konn, [txarra, ona])
    assert emaitza["berriak"] == 1
    assert len(emaitza["baztertuak"]) == 1


def test_puntu_eta_jokalari_mugak(konn):
    with pytest.raises(gertaerak.GertaeraErrorea):
        gertaerak.karga_balidatu("partida_gorde", partida_karga("j1", puntuak=99999))

    gehiegi = partida_karga("j1")
    gehiegi["jokalariak"] = [
        {"jokalari_id": f"j{i}", "puntuak": 1} for i in range(20)
    ]
    with pytest.raises(gertaerak.GertaeraErrorea):
        gertaerak.karga_balidatu("partida_gorde", gehiegi)


def test_jokalari_errepikatua_partida_batean(konn):
    karga = partida_karga("j1")
    karga["jokalariak"].append({"jokalari_id": "j1", "puntuak": 5})
    with pytest.raises(gertaerak.GertaeraErrorea):
        gertaerak.karga_balidatu("partida_gorde", karga)
