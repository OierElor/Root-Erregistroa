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


def test_zutabe_berriak_lehendik_dagoen_datu_basean(tmp_path):
    """`CREATE TABLE IF NOT EXISTS`-ek ez ditu zutabeak gehitzen.

    Datu-base zaharrago batek taulak baditu baina zutabe berririk ez, eta
    horiek gehitu behar dira datuak galdu gabe.
    """
    import sqlite3

    bidea = tmp_path / "zutabeak.db"
    db.hasieratu(bidea)

    # Bertsio zaharreko egoera simulatu: zutabe berriak kendu.
    zaharra = sqlite3.connect(bidea)
    zaharra.execute("ALTER TABLE fakzioak DROP COLUMN arlotea")
    zaharra.execute("ALTER TABLE partida_jokalariak DROP COLUMN arlote_kodea")
    zaharra.commit()
    zaharra.close()

    db.hasieratu(bidea)

    konn = db.konexioa(bidea)
    fakzio_zutabeak = {l[1] for l in konn.execute("PRAGMA table_info(fakzioak)")}
    pj_zutabeak = {l[1] for l in konn.execute("PRAGMA table_info(partida_jokalariak)")}
    assert "arlotea" in fakzio_zutabeak
    assert "arlote_kodea" in pj_zutabeak
    # Eta hazi-datuek berriro markatzen dute zein diren Vagabond-ak.
    assert konn.execute(
        "SELECT arlotea FROM fakzioak WHERE kodea = 'vagabond'").fetchone()[0] == 1
    konn.close()


def test_arlote_katalogoa_hasieratzen_da(tmp_path):
    bidea = tmp_path / "arloteak.db"
    db.hasieratu(bidea)
    konn = db.konexioa(bidea)

    izenak = {l[0] for l in konn.execute("SELECT izena FROM arloteak")}
    assert izenak == {"Thief", "Tinker", "Ranger", "Vagrant", "Arbiter",
                      "Scoundrel", "Ronin", "Adventurer", "Harrier"}
    assert {l[0] for l in konn.execute("SELECT kodea FROM fakzioak WHERE arlotea = 1")} == {
        "vagabond", "vagabond2"}
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
