// Service worker-a: aplikazioa offline erabiltzeko.
//
// Hemen KODEA bakarrik cachetzen da, inoiz ez datuak: partidak IndexedDB-n daude
// (Pythonek idatzita) eta ez dute nabigatzailea uzten. Cache honek Pyodide
// (~10 MB) eta erregistroaren kodea gordetzen ditu, lehen bisitaren ondoren
// sarerik gabe ere ibil dadin.

const CACHE = "root-erregistroa-v2";

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
        izenak.filter((i) => i !== CACHE).map((i) => caches.delete(i))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (ev) => {
  if (ev.request.method !== "GET") return;

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
