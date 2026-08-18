# 🌲 Root Erregistroa

Root mahai-jokoaren partiden erregistroa, **zerbitzaririk gabe** sinkronizatzen dena
taldeko ordenagailu guztien artean, eta babeskopia automatikoekin.

* Partidak sartu, **editatu** eta ezabatu: data, mapa, karta sorta, jokalari bakoitzaren
  fakzioa, puntuak eta garaipen mota, Vagabond-en **pertsonaia** (Thief, Ranger…),
  erabilitako **mertzenarioak** (Hirelings) eta **leku bereziak** (Landmarks).
* Jokoaren izen guztiak **ingelesez, kartetan bezala** (interfazea euskaraz).
* Estatistikak: jokalarien sailkapena, fakzioen irabazte-tasak, jokalari bakoitzak zein
  fakziorekin jokatzen duen ondoen, eta mertzenario/leku erabilienak.
* **Sinkronizazioa zerbitzaririk gabe**: sare lokalean automatikoki, edo fitxategi zifratu
  baten bidez (USB, posta, hodeia) urrutitik.
* **Babeskopiak**: automatikoak, aldaketa arriskutsuen aurretik, eta eskuz.

---

## Instalazioa

Dependentzia guztiak Debian 13-n instalatuta datoz jada. Bestela:

```bash
sudo apt install python3-flask python3-cryptography
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
| `SYNC_PORT` | Sinkronizazioaren portua (lehenetsia: 47778) |
| `GAILU_IZENA` | Gailu honen izena kideen zerrendan |

---

## Taldea sortzea eta besteak elkartzea

1. **Sinkronizazioa** atalean, idatzi **taldearen izena** eta **pasaesaldi bat**.
2. Lagun bakoitzak gauza bera egiten du bere ordenagailuan: **izen eta pasaesaldi berak**.
3. Berrabiarazi aplikazioa (LAN zerbitzua abiarazteko).

Hori da dena. Ez dago konturik, ez zerbitzaririk, ez erregistratzerik: izen eta pasaesaldi
beretik gako berbera eratortzen da ordenagailu guztietan, eta gako hori dutenek bakarrik
ulertzen dute elkar.

> **Pasaesaldia ahoz eman lagunei** (edo paperean). Ez bidali erregistroa sinkronizatzeko
> erabiliko duzun bide beretik.

### Nola sinkronizatzen den

* **Sare berean bazaudete** (adib. partida bat jokatzen ari zarete): aplikazioek elkar
  aurkitzen dute automatikoki eta 20 segundoro sinkronizatzen dira. `Orain sinkronizatu`
  botoiak berehala egiten du.
* **Urrun bazaude**: `Esportatu .rootsync` botoiak fitxategi zifratu bat sortzen du.
  Bidali nahi duzun bidetik (USB, Telegram, posta, Nextcloud) eta besteak `Inportatu`
  botoiarekin sartzen du. Fitxategiak ez du ezer ezabatzen: gehitu baino ez du egiten.

Bi bideek gauza bera erabiltzen dute barnean, eta biak dira **norabide bikoak**: partidak
zeinek sartu dituen axola gabe, denek dena amaitzen dute edukitzen.

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

### Zergatik ez den ezer galtzen

Datuak ez dira "azken bertsioak irabazi" moduan gainidazten. Aldaketa bakoitza **gertaera
bat** da (partida bat gehitu, aldatu, ezabatu), identifikatzaile bakar batekin. Bi
ordenagailu bateratzean, gertaeren batuketa egiten da:

* Ordenak ez du axola: gertaerak edozein ordenatan iritsita ere emaitza berbera da.
* Errepikatzeak ez du kalterik: fitxategi bera hamar aldiz inportatzeak ez du ezer bikoizten.
* Bi lagunek partida bera aldatzen badute konexiorik gabe, biek emaitza **berbera** ikusiko
  dute bateratu ondoren (ez bata bat eta bestea beste bat).

Erregistroa osorik gordetzen denez, `Erregistrotik berreraiki` botoiak taula guztiak
zerotik sortzen ditu zerbait arraro ikusiz gero.

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
* **Ordenagailutik kanpo gordetzeko**, erabili `Esportatu .rootsync`: zifratuta dagoenez,
  hodeian edo posta batean uztea arriskurik gabea da.

Leheneratzeak uneko egoeraren kopia bat egiten du beti aurretik, beraz leheneratze oker
batek ere ez du ezer galtzen.

---

## Segurtasuna

Kontuan hartutakoa:

| Arriskua | Babesa |
|---|---|
| Wifiko besteek zure partidak irakurtzea | ChaCha20-Poly1305 zifratzea; gakorik gabe ezer ez |
| Datuak bidean aldatzea | AEAD osotasun-etiketa: byte bat aldatuta, fardela baztertu egiten da |
| Fardel zahar bat berriro bidaltzea | Nonce bakarra + ±10 minutuko leihoa |
| Beste webgune batek zure aplikazio lokalari eskaerak egitea | Saio-tokena + `Origin`/`Host` egiaztapena |
| Aplikazioa sareari zabalik egotea | Interfazea **127.0.0.1**-en soilik; kanpora `POST /sync` bakarrik |
| Datu okerrak sinkronizazioan | Gertaera bakoitza balidatu egiten da datu-basera iritsi aurretik |
| Fitxategi-izen maltzurrak babeskopietan | Izen-eredu zorrotza; karpetatik kanpoko bideak baztertuta |
| Konpresio-bonbak | Deskonpresio mugatua |
| Pasaesaldi ahulak indarrez asmatzea | scrypt (2¹⁷ · 8 · 1, ~134 MB saiakera bakoitzeko) |

**Zer EZ du babesten** (aukeratutako eredua "pasaesaldia bakarrik" da): taldeko pasaesaldia
duen edonork partidak sor edo alda ditzake beste edonoren izenean, eta ezin da frogatu nork
egin duen. Talde txiki eta fidagarri batentzat nahikoa da. Bermea handiagoa nahi izanez gero,
gertaera bakoitzari gailuaren sinadura (Ed25519) gehitzea da hurrengo urratsa: formatuak
`sinadura` eremua **erreserbatuta** du hasieratik, beraz gehitzean ez da ezer hautsiko eta
datu zaharrek balio izaten jarraituko dute.

Taldearen gakoa `~/.config/root-erregistroa/talde.json`-en gordetzen da, `0600` baimenekin.
Pasaesaldia bera ez da inoiz gordetzen. Zure kontuan sartzeko modua duen norbaitek gakoa
irakur dezake — hori ekiditeko modu bakarra abio bakoitzean pasaesaldia eskatzea litzateke,
eta mahai-joko baten erregistro batentzat ez du merezi.

### Suebakia

LAN sinkronizazioak bi portu behar ditu sare lokalean:

```bash
sudo ufw allow from 192.168.0.0/16 to any port 47777 proto udp   # aurkikuntza
sudo ufw allow from 192.168.0.0/16 to any port 47778 proto tcp   # trukea
```

Interfazearen portua (3000) **ez da inoiz** kanpora zabaldu behar.

---

## Egitura

| Fitxategia | Zertarako |
|---|---|
| `app.py` | Interfaze lokala eta APIa (127.0.0.1) |
| `gertaerak.py` | Gertaera-erregistroa: balidazioa, bateratzea, proiekzioak |
| `kripto.py` | `.rootsync` fardela: scrypt, ChaCha20-Poly1305, mugak |
| `sinkro.py` | Taldea eta sinkronizazio-protokoloa |
| `sarea.py` | LAN aurkikuntza eta trukea |
| `babeskopiak.py` | Kopiak, atxikitzea, leheneratzea |
| `estatistikak.py` | Kontsultak |
| `db.py`, `eskema.sql` | Datu-basea eta hazi-datuak (fakzioak, mapak, mertzenarioak, lekuak) |
| `static/index.html` | Interfaze osoa (dependentziarik gabe) |

Testak:

```bash
python3 -m pytest tests/ -q
```

---

## Ohar praktikoak

* **Jokalari beraren izena bi ordenagailutan**: identifikatzailea izenetik eratortzen da,
  beraz "Oier" bi lekutan sartzeak jokalari bakarra sortzen du bateratzean. Hala ere, jokalari
  bati izena aldatu eta aldaketa iritsi baino lehen beste ordenagailu batean izen zaharra
  idazten bada, bikoiztu daiteke; konpontzeko, editatu partida eta hautatu zerrendako jokalaria.
* **Hedapen berri bat** atera bada, fakzio berriak gehi daitezke; sinkronizatu egiten dira
  beste guztiekin.
* **Bi ordenagailu proban**, makina berean:

  ```bash
  DB_FILE=/tmp/a.db KONFIG_DIR=/tmp/konfA PORT=3000 SYNC_PORT=47778 python3 app.py
  DB_FILE=/tmp/b.db KONFIG_DIR=/tmp/konfB PORT=3001 SYNC_PORT=47779 python3 app.py
  ```

* **Sinkronizatuta zaudeten egiaztatzeko**: Sinkronizazioa atalean agertzen den
  *erregistroaren hatz-marka* berdina izan behar da ordenagailu guztietan.
