#!/usr/bin/env python3
"""Babeskopiak: sortu, atxiki eta leheneratu.

`cp` erabili beharrean SQLite-ren babeskopia APIa erabiltzen da: datu-basea
irekita eta idazketa erdian dagoela ere kopia koherentea ateratzen du. Fitxategia
zuzenean kopiatzeak WAL fitxategia atzean utz lezake eta kopia hondatua sortu.
"""

import re
import sqlite3
import time
from pathlib import Path

import db

# Babeskopiak datu-basearen ondoan: DB_FILE aldatzen bada (proba bat, bigarren
# erregistro bat), haren kopiak ere bereizita geratzen dira.
KOPIA_DIR = db.DB_FITX.parent / "backups"

# Izen-eredu zorrotza. Fitxategi-izenak erabiltzailearengandik datoz (leheneratze
# eskaeretan), eta "../../.ssh/id_rsa" bezalako izenak baztertu behar dira.
KOPIA_ERED = re.compile(
    r"^kopia-\d{8}-\d{6}(-(auto|eskuz|inportazio|aurretik))?\.db$"
)
ETIKETAK = {"auto", "eskuz", "inportazio", "aurretik"}


def _karpeta():
    KOPIA_DIR.mkdir(exist_ok=True)
    return KOPIA_DIR


def kopia_egin(konn: sqlite3.Connection, etiketa: str = "eskuz") -> Path:
    if etiketa not in ETIKETAK:
        etiketa = "eskuz"
    _karpeta()
    izena = f"kopia-{time.strftime('%Y%m%d-%H%M%S')}-{etiketa}.db"
    helburua = KOPIA_DIR / izena

    # Denbora-marka bereko bi kopia (proba azkarrak): ez gainidatzi.
    kontagailua = 1
    while helburua.exists():
        kontagailua += 1
        helburua = KOPIA_DIR / f"kopia-{time.strftime('%Y%m%d-%H%M%S')}-{etiketa}.db"
        if kontagailua > 3:
            time.sleep(1)
            kontagailua = 1

    helburu_konn = sqlite3.connect(str(helburua))
    try:
        konn.backup(helburu_konn)
        # Kopiak WAL modua heredatzen du, eta horrek `-wal`/`-shm` fitxategi
        # lagunak sortzen ditu irakurtzean ere. Fitxategi bakar bat izatea nahi
        # dugu: USB batera kopiatzeko modukoa, zatirik ahaztu gabe.
        helburu_konn.execute("PRAGMA journal_mode = DELETE")
    finally:
        helburu_konn.close()
    helburua.chmod(0o600)
    for luzapena in ("-wal", "-shm"):
        Path(str(helburua) + luzapena).unlink(missing_ok=True)
    return helburua


def zerrenda() -> list:
    _karpeta()
    emaitza = []
    for bidea in sorted(KOPIA_DIR.glob("kopia-*.db"), reverse=True):
        if not KOPIA_ERED.match(bidea.name):
            continue
        egoera = bidea.stat()
        emaitza.append(
            {
                "izena": bidea.name,
                "tamaina": egoera.st_size,
                "noiz": int(egoera.st_mtime),
            }
        )
    return emaitza


def garbitu(gehienez: int = 20) -> list:
    """Kopia zaharrenak ezabatu, azken `gehienez` gordez.

    Egun bakoitzeko kopia zaharrena beti gordetzen da azken hilabetean: horrela
    egun bereko hogei kopiak ez dute historia osoa botatzen.
    """
    guztiak = zerrenda()
    if len(guztiak) <= gehienez:
        return []

    gordetzekoak = {k["izena"] for k in guztiak[:gehienez]}
    egun_bakarrak = {}
    for kopia in guztiak:
        eguna = kopia["izena"][6:14]
        egun_bakarrak.setdefault(eguna, kopia["izena"])
    gordetzekoak |= set(egun_bakarrak.values())

    ezabatuak = []
    for kopia in guztiak:
        if kopia["izena"] not in gordetzekoak:
            (KOPIA_DIR / kopia["izena"]).unlink(missing_ok=True)
            ezabatuak.append(kopia["izena"])
    return ezabatuak


def bidea_lortu(izena: str) -> Path:
    """Kopia baten bide segurua. Izen susmagarri orok salbuespena eragiten du."""
    if not KOPIA_ERED.match(izena or ""):
        raise ValueError("Babeskopia izen baliogabea")
    bidea = (KOPIA_DIR / izena).resolve()
    if bidea.parent != KOPIA_DIR.resolve() or not bidea.is_file():
        raise ValueError("Babeskopia ez da existitzen")
    return bidea


def leheneratu(konn: sqlite3.Connection, izena: str) -> dict:
    """Babeskopia bat uneko datu-basearen gainean ezarri.

    Aurretik uneko egoeraren kopia bat egiten da beti: leheneratzea okerra bada
    ere, ez da ezer galtzen.
    """
    iturria = bidea_lortu(izena)
    if not db.eskema_zuzena(iturria):
        raise ValueError("Fitxategi hori ez da Root Erregistroa datu-base bat")

    segurtasun_kopia = kopia_egin(konn, "aurretik")

    iturri_konn = sqlite3.connect(f"file:{iturria}?mode=ro", uri=True)
    try:
        # Alderantzizko norabidean: kopiatik datu-base bizira. Konexio irekiak
        # baliozkoa izaten jarraitzen du eta WAL egoera koherentea da.
        iturri_konn.backup(konn)
    finally:
        iturri_konn.close()

    return {
        "leheneratua": izena,
        "aurreko_kopia": segurtasun_kopia.name,
    }


def abioko_kopia(konn: sqlite3.Connection, gehienez: int = 20) -> Path | None:
    """Eguneko lehen abioan kopia automatiko bat egin."""
    gaur = time.strftime("%Y%m%d")
    for kopia in zerrenda():
        if kopia["izena"].startswith(f"kopia-{gaur}") and kopia["izena"].endswith("-auto.db"):
            return None
    bidea = kopia_egin(konn, "auto")
    garbitu(gehienez)
    return bidea
