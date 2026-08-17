#!/usr/bin/env python3
"""Gailuaren identitatea eta taldearen konfigurazioa.

Datu hauek EZ dira datu-basean gordetzen, nahita: datu-basea beste ordenagailu
batera kopiatzen bada (babeskopia bat leheneratuz, adibidez), gailu berri horrek
bere identitate propioa izan behar du. Bi gailuk `gailu_id` bera izango balute,
gertaeren ordena deterministikoa hautsiko litzateke.

Konfigurazio-karpeta: ~/.config/root-erregistroa/  (KONFIG_DIR-ekin alda daiteke)
"""

import json
import os
import stat
import uuid
from pathlib import Path

KONFIG_DIR = Path(
    os.environ.get("KONFIG_DIR", Path.home() / ".config" / "root-erregistroa")
)
GAILU_FITX = KONFIG_DIR / "gailua.json"
TALDE_FITX = KONFIG_DIR / "talde.json"
EZARPEN_FITX = KONFIG_DIR / "ezarpenak.json"

EZARPEN_LEHENETSIAK = {
    "sync_auto": True,
    "babeskopia_gehienez": 20,
    "babeskopia_abioan": True,
}


def _karpeta_ziurtatu() -> None:
    KONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Norberarentzat soilik: taldearen gakoa hemen bizi da.
    os.chmod(KONFIG_DIR, stat.S_IRWXU)


def _idatzi_pribatua(bidea: Path, edukia: dict) -> None:
    """Idatzi 0600 baimenekin, aldi baterako fitxategi baten bidez (atomikoa)."""
    _karpeta_ziurtatu()
    behin_behinekoa = bidea.with_suffix(bidea.suffix + ".berria")
    fd = os.open(behin_behinekoa, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(edukia, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(behin_behinekoa, bidea)


def _irakurri(bidea: Path) -> dict | None:
    try:
        with open(bidea, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ─── Gailua ─────────────────────────────────────────────────────────────────


def gailua() -> dict:
    """Gailu honen identitatea; lehen deian sortzen da."""
    ingurunekoa = os.environ.get("GAILU_ID")
    if ingurunekoa:
        return {
            "gailu_id": ingurunekoa,
            "izena": os.environ.get("GAILU_IZENA", ingurunekoa[:8]),
        }

    datuak = _irakurri(GAILU_FITX)
    if datuak and datuak.get("gailu_id"):
        return datuak

    datuak = {
        "gailu_id": uuid.uuid4().hex,
        "izena": os.environ.get("GAILU_IZENA") or os.uname().nodename,
    }
    _idatzi_pribatua(GAILU_FITX, datuak)
    return datuak


def gailu_id() -> str:
    return gailua()["gailu_id"]


def gailu_izena() -> str:
    return gailua().get("izena") or gailu_id()[:8]


def gailua_izendatu(izena: str) -> None:
    datuak = gailua()
    datuak["izena"] = izena.strip()[:60]
    _idatzi_pribatua(GAILU_FITX, datuak)


# ─── Taldea ─────────────────────────────────────────────────────────────────
#
# {"gatza": b64, "gakoa": b64, "talde_marka": hex, "izena": str}
#
# Pasaesaldia bera EZ da inoiz gordetzen; eratorritako gakoa bakarrik, 0600
# baimenekin. Zure erabiltzaile-kontua duen norbaitek irakur dezake — hori
# saihesteko modu bakarra abio bakoitzean pasaesaldia eskatzea litzateke, eta
# erabilerraztasunaren truke ez da merezi mahai-joko baten erregistro batentzat.


def taldea() -> dict | None:
    return _irakurri(TALDE_FITX)


def taldea_gorde(datuak: dict) -> None:
    _idatzi_pribatua(TALDE_FITX, datuak)


def taldea_ezabatu() -> None:
    TALDE_FITX.unlink(missing_ok=True)


def talderik_badago() -> bool:
    d = taldea()
    return bool(d and d.get("gakoa"))


# ─── Ezarpenak ──────────────────────────────────────────────────────────────


def ezarpenak() -> dict:
    return {**EZARPEN_LEHENETSIAK, **(_irakurri(EZARPEN_FITX) or {})}


def ezarpenak_gorde(berriak: dict) -> dict:
    oraingoak = ezarpenak()
    for gakoa, balioa in berriak.items():
        if gakoa in EZARPEN_LEHENETSIAK:
            oraingoak[gakoa] = balioa
    _idatzi_pribatua(EZARPEN_FITX, oraingoak)
    return oraingoak
