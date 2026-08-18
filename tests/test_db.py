"""Hazi-datuen migrazioaren testak.

Izenak aldatzen direnean (adib. euskaratik ingelesezko izen ofizialetara),
lehendik dagoen datu-baseak ere eguneratu behar du — baina erabiltzaileak eskuz
aldatutakoa errespetatuz.
"""

import db
import gertaerak


def test_izen_zaharrak_eguneratzen_dira(tmp_path):
    bidea = tmp_path / "zaharra.db"
    db.hasieratu(bidea)
    konn = db.konexioa(bidea)

    # Bertsio zaharreko egoera simulatu.
    konn.execute("UPDATE fakzioak SET izena = 'Katu Markesa' WHERE kodea = 'marquise'")
    konn.execute("UPDATE mapak SET izena = 'Udazkena' WHERE kodea = 'udazkena'")
    konn.commit()
    konn.close()

    db.hasieratu(bidea)

    konn = db.konexioa(bidea)
    assert konn.execute(
        "SELECT izena FROM fakzioak WHERE kodea = 'marquise'"
    ).fetchone()[0] == "Marquise de Cat"
    assert konn.execute(
        "SELECT izena FROM mapak WHERE kodea = 'udazkena'"
    ).fetchone()[0] == "Autumn"
    konn.close()


def test_eskuz_aldatutakoa_ez_da_berridazten(tmp_path, monkeypatch):
    """Katalogotik izena aldatuz gero, hurrengo abioak ez du desegiten."""
    monkeypatch.setenv("GAILU_ID", "gailua-a")
    bidea = tmp_path / "editatua.db"
    db.hasieratu(bidea)
    konn = db.konexioa(bidea)

    gertaerak.gertaera_berria(konn, "fakzioa_gorde", {
        "kodea": "marquise", "izena": "Katutxoak", "hedapena": "Nirea", "kolorea": "#111111",
    })
    konn.close()

    db.hasieratu(bidea)

    konn = db.konexioa(bidea)
    lerroa = konn.execute("SELECT * FROM fakzioak WHERE kodea = 'marquise'").fetchone()
    assert lerroa["izena"] == "Katutxoak"
    assert lerroa["azken_lamport"] > 0
    konn.close()


def test_partida_zaharrek_izen_berriak_erakusten_dituzte(tmp_path, monkeypatch):
    """Kodeak ez direnez aldatzen, lehendik sartutako partidak ez dira hausten."""
    monkeypatch.setenv("GAILU_ID", "gailua-a")
    bidea = tmp_path / "partidak.db"
    db.hasieratu(bidea)
    konn = db.konexioa(bidea)

    gertaerak.gertaera_berria(konn, "partida_gorde", {
        "id": "p1", "data": "2026-01-01", "mapa_kodea": "udazkena",
        "jokalariak": [{"jokalari_id": "j1", "fakzio_kodea": "marquise", "puntuak": 30}],
    })

    izena = konn.execute(
        "SELECT f.izena FROM partida_jokalariak pj "
        "JOIN fakzioak f ON f.kodea = pj.fakzio_kodea WHERE pj.partida_id = 'p1'"
    ).fetchone()[0]
    assert izena == "Marquise de Cat"
    konn.close()


def test_mertzenario_eta_leku_katalogoak_hasieratzen_dira(tmp_path):
    bidea = tmp_path / "katalogoak.db"
    db.hasieratu(bidea)
    konn = db.konexioa(bidea)

    assert konn.execute("SELECT COUNT(*) FROM mertzenarioak").fetchone()[0] == len(db.MERTZENARIOAK)
    assert konn.execute("SELECT COUNT(*) FROM leku_bereziak").fetchone()[0] == len(db.LEKU_BEREZIAK)
    assert konn.execute(
        "SELECT izena FROM mertzenarioak WHERE kodea = 'forest-patrol'"
    ).fetchone()[0] == "Forest Patrol"
    assert konn.execute(
        "SELECT izena FROM leku_bereziak WHERE kodea = 'tower'"
    ).fetchone()[0] == "The Tower"
    konn.close()


def test_kodeak_ez_dira_aldatu(tmp_path):
    """Kode bat aldatzeak lehendik dauden gertaerak hautsiko lituzke.

    Test hau txartel gorri bat da: kodeak nahi gabe aldatzen badira, hemen
    geldituko da.
    """
    fakzio_kodeak = {k for k, *_ in db.FAKZIOAK}
    assert {"marquise", "eyrie", "alliance", "vagabond", "cult", "riverfolk",
            "duchy", "corvid", "hundreds", "keepers"} <= fakzio_kodeak
    assert {k for k, _ in db.MAPAK} == {"udazkena", "negua", "aintzira", "mendia"}
    assert {k for k, _ in db.KARTA_SORTAK} == {"estandarra", "erbesteratuak"}
    assert db.GARAIPEN_KODEAK == ("puntuak", "nagusitasuna", "koalizioa", "berezia")
