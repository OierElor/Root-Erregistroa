"""Fardel zifratuaren testak: konfidentzialtasuna, osotasuna eta mugak."""

import time
import zlib

import pytest

import kripto

GATZA = b"0123456789abcdef"


@pytest.fixture
def gakoa():
    return kripto.gakoa_eratorri("pasaesaldi-luze-bat", GATZA)


def test_joan_etorria(gakoa):
    fardela = kripto.fardela_sortu(gakoa, {"gertaerak": [1, 2, 3]}, "gailua-a")
    goiburua, edukia = kripto.fardela_ireki(gakoa, fardela)
    assert edukia["gertaerak"] == [1, 2, 3]
    assert goiburua["gailu_id"] == "gailua-a"


def test_gako_bera_pasaesaldi_beretik():
    assert kripto.gakoa_eratorri("abc12345", GATZA) == kripto.gakoa_eratorri("abc12345", GATZA)
    assert kripto.gakoa_eratorri("abc12345", GATZA) != kripto.gakoa_eratorri("abc12346", GATZA)


def test_pasaesaldi_laburregia_baztertu():
    with pytest.raises(kripto.KriptoErrorea):
        kripto.gakoa_eratorri("laburra", GATZA)


def test_edukia_ez_da_testu_lauan_agertzen(gakoa):
    fardela = kripto.fardela_sortu(gakoa, {"oharra": "SEKRETUA-1234"}, "gailua-a")
    assert b"SEKRETUA" not in fardela


def test_gako_okerrak_huts_egiten_du(gakoa):
    fardela = kripto.fardela_sortu(gakoa, {"a": 1}, "gailua-a")
    bestea = kripto.gakoa_eratorri("beste-pasaesaldia", GATZA)
    with pytest.raises(kripto.KriptoErrorea):
        kripto.fardela_ireki(bestea, fardela)


@pytest.mark.parametrize("posizioa", [-1, -20, 20, 60])
def test_byte_bat_aldatzeak_fardela_baliogabetzen_du(gakoa, posizioa):
    """Osotasuna: sarean edo diskoan aldatutako fardel bat ez da onartzen."""
    fardela = bytearray(kripto.fardela_sortu(gakoa, {"a": "x" * 100}, "gailua-a"))
    fardela[posizioa] ^= 0x01
    with pytest.raises(kripto.KriptoErrorea):
        kripto.fardela_ireki(gakoa, bytes(fardela))


def test_goiburua_manipulatzeak_huts_egiten_du(gakoa):
    """Goiburua AAD da: testu lauan egon arren, ezin da ukitu."""
    fardela = kripto.fardela_sortu(gakoa, {"a": 1}, "gailua-a")
    aldatua = fardela.replace(b'"gailua-a"', b'"gailua-x"')
    assert aldatua != fardela
    with pytest.raises(kripto.KriptoErrorea):
        kripto.fardela_ireki(gakoa, aldatua)


def test_denbora_leihotik_kanpokoa_baztertu(gakoa, monkeypatch):
    fardela = kripto.fardela_sortu(gakoa, {"a": 1}, "gailua-a")
    oraingoa = time.time()
    monkeypatch.setattr(time, "time", lambda: oraingoa + kripto.DENBORA_LEIHOA + 60)
    with pytest.raises(kripto.KriptoErrorea):
        kripto.fardela_ireki(gakoa, fardela)
    # Babeskopiek zaharrak izan behar dute, eta hor ez da denbora egiaztatzen.
    assert kripto.fardela_ireki(gakoa, fardela, denbora_egiaztatu=False)[1] == {"a": 1}


def test_fitxategi_arrotza_baztertu(gakoa):
    with pytest.raises(kripto.KriptoErrorea):
        kripto.fardela_ireki(gakoa, b"PK\x03\x04 zip fitxategi bat")


def test_konpresio_bonba_baztertu(gakoa):
    """Byte gutxi batzuk gigabyte bihur daitezke deskonprimatzean."""
    bonba = zlib.compress(b"\0" * (kripto.GEHIENEZ_DESKONPRIMATUTA + 1024))
    with pytest.raises(kripto.KriptoErrorea):
        kripto._deskonprimatu(bonba)


def test_talde_markak_ez_du_gakoa_agertzen(gakoa):
    marka = kripto.talde_marka(gakoa)
    assert gakoa.hex() not in marka
    assert len(marka) == 32
