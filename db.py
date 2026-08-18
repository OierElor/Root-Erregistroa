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

# Izenak jokoan ageri diren bezala daude, ingelesez: kartetan eta arauetan halaxe
# datoz, eta partida sartzean itzultzen ibili beharrik ez izateko.
#
# KODEAK EZ DIRA INOIZ ALDATZEN. Gertaeretan idatzita daude, eta gertaerak
# aldaezinak dira (sinkronizatuta eta babeskopietan). Izena bakarrik alda daiteke.

FAKZIOAK = [
    # (kodea, izena, hedapena, kolorea, arlotea)
    # `arlotea = 1`: fakzio horrek pertsonaia bat hautatzen du (Vagabond-ak).
    ("marquise",  "Marquise de Cat",      "Root",                    "#E8912D", 0),
    ("eyrie",     "Eyrie Dynasties",      "Root",                    "#3B76C4", 0),
    ("alliance",  "Woodland Alliance",    "Root",                    "#4FA65B", 0),
    ("vagabond",  "Vagabond",             "Root",                    "#9B9B9B", 1),
    ("vagabond2", "Vagabond (2nd)",       "The Riverfolk Expansion", "#6E6E6E", 1),
    ("cult",      "Lizard Cult",          "The Riverfolk Expansion", "#E8D44D", 0),
    ("riverfolk", "Riverfolk Company",    "The Riverfolk Expansion", "#43BFC7", 0),
    ("duchy",     "Underground Duchy",    "The Underworld Expansion", "#C4762D", 0),
    ("corvid",    "Corvid Conspiracy",    "The Underworld Expansion", "#7A4FA6", 0),
    ("hundreds",  "Lord of the Hundreds", "The Marauder Expansion",  "#C43B3B", 0),
    ("keepers",   "Keepers in Iron",      "The Marauder Expansion",  "#8C9EA6", 0),
]

# Vagabond-aren pertsonaiak. Fakzioa bera "Vagabond" da; hemen zein pertsonaia
# erabili den zehazten da (Thief, Ranger…).
ARLOTEAK = [
    ("thief",      "Thief",      "Root"),
    ("tinker",     "Tinker",     "Root"),
    ("ranger",     "Ranger",     "Root"),
    ("vagrant",    "Vagrant",    "The Riverfolk Expansion"),
    ("arbiter",    "Arbiter",    "The Riverfolk Expansion"),
    ("scoundrel",  "Scoundrel",  "The Riverfolk Expansion"),
    ("ronin",      "Ronin",      "The Vagabond Pack"),
    ("adventurer", "Adventurer", "The Vagabond Pack"),
    ("harrier",    "Harrier",    "The Vagabond Pack"),
]

MAPAK = [
    ("udazkena", "Autumn"),
    ("negua",    "Winter"),
    ("aintzira", "Lake"),
    ("mendia",   "Mountain"),
]

KARTA_SORTAK = [
    ("estandarra",    "Standard Deck"),
    ("erbesteratuak", "Exiles and Partisans Deck"),
]

# Mertzenarioak (Hirelings). Karta bakoitzak izen propioa du sustatuta (promoted)
# edo jaitsita (demoted) dagoenaren arabera, beraz izena hautatzeak dena esaten du:
# ez da alde bat markatzeko eremurik behar. Bikoteka daude zerrendatuta.
MERTZENARIOAK = [
    # (kodea, izena, hedapena)
    ("forest-patrol",     "Forest Patrol",     "The Marauder Expansion"),
    ("feline-physicians", "Feline Physicians", "The Marauder Expansion"),
    ("last-dynasty",      "Last Dynasty",      "The Marauder Expansion"),
    ("bluebird-nobles",   "Bluebird Nobles",   "The Marauder Expansion"),
    ("spring-uprising",   "Spring Uprising",   "The Marauder Expansion"),
    ("rabbit-scouts",     "Rabbit Scouts",     "The Marauder Expansion"),
    ("the-exile",         "The Exile",         "The Marauder Expansion"),
    ("the-brigand",       "The Brigand",       "The Marauder Expansion"),

    ("riverfolk-flotilla", "Riverfolk Flotilla", "Riverfolk Hirelings Pack"),
    ("otter-divers",       "Otter Divers",       "Riverfolk Hirelings Pack"),
    ("warm-sun-prophets",  "Warm Sun Prophets",  "Riverfolk Hirelings Pack"),
    ("lizard-envoys",      "Lizard Envoys",      "Riverfolk Hirelings Pack"),
    ("highway-bandits",    "Highway Bandits",    "Riverfolk Hirelings Pack"),
    ("bandit-gangs",       "Bandit Gangs",       "Riverfolk Hirelings Pack"),

    ("sunward-expedition", "Sunward Expedition", "Underworld Hirelings Pack"),
    ("mole-artisans",      "Mole Artisans",      "Underworld Hirelings Pack"),
    ("furious-protector",  "Furious Protector",  "Underworld Hirelings Pack"),
    ("stoic-protector",    "Stoic Protector",    "Underworld Hirelings Pack"),
    ("corvid-spies",       "Corvid Spies",       "Underworld Hirelings Pack"),
    ("raven-sentinels",    "Raven Sentinels",    "Underworld Hirelings Pack"),

    ("flame-bearers",      "Flame Bearers",      "Marauder Hirelings Pack"),
    ("rat-smugglers",      "Rat Smugglers",      "Marauder Hirelings Pack"),
    ("street-band",        "Street Band",        "Marauder Hirelings Pack"),
    ("popular-band",       "Popular Band",       "Marauder Hirelings Pack"),
    ("vault-keepers",      "Vault Keepers",      "Marauder Hirelings Pack"),
    ("badger-bodyguards",  "Badger Bodyguards",  "Marauder Hirelings Pack"),
]

# Leku bereziak (Landmarks).
LEKU_BEREZIAK = [
    ("tower",           "The Tower",           "The Underworld Expansion"),
    ("ferry",           "The Ferry",           "The Underworld Expansion"),
    ("black-market",    "The Black Market",    "Landmark Pack"),
    ("lost-city",       "The Lost City",       "Landmark Pack"),
    ("legendary-forge", "The Legendary Forge", "Landmark Pack"),
    ("elder-treetop",   "The Elder Treetop",   "Landmark Pack"),
]

# Kodea gertaeretan gordetzen da; etiketa ikusteko bakarrik da.
GARAIPEN_MOTAK = [
    ("puntuak",      "Points"),
    ("nagusitasuna", "Dominance"),
    ("koalizioa",    "Coalition"),
    ("berezia",      "Other"),
]
GARAIPEN_KODEAK = tuple(kodea for kodea, _ in GARAIPEN_MOTAK)

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
        eskema_ezarri(konn)
        konn.commit()
    finally:
        konn.close()


def eskema_ezarri(konn: sqlite3.Connection) -> None:
    """Eskema eta hazi-datuak konexio ireki baten gainean ezarri.

    Idempotentea. `hasieratu`-k erabiltzen du, eta baita babeskopia bat
    leheneratu ondoren ere: kopia zaharrago batek taula berriak falta izan
    ditzake, eta hemen osatzen dira.
    """
    konn.executescript(ESKEMA_FITX.read_text(encoding="utf-8"))
    _zutabeak_ziurtatu(konn)

    # Izenak abio bakoitzean freskatzen dira, hazi-datuak aldatzen direnean
    # lehendik dagoen datu-basea ere eguneratu dadin (adib. euskarazko izenetatik
    # ingelesezko ofizialetara). Baina EZ dira berridazten erabiltzaileak
    # katalogotik eskuz aldatu dituenean: hori gertaera batek markatzen du,
    # `azken_lamport > 0` utziz.
    konn.executemany(
        "INSERT INTO fakzioak (kodea, izena, hedapena, kolorea, arlotea) VALUES (?,?,?,?,?) "
        "ON CONFLICT(kodea) DO UPDATE SET izena = excluded.izena, "
        "hedapena = excluded.hedapena, kolorea = excluded.kolorea, "
        "arlotea = excluded.arlotea "
        "WHERE fakzioak.azken_lamport = 0",
        FAKZIOAK,
    )
    konn.executemany(
        "INSERT INTO arloteak (kodea, izena, hedapena) VALUES (?,?,?) "
        "ON CONFLICT(kodea) DO UPDATE SET izena = excluded.izena, "
        "hedapena = excluded.hedapena WHERE arloteak.azken_lamport = 0",
        ARLOTEAK,
    )
    konn.executemany(
        "INSERT INTO mertzenarioak (kodea, izena, hedapena) VALUES (?,?,?) "
        "ON CONFLICT(kodea) DO UPDATE SET izena = excluded.izena, "
        "hedapena = excluded.hedapena WHERE mertzenarioak.azken_lamport = 0",
        MERTZENARIOAK,
    )
    konn.executemany(
        "INSERT INTO leku_bereziak (kodea, izena, hedapena) VALUES (?,?,?) "
        "ON CONFLICT(kodea) DO UPDATE SET izena = excluded.izena, "
        "hedapena = excluded.hedapena WHERE leku_bereziak.azken_lamport = 0",
        LEKU_BEREZIAK,
    )
    konn.executemany(
        "INSERT INTO mapak (kodea, izena) VALUES (?,?) "
        "ON CONFLICT(kodea) DO UPDATE SET izena = excluded.izena",
        MAPAK,
    )
    konn.executemany(
        "INSERT INTO karta_sortak (kodea, izena) VALUES (?,?) "
        "ON CONFLICT(kodea) DO UPDATE SET izena = excluded.izena",
        KARTA_SORTAK,
    )
    konn.execute("INSERT OR IGNORE INTO meta (gakoa, balioa) VALUES ('lamport', '0')")


# Zutabe berriak lehendik dauden tauletan. `CREATE TABLE IF NOT EXISTS`-ek ez
# ditu zutabeak gehitzen, beraz eskema hazten denean hemen zerrendatu behar dira.
# Zerrenda hau ez da inoiz txikitzen: datu-base zaharrago batek urrats guztiak
# behar ditu.
ZUTABE_BERRIAK = [
    ("fakzioak", "arlotea", "INTEGER NOT NULL DEFAULT 0"),
    ("partida_jokalariak", "arlote_kodea", "TEXT"),
]


def _zutabeak_ziurtatu(konn: sqlite3.Connection) -> None:
    for taula, zutabea, definizioa in ZUTABE_BERRIAK:
        badaudenak = {l[1] for l in konn.execute(f"PRAGMA table_info({taula})")}
        if zutabea not in badaudenak:
            konn.execute(f"ALTER TABLE {taula} ADD COLUMN {zutabea} {definizioa}")


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
