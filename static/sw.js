// Service worker-a: aplikazioa offline erabiltzeko.
//
// Hemen KODEA bakarrik cachetzen da, inoiz ez datuak: partidak IndexedDB-n daude
// (Pythonek idatzita) eta ez dute nabigatzailea uzten. Cache honek Pyodide
// (~10 MB) eta erregistroaren kodea gordetzen ditu, lehen bisitaren ondoren
// sarerik gabe ere ibil dadin.

const CACHE = "root-erregistroa-v3";

// Partekatze-fitxategi bat (`.rootsync`) aldi baterako uzteko lekua. Ez CACHE
// bera erabili: `activate`-k CACHE ez diren guztiak ezabatzen ditu, eta
// partekatze bat martxan egongo litzatekeen bitartean galduko litzateke.
const PARTEKATZE_CACHE = "root-partekatzea";
const PARTEKATZE_GAKOA = "./partekatutako-fitxategia";

// Aplikazioaren muina. Python iturriak `../`-tik datoz: mahaigainak eta
// mobilak fitxategi berberak erabiltzen dituzte, kopiarik gabe.
const OINARRIA = [
  "./",
  "./index.html",
  "./pyodide-abioa.js",
  "./manifest.json",
  "./ikonoa.svg",
  "./ikonoa-192.png",
  "./ikonoa-512.png",
  "./ikonoa-maskagarria-512.png",
  "./ikonoa-180.png",
  "../db.py",
  "../konfig.py",
  "../gertaerak.py",
  "../estatistikak.py",
  "../sinkro.py",
  "../babeskopiak.py",
  "../web_api.py",
  "../mobil_zubia.py",
  "../eskema.sql",
];

self.addEventListener("install", (ev) => {
  ev.waitUntil(
    caches.open(CACHE)
      // Banaka: fitxategi batek huts eginda ere, besteak cachean geratzen dira.
      .then((c) => Promise.allSettled(OINARRIA.map((b) => c.add(b))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (ev) => {
  ev.waitUntil(
    caches.keys()
      .then((izenak) => Promise.all(
        izenak.filter((i) => i !== CACHE && i !== PARTEKATZE_CACHE)
              .map((i) => caches.delete(i))
      ))
      .then(() => self.clients.claim())
  );
});

// Beste app batetik (Telegram, posta...) «Partekatu → Root Erregistroa»
// sakatuta, Androidek POST bat bidaltzen du hona zuzenean, manifestuko
// `share_target`-ek adierazitako `action`-era. Zerbitzaririk ez dagoenez,
// service worker honek berak erantzun behar dio: fitxategia aldi baterako
// cachean uzten du eta index.html-era birbideratzen, handik `api()` bidez
// inportatzeko (ikus static/index.html-eko `partekatzeaEgiaztatu`).
async function partekatzeaKudeatu(eskaera) {
  try {
    const forma = await eskaera.formData();
    const fitxategia = forma.get("fitxategia");
    if (fitxategia) {
      const c = await caches.open(PARTEKATZE_CACHE);
      await c.put(PARTEKATZE_GAKOA, new Response(fitxategia));
    }
  } catch (e) {
    // Fitxategirik gabe ere birbideratu: erabiltzaileak eskuz inporta dezake.
  }
  return Response.redirect("./index.html?partekatuta=1", 303);
}

self.addEventListener("fetch", (ev) => {
  const bidea = new URL(ev.request.url).pathname;
  if (ev.request.method === "POST" && bidea.endsWith("/index.html")) {
    ev.respondWith(partekatzeaKudeatu(ev.request));
    return;
  }

  if (ev.request.method !== "GET") return;

  const kanpokoa = new URL(ev.request.url).origin !== self.location.origin;

  if (kanpokoa) {
    // Pyodide CDNtik dator (jsDelivr): bertsioz finkatuta dago eta ez da
    // INOIZ aldatzen ("v0.29.0" URLan idatzita). Horregatik cache-first du
    // zentzurik gehien hemen: konexio motelarekin ere berehala kargatzen da,
    // eta zaharkitze-arriskurik ez dago, aldaezina baita. Gure kodearentzat
    // (behean) network-first mantentzen da, hori aldatu egiten baita.
    ev.respondWith(
      caches.match(ev.request).then((cachekoa) => {
        if (cachekoa) return cachekoa;
        return fetch(ev.request, { mode: "cors" }).then((erantzuna) => {
          const kopia = erantzuna.clone();
          caches.open(CACHE).then((c) => c.put(ev.request, kopia));
          return erantzuna;
        });
      })
    );
    return;
  }

  // Lehenik sarea, gero cachea: horrela kodea eguneratzen da konexioa dagoenean,
  // baina offline ere ibiltzen da. Datuak ez daude hemen, beraz ez dago
  // zaharkitutako partidarik erakusteko arriskurik.
  ev.respondWith(
    fetch(ev.request)
      .then((erantzuna) => {
        if (erantzuna.ok) {
          const kopia = erantzuna.clone();
          caches.open(CACHE).then((c) => c.put(ev.request, kopia));
        }
        return erantzuna;
      })
      .catch(() => caches.match(ev.request, { ignoreSearch: false }))
  );
});
