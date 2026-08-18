"""`web_api` geruzaren testak: HTTPrik gabeko APIa.

Geruza hau mahaigainak (`app.py`, Flask bidez) eta mobilak (Pyodide bidez,
nabigatzailean) partekatzen dute. Testek bi gauza bermatzen dituzte:

  * Bidea → funtzio bideratzea zuzena dela, bide-zatiak harrapatuta.
  * Emaitza HTTP bidezkoaren **berbera** dela: bi bideek logika bera erabiltzen
    dutela, eta ez direla denborarekin aldenduko.

Bigarrena da garrantzitsuena: bi inplementazio egongo balira, jokalari-id edo
Lamport ordena desberdinak sor litzakete, eta `.rootsync` fitxategiak bateratzean
datuak zatituko lirateke.
"""

import pytest

import app as aplikazioa
import db
import gertaerak
import web_api

OSTALARIA = "127.0.0.1:3000"


@pytest.fixture
def konn():
    db.hasieratu()
    k = db.konexioa()
    for taula in ("gertaerak", "partida_jokalariak", "partidak", "jokalariak"):
        k.execute(f"DELETE FROM {taula}")
    k.commit()
    yield k
    k.close()


@pytest.fixture
def bezeroa(konn):
    aplikazioa.app.config.update(TESTING=True)
    with aplikazioa.app.test_client() as k:
        yield k


def partida_datuak():
    return {
        "data": "2026-05-01",
        "mapa_kodea": "udazkena",
        "jokalariak": [
            {"izena": "Oier", "fakzio_kodea": "marquise", "puntuak": 30,
             "irabazlea": True, "garaipen_mota": "puntuak"},
            {"izena": "Ander", "fakzio_kodea": "eyrie", "puntuak": 24},
        ],
    }


# ─── Bideratzea ─────────────────────────────────────────────────────────────


def test_bide_ezezagunak_errorea(konn):
    with pytest.raises(web_api.BideErrorea):
        web_api.deitu(konn, "/api/ez-dago", "GET")


def test_metodo_okerrak_ez_du_bat_egiten(konn):
    """`/api/hasiera` GET da; POST batek ez du bide hori hartu behar."""
    with pytest.raises(web_api.BideErrorea):
        web_api.deitu(konn, "/api/hasiera", "POST", gorputza={})


def test_bide_zatiak_harrapatzen_dira(konn):
    """`/api/katalogoak/*/*`-k bi zati pasatu behar dizkio funtzioari."""
    web_api.deitu(konn, "/api/katalogoak/fakzioak", "POST",
                  gorputza={"kodea": "proba", "izena": "Proba"})
    emaitza = web_api.deitu(konn, "/api/katalogoak/fakzioak/proba", "DELETE")
    assert emaitza["ok"] is True
    kodeak = [f["kodea"] for f in web_api.deitu(konn, "/api/hasiera")["fakzioak"]]
    assert "proba" not in kodeak


def test_katalogo_ezezaguna_baztertzen_da(konn):
    with pytest.raises(ValueError):
        web_api.deitu(konn, "/api/katalogoak/asmatua", "POST",
                      gorputza={"kodea": "x", "izena": "X"})


def test_kontsulta_parametroak_iristen_dira(konn):
    web_api.deitu(konn, "/api/partidak", "POST", gorputza=partida_datuak())
    denak = web_api.deitu(konn, "/api/partidak")["partidak"]
    assert len(denak) == 1

    jokalari_id = gertaerak.jokalari_id_izenetik("Oier")
    bat = web_api.deitu(konn, "/api/partidak", kontsulta={"jokalari_id": jokalari_id})
    assert len(bat["partidak"]) == 1
    hutsa = web_api.deitu(konn, "/api/partidak", kontsulta={"jokalari_id": "j-ez-dago"})
    assert hutsa["partidak"] == []


# ─── Gorputz baliogabeak ────────────────────────────────────────────────────


def test_json_gorputza_beharrezkoa_da(konn):
    with pytest.raises(ValueError):
        web_api.deitu(konn, "/api/jokalariak", "POST", gorputza=None)


def test_jokalari_zerrenda_baliogabea(konn):
    with pytest.raises(ValueError):
        web_api.deitu(konn, "/api/partidak", "POST", gorputza={"jokalariak": "ez-zerrenda"})


def test_inportazio_hutsa_baztertzen_da(konn):
    with pytest.raises(ValueError):
        web_api.deitu(konn, "/api/sinkro/inportatu", "POST", byteak=b"")


# ─── Esportazioa fitxategi gisa ─────────────────────────────────────────────


def test_esportazioak_fitxategia_itzultzen_du(konn):
    web_api.deitu(konn, "/api/partidak", "POST", gorputza=partida_datuak())
    emaitza = web_api.deitu(konn, "/api/sinkro/esportatu")
    assert isinstance(emaitza, web_api.Fitxategia)
    assert emaitza.izena.endswith(".rootsync")
    assert b"root-erregistroa" in emaitza.byteak


# ─── HTTP eta HTTPrik gabekoa bat datoz ─────────────────────────────────────


def test_hasiera_berdina_bi_bideetatik(bezeroa, konn):
    """Mobilak eta mahaigainak datu berberak jaso behar dituzte."""
    web_api.deitu(konn, "/api/partidak", "POST", gorputza=partida_datuak())

    zuzena = web_api.deitu(konn, "/api/hasiera")
    bidez = bezeroa.get("/api/hasiera", headers={"Host": OSTALARIA}).get_json()

    # `sinkro` atalak denbora-marka bat du (azken_ikusia); gainerakoak berdinak.
    zuzena.pop("sinkro"), bidez.pop("sinkro")
    assert zuzena == bidez


def test_hatz_marka_berdina_bi_bideetatik(bezeroa, konn):
    """Hatz-marka da bi erregistro berdinak diren egiaztatzeko neurria."""
    web_api.deitu(konn, "/api/partidak", "POST", gorputza=partida_datuak())

    zuzena = web_api.deitu(konn, "/api/sinkro/egoera")["hatz_marka"]
    bidez = bezeroa.get("/api/sinkro/egoera",
                        headers={"Host": OSTALARIA}).get_json()["hatz_marka"]
    assert zuzena == bidez


def test_estatistikak_berdinak_bi_bideetatik(bezeroa, konn):
    web_api.deitu(konn, "/api/partidak", "POST", gorputza=partida_datuak())

    zuzena = web_api.deitu(konn, "/api/estatistikak")
    bidez = bezeroa.get("/api/estatistikak", headers={"Host": OSTALARIA}).get_json()
    assert zuzena == bidez


def test_bide_ezezagunak_404_ematen_du_httpn(bezeroa):
    erantzuna = bezeroa.get("/api/ez-dago", headers={"Host": OSTALARIA})
    assert erantzuna.status_code == 404


# ─── Jokalari-identitatea (mobilaren arrisku nagusia) ───────────────────────


@pytest.mark.parametrize("izena", ["Oier", "  Oier  ", "OIER", "oier"])
def test_jokalari_id_egonkorra_da(konn, izena):
    """Izen bera modu desberdinetan idatzita, jokalari bakarra.

    Mobilak identifikatzaile bera kalkulatu behar du, bestela `.rootsync` bat
    bateratzean jokalari bera bitan zatituko litzateke.
    """
    web_api.deitu(konn, "/api/partidak", "POST", gorputza={
        "data": "2026-05-01",
        "jokalariak": [{"izena": izena, "fakzio_kodea": "marquise", "puntuak": 30}],
    })
    jokalariak = web_api.deitu(konn, "/api/hasiera")["jokalariak"]
    assert len(jokalariak) == 1
