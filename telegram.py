"""
telegram.py – Sender varsler via Telegram Bot API.

Bruker bare standardbiblioteket (urllib) – ingen ekstra avhengigheter.
"""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from filter import ScoredArticle

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

# Score-til-emoji mapping for å gi meldingen litt visuelt nivå
def _urgency_emoji(score: int) -> str:
    if score >= 80:
        return "🚨"
    elif score >= 60:
        return "⚠️"
    elif score >= 40:
        return "📰"
    return "ℹ️"


def _score_bar(score: int) -> str:
    """Enkel visuell score-indikator."""
    filled = round(score / 10)
    return "█" * filled + "░" * (10 - filled)


def _format_message(scored: ScoredArticle) -> str:
    """
    Lager en pen Telegram-melding i ren tekst (unngår Markdown-parsing-problemer).
    """
    a = scored.article
    emoji = _urgency_emoji(scored.score)
    bar = _score_bar(scored.score)

    # Klipp summary hvis for lang
    summary = a.summary[:300].strip()
    if len(a.summary) > 300:
        summary += "…"

    # Nøkkelord (maks 5 stykker)
    kw_list = scored.matched_keywords[:5]
    kw_str = " · ".join(f"#{k.replace(' ', '_')}" for k in kw_list) if kw_list else ""

    lines = [
        f"{emoji} OLJEPRISVARSEL",
        f"",
        a.title,
        f"",
    ]

    if summary:
        lines.append(summary)
        lines.append("")

    lines += [
        f"📊 Relevans: {bar} {scored.score}/100",
        f"📡 Kilde: {a.source}",
    ]

    if a.published:
        lines.append(f"🕐 {a.published.strftime('%d.%m.%Y %H:%M')} UTC")

    if kw_str:
        lines.append(f"")
        lines.append(kw_str)

    lines += [
        f"",
        f"🔗 {a.url}",
    ]

    return "\n".join(lines)


def _api_call(
    token: str,
    method: str,
    payload: dict,
    timeout: int = 15,
) -> Optional[dict]:
    """Gjør et POST-kall mot Telegram Bot API."""
    url = TELEGRAM_API.format(token=token, method=method)
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"Telegram API HTTP-feil {e.code}: {body}")
        return None
    except Exception as e:
        logger.error(f"Telegram API-feil: {e}")
        return None


def send_alert(
    scored: ScoredArticle,
    token: str,
    chat_id: str,
) -> bool:
    """
    Sender én varselmelding til Telegram.
    Returnerer True hvis suksess.
    """
    message = _format_message(scored)

    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": False,
    }

    result = _api_call(token, "sendMessage", payload)
    if result and result.get("ok"):
        logger.info(f"Telegram: sendt varsel for '{scored.article.title[:60]}'")
        return True

    logger.error(f"Telegram: klarte ikke sende varsel. Respons: {result}")
    return False


def send_startup_message(token: str, chat_id: str) -> bool:
    """Sender en oppstartsmelding for å bekrefte at boten kjører."""
    payload = {
        "chat_id": chat_id,
        "text": (
            "🛢️ Oljepris-varsler startet!\n\n"
            "Overvåker nyheter fra Reuters, AP, OilPrice.com, OPEC, EIA og mer.\n"
            "Du vil motta varsler når relevante oljeprissensitive nyheter oppdages."
        ),
    }
    result = _api_call(token, "sendMessage", payload)
    return bool(result and result.get("ok"))


def send_batch(
    scored_articles: list[ScoredArticle],
    token: str,
    chat_id: str,
    max_per_run: int = 10,
) -> int:
    """
    Sender opptil max_per_run varsler.
    Returnerer antall vellykket sendte meldinger.
    """
    sent = 0
    for scored in scored_articles[:max_per_run]:
        if send_alert(scored, token, chat_id):
            sent += 1

    if sent:
        logger.info(f"Telegram: sendte {sent} varsler denne kjøringen")
    return sent


def get_bot_info(token: str) -> Optional[dict]:
    """Sjekker at bot-tokenet er gyldig. Returnerer bot-info."""
    result = _api_call(token, "getMe", {}, timeout=10)
    if result and result.get("ok"):
        return result.get("result")
    return None


def get_chat_id_from_updates(token: str) -> Optional[str]:
    """
    Hjelpefunksjon: henter chat_id fra siste melding sendt til boten.
    Nyttig under oppsett – send /start til boten og kjør dette.
    """
    result = _api_call(token, "getUpdates", {"limit": 5, "timeout": 5})
    if not result or not result.get("ok"):
        return None

    updates = result.get("result", [])
    for update in reversed(updates):
        msg = update.get("message") or update.get("channel_post")
        if msg:
            chat = msg.get("chat", {})
            cid = chat.get("id")
            title = chat.get("title") or chat.get("username") or chat.get("first_name", "")
            logger.info(f"Fant chat_id: {cid} ({title})")
            return str(cid)

    return None


if __name__ == "__main__":
    # Kjør dette scriptet direkte for å finne din chat_id:
    #   TELEGRAM_TOKEN=xxx python telegram.py
    import sys

    logging.basicConfig(level=logging.INFO)
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("Sett TELEGRAM_TOKEN som miljøvariabel")
        sys.exit(1)

    info = get_bot_info(token)
    if info:
        print(f"Bot OK: @{info.get('username')} ({info.get('first_name')})")
    else:
        print("Ugyldig token!")
        sys.exit(1)

    print("\nSender /start til boten i Telegram nå...")
    print("Venter 5 sekunder på svar...")
    import time
    time.sleep(5)

    chat_id = get_chat_id_from_updates(token)
    if chat_id:
        print(f"\n✅ Din TELEGRAM_CHAT_ID er: {chat_id}")
        print("Legg denne til i Railway som miljøvariabel.")
    else:
        print("\nIngen meldinger funnet. Sørg for at du har sendt /start til boten.")
