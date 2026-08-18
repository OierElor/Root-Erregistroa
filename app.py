#!/usr/bin/env python3
"""Root Erregistroa — interfaze lokala eta APIa.

Zerbitzari hau **127.0.0.1-en bakarrik** entzuten du: interfazea zure
ordenagailurako da, ez sarerako. Beste ordenagailuekin erregistroa trukatzeko
fitxategiak erabiltzen dira (`sinkro.py`), ez konexioak: aplikazioak ez du
sarera portu bakar bat ere irekitzen.

Fitxategi honek HTTP geruza baino ez du: eskaerak `web_api.deitu()`-ra bideratzen
ditu. Logika bera mobileko bertsioak ere erabiltzen du (Pyodide bidez, HTTPrik
gabe), eta hori beharrezkoa da `.rootsync` fitxategiak bateragarriak izan daitezen.

Erabilera::

    python3 app.py                 # http://127.0.0.1:3000
    PORT=3001 DB_FILE=/tmp/b.db KONFIG_DIR=/tmp/konfB python3 app.py
"""

import os
import sqlite3

from flask import Flask, Response, g, jsonify, request

import babeskopiak
import db
import gertaerak
import konfig
import sinkro
import web_api

PORTUA = int(os.environ.get("PORT", "3000"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=None)
# Inportatzen den fitxategiaren gehienezko tamaina.
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

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


# ─── Interfazea ─────────────────────────────────────────────────────────────


@app.route("/")
def orria():
    with open(os.path.join(BASE_DIR, "static", "index.html"), encoding="utf-8") as f:
        html = f.read().replace("__SAIO_TOKENA__", SAIO_TOKENA)
    return Response(html, mimetype="text/html; charset=utf-8")


# ─── APIa ───────────────────────────────────────────────────────────────────


@app.route("/api/<path:azpibidea>", methods=["GET", "POST", "DELETE"])
def api(azpibidea):
    """Eskaera HTTPtik atera eta `web_api`-ri eman.

    Bide-taula `web_api.BIDEAK`-en dago, mobileko bertsioak berdin erabil dezan.
    """
    try:
        emaitza = web_api.deitu(
            konn(),
            f"/api/{azpibidea}",
            request.method,
            gorputza=request.get_json(silent=True),
            kontsulta=request.args.to_dict(),
            byteak=request.get_data() if request.method == "POST" else None,
        )
    except web_api.BideErrorea:
        return jsonify(errorea="Bide ezezaguna"), 404
    except (gertaerak.GertaeraErrorea, sinkro.SinkroErrorea, ValueError) as e:
        return jsonify(errorea=str(e)), 400
    except sqlite3.Error:
        return jsonify(errorea="Datu-basearen errorea"), 500

    if isinstance(emaitza, web_api.Fitxategia):
        return Response(
            emaitza.byteak,
            mimetype=emaitza.mota,
            headers={"Content-Disposition": f'attachment; filename="{emaitza.izena}"'},
        )
    return jsonify(**emaitza)


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

    print(f"\n  Root Erregistroa → http://127.0.0.1:{PORTUA}")
    print(f"  Datu-basea: {db.DB_FITX}")
    print(f"  Gailua: {konfig.gailu_izena()} ({konfig.gailu_id()[:8]})\n")

    # 127.0.0.1: aplikazioak ez du sarera ezer irekitzen. Beste ordenagailuekin
    # trukea fitxategi bidez egiten da, konexiorik gabe.
    app.run(host="127.0.0.1", port=PORTUA, threaded=True)


if __name__ == "__main__":
    abiarazi()
