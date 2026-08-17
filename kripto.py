#!/usr/bin/env python3
"""`.rootsync` fardela: zifratzea, osotasuna eta konpresioa.

Formatu bakar bat hiru gauzatarako:
  * LAN bidezko sinkronizazioa,
  * fitxategi bidezko trukea (USB, posta, hodeia),
  * kanpoko babeskopia zifratuak.

Egitura::

    "ROOTSYNC1" | goiburu_luzera (4 byte) | goiburua (JSON) | gorputz zifratua

Goiburua testu lauan doa (deszifratu aurretik jakin behar da zein taldetarako
den), baina AEAD-aren datu gehigarri (AAD) gisa erabiltzen da: bertan byte bat
aldatzeak deszifratzea hondatzen du. Gorputza ChaCha20-Poly1305-ekin zifratuta
dago; Poly1305 etiketak edozein manipulazio detektatzen du.

Zifratzerik gabe ez legoke datu-osotasunik: sarean dabilen fardel bat edonork
alda lezake bestela.
"""

import hashlib
import json
import os
import secrets
import struct
import time
import zlib

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

MAGIA = b"ROOTSYNC1"
BERTSIOA = 1
GATZ_LUZERA = 16
NONCE_LUZERA = 12

# scrypt parametroak: ~134 MB memoria eta ~1 s. Pasaesaldi ahul bat indarrez
# asmatzea izugarri garestitzen du. Eratorritako gakoa cachean gordetzen denez,
# behin bakarrik ordaintzen da kostua (taldea sortu/elkartzean).
KDF_N = 2 ** int(os.environ.get("ROOT_KDF_N", "17"))  # ROOT_KDF_N testetarako soilik
KDF_R, KDF_P = 8, 1
KDF_MAXMEM = 256 * 1024 * 1024

# Mugak: fardel gaizto batek memoria agortu edo prozesua blokeatu ez dezan.
GEHIENEZ_FARDELA = 64 * 1024 * 1024
GEHIENEZ_GOIBURUA = 8 * 1024
GEHIENEZ_DESKONPRIMATUTA = 256 * 1024 * 1024
DENBORA_LEIHOA = 600  # ±10 minutu sinkronizazio-fardeletan

GUTXIENEZ_PASAESALDIA = 8


class KriptoErrorea(Exception):
    """Fardela ezin da ireki: gako okerra, manipulatua edo hondatua."""


# ─── Gakoak ─────────────────────────────────────────────────────────────────


def gatz_berria() -> bytes:
    return secrets.token_bytes(GATZ_LUZERA)


def gakoa_eratorri(pasaesaldia: str, gatza: bytes) -> bytes:
    """Pasaesalditik 32 byteko gakoa eratorri (scrypt).

    Gailu guztiek gatz bera erabiltzen dute (taldearen konfigurazioan doa),
    beraz denek gako bera lortzen dute pasaesaldi beretik.
    """
    if not isinstance(pasaesaldia, str) or len(pasaesaldia) < GUTXIENEZ_PASAESALDIA:
        raise KriptoErrorea(
            f"Pasaesaldiak gutxienez {GUTXIENEZ_PASAESALDIA} karaktere behar ditu"
        )
    return hashlib.scrypt(
        pasaesaldia.encode("utf-8"),
        salt=gatza,
        n=KDF_N,
        r=KDF_R,
        p=KDF_P,
        dklen=32,
        maxmem=KDF_MAXMEM,
    )


def talde_marka(gakoa: bytes) -> str:
    """Taldearen marka publikoa: gakoaren hash-a, EZ gakoa.

    Sarean iragartzen da, talde bereko gailuak elkar ezagutzeko. Hemendik ezin
    da gakoa berreskuratu.
    """
    return hashlib.blake2b(gakoa, digest_size=16, person=b"root-taldea").hexdigest()


# ─── Fardela ────────────────────────────────────────────────────────────────


def fardela_sortu(gakoa: bytes, edukia: dict, gailu_id: str, mota: str = "sync") -> bytes:
    goiburua = {
        "bertsioa": BERTSIOA,
        "mota": mota,
        "nonce": secrets.token_bytes(NONCE_LUZERA).hex(),
        "talde_marka": talde_marka(gakoa),
        "gailu_id": gailu_id,
        "sortze_ordua": int(time.time()),
    }
    goiburu_byteak = json.dumps(goiburua, sort_keys=True).encode("utf-8")
    aurrizkia = MAGIA + struct.pack(">I", len(goiburu_byteak)) + goiburu_byteak

    gordina = json.dumps(edukia, ensure_ascii=False).encode("utf-8")
    konprimatua = zlib.compress(gordina, 6)
    zifratua = ChaCha20Poly1305(gakoa).encrypt(
        bytes.fromhex(goiburua["nonce"]), konprimatua, aurrizkia
    )
    return aurrizkia + zifratua


def goiburua_irakurri(fardela: bytes) -> dict:
    """Goiburua irakurri deszifratu gabe (zein taldetakoa den jakiteko)."""
    if len(fardela) > GEHIENEZ_FARDELA:
        raise KriptoErrorea("Fardela handiegia da")
    if not fardela.startswith(MAGIA):
        raise KriptoErrorea("Ez da Root Erregistroa fitxategi bat")
    hasiera = len(MAGIA)
    if len(fardela) < hasiera + 4:
        raise KriptoErrorea("Fardel hondatua")
    luzera = struct.unpack(">I", fardela[hasiera:hasiera + 4])[0]
    if luzera > GEHIENEZ_GOIBURUA or len(fardela) < hasiera + 4 + luzera:
        raise KriptoErrorea("Goiburu baliogabea")
    try:
        goiburua = json.loads(fardela[hasiera + 4:hasiera + 4 + luzera])
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise KriptoErrorea("Goiburua ezin da irakurri") from e
    if not isinstance(goiburua, dict) or goiburua.get("bertsioa") != BERTSIOA:
        raise KriptoErrorea("Formatu bertsio ezezaguna")
    return goiburua


def fardela_ireki(gakoa: bytes, fardela: bytes, denbora_egiaztatu: bool = True) -> tuple:
    """Fardela deszifratu eta egiaztatu. `(goiburua, edukia)` itzultzen du.

    `denbora_egiaztatu` sinkronizaziorako da (fardel zaharrak baztertzeko);
    babeskopietan itzalita joan behar du, zaharrak izatea normala baita.
    """
    goiburua = goiburua_irakurri(fardela)
    if goiburua.get("talde_marka") != talde_marka(gakoa):
        raise KriptoErrorea("Beste talde batekoa da (pasaesaldi desberdina)")

    if denbora_egiaztatu:
        aldea = abs(int(time.time()) - int(goiburua.get("sortze_ordua", 0)))
        if aldea > DENBORA_LEIHOA:
            raise KriptoErrorea("Fardela zaharregia edo etorkizunekoa da")

    goiburu_luzera = struct.unpack(">I", fardela[len(MAGIA):len(MAGIA) + 4])[0]
    mugarria = len(MAGIA) + 4 + goiburu_luzera
    aurrizkia, zifratua = fardela[:mugarria], fardela[mugarria:]

    try:
        nonce = bytes.fromhex(goiburua["nonce"])
        if len(nonce) != NONCE_LUZERA:
            raise ValueError
    except (KeyError, ValueError) as e:
        raise KriptoErrorea("Nonce baliogabea") from e

    try:
        konprimatua = ChaCha20Poly1305(gakoa).decrypt(nonce, zifratua, aurrizkia)
    except (InvalidTag, ValueError) as e:
        raise KriptoErrorea("Fardela manipulatuta dago edo gakoa ez da zuzena") from e

    return goiburua, _deskonprimatu(konprimatua)


def _deskonprimatu(konprimatua: bytes) -> dict:
    """Konpresio-bonben aurkako deskonpresio mugatua.

    Konprimatutako byte gutxi batzuk gigabyteak izan daitezke deskonprimatuta;
    horregatik ez da inoiz `zlib.decompress` hutsa erabiltzen.
    """
    deskonprimatzailea = zlib.decompressobj()
    gordina = deskonprimatzailea.decompress(konprimatua, GEHIENEZ_DESKONPRIMATUTA)
    if not deskonprimatzailea.eof:
        raise KriptoErrorea("Edukia handiegia da")
    try:
        edukia = json.loads(gordina)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise KriptoErrorea("Edukia ezin da irakurri") from e
    if not isinstance(edukia, dict):
        raise KriptoErrorea("Eduki baliogabea")
    return edukia
