#!/usr/bin/env python3
"""Root Erregistroa — interfaze lokala eta APIa.

Zerbitzari hau **127.0.0.1-en bakarrik** entzuten du: interfazea zure
ordenagailurako da, ez sarerako. Sinkronizazioa `sarea.py`-k kudeatzen du beste
portu batean, eta hark fardel zifratuak baino ez ditu onartzen.

Erabilera::

    python3 app.py                 # http://127.0.0.1:3000
    PORT=3001 DB_FILE=/tmp/b.db KONFIG_DIR=/tmp/konfB python3 app.py
"""

import os
import sqlite3
import time
import uuid
from functools import wraps

from flask import Flask, Response, g, jsonify, request

import babeskopiak
import db
import estatistikak
import gertaerak
import konfig
import kripto
import sarea
import sinkro

PORTUA = int(os.environ.get("PORT", "3000"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = kripto.GEHIENEZ_FARDELA

# Saio-tokena: abio bakoitzean berria. Nabigatzailean irekita duzun beste
# webgune batek ezin dizu APIra eskaerarik egin tokenik gabe.
SAIO_TOKENA = os.urandom(24).hex()

ONARTUTAKO_OSTALARIAK = {
    f"127.0.0.1:{PORTUA}", f"localhost:{PORTUA}", f"[::1]:{PORTUA}",
}
ONARTUTAKO_JATORRIAK = {
    f"http://127.0.0.1:{PORTUA}", f"http://localhost:{PORTUA}", f"http://[::1]:{PORTUA}",
}


# ─── Konexioa ───────────────────────────────────────────────────────────────


def konn() -> sqlite3.Connection:
    if "db" not in g:
        g.db = db.konexioa()
    return g.db


@app.teardown_appcontext
def _konexioa_itxi(salbuespena):
    konexioa = g.pop("db", None)
    if konexioa is not None:
        konexioa.close()


# ─── Segurtasun-geruza ──────────────────────────────────────────────────────


@app.before_request
def _sarrera_egiaztatu():
    """DNS rebinding eta CSRF babesa.

    * `Host`: nabigatzaile batek zure aplikaziora erasotzaile baten domeinu
      baten bidez iristea eragozten du (DNS rebinding).
    * `Origin` + tokena: kanpoko webgune batek datuak alda ditzan eragozten du.
    """
    ostalaria = (request.headers.get("Host") or "").lower()
    if ostalaria not in ONARTUTAKO_OSTALARIAK:
        return jsonify(errorea="Ostalari baliogabea"), 403

    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None

    jatorria = request.headers.get("Origin")
    if jatorria and jatorria not in ONARTUTAKO_JATORRIAK:
        return jsonify(errorea="Jatorri baliogabea"), 403

    if request.headers.get("X-Root-Token") != SAIO_TOKENA:
        return jsonify(errorea="Saio-token baliogabea. Freskatu orria."), 403

    return None


@app.after_request
def _goiburu_seguruak(erantzuna):
    erantzuna.headers["X-Content-Type-Options"] = "nosniff"
    erantzuna.headers["X-Frame-Options"] = "DENY"
    erantzuna.headers["Referrer-Policy"] = "no-referrer"
    erantzuna.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'"
    )
    return erantzuna


def akatsak_harrapatu(funtzioa):
    """Salbuespenak JSON erantzun garbi bihurtu, arrasto teknikorik erakutsi gabe."""

    @wraps(funtzioa)
    def bilgarria(*a, **kw):
        try:
            return funtzioa(*a, **kw)
        except (gertaerak.GertaeraErrorea, sinkro.SinkroErrorea,
                kripto.KriptoErrorea, ValueError) as e:
            return jsonify(errorea=str(e)), 400
        except sqlite3.Error:
            return jsonify(errorea="Datu-basearen errorea"), 500

    return bilgarria


def json_gorputza() -> dict:
    datuak = request.get_json(silent=True)
    if not isinstance(datuak, dict):
        raise ValueError("JSON objektu bat espero zen")
    return datuak


# Katalogo guztiek egitura bera dute; taula-izena kodean dago finkatuta, ez
# eskaeran (ikus `_KATALOGOAK`), beraz ez dago SQL injekziorako biderik.
_KATALOGO_KONTSULTA = (
    "SELECT kodea, izena, hedapena FROM %s WHERE ezabatuta = 0 "
    "ORDER BY hedapena, izena"
)


# ─── Interfazea ─────────────────────────────────────────────────────────────


@app.route("/")
def orria():
    with open(os.path.join(BASE_DIR, "static", "index.html"), encoding="utf-8") as f:
        html = f.read().replace("__SAIO_TOKENA__", SAIO_TOKENA)
    return Response(html, mimetype="text/html; charset=utf-8")


# ─── Katalogoak eta hasierako datuak ────────────────────────────────────────


@app.route("/api/hasiera")
@akatsak_harrapatu
def hasiera():
    k = konn()
    return jsonify(
        laburpena=estatistikak.laburpena(k),
        jokalariak=[
            dict(l) for l in k.execute(
                "SELECT id, izena, ezizena FROM jokalariak WHERE ezabatuta = 0 "
                "ORDER BY izena COLLATE NOCASE"
            )
        ],
        fakzioak=[
            dict(l) for l in k.execute(
                "SELECT kodea, izena, hedapena, kolorea FROM fakzioak "
                "WHERE ezabatuta = 0 ORDER BY hedapena, izena"
            )
        ],
        mertzenarioak=[dict(l) for l in k.execute(_KATALOGO_KONTSULTA % "mertzenarioak")],
        leku_bereziak=[dict(l) for l in k.execute(_KATALOGO_KONTSULTA % "leku_bereziak")],
        mapak=[dict(l) for l in k.execute("SELECT * FROM mapak ORDER BY izena")],
        karta_sortak=[dict(l) for l in k.execute("SELECT * FROM karta_sortak")],
        garaipen_motak=[
            {"kodea": kodea, "izena": izena} for kodea, izena in db.GARAIPEN_MOTAK
        ],
        sinkro=sinkro.egoera(k),
        ezarpenak=konfig.ezarpenak(),
    )


# ─── Jokalariak ─────────────────────────────────────────────────────────────


def _jokalaria_ziurtatu(k, izena: str) -> str:
    """Izen bat jokalari-id bihurtu, behar bada jokalaria sortuz.

    Identifikatzailea izenetik eratortzen da, beraz bi ordenagailutan jokalari
    bera sartzeak ez du bikoizturik sortzen sinkronizatzean.
    """
    izena = (izena or "").strip()
    if not izena:
        raise ValueError("Jokalariaren izena hutsik dago")

    # Lehenik izenez: jokalariari izena aldatu bazaio, ez sortu berri bat.
    lerroa = k.execute(
        "SELECT id FROM jokalariak WHERE izena = ? COLLATE NOCASE AND ezabatuta = 0",
        (izena,),
    ).fetchone()
    if lerroa:
        return lerroa["id"]

    jokalari_id = gertaerak.jokalari_id_izenetik(izena)
    if k.execute("SELECT 1 FROM jokalariak WHERE id = ?", (jokalari_id,)).fetchone():
        # Badago (izena aldatuta edo ezabatuta): ez berridatzi isilean.
        return jokalari_id

    gertaerak.gertaera_berria(k, "jokalaria_gorde", {"id": jokalari_id, "izena": izena})
    return jokalari_id


@app.route("/api/jokalariak", methods=["POST"])
@akatsak_harrapatu
def jokalaria_gorde():
    datuak = json_gorputza()
    karga = {
        "id": datuak.get("id") or gertaerak.jokalari_id_izenetik(datuak.get("izena", "")),
        "izena": datuak.get("izena"),
        "ezizena": datuak.get("ezizena"),
    }
    gertaerak.gertaera_berria(konn(), "jokalaria_gorde", karga)
    return jsonify(ok=True, id=karga["id"])


@app.route("/api/jokalariak/<jokalari_id>", methods=["DELETE"])
@akatsak_harrapatu
def jokalaria_ezabatu(jokalari_id):
    gertaerak.gertaera_berria(konn(), "jokalaria_ezabatu", {"id": jokalari_id})
    return jsonify(ok=True)


# ─── Partidak ───────────────────────────────────────────────────────────────


@app.route("/api/partidak")
@akatsak_harrapatu
def partidak_zerrendatu():
    iragazkia = {
        "jokalari_id": request.args.get("jokalari_id"),
        "fakzio_kodea": request.args.get("fakzio_kodea"),
        "mapa_kodea": request.args.get("mapa_kodea"),
    }
    muga = request.args.get("muga", "50")
    return jsonify(
        partidak=estatistikak.azken_partidak(
            konn(), int(muga) if muga.isdigit() else 50, iragazkia
        )
    )


@app.route("/api/partidak", methods=["POST"])
@akatsak_harrapatu
def partida_gorde():
    datuak = json_gorputza()
    k = konn()

    parte_hartzaileak = datuak.get("jokalariak")
    if not isinstance(parte_hartzaileak, list):
        raise ValueError("jokalariak: zerrenda bat behar da")

    prestatuak = []
    for sarrera in parte_hartzaileak:
        if not isinstance(sarrera, dict):
            raise ValueError("jokalari sarrera baliogabea")
        jokalari_id = sarrera.get("jokalari_id") or _jokalaria_ziurtatu(
            k, sarrera.get("izena", "")
        )
        prestatuak.append({**sarrera, "jokalari_id": jokalari_id})

    karga = {
        "id": datuak.get("id") or uuid.uuid4().hex,
        "data": datuak.get("data") or time.strftime("%Y-%m-%d"),
        "mapa_kodea": datuak.get("mapa_kodea"),
        "karta_sorta": datuak.get("karta_sorta"),
        "oharrak": datuak.get("oharrak"),
        "jokalariak": prestatuak,
        "mertzenarioak": datuak.get("mertzenarioak"),
        "leku_bereziak": datuak.get("leku_bereziak"),
    }
    gertaerak.gertaera_berria(k, "partida_gorde", karga)
    return jsonify(ok=True, id=karga["id"])


@app.route("/api/partidak/<partida_id>", methods=["DELETE"])
@akatsak_harrapatu
def partida_ezabatu(partida_id):
    gertaerak.gertaera_berria(konn(), "partida_ezabatu", {"id": partida_id})
    return jsonify(ok=True)


# ─── Fakzioak ───────────────────────────────────────────────────────────────


# Katalogoen izen publikoa → (gorde gertaera, ezabatu gertaera, kolorea du?)
_KATALOGOAK = {
    "fakzioak":      ("fakzioa_gorde", "fakzioa_ezabatu", True),
    "mertzenarioak": ("mertzenarioa_gorde", "mertzenarioa_ezabatu", False),
    "leku-bereziak": ("lekua_gorde", "lekua_ezabatu", False),
}


@app.route("/api/katalogoak/<katalogoa>", methods=["POST"])
@akatsak_harrapatu
def katalogoa_gorde(katalogoa):
    """Katalogo bateko sarrera bat gehitu edo izena aldatu.

    Gertaera bat denez, aldaketa ordenagailu guztietara sinkronizatzen da; eta
    `azken_lamport` mugitzen duenez, hurrengo abioan hazi-datuek ez dute
    berridazten (ikus `db.hasieratu`).
    """
    if katalogoa not in _KATALOGOAK:
        raise ValueError("Katalogo ezezaguna")
    gorde_mota, _, kolorea_du = _KATALOGOAK[katalogoa]

    datuak = json_gorputza()
    karga = {
        "kodea": datuak.get("kodea"),
        "izena": datuak.get("izena"),
        "hedapena": datuak.get("hedapena") or "Norberarena",
    }
    if kolorea_du:
        karga["kolorea"] = datuak.get("kolorea") or "#888888"

    gertaerak.gertaera_berria(konn(), gorde_mota, karga)
    return jsonify(ok=True, kodea=karga["kodea"])


@app.route("/api/katalogoak/<katalogoa>/<kodea>", methods=["DELETE"])
@akatsak_harrapatu
def katalogoa_ezabatu(katalogoa, kodea):
    if katalogoa not in _KATALOGOAK:
        raise ValueError("Katalogo ezezaguna")
    gertaerak.gertaera_berria(konn(), _KATALOGOAK[katalogoa][1], {"kodea": kodea})
    return jsonify(ok=True)


# ─── Estatistikak ───────────────────────────────────────────────────────────


@app.route("/api/estatistikak")
@akatsak_harrapatu
def estatistikak_ikusi():
    k = konn()
    return jsonify(
        laburpena=estatistikak.laburpena(k),
        jokalariak=estatistikak.jokalarien_sailkapena(k),
        fakzioak=estatistikak.fakzioen_estatistikak(k),
        matrizea=estatistikak.jokalari_fakzio_matrizea(k),
        bilakaera=estatistikak.bilakaera(k),
        **estatistikak.osagarrien_erabilera(k),
    )


# ─── Sinkronizazioa ─────────────────────────────────────────────────────────


@app.route("/api/sinkro/egoera")
@akatsak_harrapatu
def sinkro_egoera():
    return jsonify(
        **sinkro.egoera(konn()),
        kideak=sarea.kideak(),
        azken_sinkro=sarea.azken_sinkro(),
        sync_portua=sarea.SYNC_PORTUA,
    )


@app.route("/api/sinkro/taldea", methods=["POST"])
@akatsak_harrapatu
def sinkro_taldea():
    datuak = json_gorputza()
    emaitza = sinkro.taldea_konfiguratu(
        datuak.get("izena", ""), datuak.get("pasaesaldia", "")
    )
    return jsonify(ok=True, **emaitza, oharra="Berrabiarazi LAN sinkronizazioa martxan jartzeko.")


@app.route("/api/sinkro/orain", methods=["POST"])
@akatsak_harrapatu
def sinkro_orain():
    return jsonify(sarea.orain_sinkronizatu())


@app.route("/api/sinkro/esportatu")
@akatsak_harrapatu
def sinkro_esportatu():
    fardela = sinkro.fitxategira_esportatu(konn())
    izena = f"root-erregistroa-{time.strftime('%Y%m%d-%H%M%S')}.rootsync"
    return Response(
        fardela,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{izena}"'},
    )


@app.route("/api/sinkro/inportatu", methods=["POST"])
@akatsak_harrapatu
def sinkro_inportatu():
    gordina = request.get_data()
    if not gordina:
        raise ValueError("Fitxategia hutsik dago")
    k = konn()
    # Babeskopia fardela ona dela egiaztatu ondoren, datuak ukitu aurretik.
    return jsonify(
        babeskopia=True,
        **sinkro.fitxategitik_inportatu(k, gordina, lambda: babeskopiak.kopia_egin(k, "inportazio")),
    )


# ─── Babeskopiak ────────────────────────────────────────────────────────────


@app.route("/api/babeskopiak")
@akatsak_harrapatu
def babeskopia_zerrenda():
    return jsonify(kopiak=babeskopiak.zerrenda(), karpeta=str(babeskopiak.KOPIA_DIR))


@app.route("/api/babeskopiak", methods=["POST"])
@akatsak_harrapatu
def babeskopia_egin():
    bidea = babeskopiak.kopia_egin(konn(), "eskuz")
    ezabatuak = babeskopiak.garbitu(konfig.ezarpenak()["babeskopia_gehienez"])
    return jsonify(ok=True, izena=bidea.name, ezabatuak=ezabatuak)


@app.route("/api/babeskopiak/leheneratu", methods=["POST"])
@akatsak_harrapatu
def babeskopia_leheneratu():
    izena = json_gorputza().get("izena", "")
    return jsonify(ok=True, **babeskopiak.leheneratu(konn(), izena))


# ─── Ezarpenak eta mantentze-lanak ──────────────────────────────────────────


@app.route("/api/ezarpenak", methods=["POST"])
@akatsak_harrapatu
def ezarpenak_gorde():
    return jsonify(ezarpenak=konfig.ezarpenak_gorde(json_gorputza()))


@app.route("/api/gailua", methods=["POST"])
@akatsak_harrapatu
def gailua_izendatu():
    konfig.gailua_izendatu(json_gorputza().get("izena", ""))
    return jsonify(ok=True, izena=konfig.gailu_izena())


@app.route("/api/birsortu", methods=["POST"])
@akatsak_harrapatu
def birsortu():
    """Proiekzioak gertaera-erregistrotik berreraiki (konponketa)."""
    return jsonify(ok=True, entitateak=gertaerak.birsortu(konn()))


# ─── Abiaraztea ─────────────────────────────────────────────────────────────


def abiarazi():
    db.hasieratu()

    hasierako_konn = db.konexioa()
    try:
        if konfig.ezarpenak().get("babeskopia_abioan", True):
            kopia = babeskopiak.abioko_kopia(
                hasierako_konn, konfig.ezarpenak()["babeskopia_gehienez"]
            )
            if kopia:
                print(f"[babeskopia] {kopia.name}")
    finally:
        hasierako_konn.close()

    zerbitzua = sarea.Zerbitzua()
    zerbitzua.abiarazi()

    print(f"\n  Root Erregistroa → http://127.0.0.1:{PORTUA}")
    print(f"  Datu-basea: {db.DB_FITX}")
    print(f"  Gailua: {konfig.gailu_izena()} ({konfig.gailu_id()[:8]})\n")

    # 127.0.0.1: sarera EZ da inoiz irekitzen; hori sarea.py-ren lana da.
    app.run(host="127.0.0.1", port=PORTUA, threaded=True)


if __name__ == "__main__":
    abiarazi()
