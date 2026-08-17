"""Babeskopien testak: kopia beroa, leheneratzea eta izenen balidazioa."""

import pytest

import babeskopiak
import db
import gertaerak


@pytest.fixture
def ingurunea(tmp_path, monkeypatch):
    monkeypatch.setenv("GAILU_ID", "gailua-a")
    monkeypatch.setattr(babeskopiak, "KOPIA_DIR", tmp_path / "backups")
    bidea = tmp_path / "root.db"
    db.hasieratu(bidea)
    konn = db.konexioa(bidea)
    yield konn
    konn.close()


def test_kopia_egin_eta_zerrendatu(ingurunea):
    gertaerak.gertaera_berria(ingurunea, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
    bidea = babeskopiak.kopia_egin(ingurunea, "eskuz")

    assert bidea.exists()
    assert babeskopiak.KOPIA_ERED.match(bidea.name)
    assert oct(bidea.stat().st_mode)[-3:] == "600"
    assert [k["izena"] for k in babeskopiak.zerrenda()] == [bidea.name]


def test_kopia_datu_basea_irekita_egiten_da(ingurunea):
    """Kopia beroa: idazketa erdian ere emaitza koherentea."""
    gertaerak.gertaera_berria(ingurunea, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
    bidea = babeskopiak.kopia_egin(ingurunea)
    assert db.eskema_zuzena(bidea)

    kopia_konn = db.konexioa(bidea)
    assert kopia_konn.execute("SELECT izena FROM jokalariak").fetchone()[0] == "Oier"
    kopia_konn.close()


def test_leheneratzeak_aurreko_egoera_itzultzen_du(ingurunea):
    gertaerak.gertaera_berria(ingurunea, "jokalaria_gorde", {"id": "j1", "izena": "Oier"})
    kopia = babeskopiak.kopia_egin(ingurunea)

    gertaerak.gertaera_berria(ingurunea, "jokalaria_gorde", {"id": "j2", "izena": "Ander"})
    assert ingurunea.execute("SELECT COUNT(*) FROM jokalariak").fetchone()[0] == 2

    emaitza = babeskopiak.leheneratu(ingurunea, kopia.name)

    assert ingurunea.execute("SELECT COUNT(*) FROM jokalariak").fetchone()[0] == 1
    # Leheneratu aurreko egoera ere gordeta dago: ez da ezer galtzen.
    aurrekoa = babeskopiak.KOPIA_DIR / emaitza["aurreko_kopia"]
    aurreko_konn = db.konexioa(aurrekoa)
    assert aurreko_konn.execute("SELECT COUNT(*) FROM jokalariak").fetchone()[0] == 2
    aurreko_konn.close()


@pytest.mark.parametrize(
    "izena",
    [
        "../../../etc/passwd",
        "/etc/passwd",
        "kopia-20260101-120000-eskuz.db/../../beste.db",
        "root.db",
        "kopia-20260101.db",
        "",
        "kopia-20260101-120000-eskuz.db.txt",
    ],
)
def test_izen_arriskutsuak_baztertzen_dira(ingurunea, izena):
    with pytest.raises(ValueError):
        babeskopiak.bidea_lortu(izena)


def test_datu_base_ez_den_fitxategia_ez_da_leheneratzen(ingurunea):
    babeskopiak.KOPIA_DIR.mkdir(exist_ok=True)
    faltsua = babeskopiak.KOPIA_DIR / "kopia-20260101-120000-eskuz.db"
    faltsua.write_bytes(b"hau ez da datu-base bat")

    with pytest.raises(ValueError, match="ez da Root Erregistroa"):
        babeskopiak.leheneratu(ingurunea, faltsua.name)


def test_garbitzeak_egun_bakoitzeko_bat_gordetzen_du(ingurunea, monkeypatch):
    babeskopiak.KOPIA_DIR.mkdir(exist_ok=True)
    for eguna in ("20260101", "20260102", "20260103"):
        for ordua in ("100000", "110000", "120000"):
            (babeskopiak.KOPIA_DIR / f"kopia-{eguna}-{ordua}-auto.db").write_bytes(b"x")

    babeskopiak.garbitu(gehienez=2)
    gelditzen_direnak = {k["izena"] for k in babeskopiak.zerrenda()}

    # Azken biak + egun bakoitzeko bat gutxienez.
    egunak = {izena[6:14] for izena in gelditzen_direnak}
    assert egunak == {"20260101", "20260102", "20260103"}
    assert len(gelditzen_direnak) < 9


def test_abioko_kopia_egunean_behin(ingurunea):
    lehena = babeskopiak.abioko_kopia(ingurunea)
    bigarrena = babeskopiak.abioko_kopia(ingurunea)
    assert lehena is not None
    assert bigarrena is None
