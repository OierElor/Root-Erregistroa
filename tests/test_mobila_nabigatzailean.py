"""Mobileko bertsioaren proba benetako nabigatzaile batean.

Beste testek Python aldea probatzen dute; honek osotasuna: Chromium bat irekitzen
du, Pyodide kargatzen da, eta mobilak eta mahaigainak `.rootsync` fitxategiak
trukatzen dituzte. Amaieran biek **hatz-marka berdina** izan behar dute.

Astiroa da (Pyodide deskargatu behar du) eta Playwright behar du, ez baita
proiektuaren dependentzia. Falta bada, saltatu egiten da:

    pip install playwright && playwright install chromium
    pytest tests/test_mobila_nabigatzailean.py -q

Sarerik gabe ere saltatu egiten da: Pyodide CDNtik datorrelako.
"""

import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest

import db
import web_api

sync_playwright = pytest.importorskip(
    "playwright.sync_api", reason="Playwright ez dago instalatuta"
).sync_playwright

ERROA = Path(__file__).resolve().parent.parent
PORTUA = 8953

# Pyodide kargatzeak denbora behar du lehen aldian.
ABIO_MUGA = 240_000


@pytest.fixture(scope="module")
def zerbitzari_estatikoa():
    """Fitxategi estatikoak bakarrik, GitHub Pages batek egingo lukeen bezala.

    `app.py` ez da erabiltzen: horixe da probatu nahi duguna, zerbitzari-logikarik
    gabe ere aplikazioak funtzionatzen duela.
    """
    kudeatzailea = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(ERROA)
    )
    kudeatzailea.log_message = lambda *a, **kw: None
    socketserver.TCPServer.allow_reuse_address = True
    zerb = socketserver.TCPServer(("127.0.0.1", PORTUA), kudeatzailea)
    threading.Thread(target=zerb.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{PORTUA}"
    zerb.shutdown()


def partida(izena, bigarrena, data):
    return {
        "data": data, "mapa_kodea": "udazkena",
        "jokalariak": [
            {"izena": izena, "fakzio_kodea": "marquise", "puntuak": 30,
             "irabazlea": True, "garaipen_mota": "puntuak"},
            {"izena": bigarrena, "fakzio_kodea": "eyrie", "puntuak": 24},
        ],
    }


def _abioaren_zain(orria):
    # `gailu-info` hasieratzea amaitzean bakarrik betetzen da.
    orria.wait_for_function(
        "() => document.getElementById('gailu-info').textContent.trim().length > 0",
        timeout=ABIO_MUGA,
    )


def test_trukea_nabigatzailearekin(zerbitzari_estatikoa, tmp_path, monkeypatch):
    """Mobilak eta mahaigainak fitxategiak trukatuta, erregistro berbera.

    Hau da mobileko bertsioaren berme nagusia: hatz-marka berdina bada, bi aldeek
    gauza bera dute eta kalkulu berbera egiten dute (jokalari-identifikatzaileak,
    Lamport ordena, proiekzioak).
    """
    # Mahaigainak bere gailu identitatea du; mobilak berea sortzen du.
    monkeypatch.setenv("GAILU_ID", "d" * 32)
    monkeypatch.setenv("GAILU_IZENA", "Mahaigainekoa")

    mahaigainaren_db = tmp_path / "mahaigaina.db"
    db.hasieratu(mahaigainaren_db)
    mahaigaina = db.konexioa(mahaigainaren_db)
    try:
        web_api.deitu(mahaigaina, "/api/partidak", "POST",
                      gorputza=partida("Ander", "Jon", "2026-05-02"))
        mahaigainarena = web_api.deitu(mahaigaina, "/api/sinkro/esportatu").byteak

        akatsak = []
        with sync_playwright() as pw:
            nab = pw.chromium.launch()
            try:
                orria = nab.new_page(viewport={"width": 390, "height": 844})
                orria.on("pageerror", lambda e: akatsak.append(str(e)))
                orria.goto(f"{zerbitzari_estatikoa}/static/index.html")
                _abioaren_zain(orria)

                # Babeskopiak ez daude mobilean.
                atalak = orria.evaluate(
                    "[...document.querySelectorAll('nav button')].map(b => b.textContent)"
                )
                assert "Babeskopiak" not in atalak

                # Mobilak bere partida sortu eta esportatzen du.
                orria.evaluate(
                    "async (p) => { await api('/api/partidak',"
                    " { method: 'POST', body: JSON.stringify(p) }); }",
                    partida("Oier", "Maddi", "2026-05-01"),
                )
                mobilarena = orria.evaluate(
                    "async () => (await RootPy.deitu('/api/sinkro/esportatu')).testua"
                )

                # Mobilak mahaigainarena inportatzen du, interfazearen bide beretik.
                orria.evaluate(
                    """async (testua) => {
                      const byteak = new TextEncoder().encode(testua);
                      await api('/api/sinkro/inportatu',
                                { method: 'POST', body: byteak.buffer });
                    }""",
                    mahaigainarena.decode("utf-8"),
                )

                mobilaren_egoera = orria.evaluate(
                    """async () => {
                      const e = await api('/api/sinkro/egoera');
                      const p = await api('/api/partidak');
                      return { hatz_marka: e.hatz_marka, gailu_id: e.gailu_id,
                               partidak: p.partidak.length };
                    }"""
                )
            finally:
                nab.close()

        # Mahaigainak mobilarena inportatzen du.
        web_api.deitu(mahaigaina, "/api/sinkro/inportatu", "POST",
                      byteak=mobilarena.encode("utf-8"))
        mahaigainaren_egoera = web_api.deitu(mahaigaina, "/api/sinkro/egoera")

        assert not akatsak, f"Nabigatzailean akatsak: {akatsak[:3]}"
        # Gailu bereiziak: Lamport berdinketak `gailu_id`-rekin hausten dira.
        assert mobilaren_egoera["gailu_id"] != mahaigainaren_egoera["gailu_id"]
        assert mobilaren_egoera["partidak"] == 2
        assert len(web_api.deitu(mahaigaina, "/api/partidak")["partidak"]) == 2
        assert mobilaren_egoera["hatz_marka"] == mahaigainaren_egoera["hatz_marka"]
    finally:
        mahaigaina.close()


def test_datuak_ez_dira_galtzen_birkargatzean(zerbitzari_estatikoa):
    """Partidak nabigatzailearen biltegian gordetzen dira, orria itxi ondoren ere."""
    akatsak = []
    with sync_playwright() as pw:
        nab = pw.chromium.launch()
        try:
            # Testuinguru berria: beste "telefono" bat, biltegi hutsarekin.
            testuingurua = nab.new_context(viewport={"width": 390, "height": 844})
            orria = testuingurua.new_page()
            orria.on("pageerror", lambda e: akatsak.append(str(e)))
            orria.goto(f"{zerbitzari_estatikoa}/static/index.html")
            _abioaren_zain(orria)

            aurretik = orria.evaluate(
                """async (p) => {
                  await api('/api/partidak', { method: 'POST', body: JSON.stringify(p) });
                  const e = await api('/api/sinkro/egoera');
                  return { hatz_marka: e.hatz_marka, gailu_id: e.gailu_id };
                }""",
                partida("Oier", "Maddi", "2026-05-01"),
            )

            orria.reload()
            _abioaren_zain(orria)

            ondoren = orria.evaluate(
                """async () => {
                  const e = await api('/api/sinkro/egoera');
                  const p = await api('/api/partidak');
                  return { hatz_marka: e.hatz_marka, gailu_id: e.gailu_id,
                           partidak: p.partidak.length };
                }"""
            )
        finally:
            nab.close()

    assert not akatsak, f"Nabigatzailean akatsak: {akatsak[:3]}"
    assert ondoren["partidak"] == 1, "Datuak galdu dira birkargatzean"
    assert ondoren["hatz_marka"] == aurretik["hatz_marka"]
    # Gailuaren identitateak ere iraun behar du: bestela gertaeren ordena
    # aldatuko litzateke birkarga bakoitzean.
    assert ondoren["gailu_id"] == aurretik["gailu_id"]
