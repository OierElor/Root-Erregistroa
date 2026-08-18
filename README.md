# 🌲 Root Erregistroa

Root mahai-jokoaren partiden erregistroa: zure gailuan bizi da, fitxategi baten bidez
partekatzen da lagunekin, eta babeskopia automatikoak ditu. Ez du sarerik, ez
zerbitzaririk, ez konturik behar.

* Partidak sartu, **editatu** eta ezabatu: data, mapa, karta sorta, jokalari bakoitzaren
  fakzioa, puntuak eta garaipen mota, Vagabond-en **pertsonaia** (Thief, Ranger…),
  erabilitako **mertzenarioak** (Hirelings) eta **leku bereziak** (Landmarks).
* Jokoaren izen guztiak **ingelesez, kartetan bezala** (interfazea euskaraz).
* Estatistikak: jokalarien sailkapena, fakzioen irabazte-tasak, jokalari bakoitzak zein
  fakziorekin jokatzen duen ondoen, eta mertzenario/leku erabilienak.
* **Partekatzea fitxategi bidez**: esportatu, bidali (Telegram, posta, USB), besteak
  inportatu. Bi erregistro batzeak ez du inoiz daturik galtzen.
* **Babeskopiak**: automatikoak, aldaketa arriskutsuen aurretik, eta eskuz.
* **Mobilean ere bai** (Android): Python bera nabigatzailean, offline. Ikus
  [Mobilean](#mobilean-android).

---

## Instalazioa

Dependentzia bakarra Flask da. Debian 13-n instalatuta dator; beste banaketa batzuetan
eskuz instalatu behar da:

```bash
# Debian / Ubuntu eta eratorriak
sudo apt install python3-flask

# Arch Linux eta eratorriak (Manjaro, EndeavourOS...)
sudo pacman -S python-flask

# Fedora
sudo dnf install python3-flask
```

Abiarazi:

```bash
cd "~/Root Erregistroa"
python3 app.py
```

Gero nabigatzailean: **http://127.0.0.1:3000**

Ingurune-aldagaiak (aukerakoak):

| Aldagaia | Zertarako |
|---|---|
| `PORT` | Interfazearen portua (lehenetsia: 3000) |
| `DB_FILE` | Beste datu-base bat erabili (probetarako) |
| `KONFIG_DIR` | Konfigurazioaren karpeta (lehenetsia: `~/.config/root-erregistroa`) |
| `GAILU_IZENA` | Gailu honen izena (esportatutako fitxategietan agertzen dena) |

---

## Erregistroa lagunekin partekatzea

**Sinkronizazioa** atalean bi botoi daude, eta hori da dena:

1. **Esportatu fitxategia** — `.rootsync` fitxategi bat sortzen du zure partida guztiekin.
2. Bidali nahi duzun bidetik: Telegram, posta, USB, hodeia… aplikazioak ez du axola.
3. Lagunak **Inportatu fitxategia** sakatzen du eta bere erregistroarekin batzen da.

Alderantziz berdin: haien fitxategia inportatuz gero, haien partidak zureekin batzen dira.
Ez dago konturik, zerbitzaririk, pasaesaldirik ez portu-rik: aplikazioak **ez du inoiz
konexiorik irekitzen**.

> Sinkronizazioa atalean **erregistroaren hatz-marka** agertzen da. Bi ordenagailutan
> berdina bada, biek gauza bera dute.

### Zergatik ez den ezer galtzen

Inportatzeak ez du **inoiz** ezer ezabatzen: gertaerak gehitu baino ez du egiten. Horri
esker:

* Fitxategi bera bi (edo hamar) aldiz inportatu dezakezu: ez du ezer bikoizten.
* Nork zer sartu duen axola ez zaio: fitxategiak batera eta bestera pasata, denek dena
  amaitzen dute edukitzen.
* Bi lagunek partida bera aldatuta ere, biek emaitza **berbera** ikusiko dute bateratu
  ondoren (azkena irabazten du, eta denek berdin kalkulatzen dute zein den azkena).
* Zure esportazioa zeuk inportatu dezakezu arazorik gabe: babeskopia eramangarri gisa balio du.

### Jokoaren izenak eta katalogoak

Fakzioak, mapak, karta sortak, mertzenarioak eta leku bereziak **ingelesez** ageri dira,
kartetan eta arauetan bezala (Marquise de Cat, Autumn, Forest Patrol, The Tower…).
Interfazea bera euskaraz dago.

`Katalogoak` atalean izen horiek zuzendu, berriak gehitu edo zerrendatik kendu ditzakezu —
hedapen berri bat erosi duzunean, adibidez. Aldaketak gertaerak dira: beste ordenagailuetara
sinkronizatzen dira eta **ez dira galtzen aplikazioa eguneratzean**.

> Barruko kodeak (`marquise`, `udazkena`) ez dira inoiz aldatzen, gertaeretan idatzita
> baitaude. Izena bakarrik aldatzen da, beraz lehendik sartutako partidek balio dute beti.

Mertzenario bakoitzak izen desberdina du sustatuta (*promoted*) edo jaitsita (*demoted*)
dagoenean — Forest Patrol / Feline Physicians, adibidez — beraz erabilitako karta hautatzeak
dena esaten du berez.

### Vagabond-en pertsonaia

Jokalari batek Vagabond aukeratzen duenean, **Pertsonaia** eremu bat agertzen da alboan:
Thief, Tinker, Ranger (oinarrizkoa), Vagrant, Arbiter, Scoundrel (*The Riverfolk Expansion*)
edo Ronin, Adventurer, Harrier (*The Vagabond Pack*). Bi Vagabond dituzten partidetan
bakoitzak berea du.

Eremua fakzioaren arabera agertzen da, eta hori katalogoko datu bat da (`arlotea` marka),
ez kodean idatzitako zerrenda bat: Vagabond moduko fakzio berri bat sortzen bada, marka
hori jarri eta pertsonaia-eremua ere agertuko zaio.

Estatistiketan pertsonaia bakoitzaren irabazte-tasa duzu.

### Partidak editatzea

Partiden zerrendan, **Editatu** botoiak partida formularioan kargatzen du: data, mapa,
karta sorta, oharrak, jokalari guztiak bere puntu eta fakzioekin, eta erabilitako
mertzenario eta lekuak. Jokalariak kendu (× botoia) edo gehitu ditzakezu, eta
`Aldaketak gorde` sakatuta partida **ordezkatu** egiten da, bat berria sortu gabe.
`Utzi edizioa` sakatuta ez da ezer aldatzen.

Editatzea ere sinkronizatu egiten da: aldaketa gertaera berri bat da partida beraren
gainean, eta ordenagailu guztietara iristen da. Bi lagunek partida bera aldatzen badute
elkarren berririk izan gabe, bateratzean **biek bertsio berbera** ikusiko dute (azkena
irabazten du, eta "azkena" zein den denek berdin kalkulatzen dute). Aurreko bertsioak
erregistroan gordeta geratzen dira, ez dira ezabatzen.

> Partida bat ustekabean ezabatu baduzu, oraindik ez dago desegiteko botoirik: erabili
> `Babeskopiak` ataleko leheneratzea, edo sartu berriro.

### Nola dagoen eginda barrutik

Datuak ez dira "azken bertsioak irabazi" moduan gainidazten. Aldaketa bakoitza **gertaera
bat** da (partida bat gehitu, aldatu, ezabatu), identifikatzaile bakar batekin, eta bi
erregistro batzea gertaera horien batuketa hutsa da. Hortik datoz goiko bermeak.

Erregistroa osorik gordetzen denez, `Erregistrotik berreraiki` botoiak taula guztiak
zerotik sortzen ditu zerbait arraro ikusiz gero.

Esportatutako fitxategia **JSON arrunta** da: editore batekin ireki eta barrukoa ikus
dezakezu.

---

## Babeskopiak

`backups/` karpetan gordetzen dira, datu-basearen ondoan, `kopia-DATA-ORDUA-mota.db` izenez.

| Noiz | Mota |
|---|---|
| Eguneko lehen abioan | `auto` |
| Fitxategi bat inportatu aurretik | `inportazio` |
| Babeskopia bat leheneratu aurretik | `aurretik` |
| Botoia sakatuta | `eskuz` |

* SQLite-ren babeskopia APIarekin egiten dira: datu-basea erabiltzen ari zarela ere kopia
  koherentea da (`cp` egiteak fitxategi hondatua utz lezake).
* Fitxategi bakarrak dira: USB batera arrastatzea nahikoa da.
* Zaharrenak automatikoki garbitzen dira, baina **egun bakoitzeko bat beti gordetzen da**.
* **Ordenagailutik kanpo gordetzeko**, erabili `Esportatu fitxategia`: `.rootsync` fitxategi
  bakar batean doa dena, eta berriro inportatuz berreskuratzen da. Testu laua da, ordea:
  ikusi behar ez lukeen inoren eskuetan ez uzteko kontuan izan.

Leheneratzeak uneko egoeraren kopia bat egiten du beti aurretik, beraz leheneratze oker
batek ere ez du ezer galtzen.

---

## Mobilean (Android)

Aplikazio bera telefonoan erabil daiteke, **partidak mahaian bertan sartzeko**. Hemen ere
ez dago zerbitzaririk: Python bera telefonoaren nabigatzailearen barruan exekutatzen da
(Pyodide/WASM), eta partidak telefonoan bertan gordetzen dira.

### Nola jarri martxan

Fitxategiak nonbaitetik zerbitzatu behar dira; ezin da `index.html` zuzenean ireki, ez
baitu biltegia atzitzen uzten. Bi bide:

```bash
# 1) Etxean probatzeko, ordenagailu berean:
python3 -m http.server 8000
#    → http://127.0.0.1:8000/static/index.html
```

2) **Telefonoan erabiltzeko**: igo karpeta osoa hosting estatiko batera (GitHub Pages,
   Codeberg Pages…) eta ireki `.../static/index.html`. Nabigatzaileak «pantaila nagusian
   gehitu» eskainiko dizu: hortik aurrera aplikazio arrunt baten itxura du.

> **Hosting estatikoak ez du zure daturik ikusten.** Kodea baino ez du bidaltzen, behin.
> Partidak telefonoaren biltegian geratzen dira eta ez dute inoiz gailua uzten: bidaltzen
> den bakarra zuk eskuz esportatzen duzun `.rootsync` fitxategia da.

Lehen irekialdian ~10 MB deskargatzen dira (Python bera). Gero cachean geratzen da eta
**offline dabil**: hegazkin-moduan ere partidak sartu ditzakezu.

### Telefonoa eta ordenagailua sinkronizatzea

Lagunekin bezala, fitxategi bidez: telefonoan `Esportatu fitxategia` sakatuta Android-en
partekatze-menua irekitzen da (Telegram, posta…), eta ordenagailuan `Inportatu fitxategia`.
Alderantziz berdin. Ez dago konexiorik bien artean.

Telefonoak bere **gailu identifikatzailea** du, ordenagailuak bezala, beraz biek partida
berbera aldatuta ere bateratzeak emaitza bakarra ematen du.

### Zer EZ dagoen mobilean

* **Babeskopiak**: ez dute zentzurik hor. Ordenagailuak gordetzen ditu kopiak, eta
  bateratzeak ez du inoiz ezer ezabatzen. Telefonoko datuak babesteko, esportatu.
* Nabigatzaileko datuak ezaba daitezke biltegia garbitzen baduzu; **esportatu aldian behin**.

---

## Segurtasuna

Aplikazioak **ez du portu bakar bat ere irekitzen sarera**: interfazea `127.0.0.1`-en
bakarrik entzuten du eta ez du inoiz konexiorik hasten. Ez dago suebakia konfiguratu beharrik.

Mobilean ere ez dago zerbitzaririk: dena nabigatzailearen barruan gertatzen da. Aldea
zera da, kodea (aplikazioa bera) hosting estatiko batetik deskargatzen dela behin. **Zure
partidak ez dira inoiz hara bidaltzen**: telefonoaren biltegian geratzen dira, eta ateratzen
den gauza bakarra zuk eskuz esportatzen duzun `.rootsync` fitxategia da.

| Arriskua | Babesa |
|---|---|
| Beste webgune batek zure aplikazio lokalari eskaerak egitea | Saio-tokena + `Origin`/`Host` egiaztapena |
| Zure aplikaziora kanpotik iristea | Interfazea **127.0.0.1**-en soilik; kanpora zabalik ezer ez |
| Fitxategi baten datu okerrek datu-basea hondatzea | Gertaera bakoitza banaka balidatzen da; baliogabeak baztertu eta besteak onartu |
| Inportatzeak zerbait apurtzea | Beti babeskopia bat aurretik; inportatzeak ez du ezer ezabatzen |
| SQL injekzioa | Kontsulta parametrizatuak salbuespenik gabe |
| Fitxategi-izen maltzurrak babeskopietan | Izen-eredu zorrotza; karpetatik kanpoko bideak baztertuta |

**Zer EZ du babesten.** `.rootsync` fitxategiak testu laua dira, zifratu gabe:

* Fitxategia eskuratzen duen edonork irakur dezake erregistroa (izenak, partidak, puntuak).
* Bidean edonork alda dezake — adibidez bere puntuak igo — inork jakin gabe. Inportatzean
  balio zentzugabeak baztertzen dira (999 puntu baino gehiago, izen luzeegiak…), baina
  sinesgarria den aldaketa bat ez da detektatzen.

Mahai-joko baten erregistroarentzat aukera egokia da; kontuan izan fitxategia bidaltzeko
bidea aukeratzean.

---

## Egitura

| Fitxategia | Zertarako |
|---|---|
| `app.py` | Mahaigaineko HTTP geruza (127.0.0.1): eskaerak `web_api`-ra bideratzen ditu |
| `web_api.py` | APIaren logika, HTTPtik aske. Mahaigainak eta mobilak berdin erabiltzen dute |
| `mobil_zubia.py` | Nabigatzailearen (Pyodide) eta `web_api`-ren arteko zubia |
| `gertaerak.py` | Gertaera-erregistroa: balidazioa, bateratzea, proiekzioak |
| `sinkro.py` | `.rootsync` fitxategia esportatu eta inportatu |
| `babeskopiak.py` | Kopiak, atxikitzea, leheneratzea (mahaigainean bakarrik) |
| `estatistikak.py` | Kontsultak |
| `db.py`, `eskema.sql` | Datu-basea eta hazi-datuak (fakzioak, mapak, mertzenarioak, lekuak) |
| `static/index.html` | Interfaze osoa (dependentziarik gabe), bi ingurunetarako |
| `static/pyodide-abioa.js` | Mobilean Python nabigatzailean abiarazten du |
| `static/sw.js`, `static/manifest.json` | Offline erabiltzeko eta instalatzeko |

Testak:

```bash
python3 -m pytest tests/ -q
```

Mobileko testek benetako nabigatzaile bat irekitzen dute (Pyodide kargatuta) eta
mobiletik mahaigainerako trukea probatzen dute. Astiroak dira eta Playwright behar
dute; instalatuta ez badago, saltatu egiten dira:

```bash
pip install playwright && playwright install chromium
python3 -m pytest tests/test_mobila_nabigatzailean.py -q
```

---

## Ohar praktikoak

* **Jokalari beraren izena bi ordenagailutan**: identifikatzailea izenetik eratortzen da,
  beraz "Oier" bi lekutan sartzeak jokalari bakarra sortzen du bateratzean. Hala ere, jokalari
  bati izena aldatu eta aldaketa iritsi baino lehen beste ordenagailu batean izen zaharra
  idazten bada, bikoiztu daiteke; konpontzeko, editatu partida eta hautatu zerrendako jokalaria.
* **Hedapen berri bat** atera bada, fakzio berriak gehi daitezke; fitxategian bidaiatzen dute
  besteekin batera.
* **Ohitura ona**: partida gau baten ondoren, batek esportatu eta taldeko txatera bidali.
  Besteek inportatu eta denek berdina dute. Ez du axola nork esportatzen duen.
* **Bi ordenagailu proban**, makina berean:

  ```bash
  DB_FILE=/tmp/a.db KONFIG_DIR=/tmp/konfA PORT=3000 python3 app.py
  DB_FILE=/tmp/b.db KONFIG_DIR=/tmp/konfB PORT=3001 python3 app.py
  ```

* **Denek berdina duzuen egiaztatzeko**: Sinkronizazioa atalean agertzen den
  *erregistroaren hatz-marka* berdina izan behar da ordenagailu guztietan.
