// Root Erregistroa mobilean: Python nabigatzailearen barruan.
//
// Ez dago zerbitzaririk. Fitxategi hauek behin deskargatzen dira (kodea, ez
// datuak), eta hortik aurrera dena telefonoan bertan gertatzen da: partidak
// nabigatzailearen biltegian gordetzen dira eta ez dute inoiz gailua uzten.
// Lagunekin partekatzeko `.rootsync` fitxategiak erabiltzen dira, mahaigainean
// bezala.
//
// Zergatik Pyodide eta ez JavaScript huts bat: mahaigaineko Python kode BERA
// exekutatzen da hemen. Bi inplementazio egongo balira, jokalari-identifikatzaile
// edo gertaera-ordena desberdinak sor litzakete, eta erregistroak bateratzean
// datuak zatituko lirateke.

const RootPy = (() => {
  // Bertsioa finkatuta: eguneratzea erabaki kontziente bat izan behar da.
  const PYODIDE_OINARRIA = "https://cdn.jsdelivr.net/pyodide/v0.29.0/full/";

  // Datuak hemen bizi dira, nabigatzailearen IndexedDB biltegian.
  const DATU_KARPETA = "/erregistroa";
  const KODE_KARPETA = "/root_app";

  // Mahaigaineko kode bera. `eskema.sql` ere behar da: `db.py`-k irakurtzen du.
  const ITURRIAK = [
    "db.py", "konfig.py", "gertaerak.py", "estatistikak.py",
    "sinkro.py", "babeskopiak.py", "web_api.py", "mobil_zubia.py",
    "eskema.sql",
  ];

  let pyodide = null;
  let zubia = null;

  async function jaso(bidea) {
    const erantzuna = await fetch(bidea, { cache: "no-cache" });
    if (!erantzuna.ok) throw new Error(`Ezin izan da kargatu: ${bidea}`);
    return erantzuna.text();
  }

  // IndexedDB-ra idatzi. Hau egin gabe, aldaketak nabigatzailea ixtean galtzen dira.
  function gorde() {
    return new Promise((ondo, gaizki) => {
      pyodide.FS.syncfs(false, (e) => (e ? gaizki(e) : ondo()));
    });
  }

  async function abiarazi(jakinarazi = () => {}) {
    if (zubia) return zubia;

    jakinarazi("Python kargatzen…");
    await new Promise((ondo, gaizki) => {
      const s = document.createElement("script");
      s.src = PYODIDE_OINARRIA + "pyodide.js";
      s.onload = ondo;
      s.onerror = () => gaizki(new Error("Ezin izan da Pyodide kargatu"));
      document.head.appendChild(s);
    });

    pyodide = await loadPyodide({ indexURL: PYODIDE_OINARRIA });

    // `sqlite3` ez dator Pyodide-ren oinarrizko banaketan: bereizita kargatzen da.
    jakinarazi("Datu-basearen euskarria kargatzen…");
    await pyodide.loadPackage("sqlite3");

    jakinarazi("Biltegia prestatzen…");
    // IDBFS: karpeta hau IndexedDB-n gordetzen da, orria itxi ondoren ere.
    pyodide.FS.mkdirTree(DATU_KARPETA);
    pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, DATU_KARPETA);
    await new Promise((ondo, gaizki) => {
      pyodide.FS.syncfs(true, (e) => (e ? gaizki(e) : ondo()));
    });

    // Ingurune-aldagaiak moduluak inportatu AURRETIK: `db.py` eta `konfig.py`-k
    // inportatzean irakurtzen dituzte.
    //
    // GAILU_ID ez da EZARTZEN nahita: `konfig.py`-k ausazko bat sortu eta
    // biltegian gordeko du, telefonoak bere identitate propioa izan dezan.
    // Bi gailuk id bera izateak gertaeren ordena deterministikoa hautsiko luke.
    pyodide.runPython(`
import os
os.environ["DB_FILE"] = "${DATU_KARPETA}/root.db"
os.environ["KONFIG_DIR"] = "${DATU_KARPETA}/konf"
os.environ.setdefault("GAILU_IZENA", "Mobila")
# Emscripten-en fitxategi-sistemak ez du WALek behar duen memoria partekatua.
os.environ["ROOT_JOURNAL"] = "DELETE"
`);

    jakinarazi("Erregistroaren kodea kargatzen…");
    pyodide.FS.mkdirTree(KODE_KARPETA);
    const kodeak = await Promise.all(ITURRIAK.map((i) => jaso(`../${i}`)));
    const kodetzailea = new TextEncoder();
    ITURRIAK.forEach((izena, i) => {
      pyodide.FS.writeFile(`${KODE_KARPETA}/${izena}`, kodetzailea.encode(kodeak[i]));
    });

    jakinarazi("Datu-basea irekitzen…");
    zubia = pyodide.runPython(`
import sys
sys.path.insert(0, "${KODE_KARPETA}")
import mobil_zubia
mobil_zubia
`);
    const gailua = JSON.parse(zubia.hasieratu());
    await gorde();
    return gailua;
  }

  // `app.py`-ren HTTP geruzaren ordezkoa: bide bera, emaitza bera.
  async function deitu(bidea, metodoa = "GET", gorputza = null, byteak = null) {
    if (!zubia) throw new Error("Aplikazioa oraindik kargatzen ari da");

    const [bideHutsa, kontsultaTestua] = bidea.split("?");
    const kontsulta = kontsultaTestua
      ? JSON.stringify(Object.fromEntries(new URLSearchParams(kontsultaTestua)))
      : null;

    // `undefined` pasatzen da eta ez `null`: Pyodide-k `undefined` bakarrik
    // bihurtzen du Python-en `None` bihurtu; `null`-ek `JsNull` objektu bat ematen du.
    const erantzuna = JSON.parse(zubia.deitu(
      bideHutsa,
      metodoa,
      gorputza === null || gorputza === undefined ? undefined : JSON.stringify(gorputza),
      kontsulta === null ? undefined : kontsulta,
      byteak ? new Uint8Array(byteak) : undefined,
    ));

    if (!erantzuna.ok) throw new Error(erantzuna.errorea);
    // Irakurketa hutsak ez du biltegia ukitzen; besteak berehala gordetzen dira,
    // orria ustekabean ixteak aldaketarik gal ez dezan.
    if (metodoa !== "GET") await gorde();

    return erantzuna.fitxategia ? erantzuna.fitxategia : erantzuna.datuak;
  }

  async function gailuaIzendatu(izena) {
    const berria = zubia.gailua_izendatu(izena);
    await gorde();
    return berria;
  }

  return { abiarazi, deitu, gailuaIzendatu };
})();
