# 🛢️ Finance Alert + Info Bot

To Telegram-botter bygget i Python:
- **@TrondAlertBot** – Push-varsler for oljeprissensitive nyheter, prisendringer og Trump Truth Social
- **@Trondinfobot** – On-demand info med 32 kommandoer (GPS, webkameraer, vær, geologi, moro)

Deployet på Railway (gratis tier), poller hvert 30. sekund.

---

## Alert-boten (@TrondAlertBot)

Sender automatiske varsler til Telegram for:

| Varsel | Beskrivelse |
|---|---|
| 📰 Oljerelevante nyheter | Score ≥ 40/100 fra 11 RSS-feeds |
| 📈 Brent prisendring | Varsel ved ±$3.00 bevegelse |
| 🇺🇸 Trump Truth Social | Oljerelevante poster + daglig digest |
| 🕐 Morgenrapport 08:00 | Brent-pris norsk tid |
| 🕐 Ettermiddagsrapport 16:00 | Brent-pris norsk tid |

### Nyhetskilder (RSS)

OilPrice.com, CNBC Energy, CNBC Business, Al Jazeera, Guardian Energy, Middle East Eye, Yahoo Finance (XLE + Brent), NGI, Hellenic Shipping, Financial Times, Trump Truth Social.

### Filtrering

Nøkkelordbasert relevansscoring (0–100) med 60+ nøkkelord i kategorier:
- Kjerneord: brent, crude, oil price, barrel, OPEC
- Geopolitikk: Iran, Hormuz, sanctions, tanker, pipeline
- Politikk: Trump, sanctions, embargo, nuclear deal
- Marked: surge, spike, slump, futures, volatility

Negativt filter for irrelevante treff (olive oil, cooking oil, etc.)

---

## Info-boten (@Trondinfobot)

32 kommandoer med instant svar. GPS-kommandoer bruker telefonens posisjon.

### 📍 GPS-basert

| Kommando | API | Beskrivelse |
|---|---|---|
| `/buss` | Entur | Nærmeste holdeplass + neste avganger |
| `/dyr` | GBIF | Dyreobservasjoner i nærheten |
| `/luft` | Open-Meteo | Luftkvalitet (PM2.5, PM10, NO₂, O₃) |
| `/lading` | Open Charge Map | Nærmeste elbil-ladere med kW |
| `/uv` | Open-Meteo | UV-indeks med solråd |
| `/navn` | SSB + Kartverket | Populære babynavn i ditt fylke |
| `/webcam` | Yr.no | Nærmeste webkamera |
| `/geologi` | Macrostrat | Bergarter og mineraler under deg |

### 📷 Webkameraer

| Kommando | Sted |
|---|---|
| `/tønsbergbåt` | Ollebukta marina, Tønsberg |
| `/tønsbergilene` | Fuglekamera Ilene (YouTube live) |
| `/sotrabro` | Sotrabrua vest (Yr.no/Vegvesen) |
| `/alta` | Alta havn 360° panorama (5 deler) |
| `/talvik` | Talvik, Altafjorden |
| `/sørøya` | Breivikbotn, Sørøya |
| `/bergenfløyen` | Fløyen, Bergen |
| `/bergenulriken` | Ulriken, Bergen |
| `/bergenpuddefjord` | Puddefjordsbroen, Bergen |
| `/bergenhavn` | Bergen havn |
| `/oslorådhus` | Rådhuskaia, Oslo |

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
| `/navnoslo` | SSB | Topp babynavn Oslo |
| `/navnvestland` | SSB | Topp babynavn Vestland |
| `/navnfinnmark` | SSB | Topp babynavn Finnmark |
| `/iss` | Where the ISS At | ISS-posisjon og avstand |
| `/nordlys` | NOAA SWPC | Aurora Kp-indeks og synlighet |
| `/romfart` | Beregnet | Reist gjennom verdensrommet i dag |
| `/fakta` | Useless Facts + MyMemory | Tilfeldig fakta oversatt til norsk |
| `/andreasnese` | – | 👃 |

---

## Prosjektstruktur

```
oil-alerts/
├── main.py            # Hovedloop, scheduler, planlagte rapporter
├── sources.py         # RSS-feeds + Trump Truth Social + Nitter
├── filter.py          # Nøkkelordbasert relevansscoring (0-100)
├── price.py           # Brent-pris fra Yahoo Finance
├── telegram.py        # Telegram API, meldinger, kommandolytter (1100+ linjer)
├── weather.py         # Vind fra Yr.no (Bårdfjordneset)
├── fun.py             # ISS, nordlys, romfart, fakta
├── gps_commands.py    # GPS: buss, luft, lading, UV, geologi, navn
├── seen.py            # Deduplisering (persistent JSON)
├── andreasnese.png    # 👃
├── Dockerfile         # Container-konfig
├── railway.toml       # Railway deploy-konfig
├── requirements.txt   # feedparser + Pillow
└── .env.example       # Mal for miljøvariabler
```

---

## Oppsett

### Telegram-botter

| Bot | Brukernavn | Funksjon |
|---|---|---|
| TrondAlertBot | @Oilalerttrondbot | Push-varsler |
| TrondInfoBot | @Trondinfobot | On-demand kommandoer |

### Railway-variabler

| Variabel | Beskrivelse |
|---|---|
| `TELEGRAM_TOKEN` | Alert-bot token |
| `TELEGRAM_CHAT_ID` | Din chat ID |
| `INFO_BOT_TOKEN` | Info-bot token |
| `POLL_INTERVAL_SECONDS` | Polling-intervall (default: 30) |
| `SCORE_THRESHOLD` | Nyhets-terskel 0-100 (default: 40) |
| `PRICE_ALERT_THRESHOLD` | Prisendring USD (default: 3.0) |
| `MAX_ALERTS_PER_RUN` | Maks varsler per kjøring (default: 8) |
| `INCLUDE_NITTER` | Twitter via Nitter (default: true) |
| `DATA_DIR` | Persistent volum sti (default: ./data) |

### Deploy

1. Push til GitHub → Railway deployer automatisk
2. Railway volum montert på `/data` for persistent lagring
3. Dockerfile-basert deploy (ikke Nixpacks)

---

## API-er brukt (alle gratis, ingen nøkkel)

| API | Brukt til |
|---|---|
| Yr.no | Vær, webkameraer, sjøtemperatur |
| Yahoo Finance | Brent-oljepris |
| Entur | Kollektivtransport |
| Open-Meteo | Luftkvalitet, UV-indeks |
| Open Charge Map | Elbil-ladere |
| GBIF | Artsobs |
| Macrostrat | Geologi |
| NOAA SWPC | Aurora/nordlys Kp-indeks |
| Where the ISS At | ISS-posisjon |
| FHI Statistikk | Helsedata per fylke |
| SSB | Navnestatistikk |
| Kartverket | Kommune fra GPS |
| MyMemory | Oversettelse til norsk |
| Useless Facts | Tilfeldige fakta |
| Trump Truth Social | Trumps poster |
| Telegram Bot API | Meldinger og kommandoer |

---

## Legge til nye kommandoer

### Nytt webkamera (1 linje)
I `telegram.py`, legg til i `run_command_listener`:
```python
elif text in ("/mittsted",):
    _handle_webcam_url_command(token, chat_id, "https://url-til-bilde.jpg", "📷 Mitt sted")
```

### Ny GPS-kommando
1. Lag funksjonen i `gps_commands.py`
2. Legg til kommando-trigger i `telegram.py` med `_pending_location`
3. Legg til routing i GPS-handleren

### Ny YouTube live-kamera
```python
elif text in ("/kanal",):
    _handle_youtube_live_command(token, chat_id, "@youtube_kanal", "📷 Beskrivelse")
```
