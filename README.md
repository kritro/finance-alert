# 🛢️ Oljepris-varsler via Telegram

En lett Python-bot som overvåker internasjonale nyhetskilder og sender deg Telegram-varsler
når oljeprissensitive nyheter publiseres – geopolitikk, OPEC-beslutninger, Hormuz-spenninger, Iran-sanksjoner og mer.

**Ingen API-nøkler nødvendig** (bortsett fra Telegram-boten). Gratis å kjøre på Railway.

---

## Hva den overvåker

**RSS-feeds (oppdateres automatisk):**
- Reuters Business / Energy
- AP News (Business + World)
- OilPrice.com
- S&P Global / Platts Commodity Insights
- OPEC pressemeldinger
- Al Jazeera (Midtøsten)
- EIA (U.S. Energy Information Administration)
- Rigzone
- Financial Times
- The Guardian Energy

**Twitter/X via Nitter RSS (ingen API-nøkkel):**
- Søk: `brent crude`, `oil price`, `OPEC production`, `Iran sanctions oil`, `Hormuz strait`, ...
- Kontoer: `@OilPrice_com`, `@EIAgov`, `@OPECSecretariat`, `@RigzoneNews`

---

## Oppsett (ca. 10 minutter)

### Steg 1 – Opprett Telegram-bot (2 min)

1. Åpne Telegram og søk etter **@BotFather**
2. Send `/newbot`
3. Velg et navn (f.eks. `Min Oljepris Bot`)
4. Velg et brukernavn (f.eks. `min_oil_alert_bot`)
5. BotFather gir deg et **token** som ser slik ut: `1234567890:ABCdef...`
6. **Kopier tokenet** – du trenger det senere

### Steg 2 – Finn din Chat ID (1 min)

1. Start din nye bot i Telegram: søk etter den og send `/start`
2. Kjør dette lokalt:
   ```bash
   TELEGRAM_TOKEN=<ditt-token> python telegram.py
   ```
3. Du får din **Chat ID** – kopier den

### Steg 3 – Test lokalt (valgfritt)

```bash
# Klon/naviger til mappen
cd oil-alerts

# Installer avhengigheter
pip install -r requirements.txt

# Kopier og fyll inn .env
cp .env.example .env
# Rediger .env med din TELEGRAM_TOKEN og TELEGRAM_CHAT_ID

# Start boten
python main.py
```

Du skal se logmeldinger og motta en oppstartsmelding på Telegram.

---

## Deploy på Railway (gratis, alltid på)

Railway gir 750 gratis CPU-timer per måned – nok til å kjøre én app 24/7 for alltid.

### Steg 1 – Opprett GitHub-repo

```bash
cd oil-alerts
git init
git add .
git commit -m "Initial commit"
```

Opprett et **privat** repo på [github.com/new](https://github.com/new) og push:
```bash
git remote add origin https://github.com/DITT-BRUKERNAVN/oil-alerts.git
git push -u origin main
```

> ⚠️ Pass på at `.env` er i `.gitignore` (den er det allerede om du bruker filen under)

### Steg 2 – Opprett Railway-prosjekt

1. Gå til [railway.app](https://railway.app) og logg inn med GitHub
2. Klikk **New Project → Deploy from GitHub repo**
3. Velg `oil-alerts`-repoet ditt
4. Railway oppdager automatisk Python og kjører `python main.py` (via `railway.toml`)

### Steg 3 – Sett miljøvariabler i Railway

I Railway-dashboardet, gå til **Variables** og legg til:

| Variabel | Verdi |
|---|---|
| `TELEGRAM_TOKEN` | Tokenet fra BotFather |
| `TELEGRAM_CHAT_ID` | Din Chat ID |
| `POLL_INTERVAL_MINUTES` | `5` (valgfritt) |
| `SCORE_THRESHOLD` | `40` (valgfritt) |

### Steg 4 (valgfritt) – Persistent lagring

For at boten skal huske sendte artikler på tvers av restarter:

1. I Railway: **Add a Volume**, mount den på `/data`
2. Legg til variabel: `DATA_DIR=/data`

Uten dette vil boten "glemme" ved restart og potensielt sende duplikater.

### Steg 5 – Deploy

Railway deployer automatisk når du pusher til `main`-branchen.
Sjekk **Deployments → Logs** for å se at boten kjører.

---

## Tuning

### Justere terskelverdi

I `.env` eller Railway-miljøvariabler:
```
SCORE_THRESHOLD=50   # Strengere: færre, men mer relevante varsler
SCORE_THRESHOLD=30   # Løsere: flere varsler
```

### Se hvilke nøkkelord som trigget

```
DEBUG_SCORING=true
```

Logger alle artikler over terskelen med hvilke nøkkelord som matchet.

### Deaktivere Nitter/Twitter

```
INCLUDE_NITTER=false
```

### Legge til egne RSS-feeds

Åpne `sources.py` og legg til en ny linje i `RSS_FEEDS`-diktet:
```python
"Min kilde": "https://eksempel.no/rss.xml",
```

### Legge til egne nøkkelord

Åpne `filter.py` og legg til i den relevante gruppen. Vekten er 1–30.

---

## Prosjektstruktur

```
oil-alerts/
├── main.py          # Hovedloop og scheduler
├── sources.py       # RSS-henting fra alle kilder + Nitter
├── filter.py        # Nøkkelordbasert relevansscoring (0–100)
├── telegram.py      # Sender varsler via Telegram Bot API
├── seen.py          # Husker allerede-sendte artikler (JSON-fil)
├── requirements.txt # feedparser + python-dotenv
├── railway.toml     # Railway deploy-konfig
├── .env.example     # Mal for miljøvariabler
└── .gitignore
```

---

## .gitignore

Opprett `.gitignore` med følgende innhold:
```
.env
data/
__pycache__/
*.pyc
.DS_Store
```

---

## Feilsøking

**Boten starter men sender ingen varsler:**
- Sjekk `SCORE_THRESHOLD` – prøv å sette den lavere (f.eks. 20) midlertidig
- Aktiver `DEBUG_SCORING=true` for å se scoring
- Noen RSS-feeds kan være nede – det er normalt

**`Invalid token` fra Telegram:**
- Kopier tokenet på nytt fra BotFather – unngå mellomrom

**`Chat not found`:**
- Sørg for at du har sendt `/start` til boten din i Telegram

**Nitter fungerer ikke:**
- Nitter-instanser er tidvis nede. Boten faller automatisk tilbake til kun RSS.
- Sett `INCLUDE_NITTER=false` for å deaktivere helt

---

## Utvidelsesmuligheter

- [ ] Legg til OpenAI for smartere sammendrag (GPT-3.5 er billig)
- [ ] Overvåk Truth Social via RSS
- [ ] Daglig oppsummering (kl. 08:00)
- [ ] Filtrer på spesifikke prisbevegelser (hent Brent-pris fra API)
- [ ] Slack-varsler i tillegg til Telegram
