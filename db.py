#!/usr/bin/env python3
"""Datu-basearen konexioa, eskema eta hazi-datuak."""

import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_FITX = Path(os.environ.get("DB_FILE", BASE_DIR / "root.db"))
ESKEMA_FITX = BASE_DIR / "eskema.sql"

# ─── Hazi-datuak ────────────────────────────────────────────────────────────
# Kode hauek egonkorrak dira: gailu guztiek berdinak dituzte, beraz ez dute
# sinkronizatu beharrik. Hedapen berri bat atera ahala, aplikaziotik gehi
# daitezke (orduan bai, gertaera baten bidez sinkronizatuta).

FAKZIOAK = [
    # (kodea, izena, hedapena, kolorea)
    ("marquise",  "Katu Markesa",          "Oinarrizkoa",           "#E8912D"),
    ("eyrie",     "Arranoen Dinastiak",    "Oinarrizkoa",           "#3B76C4"),
    ("alliance",  "Basoko Aliantza",       "Oinarrizkoa",           "#4FA65B"),
    ("vagabond",  "Arlotea",               "Oinarrizkoa",           "#9B9B9B"),
    ("vagabond2", "Bigarren Arlotea",      "Ibaia eta Lurpea",      "#6E6E6E"),
    ("cult",      "Musker Kultua",         "Ibaia eta Lurpea",      "#E8D44D"),
    ("riverfolk", "Ibaitarren Konpainia",  "Ibaia eta Lurpea",      "#43BFC7"),
    ("duchy",     "Lurpeko Dukerria",      "Lurpeko Dukerria",      "#C4762D"),
    ("corvid",    "Korbiden Konspirazioa", "Lurpeko Dukerria",      "#7A4FA6"),
    ("hundreds",  "Ehunen Jauna",          "Erbesteratuak",         "#C43B3B"),
    ("keepers",   "Burdinazko Zaindariak", "Erbesteratuak",         "#8C9EA6"),
]

MAPAK = [
    ("udazkena", "Udazkena"),
    ("negua",    "Negua"),
    ("aintzira", "Aintzira"),
    ("mendia",   "Mendia"),
]

KARTA_SORTAK = [
    ("estandarra",   "Estandarra"),
    ("erbesteratuak", "Erbesteratuak eta Partisanoak"),
]

GARAIPEN_MOTAK = ("puntuak", "nagusitasuna", "koalizioa", "berezia")

BEHARREZKO_TAULAK = {"gertaerak", "partidak", "partida_jokalariak", "jokalariak", "meta"}


def konexioa(bidea: Path | str | None = None) -> sqlite3.Connection:
    konn = sqlite3.connect(str(bidea or DB_FITX), timeout=15)
    konn.row_factory = sqlite3.Row
    konn.execute("PRAGMA foreign_keys = ON")
    # WAL: irakurketek ez dute idazketarik blokeatzen (sinkronizazioa hari
    # bereizian dabil), eta hutsegite baten aurrean sendoagoa da.
    konn.execute("PRAGMA journal_mode = WAL")
    konn.execute("PRAGMA synchronous = NORMAL")
    return konn


def hasieratu(bidea: Path | str | None = None) -> None:
    """Eskema sortu (idempotentea) eta hazi-datuak sartu."""
    Path(bidea or DB_FITX).parent.mkdir(parents=True, exist_ok=True)
    konn = konexioa(bidea)
    try:
        konn.executescript(ESKEMA_FITX.read_text(encoding="utf-8"))
        konn.executemany(
            "INSERT OR IGNORE INTO fakzioak (kodea, izena, hedapena, kolorea) "
            "VALUES (?,?,?,?)",
            FAKZIOAK,
        )
        konn.executemany(
            "INSERT OR IGNORE INTO mapak (kodea, izena) VALUES (?,?)", MAPAK
        )
        konn.executemany(
            "INSERT OR IGNORE INTO karta_sortak (kodea, izena) VALUES (?,?)",
            KARTA_SORTAK,
        )
        konn.execute(
            "INSERT OR IGNORE INTO meta (gakoa, balioa) VALUES ('lamport', '0')"
        )
        konn.commit()
    finally:
        konn.close()


def meta_irakurri(konn: sqlite3.Connection, gakoa: str, lehenetsia: str = "") -> str:
    lerroa = konn.execute(
        "SELECT balioa FROM meta WHERE gakoa = ?", (gakoa,)
    ).fetchone()
    return lerroa["balioa"] if lerroa else lehenetsia


def meta_idatzi(konn: sqlite3.Connection, gakoa: str, balioa: str) -> None:
    konn.execute(
        "INSERT INTO meta (gakoa, balioa) VALUES (?, ?) "
        "ON CONFLICT(gakoa) DO UPDATE SET balioa = excluded.balioa",
        (gakoa, str(balioa)),
    )


def eskema_zuzena(bidea: Path | str) -> bool:
    """Egiaztatu fitxategi bat benetan gure datu-base bat den.

    Babeskopia bat leheneratu aurretik erabiltzen da: fitxategi arbitrario bat
    ez dadin datu-base gisa jarri.
    """
    try:
        konn = sqlite3.connect(f"file:{bidea}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        izenak = {
            l[0]
            for l in konn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        return BEHARREZKO_TAULAK.issubset(izenak)
    except sqlite3.DatabaseError:
        return False
    finally:
        konn.close()


if __name__ == "__main__":
    hasieratu()
    print(f"Datu-basea prest: {DB_FITX}")
