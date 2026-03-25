"""
price.py – Overvåker Brent-oljepris via Yahoo Finance (gratis, ingen API-nøkkel).
Varsler når prisen endrer seg mer enn PRICE_ALERT_THRESHOLD dollar fra referansepunktet.
"""

import json
import logging
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BRENT_TICKER = "BZ=F"
PRICE_ALERT_THRESHOLD = float(os.getenv("PRICE_ALERT_THRESHOLD", "3.0"))
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
PRICE_FILE = DATA_DIR / "price_ref.json"

YAHOO_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    "?interval=1d&range=5d"
)


@dataclass
class PriceSnapshot:
    price: float
    change: float
    change_pct: float
    ref_price: float
    direction: str  # "up" / "down"


def fetch_brent_price() -> Optional[float]:
    """Henter siste Brent-pris fra Yahoo Finance."""
    url = YAHOO_URL.format(ticker=BRENT_TICKER)
    req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        if price and price > 0:
            return float(price)
        closes = data["chart"]["result"][0]["indicators"]["quote"][0].get("close", [])
        valid = [c for c in closes if c is not None]
        return float(valid[-1]) if valid else None
    except Exception as e:
        logger.error(f"Yahoo Finance feil: {e}")
        return None


def _load_ref() -> Optional[dict]:
    try:
        if PRICE_FILE.exists():
            with open(PRICE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _save_ref(price: float) -> None:
    PRICE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRICE_FILE, "w") as f:
        json.dump({"price": price, "ts": datetime.utcnow().isoformat()}, f)


def check_price(threshold: float = PRICE_ALERT_THRESHOLD) -> Optional[PriceSnapshot]:
    """Sjekker pris mot referanse. Returnerer PriceSnapshot hvis endring >= terskel."""
    current = fetch_brent_price()
    if current is None:
        return None

    ref = _load_ref()
    if ref is None:
        _save_ref(current)
        logger.info(f"Referansepris satt: ${current:.2f}")
        return None

    ref_price = ref["price"]
    change = current - ref_price
    if abs(change) < threshold:
        logger.debug(f"Brent ${current:.2f} (endring {change:+.2f} fra ref ${ref_price:.2f})")
        return None

    _save_ref(current)
    return PriceSnapshot(
        price=current,
        change=change,
        change_pct=(change / ref_price) * 100,
        ref_price=ref_price,
        direction="up" if change > 0 else "down",
    )


def format_price_alert(s: PriceSnapshot) -> str:
    """Formaterer prisvarsel for Telegram."""
    emoji = "📈" if s.direction == "up" else "📉"
    arrow = "⬆️" if s.direction == "up" else "⬇️"
    word = "STIGNING" if s.direction == "up" else "FALL"

    lines = [
        f"{emoji} BRENT PRISVARSEL: {word}",
        "",
        f"{arrow} ${s.price:.2f} per fat",
        "",
        f"Endring: {s.change:+.2f} USD ({s.change_pct:+.1f}%)",
        f"Fra referanse: ${s.ref_price:.2f}",
    ]

    if abs(s.change) >= 8:
        lines.append("\n🚨 Ekstrem bevegelse!")
    elif abs(s.change) >= 5:
        lines.append("\n⚠️ Stor bevegelse i markedet.")

    return "\n".join(lines)


def format_scheduled_price_report(time_label: str) -> Optional[str]:
    """Formaterer en planlagt prisoppdatering (morgen/ettermiddag)."""
    current = fetch_brent_price()
    if current is None:
        return None

    ref = _load_ref()
    if ref:
        change = current - ref["price"]
        change_pct = (change / ref["price"]) * 100
        change_str = f"Endring siden sist: {change:+.2f} USD ({change_pct:+.1f}%)"
    else:
        change_str = ""

    lines = [
        f"🛢️ BRENT PRISOPPDATERING – {time_label}",
        "",
        f"💰 ${current:.2f} per fat",
    ]

    if change_str:
        lines.append(change_str)

    return "\n".join(lines)
