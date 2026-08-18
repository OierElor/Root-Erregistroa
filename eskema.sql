-- Root Erregistroa — datu-basearen eskema
--
-- Bi geruza daude:
--   1) `gertaerak`: soilik gehitzeko erregistroa. HAU DA EGIA ITURRIA.
--   2) proiekzio-taulak (jokalariak, partidak...): gertaeretatik eraikitzen dira,
--      kontsultak azkarrak izan daitezen. Beti berreraiki daitezke.

CREATE TABLE IF NOT EXISTS meta (
    gakoa  TEXT PRIMARY KEY,
    balioa TEXT NOT NULL
);

-- ─── 1. geruza: gertaera-erregistroa ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gertaerak (
    gertaera_id TEXT PRIMARY KEY,          -- UUIDv4, mundu mailan bakarra
    gailu_id    TEXT NOT NULL,             -- nork sortu zuen
    lamport     INTEGER NOT NULL,          -- erloju logikoa (ez du orduarekin zerikusirik)
    unix_ordua  INTEGER NOT NULL,          -- informaziorako soilik
    mota        TEXT NOT NULL,
    entitate_id TEXT NOT NULL,
    karga       TEXT NOT NULL,             -- JSON
    sinadura    TEXT,                      -- ERRESERBATUTA: Ed25519 etorkizunean
    jaso_ordua  INTEGER NOT NULL
);

-- Ordena deterministikoa: gailu guztiek berdin ordenatzen dituzte gertaerak.
CREATE INDEX IF NOT EXISTS idx_gertaerak_ordena
    ON gertaerak (lamport, gailu_id, gertaera_id);
CREATE INDEX IF NOT EXISTS idx_gertaerak_entitatea
    ON gertaerak (entitate_id);

-- ─── 2. geruza: proiekzioak ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jokalariak (
    id            TEXT PRIMARY KEY,
    izena         TEXT NOT NULL,
    ezizena       TEXT,
    ezabatuta     INTEGER NOT NULL DEFAULT 0,
    azken_lamport INTEGER NOT NULL DEFAULT 0,
    azken_gailua  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS partidak (
    id            TEXT PRIMARY KEY,
    data          TEXT NOT NULL,           -- YYYY-MM-DD
    mapa_kodea    TEXT,
    karta_sorta   TEXT,
    oharrak       TEXT,
    ezabatuta     INTEGER NOT NULL DEFAULT 0,
    azken_lamport INTEGER NOT NULL DEFAULT 0,
    azken_gailua  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_partidak_data ON partidak (data DESC);

-- Partida bat bere osotasunean ordezkatzen da gertaera bakoitzean, beraz
-- lerro hauek partidaren mendekoak dira erabat.
CREATE TABLE IF NOT EXISTS partida_jokalariak (
    partida_id     TEXT NOT NULL REFERENCES partidak(id) ON DELETE CASCADE,
    jokalari_id    TEXT NOT NULL,
    fakzio_kodea   TEXT,
    puntuak        INTEGER,
    hasiera_ordena INTEGER,
    irabazlea      INTEGER NOT NULL DEFAULT 0,
    garaipen_mota  TEXT,                   -- puntuak | nagusitasuna | koalizioa | berezia
    koalizio_kidea TEXT,
    PRIMARY KEY (partida_id, jokalari_id)
);

CREATE INDEX IF NOT EXISTS idx_pj_jokalaria ON partida_jokalariak (jokalari_id);
CREATE INDEX IF NOT EXISTS idx_pj_fakzioa   ON partida_jokalariak (fakzio_kodea);

-- Partidan erabilitako mertzenarioak eta leku bereziak. Jokalariak bezala,
-- partidaren mendekoak dira erabat: partida gordetzean osorik ordezkatzen dira.
CREATE TABLE IF NOT EXISTS partida_mertzenarioak (
    partida_id        TEXT NOT NULL REFERENCES partidak(id) ON DELETE CASCADE,
    mertzenario_kodea TEXT NOT NULL,
    PRIMARY KEY (partida_id, mertzenario_kodea)
);

CREATE TABLE IF NOT EXISTS partida_lekuak (
    partida_id TEXT NOT NULL REFERENCES partidak(id) ON DELETE CASCADE,
    leku_kodea TEXT NOT NULL,
    PRIMARY KEY (partida_id, leku_kodea)
);

CREATE INDEX IF NOT EXISTS idx_pm_mertzenarioa ON partida_mertzenarioak (mertzenario_kodea);
CREATE INDEX IF NOT EXISTS idx_pl_lekua        ON partida_lekuak (leku_kodea);

-- ─── Katalogoak ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fakzioak (
    kodea         TEXT PRIMARY KEY,
    izena         TEXT NOT NULL,
    hedapena      TEXT,
    kolorea       TEXT,
    ezabatuta     INTEGER NOT NULL DEFAULT 0,
    azken_lamport INTEGER NOT NULL DEFAULT 0,
    azken_gailua  TEXT NOT NULL DEFAULT ''
);

-- Mertzenarioak (Hirelings) eta leku bereziak (Landmarks): fakzioen egitura bera,
-- katalogotik editatu ahal izateko (hedapen berriak, izen zuzenketak).
CREATE TABLE IF NOT EXISTS mertzenarioak (
    kodea         TEXT PRIMARY KEY,
    izena         TEXT NOT NULL,
    hedapena      TEXT,
    ezabatuta     INTEGER NOT NULL DEFAULT 0,
    azken_lamport INTEGER NOT NULL DEFAULT 0,
    azken_gailua  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS leku_bereziak (
    kodea         TEXT PRIMARY KEY,
    izena         TEXT NOT NULL,
    hedapena      TEXT,
    ezabatuta     INTEGER NOT NULL DEFAULT 0,
    azken_lamport INTEGER NOT NULL DEFAULT 0,
    azken_gailua  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS mapak (
    kodea TEXT PRIMARY KEY,
    izena TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS karta_sortak (
    kodea TEXT PRIMARY KEY,
    izena TEXT NOT NULL
);

-- ─── Sinkronizazioa ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gailuak (
    gailu_id      TEXT PRIMARY KEY,
    izena         TEXT,
    azken_ikusia  INTEGER,
    azken_lamport INTEGER NOT NULL DEFAULT 0
);

-- Errepikapenen (replay) aurkako babesa: fardel baten nonce-a behin bakarrik.
CREATE TABLE IF NOT EXISTS ikusitako_nonceak (
    nonce TEXT PRIMARY KEY,
    noiz  INTEGER NOT NULL
);
