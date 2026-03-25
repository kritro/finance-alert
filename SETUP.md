# Finance Alert Bot – Oppsett og oversikt

## Telegram-botter

| Bot | Brukernavn | Funksjon |
|---|---|---|
| **TrondAlertBot** | @Oilalerttrondbot | Push-varsler (nyheter, prisendringer, Trump) |
| **TrondInfoBot** | @Trondinfobot | On-demand kommandoer (/price, /bårdfjord, etc.) |

## Kommandoer (TrondInfoBot)

| Kommando | Beskrivelse |
|---|---|
| `/price` eller `pris` | Nåværende Brent-oljepris |
| `/bårdfjord` | Vind og temperatur på Bårdfjordneset |
| `/status` | Bot-statistikk |
| `/help` | Liste over kommandoer |

## Push-varsler (TrondAlertBot)

Boten sender automatiske varsler for:

- **Oljerelevante nyheter** – Score ≥ 40/100 fra 11 RSS-feeds
- **Brent prisendring** – Varsel ved ±$3.00 bevegelse
- **Trump Truth Social** – Oljerelevante poster + daglig digest av alle poster
- **Morgenrapport** – Brent-pris kl 08:00 norsk tid
- **Ettermiddagsrapport** – Brent-pris kl 16:00 norsk tid

## Nyhetskilder (RSS)

| Kilde | Feed |
|---|---|
| OilPrice.com | oilprice.com/rss/main |
| CNBC Energy | cnbc.com energy feed |
| CNBC Business | cnbc.com business feed |
| Al Jazeera | aljazeera.com/xml/rss/all.xml |
| Guardian Energy | theguardian.com energy RSS |
| Middle East Eye | middleeasteye.net/rss |
| Yahoo Finance (XLE) | Energy ETF nyheter |
| Yahoo Finance (Brent) | BZ=F nyheter |
| NGI | naturalgasintel.com/feed |
| Hellenic Shipping | hellenicshippingnews.com/feed |
| Financial Times | ft.com RSS |
| Trump Truth Social | trumpstruth.org/feed |

## Railway-variabler

| Variabel | Verdi | Beskrivelse |
|---|---|---|
| `TELEGRAM_TOKEN` | `8658424510:AAHHp2k-...` | Alert-bot token |
| `TELEGRAM_CHAT_ID` | `5185818616` | Din chat ID |
| `INFO_BOT_TOKEN` | `8745637212:AAEx2Lrz...` | Info-bot token |
| `POLL_INTERVAL_SECONDS` | `30` | Polling-intervall |
| `SCORE_THRESHOLD` | `40` | Relevansscore-terskel (0-100) |
| `PRICE_ALERT_THRESHOLD` | `3.0` | Prisendring i USD for varsel |
| `MAX_ALERTS_PER_RUN` | `8` | Maks varsler per kjøring |
| `INCLUDE_NITTER` | `true` | Twitter via Nitter (ofte nede) |
| `DATA_DIR` | `/data` | Persistent volum for seen.json |

## Prosjektstruktur

```
oil-alerts/
├── main.py          # Hovedloop, scheduler, planlagte rapporter
├── sources.py       # RSS-feeds + Trump Truth Social + Nitter
├── filter.py        # Nøkkelordbasert relevansscoring (0-100)
├── price.py         # Brent-pris fra Yahoo Finance
├── weather.py       # Vind fra Yr.no (Bårdfjordneset)
├── telegram.py      # Telegram API, meldinger, kommandolytter
├── seen.py          # Deduplisering (persistent JSON)
├── Dockerfile       # Container-konfig
├── railway.toml     # Railway deploy-konfig
├── requirements.txt # Python-avhengigheter
└── .env.example     # Mal for lokale miljøvariabler
```

## Tuning

### Justere nyhetsterskel
- `SCORE_THRESHOLD=30` → Flere varsler, bredere fangst
- `SCORE_THRESHOLD=50` → Strengere, kun tydelig oljerelevante
- `SCORE_THRESHOLD=70` → Kun de mest direkte oljepris-artiklene

### Justere prisvarsel
- `PRICE_ALERT_THRESHOLD=2.0` → Mer sensitive prisvarsler
- `PRICE_ALERT_THRESHOLD=5.0` → Kun store bevegelser

### Legge til egne nøkkelord
Rediger `filter.py` – legg til i relevant gruppe med vekt 1-30.

### Legge til egne RSS-feeds
Rediger `sources.py` – legg til i `RSS_FEEDS`-dictet.

## Feilsøking

- **Ingen varsler:** Sjekk `SCORE_THRESHOLD`, prøv lavere verdi
- **Duplikater etter redeploy:** Sjekk at `DATA_DIR=/data` og volum er montert
- **Bot svarer ikke på kommandoer:** Sjekk `INFO_BOT_TOKEN` og at du skriver til @Trondinfobot
- **Nitter nede:** Normalt – cloud-servere blokkeres ofte. RSS-feeds dekker det meste
