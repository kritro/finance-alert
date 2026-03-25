"""
main.py – Hovedloop for oljepris-varsel-boten.

Kjører hvert POLL_INTERVAL_SECONDS minutt og:
  1. Henter artikler fra alle RSS-feeds (og Nitter)
  2. Filtrerer på oljeprisrelevans
  3. Sender varsler for nye, relevante artikler
  4. Husker hva som allerede er sendt

Kjør lokalt:
    TELEGRAM_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python main.py

Deploy på Railway:
    Sett miljøvariablene i Railway-dashboardet og push til GitHub.
"""

import logging
import os
import sys
import time
from datetime import datetime

# ──────────────────────────────────────────────
# Konfigurasjon (leses fra miljøvariabler)
# ──────────────────────────────────────────────

TELEGRAM_TOKEN: str = ""
TELEGRAM_CHAT_ID: str = ""

# Hvor ofte vi sjekker (minutter)
POLL_INTERVAL_SECONDS: int = 30

# Score-terskel for varsler (0–100)
SCORE_THRESHOLD: int = 40

# Prisendring-terskel i USD (varsler ved ±denne endringen)
PRICE_ALERT_THRESHOLD: float = 3.0

# Maks varsler per kjøring (forhindrer spam ved oppstart)
MAX_ALERTS_PER_RUN: int = 8

# Om Nitter (Twitter) skal inkluderes
INCLUDE_NITTER: bool = True

# Debug-modus: vis scoring for alle artikler
DEBUG_SCORING: bool = False


def load_config():
    """Laster konfig."""
    global TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, POLL_INTERVAL_SECONDS
    global SCORE_THRESHOLD, PRICE_ALERT_THRESHOLD, MAX_ALERTS_PER_RUN
    global INCLUDE_NITTER, DEBUG_SCORING

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
    SCORE_THRESHOLD = int(os.getenv("SCORE_THRESHOLD", "40"))
    PRICE_ALERT_THRESHOLD = float(os.getenv("PRICE_ALERT_THRESHOLD", "3.0"))
    MAX_ALERTS_PER_RUN = int(os.getenv("MAX_ALERTS_PER_RUN", "8"))
    INCLUDE_NITTER = os.getenv("INCLUDE_NITTER", "true").lower() == "true"
    DEBUG_SCORING = os.getenv("DEBUG_SCORING", "false").lower() == "true"


# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if DEBUG_SCORING else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


# ──────────────────────────────────────────────
# Valider konfigurasjon
# ──────────────────────────────────────────────

def validate_config() -> bool:
    """Sjekker at nødvendige miljøvariabler er satt."""
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")

    if missing:
        logger.error(
            f"Mangler miljøvariabler: {', '.join(missing)}\n"
            f"Se .env.example for instruksjoner."
        )
        return False
    return True


# ──────────────────────────────────────────────
# Trump Truth Social digest
# ──────────────────────────────────────────────

def _format_trump_digest(posts: list) -> str:
    """Formaterer en oppsummering av alle Trumps poster i dag."""
    if not posts:
        return ""

    lines = [
        f"🇺🇸 TRUMP TRUTH SOCIAL – {len(posts)} nye poster i dag",
        "",
    ]

    for i, p in enumerate(posts, 1):
        # Bruk title, men klipp til 200 tegn
        text = p.title.strip()
        if not text or text.startswith("[No Title]"):
            text = p.summary.strip()
        if not text:
            text = "(bilde/video uten tekst)"
        # Fjern HTML-rester
        import re
        text = re.sub(r"<[^>]+>", "", text).strip()
        if len(text) > 200:
            text = text[:200] + "…"

        time_str = p.published.strftime("%H:%M") if p.published else ""
        lines.append(f"{i}. [{time_str}] {text}")
        lines.append("")

    lines.append("🔗 https://www.trumpstruth.org")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# En enkelt polling-kjøring
# ──────────────────────────────────────────────

def run_once(seen, prune_every: int = 20, _run_count: list = [0]) -> int:
    """
    Utfører én polling-syklus.
    Returnerer antall varsler sendt.
    """
    from sources import fetch_all
    from filter import filter_articles, explain_score
    from telegram import send_batch, _api_call
    from seen import SeenStore
    from price import check_price, format_price_alert

    _run_count[0] += 1
    logger.info(f"--- Kjøring #{_run_count[0]} startet {datetime.utcnow().strftime('%H:%M:%S')} UTC ---")

    sent = 0

    # ── Prissjekk ──
    try:
        snapshot = check_price(PRICE_ALERT_THRESHOLD)
        if snapshot:
            msg = format_price_alert(snapshot)
            result = _api_call(TELEGRAM_TOKEN, "sendMessage", {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg,
            })
            if result and result.get("ok"):
                sent += 1
                logger.info(f"Prisvarsel sendt: Brent ${snapshot.price:.2f} ({snapshot.change:+.2f})")
    except Exception as e:
        logger.error(f"Prissjekk feilet: {e}")

    # 1. Hent artikler + Trump-poster
    articles, trump_today = fetch_all(include_nitter=INCLUDE_NITTER)

    # ── Trump Truth Social ──
    # Oljerelevante poster → varsel som vanlig
    # Alle dagens poster → daglig oppsummering
    try:
        new_trump = [t for t in trump_today if not seen.has_seen(t.url)]
        if new_trump:
            from filter import filter_articles as _filter, score_article
            # Send oljerelevante Trump-poster som vanlige varsler
            trump_scored = _filter(new_trump, threshold=SCORE_THRESHOLD)
            for ts in trump_scored:
                from telegram import send_alert
                if send_alert(ts, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
                    sent += 1

            # Send oppsummering av ALLE nye Trump-poster (uavhengig av score)
            trump_summary = _format_trump_digest(new_trump)
            if trump_summary:
                _api_call(TELEGRAM_TOKEN, "sendMessage", {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": trump_summary,
                })

            seen.mark_seen_batch([t.url for t in new_trump])
    except Exception as e:
        logger.error(f"Trump-sjekk feilet: {e}")

    # 2. Hent nyhetsartikler
    if not articles:
        logger.warning("Ingen artikler hentet denne kjøringen")
        return sent

    # 2. Filtrer til kun usette artikler
    new_articles = [a for a in articles if not seen.has_seen(a.url)]
    logger.info(f"{len(new_articles)} nye (usette) av {len(articles)} totalt")

    if not new_articles:
        return sent

    # 3. Score og filtrer
    scored = filter_articles(new_articles, threshold=SCORE_THRESHOLD)

    if DEBUG_SCORING:
        for s in scored[:20]:
            logger.debug(explain_score(s))

    if not scored:
        logger.info("Ingen artikler passerte relevansterskelen denne kjøringen")
        return 0

    # 4. Send varsler
    sent = send_batch(scored, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, MAX_ALERTS_PER_RUN)

    # 5. Marker alt som sett (også de vi ikke sendte – de vil heller ikke bli bedre)
    seen.mark_seen_batch([a.url for a in new_articles])

    # 6. Rydd opp gamle oppføringer periodisk
    if _run_count[0] % prune_every == 0:
        seen.prune_old()

    logger.info(f"--- Kjøring #{_run_count[0]} ferdig. Sendte {sent} varsler ---")
    return sent


# ──────────────────────────────────────────────
# Hovedloop
# ──────────────────────────────────────────────

def main() -> None:
    from telegram import get_bot_info, send_startup_message
    from seen import get_store

    load_config()

    logger.info("=" * 60)
    logger.info("  Oljepris-varsel-bot starter")
    logger.info("=" * 60)

    if not validate_config():
        sys.exit(1)

    # Sjekk at Telegram-boten virker
    bot_info = get_bot_info(TELEGRAM_TOKEN)
    if not bot_info:
        logger.error("Klarte ikke koble til Telegram – sjekk TELEGRAM_TOKEN")
        sys.exit(1)

    logger.info(f"Bot verifisert: @{bot_info.get('username')}")
    logger.info(f"Poller hvert {POLL_INTERVAL_SECONDS} sekund")
    logger.info(f"Score-terskel: {SCORE_THRESHOLD}/100")
    logger.info(f"Nitter aktivert: {INCLUDE_NITTER}")

    # Hent seen-store
    seen = get_store()
    logger.info(f"SeenStore: {seen.stats()}")

    # Vis innhold i DATA_DIR
    from pathlib import Path
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    if data_dir.exists():
        files = list(data_dir.iterdir())
        logger.info(f"DATA_DIR ({data_dir}): {len(files)} filer")
        for f in files:
            logger.info(f"  {f.name} ({f.stat().st_size} bytes)")
    else:
        logger.info(f"DATA_DIR ({data_dir}): finnes ikke ennå")

    # Oppstartsmelding til Telegram
    try:
        send_startup_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    except Exception as e:
        logger.warning(f"Klarte ikke sende oppstartsmelding: {e}")

    # Første kjøring umiddelbart
    try:
        run_once(seen)
    except Exception as e:
        logger.error(f"Feil i første kjøring: {e}", exc_info=True)

    # Scheduler-loop
    interval_seconds = POLL_INTERVAL_SECONDS
    logger.info(f"Venter {POLL_INTERVAL_SECONDS}s til neste kjøring…")

    while True:
        time.sleep(interval_seconds)
        try:
            run_once(seen)
        except KeyboardInterrupt:
            logger.info("Stoppet av bruker (KeyboardInterrupt)")
            break
        except Exception as e:
            logger.error(f"Uventet feil i kjøring: {e}", exc_info=True)
            # Ikke krasj – vent og prøv igjen
            logger.info("Fortsetter etter feil…")

        logger.info(f"Venter {POLL_INTERVAL_SECONDS}s til neste kjøring…")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stoppet.")
        sys.exit(0)
