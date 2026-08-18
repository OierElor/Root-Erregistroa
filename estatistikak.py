#!/usr/bin/env python3
"""Erregistroaren gaineko kontsultak.

Ezabatutako partidak eta jokalariak beti kanpoan uzten dira (`ezabatuta = 0`),
baina erregistroan jarraitzen dute sinkronizaziorako.
"""

import sqlite3

PARTIDA_BALIODUNAK = "p.ezabatuta = 0"


def laburpena(konn: sqlite3.Connection) -> dict:
    partidak = konn.execute(
        "SELECT COUNT(*) FROM partidak p WHERE p.ezabatuta = 0"
    ).fetchone()[0]
    jokalariak = konn.execute(
        "SELECT COUNT(*) FROM jokalariak WHERE ezabatuta = 0"
    ).fetchone()[0]
    azkena = konn.execute(
        "SELECT MAX(p.data) FROM partidak p WHERE p.ezabatuta = 0"
    ).fetchone()[0]
    gertaerak = konn.execute("SELECT COUNT(*) FROM gertaerak").fetchone()[0]
    return {
        "partidak": partidak,
        "jokalariak": jokalariak,
        "azken_partida": azkena,
        "gertaerak": gertaerak,
    }


def jokalarien_sailkapena(konn: sqlite3.Connection) -> list:
    """Jokalari bakoitzaren partidak, garaipenak eta batez besteko puntuak."""
    lerroak = konn.execute(
        """
        SELECT j.id,
               j.izena,
               j.ezizena,
               COUNT(*)                                   AS partidak,
               SUM(pj.irabazlea)                          AS garaipenak,
               ROUND(AVG(pj.puntuak), 1)                  AS batez_beste,
               MAX(pj.puntuak)                            AS puntu_gehien,
               COUNT(DISTINCT pj.fakzio_kodea)            AS fakzio_kopurua
        FROM partida_jokalariak pj
        JOIN partidak  p ON p.id = pj.partida_id
        JOIN jokalariak j ON j.id = pj.jokalari_id
        WHERE p.ezabatuta = 0 AND j.ezabatuta = 0
        GROUP BY j.id
        ORDER BY garaipenak DESC, partidak DESC, j.izena
        """
    ).fetchall()
    return [_tasarekin(dict(l), "garaipenak", "partidak") for l in lerroak]


def fakzioen_estatistikak(konn: sqlite3.Connection) -> list:
    lerroak = konn.execute(
        """
        SELECT f.kodea,
               f.izena,
               f.kolorea,
               f.hedapena,
               COUNT(*)                  AS partidak,
               SUM(pj.irabazlea)         AS garaipenak,
               ROUND(AVG(pj.puntuak), 1) AS batez_beste
        FROM partida_jokalariak pj
        JOIN partidak p ON p.id = pj.partida_id
        JOIN fakzioak f ON f.kodea = pj.fakzio_kodea
        WHERE p.ezabatuta = 0
        GROUP BY f.kodea
        ORDER BY garaipenak DESC, partidak DESC
        """
    ).fetchall()
    return [_tasarekin(dict(l), "garaipenak", "partidak") for l in lerroak]


def jokalari_fakzio_matrizea(konn: sqlite3.Connection) -> list:
    """Nork zein fakziorekin jokatzen duen ondoen."""
    lerroak = konn.execute(
        """
        SELECT j.izena AS jokalaria, f.izena AS fakzioa, f.kolorea,
               COUNT(*) AS partidak, SUM(pj.irabazlea) AS garaipenak
        FROM partida_jokalariak pj
        JOIN partidak   p ON p.id = pj.partida_id
        JOIN jokalariak j ON j.id = pj.jokalari_id
        JOIN fakzioak   f ON f.kodea = pj.fakzio_kodea
        WHERE p.ezabatuta = 0 AND j.ezabatuta = 0
        GROUP BY j.id, f.kodea
        HAVING partidak > 0
        ORDER BY j.izena, garaipenak DESC
        """
    ).fetchall()
    return [_tasarekin(dict(l), "garaipenak", "partidak") for l in lerroak]


def bilakaera(konn: sqlite3.Connection) -> list:
    """Hilabeteko partida kopurua, jardueraren bilakaera ikusteko."""
    lerroak = konn.execute(
        """
        SELECT substr(p.data, 1, 7) AS hilabetea, COUNT(*) AS partidak
        FROM partidak p WHERE p.ezabatuta = 0
        GROUP BY hilabetea ORDER BY hilabetea
        """
    ).fetchall()
    return [dict(l) for l in lerroak]


def azken_partidak(konn: sqlite3.Connection, muga: int = 50, iragazkia: dict | None = None) -> list:
    """Partidak, bakoitzaren parte-hartzaileekin.

    Kontsulta guztiak parametrizatuta daude; iragazkiak ere bai.
    """
    iragazkia = iragazkia or {}
    baldintzak = ["p.ezabatuta = 0"]
    parametroak: list = []

    if iragazkia.get("jokalari_id"):
        baldintzak.append(
            "EXISTS (SELECT 1 FROM partida_jokalariak x "
            "WHERE x.partida_id = p.id AND x.jokalari_id = ?)"
        )
        parametroak.append(iragazkia["jokalari_id"])
    if iragazkia.get("fakzio_kodea"):
        baldintzak.append(
            "EXISTS (SELECT 1 FROM partida_jokalariak x "
            "WHERE x.partida_id = p.id AND x.fakzio_kodea = ?)"
        )
        parametroak.append(iragazkia["fakzio_kodea"])
    if iragazkia.get("mapa_kodea"):
        baldintzak.append("p.mapa_kodea = ?")
        parametroak.append(iragazkia["mapa_kodea"])

    muga = max(1, min(int(muga), 500))
    partidak = konn.execute(
        f"SELECT * FROM partidak p WHERE {' AND '.join(baldintzak)} "
        f"ORDER BY p.data DESC, p.rowid DESC LIMIT ?",
        (*parametroak, muga),
    ).fetchall()

    emaitza = []
    for p in partidak:
        parte_hartzaileak = konn.execute(
            """
            SELECT pj.*, j.izena AS jokalari_izena, f.izena AS fakzio_izena,
                   f.kolorea AS fakzio_kolorea, a.izena AS arlote_izena
            FROM partida_jokalariak pj
            LEFT JOIN jokalariak j ON j.id = pj.jokalari_id
            LEFT JOIN fakzioak   f ON f.kodea = pj.fakzio_kodea
            LEFT JOIN arloteak   a ON a.kodea = pj.arlote_kodea
            WHERE pj.partida_id = ?
            ORDER BY pj.irabazlea DESC, pj.puntuak DESC
            """,
            (p["id"],),
        ).fetchall()
        partida = dict(p)
        partida["jokalariak"] = [dict(x) for x in parte_hartzaileak]
        partida["mertzenarioak"] = [
            dict(x) for x in konn.execute(
                "SELECT pm.mertzenario_kodea AS kodea, m.izena "
                "FROM partida_mertzenarioak pm "
                "LEFT JOIN mertzenarioak m ON m.kodea = pm.mertzenario_kodea "
                "WHERE pm.partida_id = ? ORDER BY m.izena",
                (p["id"],),
            )
        ]
        partida["leku_bereziak"] = [
            dict(x) for x in konn.execute(
                "SELECT pl.leku_kodea AS kodea, l.izena "
                "FROM partida_lekuak pl "
                "LEFT JOIN leku_bereziak l ON l.kodea = pl.leku_kodea "
                "WHERE pl.partida_id = ? ORDER BY l.izena",
                (p["id"],),
            )
        ]
        emaitza.append(partida)
    return emaitza


def osagarrien_erabilera(konn: sqlite3.Connection) -> dict:
    """Zein mertzenario eta leku berezi erabiltzen diren gehien."""
    def kontatu(lotura_taula, kode_zutabea, katalogoa):
        return [
            dict(l) for l in konn.execute(
                f"""
                SELECT k.kodea, k.izena, k.hedapena, COUNT(*) AS partidak
                FROM {lotura_taula} lt
                JOIN partidak p ON p.id = lt.partida_id
                JOIN {katalogoa} k ON k.kodea = lt.{kode_zutabea}
                WHERE p.ezabatuta = 0
                GROUP BY k.kodea
                ORDER BY partidak DESC, k.izena
                """
            )
        ]

    return {
        "mertzenarioak": kontatu("partida_mertzenarioak", "mertzenario_kodea", "mertzenarioak"),
        "leku_bereziak": kontatu("partida_lekuak", "leku_kodea", "leku_bereziak"),
    }


def arloteen_estatistikak(konn: sqlite3.Connection) -> list:
    """Vagabond pertsonaia bakoitzarekin nola joan den."""
    lerroak = konn.execute(
        """
        SELECT a.kodea, a.izena, a.hedapena,
               COUNT(*)                  AS partidak,
               SUM(pj.irabazlea)         AS garaipenak,
               ROUND(AVG(pj.puntuak), 1) AS batez_beste
        FROM partida_jokalariak pj
        JOIN partidak p ON p.id = pj.partida_id
        JOIN arloteak a ON a.kodea = pj.arlote_kodea
        WHERE p.ezabatuta = 0
        GROUP BY a.kodea
        ORDER BY garaipenak DESC, partidak DESC, a.izena
        """
    ).fetchall()
    return [_tasarekin(dict(l), "garaipenak", "partidak") for l in lerroak]


def _tasarekin(lerroa: dict, zenbakitzailea: str, izendatzailea: str) -> dict:
    guztira = lerroa.get(izendatzailea) or 0
    onak = lerroa.get(zenbakitzailea) or 0
    lerroa["tasa"] = round(100 * onak / guztira, 1) if guztira else 0.0
    lerroa[zenbakitzailea] = onak
    return lerroa
