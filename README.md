# 🛢️ Finance Alert + Info Bot

To Telegram-botter + en PWA, bygget i Python og deployet på Railway.

- **@TrondAlertBot** – Push-varsler for oljeprissensitive nyheter og prisendringer
- **@Trondinfobot** – On-demand info via Telegram (30+ kommandoer)
- **PWA** – Mobilapp (legg til hjemskjerm) på `finance-alert-production.up.railway.app`

---

## Alert-boten (@TrondAlertBot)

Sender automatiske varsler til Telegram for:

| Varsel | Beskrivelse |
|---|---|
| 📰 Oljerelevante nyheter | Score ≥ `SCORE_THRESHOLD`/100 fra 11 RSS-feeds |
| 📈 Brent prisendring | Varsel ved ± `PRICE_ALERT_THRESHOLD` USD |
| 🇺🇸 Trump Truth Social | Oljerelevante poster |
| 🕐 Morgenrapport 08:00 | Brent-pris (norsk tid) |
| 🕐 Ettermiddagsrapport 16:00 | Brent-pris (norsk tid) |

### Nyhetskilder (RSS)

OilPrice.com, CNBC Energy, CNBC Business, Al Jazeera, Guardian Energy, Middle East Eye, Yahoo Finance (XLE + Brent), NGI, Hellenic Shipping, Financial Times, Trump Truth Social.

### Filtrering

Nøkkelordbasert relevansscoring (0–100) med 60+ nøkkelord:
- **Kjerneord:** brent, crude, oil price, barrel, OPEC
- **Geopolitikk:** Iran, Hormuz, sanctions, tanker, pipeline
- **Marked:** surge, spike, slump, futures, volatility

Negativt filter fjerner irrelevante treff (olive oil, cooking oil, etc.)

---

## Info-boten (@Trondinfobot)

On-demand kommandoer. GPS-kommandoer ber om posisjon via Telegram.

### 📍 GPS-basert

| Kommando | API | Beskrivelse |
|---|---|---|
| `/buss` | Entur | Nærmeste holdeplass + neste avganger |
| `/dyr` | GBIF | Dyreobservasjoner i nærheten |
| `/luft` | Open-Meteo | Luftkvalitet (PM2.5, PM10, NO₂, O₃) |
| `/lading` | OpenStreetMap Overpass | Nærmeste elbil-ladere |
| `/uv` | Open-Meteo | UV-indeks med solråd |
| `/navn` | SSB + Kartverket | Populære babynavn i ditt fylke |
| `/webcam` | Yr.no | Nærmeste webkamera |
| `/geologi` | Macrostrat | Bergarter og mineraler under deg |
| `/iss` | Where the ISS At | ISS-posisjon og avstand fra deg |
| `/nordlys` | NOAA SWPC | Aurora Kp-indeks tilpasset din breddegrad |

### 📷 Webkameraer

| Kommando | Sted |
|---|---|
| `/tønsbergbåt` | Ollebukta marina, Tønsberg |
| `/tønsbergilene` | Fuglekamera Ilene (YouTube live) |
| `/sotrabro` | Sotrabrua vest (Yr.no) |
| `/vidden` | Vidden, Bergen (Yr.no) |
| `/bergenulriken` | Ulriken, Bergen |
| `/bergenhavn` | Bergen havn |
| `/oslorådhus` | Rådhuskaia, Oslo |
| `/alta` | Alta havn 360° panorama |
| `/talvik` | Talvik, Altafjorden |
| `/sørøya` | Breivikbotn, Sørøya |

### 🌍 Vær

| Kommando | API | Beskrivelse |
|---|---|---|
| `/tønsberg` | Yr.no | Vær, vind og sjøtemperatur |
| `/bårdfjord` | Yr.no | Vindstyrke og temperatur Bårdfjordneset |

### 📊 Info og moro

| Kommando | API | Beskrivelse |
|---|---|---|
| `/price` | Yahoo Finance | Brent-oljepris med endring |
| `/bmi` | FHI | Overvekt-statistikk per fylke (17-åringer) |
| `/navn` + region | SSB | Topp babynavn for Oslo / Vestland / Finnmark |
| `/romfart` | Beregnet | Reist gjennom verdensrommet i dag |
| `/fakta` | Useless Facts + MyMemory | Tilfeldig fakta oversatt til norsk |
| `/andreasnese` | – | 👃 |

---

## PWA (mobil-app)

Tilgjengelig på `finance-alert-production.up.railway.app` – legg til på hjemskjermen.

### Faner

| Fane | Innhold |
|---|---|
| 📊 Info | GPS-kommandoer, Generelt, Skarverennet, Babynavn |
| 📷 Kamera | Webkameraer med auto-refresh |
| 📺 Live | Port of Alta panorama (kystnor.no), Fuglekamera Ilene |
| ✉️ Be om ny | Innsending av feature requests → @TrondRequestBot |

### Skarverennet-resultater

Boks under Info-fanen. Viser resultater for 6 familiemedlemmer (Trond, Øyvind, Simen, Andreas, Dagny, Maria) fra 2022 og utover. Henter data fra eqtiming API og cacher permanent i `/data/skarverennet_cache.json` — kun nye renn trigger eqtiming-kall.

### Feature requests

Sendes via tekstboks i PWA → `POST /api/feature` → lagres i `/data/feature_requests.log` + varsles via **@TrondRequestBot** på Telegram.

---

## Prosjektstruktur

```
oil-alerts/
├── main.py            # Hovedloop, scheduler, planlagte rapporter
├── sources.py         # RSS-feeds + Trump Truth Social + Nitter
├── filter.py          # Nøkkelordbasert relevansscoring (0–100)
├── price.py           # Brent-pris fra Yahoo Finance
├── telegram.py        # Telegram API, 30+ kommandoer (~1100 linjer)
├── api.py             # FastAPI HTTP-backend for PWA (~620 linjer)
├── weather.py         # Vind fra Yr.no (Bårdfjordneset)
├── fun.py             # ISS, nordlys, romfart, fakta
├── gps_commands.py    # GPS-baserte kommandoer
├── seen.py            # Deduplisering (persistent JSON)
├── andreasnese.png    # 👃
├── pwa/
│   ├── index.html     # Komplett PWA (single file, ~600 linjer)
│   ├── sw.js          # Service worker med network-first for HTML
│   └── manifest.json  # PWA-manifest
├── Dockerfile
├── railway.toml
└── requirements.txt
```

---

## Oppsett

### Botter

| Bot | Brukernavn | Funksjon |
|---|---|---|
| @TrondAlertBot | Alert-bot | Push-varsler olje |
| @Trondinfobot | Info-bot | On-demand kommandoer |
| @TrondRequestBot | Request-bot | Mottar feature requests fra PWA |

### Railway-variabler

| Variabel | Beskrivelse |
|---|---|
| `TELEGRAM_TOKEN` | Alert-bot token |
| `TELEGRAM_CHAT_ID` | Din chat ID |
| `INFO_BOT_TOKEN` | Info-bot token |
| `REQUEST_BOT_TOKEN` | Request-bot token (@TrondRequestBot) |
| `SCORE_THRESHOLD` | Nyhets-terskel 0–100 |
| `PRICE_ALERT_THRESHOLD` | Prisendring USD for varsel (default: 3.0) |
| `MAX_ALERTS_PER_RUN` | Maks varsler per kjøring (default: 8) |
| `POLL_INTERVAL_MINUTES` | Polling-intervall minutter (default: 5) |
| `INCLUDE_NITTER` | Twitter via Nitter (default: true) |
| `DATA_DIR` | Persistent volum-sti (default: ./data) |

### Persistent lagring (`/data`)

| Fil | Innhold |
|---|---|
| `seen_articles.json` | Sette artikler (deduplisering) |
| `feature_requests.log` | Innsendte feature requests |
| `skarverennet_cache.json` | Cachet Skarverennet-resultater |

### Deploy

GitHub push → `railway up --service finance-alert` (GitHub webhook ikke konfigurert — kjør manuelt)

---

## API-er brukt

| API | Brukt til | Nøkkel |
|---|---|---|
| Yr.no | Vær, webkameraer, sjøtemperatur | Nei |
| Yahoo Finance | Brent-oljepris | Nei |
| Entur | Kollektivtransport | Nei |
| Open-Meteo | Luftkvalitet, UV-indeks | Nei |
| OpenStreetMap Overpass | Elbil-ladere | Nei |
| GBIF | Artsobs | Nei |
| Macrostrat | Geologi | Nei |
| NOAA SWPC | Aurora/nordlys Kp-indeks | Nei |
| Where the ISS At | ISS-posisjon | Nei |
| FHI Statistikk | Helsedata per fylke | Nei |
| SSB | Navnestatistikk | Nei |
| Kartverket | Kommune fra GPS | Nei |
| MyMemory | Oversettelse til norsk | Nei |
| Trump Truth Social | Trumps poster | Nei |
| eqtiming.com | Skarverennet-resultater | Nei |
| Telegram Bot API | Meldinger og kommandoer | Ja |

---

## Legge til nye kommandoer

### Nytt webkamera (1 linje i telegram.py)
```python
elif text in ("/mittsted",):
    _handle_webcam_url_command(token, chat_id, "https://url.jpg", "📷 Mitt sted")
```
Og i `WEBCAMS`-dict i `api.py` for PWA-støtte:
```python
"mittsted": {"name": "📷 Mitt sted", "url": "https://url.jpg"},
```

### Ny GPS-kommando
1. Lag funksjonen i `gps_commands.py`
2. Legg til trigger i `telegram.py` med `_pending_location`
3. Legg til routing i GPS-handleren i `telegram.py`
4. Legg til `@app.get("/api/kommando")` i `api.py`
5. Legg til knapp i `GPS_CMDS`-arrayen i `pwa/index.html`
