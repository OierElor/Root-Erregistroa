#!/usr/bin/env python3
"""Gertaera-erregistroa: sortu, balidatu, bateratu eta proiektatu.

Aplikazio osoaren muina. Datuak ez dira inoiz zuzenean aldatzen: gertaera bat
sortzen da, eta gertaeratik eratortzen da egoera. Horri esker bi gailuren
erregistroak bateratzea gertaeren bilketa hutsa da, gatazkak konpondu beharrik
gabe.

Oinarrizko arauak
-----------------
* Gertaera bakoitzak `gertaera_id` bakarra du → bikoiztuak berez baztertzen dira.
* Ordena deterministikoa: (lamport, gailu_id, gertaera_id). Gailu guztiek ordena
  BERA kalkulatzen dute, erlojuak desdoituta egonda ere.
* Entitate baten egoera bere gertaerak ordenan aplikatuz lortzen da. Gertaera
  berri bat sartzean, entitate hori bakarrik berreraikitzen da; emaitza berdina
  da beti, gertaerak zein ordenatan iritsi diren axola gabe.
"""

import hashlib
import json
import re
import sqlite3
import time
import unicodedata
import uuid

import db
import konfig

# ─── Balidazioa ─────────────────────────────────────────────────────────────
# Erregistro banatu batean gertaerak KANPOTIK datoz. Aplikatu aurretik guztiak
# balidatzen dira: eremu ezezagunak, mota okerrak eta neurriz kanpoko balioak
# baztertu egiten dira, datu-basera iritsi baino lehen.

ID_ERED = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
DATA_ERED = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KODE_ERED = re.compile(r"^[a-z0-9_-]{1,32}$")

GEHIENEZ_JOKALARI = 12
GEHIENEZ_PUNTU = 999
GEHIENEZ_LAMPORT = 2**53


class GertaeraErrorea(ValueError):
    """Gertaera bat baliogabea da eta ez da aplikatuko."""


def _testua(balioa, izena, gehienez, hutsa_onartu=False):
    if balioa is None:
        if hutsa_onartu:
            return None
        raise GertaeraErrorea(f"{izena}: falta da")
    if not isinstance(balioa, str):
        raise GertaeraErrorea(f"{izena}: testua izan behar du")
    balioa = balioa.strip()
    if not balioa and not hutsa_onartu:
        raise GertaeraErrorea(f"{izena}: hutsik dago")
    if len(balioa) > gehienez:
        raise GertaeraErrorea(f"{izena}: luzeegia ({len(balioa)} > {gehienez})")
    return balioa


def _osokoa(balioa, izena, gutxienez, gehienez, hutsa_onartu=False):
    if balioa is None and hutsa_onartu:
        return None
    if isinstance(balioa, bool) or not isinstance(balioa, int):
        raise GertaeraErrorea(f"{izena}: zenbaki osoa izan behar du")
    if not gutxienez <= balioa <= gehienez:
        raise GertaeraErrorea(f"{izena}: {gutxienez}..{gehienez} tartetik kanpo")
    return balioa


def _id(balioa, izena):
    balioa = _testua(balioa, izena, 64)
    if not ID_ERED.match(balioa):
        raise GertaeraErrorea(f"{izena}: identifikatzaile baliogabea")
    return balioa


def _kodea(balioa, izena, hutsa_onartu=False):
    if balioa in (None, "") and hutsa_onartu:
        return None
    balioa = _testua(balioa, izena, 32)
    if not KODE_ERED.match(balioa):
        raise GertaeraErrorea(f"{izena}: kode baliogabea")
    return balioa


def _balidatu_jokalaria_gorde(karga: dict) -> dict:
    return {
        "id": _id(karga.get("id"), "jokalaria.id"),
        "izena": _testua(karga.get("izena"), "jokalaria.izena", 80),
        "ezizena": _testua(karga.get("ezizena"), "jokalaria.ezizena", 40, True),
    }


def _balidatu_partida_gorde(karga: dict) -> dict:
    data = _testua(karga.get("data"), "partida.data", 10)
    if not DATA_ERED.match(data):
        raise GertaeraErrorea("partida.data: UUUU-HH-EE formatua behar du")

    zerrenda = karga.get("jokalariak")
    if not isinstance(zerrenda, list) or not zerrenda:
        raise GertaeraErrorea("partida.jokalariak: zerrenda ez-hutsa behar du")
    if len(zerrenda) > GEHIENEZ_JOKALARI:
        raise GertaeraErrorea("partida.jokalariak: jokalari gehiegi")

    parte_hartzaileak = []
    ikusitakoak = set()
    for i, sarrera in enumerate(zerrenda):
        if not isinstance(sarrera, dict):
            raise GertaeraErrorea(f"partida.jokalariak[{i}]: objektua behar du")
        jokalari_id = _id(sarrera.get("jokalari_id"), f"jokalariak[{i}].jokalari_id")
        if jokalari_id in ikusitakoak:
            raise GertaeraErrorea("partida.jokalariak: jokalari bera errepikatuta")
        ikusitakoak.add(jokalari_id)

        mota = sarrera.get("garaipen_mota")
        if mota not in (None, "", *db.GARAIPEN_MOTAK):
            raise GertaeraErrorea(f"jokalariak[{i}].garaipen_mota: ezezaguna")

        parte_hartzaileak.append(
            {
                "jokalari_id": jokalari_id,
                "fakzio_kodea": _kodea(
                    sarrera.get("fakzio_kodea"), f"jokalariak[{i}].fakzio_kodea", True
                ),
                "puntuak": _osokoa(
                    sarrera.get("puntuak"), f"jokalariak[{i}].puntuak",
                    0, GEHIENEZ_PUNTU, True,
                ),
                "hasiera_ordena": _osokoa(
                    sarrera.get("hasiera_ordena"), f"jokalariak[{i}].hasiera_ordena",
                    1, GEHIENEZ_JOKALARI, True,
                ),
                "irabazlea": 1 if sarrera.get("irabazlea") else 0,
                "garaipen_mota": mota or None,
                "koalizio_kidea": _kodea(
                    sarrera.get("koalizio_kidea"), f"jokalariak[{i}].koalizio_kidea", True
                ),
            }
        )

    return {
        "id": _id(karga.get("id"), "partida.id"),
        "data": data,
        "mapa_kodea": _kodea(karga.get("mapa_kodea"), "partida.mapa_kodea", True),
        "karta_sorta": _kodea(karga.get("karta_sorta"), "partida.karta_sorta", True),
        "oharrak": _testua(karga.get("oharrak"), "partida.oharrak", 2000, True),
        "jokalariak": parte_hartzaileak,
    }


def _balidatu_fakzioa_gorde(karga: dict) -> dict:
    return {
        "kodea": _kodea(karga.get("kodea"), "fakzioa.kodea"),
        "izena": _testua(karga.get("izena"), "fakzioa.izena", 60),
        "hedapena": _testua(karga.get("hedapena"), "fakzioa.hedapena", 60, True),
        "kolorea": _testua(karga.get("kolorea"), "fakzioa.kolorea", 9, True),
    }


def _balidatu_ezabatu(eremua):
    def balidatzailea(karga: dict) -> dict:
        return {eremua: _id(karga.get(eremua), f"{eremua}")}

    return balidatzailea


# mota → (balidatzailea, entitatearen identifikatzailea kargan)
MOTAK = {
    "jokalaria_gorde":   (_balidatu_jokalaria_gorde, "id"),
    "jokalaria_ezabatu": (_balidatu_ezabatu("id"), "id"),
    "partida_gorde":     (_balidatu_partida_gorde, "id"),
    "partida_ezabatu":   (_balidatu_ezabatu("id"), "id"),
    "fakzioa_gorde":     (_balidatu_fakzioa_gorde, "kodea"),
    "fakzioa_ezabatu":   (_balidatu_ezabatu("kodea"), "kodea"),
}


def karga_balidatu(mota: str, karga: dict) -> dict:
    if mota not in MOTAK:
        raise GertaeraErrorea(f"gertaera mota ezezaguna: {mota!r}")
    if not isinstance(karga, dict):
        raise GertaeraErrorea("karga: objektua izan behar du")
    balidatzailea, _ = MOTAK[mota]
    return balidatzailea(karga)


def gertaera_balidatu(gertaera: dict) -> dict:
    """Kanpotik jasotako gertaera oso bat balidatu (gutun-azala + karga)."""
    if not isinstance(gertaera, dict):
        raise GertaeraErrorea("gertaera: objektua izan behar du")

    mota = _testua(gertaera.get("mota"), "mota", 40)
    karga = karga_balidatu(mota, gertaera.get("karga"))
    _, id_eremua = MOTAK[mota]

    entitate_id = _id(gertaera.get("entitate_id"), "entitate_id")
    if entitate_id != karga[id_eremua]:
        raise GertaeraErrorea("entitate_id ez dator bat kargarekin")

    return {
        "gertaera_id": _id(gertaera.get("gertaera_id"), "gertaera_id"),
        "gailu_id": _id(gertaera.get("gailu_id"), "gailu_id"),
        "lamport": _osokoa(gertaera.get("lamport"), "lamport", 1, GEHIENEZ_LAMPORT),
        "unix_ordua": _osokoa(gertaera.get("unix_ordua"), "unix_ordua", 0, 2**40),
        "mota": mota,
        "entitate_id": entitate_id,
        "karga": karga,
        "sinadura": _testua(gertaera.get("sinadura"), "sinadura", 200, True),
    }


# ─── Identitate deterministak ───────────────────────────────────────────────


def jokalari_id_izenetik(izena: str) -> str:
    """Jokalari baten identifikatzailea bere izenetik eratorri.

    Zergatik ez ausazko UUID bat? Bi ordenagailutan "Oier" idazten bada elkarren
    berririk izan gabe (ohikoena: bakoitzak bere partidak sartzen ditu), ausazko
    identifikatzaileek bi jokalari sortuko lituzkete eta sinkronizatzean
    estatistikak zatituta geldituko lirateke. Izenetik eratortzean, bi gailuek
    identifikatzaile BERA kalkulatzen dute eta bat egiten dute berez.

    Izena aldatzeak ez du identifikatzailea aldatzen: aldaketa entitate beraren
    gaineko gertaera bat da.
    """
    normalizatua = unicodedata.normalize("NFC", " ".join((izena or "").split())).casefold()
    return "j" + hashlib.blake2b(
        normalizatua.encode("utf-8"), digest_size=12, person=b"root-jokalari"
    ).hexdigest()


# ─── Erloju logikoa ─────────────────────────────────────────────────────────


def _lamport_hurrengoa(konn: sqlite3.Connection) -> int:
    oraingoa = int(db.meta_irakurri(konn, "lamport", "0") or 0)
    hurrengoa = oraingoa + 1
    db.meta_idatzi(konn, "lamport", hurrengoa)
    return hurrengoa


def _lamport_aurreratu(konn: sqlite3.Connection, ikusitakoa: int) -> None:
    """Beste gailu baten gertaera ikustean, gure erlojua haren gainetik jarri."""
    oraingoa = int(db.meta_irakurri(konn, "lamport", "0") or 0)
    if ikusitakoa > oraingoa:
        db.meta_idatzi(konn, "lamport", ikusitakoa)


# ─── Proiekzioa ─────────────────────────────────────────────────────────────


def _entitatearen_gertaerak(konn: sqlite3.Connection, entitate_id: str):
    return konn.execute(
        "SELECT mota, karga, lamport, gailu_id FROM gertaerak "
        "WHERE entitate_id = ? ORDER BY lamport, gailu_id, gertaera_id",
        (entitate_id,),
    ).fetchall()


def entitatea_berreraiki(konn: sqlite3.Connection, entitate_id: str) -> None:
    """Entitate baten proiekzioa bere gertaera guztietatik berreraiki.

    Gertaera bat gehitu ondoren deitzen da. Zerotik berreraikitzen denez,
    emaitza ez dago gertaerak zein ordenatan iritsi diren mende: beranduago
    iristen den gertaera zahar batek ez du egoera hondatzen.
    """
    lerroak = _entitatearen_gertaerak(konn, entitate_id)
    if not lerroak:
        return

    konn.execute("DELETE FROM partida_jokalariak WHERE partida_id = ?", (entitate_id,))

    egoera = None
    mota_azkena = None
    ezabatuta = 0
    for lerroa in lerroak:
        mota = lerroa["mota"]
        karga = json.loads(lerroa["karga"])
        azken_lamport, azken_gailua = lerroa["lamport"], lerroa["gailu_id"]
        if mota.endswith("_ezabatu"):
            ezabatuta = 1
        else:
            egoera = karga
            ezabatuta = 0
            mota_azkena = mota

    if egoera is None:
        # Ezabatze-gertaera bat iritsi da sorrera baino lehen (birbidalketa
        # baten ondorioz, adibidez). Sorrera iristean berreraikiko da berriro.
        return

    if mota_azkena == "jokalaria_gorde":
        konn.execute(
            "INSERT INTO jokalariak (id, izena, ezizena, ezabatuta, azken_lamport, azken_gailua) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
            "izena=excluded.izena, ezizena=excluded.ezizena, ezabatuta=excluded.ezabatuta, "
            "azken_lamport=excluded.azken_lamport, azken_gailua=excluded.azken_gailua",
            (egoera["id"], egoera["izena"], egoera["ezizena"], ezabatuta,
             azken_lamport, azken_gailua),
        )
    elif mota_azkena == "partida_gorde":
        konn.execute(
            "INSERT INTO partidak (id, data, mapa_kodea, karta_sorta, oharrak, "
            "ezabatuta, azken_lamport, azken_gailua) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET data=excluded.data, mapa_kodea=excluded.mapa_kodea, "
            "karta_sorta=excluded.karta_sorta, oharrak=excluded.oharrak, "
            "ezabatuta=excluded.ezabatuta, azken_lamport=excluded.azken_lamport, "
            "azken_gailua=excluded.azken_gailua",
            (egoera["id"], egoera["data"], egoera["mapa_kodea"], egoera["karta_sorta"],
             egoera["oharrak"], ezabatuta, azken_lamport, azken_gailua),
        )
        konn.executemany(
            "INSERT INTO partida_jokalariak (partida_id, jokalari_id, fakzio_kodea, "
            "puntuak, hasiera_ordena, irabazlea, garaipen_mota, koalizio_kidea) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                (egoera["id"], p["jokalari_id"], p["fakzio_kodea"], p["puntuak"],
                 p["hasiera_ordena"], p["irabazlea"], p["garaipen_mota"],
                 p["koalizio_kidea"])
                for p in egoera["jokalariak"]
            ],
        )
    elif mota_azkena == "fakzioa_gorde":
        konn.execute(
            "INSERT INTO fakzioak (kodea, izena, hedapena, kolorea, ezabatuta, "
            "azken_lamport, azken_gailua) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(kodea) DO UPDATE SET izena=excluded.izena, "
            "hedapena=excluded.hedapena, kolorea=excluded.kolorea, "
            "ezabatuta=excluded.ezabatuta, azken_lamport=excluded.azken_lamport, "
            "azken_gailua=excluded.azken_gailua",
            (egoera["kodea"], egoera["izena"], egoera["hedapena"], egoera["kolorea"],
             ezabatuta, azken_lamport, azken_gailua),
        )


def birsortu(konn: sqlite3.Connection) -> int:
    """Proiekzio guztiak zerotik berreraiki gertaera-erregistrotik.

    Ez da normalean beharrezkoa (gehitzeak berak eguneratzen ditu proiekzioak),
    baina konponketarako eta testetarako funtsezkoa da: emaitzak berdina izan
    behar du beti.
    """
    konn.execute("DELETE FROM partida_jokalariak")
    konn.execute("DELETE FROM partidak")
    konn.execute("DELETE FROM jokalariak")
    konn.execute("UPDATE fakzioak SET ezabatuta = 0, azken_lamport = 0, azken_gailua = ''")

    idak = [
        l[0] for l in konn.execute("SELECT DISTINCT entitate_id FROM gertaerak")
    ]
    for entitate_id in idak:
        entitatea_berreraiki(konn, entitate_id)
    konn.commit()
    return len(idak)


# ─── Sortzea eta bateratzea ─────────────────────────────────────────────────


def gertaera_berria(konn: sqlite3.Connection, mota: str, karga: dict) -> dict:
    """Gailu honetan gertaera berri bat sortu, gorde eta aplikatu."""
    karga = karga_balidatu(mota, karga)
    _, id_eremua = MOTAK[mota]

    gertaera = {
        "gertaera_id": uuid.uuid4().hex,
        "gailu_id": konfig.gailu_id(),
        "lamport": _lamport_hurrengoa(konn),
        "unix_ordua": int(time.time()),
        "mota": mota,
        "entitate_id": karga[id_eremua],
        "karga": karga,
        "sinadura": None,
    }
    _txertatu(konn, gertaera)
    entitatea_berreraiki(konn, gertaera["entitate_id"])
    konn.commit()
    return gertaera


def _txertatu(konn: sqlite3.Connection, gertaera: dict) -> bool:
    """Gertaera bat erregistroan gorde. False bikoiztua bada."""
    kurtsorea = konn.execute(
        "INSERT OR IGNORE INTO gertaerak (gertaera_id, gailu_id, lamport, unix_ordua, "
        "mota, entitate_id, karga, sinadura, jaso_ordua) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            gertaera["gertaera_id"], gertaera["gailu_id"], gertaera["lamport"],
            gertaera["unix_ordua"], gertaera["mota"], gertaera["entitate_id"],
            json.dumps(gertaera["karga"], ensure_ascii=False, sort_keys=True),
            gertaera.get("sinadura"), int(time.time()),
        ),
    )
    return kurtsorea.rowcount > 0


def gehitu(konn: sqlite3.Connection, kanpokoak: list) -> dict:
    """Kanpoko gertaerak bateratu. Idempotentea eta ordenarekiko independentea.

    Gertaera baliogabeak baztertu egiten dira, gainerakoak onartuz: gailu
    zaharrago batek bidalitako gertaera ezezagun batek ez du sinkronizazio osoa
    hondatzen.
    """
    berriak, baztertuak, ukituak = 0, [], set()

    for gordina in kanpokoak:
        try:
            gertaera = gertaera_balidatu(gordina)
        except GertaeraErrorea as e:
            baztertuak.append(str(e))
            continue
        if _txertatu(konn, gertaera):
            berriak += 1
            ukituak.add(gertaera["entitate_id"])
            _lamport_aurreratu(konn, gertaera["lamport"])
            konn.execute(
                "INSERT INTO gailuak (gailu_id, azken_ikusia, azken_lamport) "
                "VALUES (?,?,?) ON CONFLICT(gailu_id) DO UPDATE SET "
                "azken_ikusia = excluded.azken_ikusia, "
                "azken_lamport = MAX(azken_lamport, excluded.azken_lamport)",
                (gertaera["gailu_id"], int(time.time()), gertaera["lamport"]),
            )

    for entitate_id in ukituak:
        entitatea_berreraiki(konn, entitate_id)
    konn.commit()

    return {"berriak": berriak, "baztertuak": baztertuak, "entitateak": len(ukituak)}


# ─── Sinkronizaziorako laguntzaileak ────────────────────────────────────────


def id_guztiak(konn: sqlite3.Connection) -> list:
    return [l[0] for l in konn.execute("SELECT gertaera_id FROM gertaerak")]


def esportatu(konn: sqlite3.Connection, kanpo_idak=None) -> list:
    """Gertaerak esportatu. `kanpo_idak` emanez gero, horiek EZ dira bidaltzen.

    Horrela beste gailuak dagoeneko dituenak ez dira sarean barrena bidaltzen.
    """
    kanpo_idak = set(kanpo_idak or ())
    emaitza = []
    for lerroa in konn.execute(
        "SELECT * FROM gertaerak ORDER BY lamport, gailu_id, gertaera_id"
    ):
        if lerroa["gertaera_id"] in kanpo_idak:
            continue
        emaitza.append(
            {
                "gertaera_id": lerroa["gertaera_id"],
                "gailu_id": lerroa["gailu_id"],
                "lamport": lerroa["lamport"],
                "unix_ordua": lerroa["unix_ordua"],
                "mota": lerroa["mota"],
                "entitate_id": lerroa["entitate_id"],
                "karga": json.loads(lerroa["karga"]),
                "sinadura": lerroa["sinadura"],
            }
        )
    return emaitza


def egoeraren_hatz_marka(konn: sqlite3.Connection) -> str:
    """Erregistroaren laburpen laburra: bi gailuk berdina badute, sinkronizatuta daude."""
    import hashlib

    hasher = hashlib.blake2b(digest_size=16)
    for lerroa in konn.execute("SELECT gertaera_id FROM gertaerak ORDER BY gertaera_id"):
        hasher.update(lerroa[0].encode())
    return hasher.hexdigest()
