"""
weather.py – Henter vinddata fra Yr.no for Bårdfjordneset.
Gratis, ingen API-nøkkel nødvendig.
"""

import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

YR_CURRENT_URL = "https://www.yr.no/api/v0/locations/1-321158/forecast/currenthour"

WIND_DIRECTIONS = [
    "N", "NNØ", "NØ", "ØNØ", "Ø", "ØSØ", "SØ", "SSØ",
    "S", "SSV", "SV", "VSV", "V", "VNV", "NV", "NNV",
]


def _degrees_to_direction(degrees: float) -> str:
    """Konverterer vindretning i grader til kompassretning."""
    idx = round(degrees / 22.5) % 16
    return WIND_DIRECTIONS[idx]


def _wind_description(speed: float) -> str:
    """Beaufort-skala beskrivelse basert på m/s."""
    if speed < 0.3:
        return "Stille"
    elif speed < 1.6:
        return "Flau vind"
    elif speed < 3.4:
        return "Svak vind"
    elif speed < 5.5:
        return "Lett bris"
    elif speed < 8.0:
        return "Laber bris"
    elif speed < 10.8:
        return "Frisk bris"
    elif speed < 13.9:
        return "Liten kuling"
    elif speed < 17.2:
        return "Stiv kuling"
    elif speed < 20.8:
        return "Sterk kuling"
    elif speed < 24.5:
        return "Liten storm"
    elif speed < 28.5:
        return "Full storm"
    elif speed < 32.7:
        return "Sterk storm"
    else:
        return "Orkan"


def fetch_bardfjordneset_wind() -> Optional[dict]:
    """Henter nåværende vind fra Yr.no for Bårdfjordneset."""
    req = urllib.request.Request(YR_CURRENT_URL, headers={
        "User-Agent": "oil-alert-bot/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        wind = data.get("wind", {})
        temp = data.get("temperature", {})
        symbol = data.get("symbolCode", {}).get("next1Hour", "")

        return {
            "speed": wind.get("speed", 0),
            "gust": wind.get("gust", 0),
            "direction_deg": wind.get("direction", 0),
            "direction": _degrees_to_direction(wind.get("direction", 0)),
            "temp": temp.get("value"),
            "feels_like": temp.get("feelsLike"),
            "symbol": symbol,
        }
    except Exception as e:
        logger.error(f"Yr.no feil: {e}")
        return None


def format_wind_report() -> Optional[str]:
    """Formaterer vindrapport for Telegram."""
    w = fetch_bardfjordneset_wind()
    if w is None:
        return None

    desc = _wind_description(w["speed"])
    arrow = _wind_arrow(w["direction_deg"])

    lines = [
        "🌬️ BÅRDFJORDNESET – Vind nå",
        "",
        f"{arrow} {w['speed']:.1f} m/s fra {w['direction']} ({w['direction_deg']}°)",
        f"💨 Vindkast: {w['gust']:.1f} m/s",
        f"📊 {desc}",
    ]

    if w["temp"] is not None:
        lines.append(f"🌡️ {w['temp']:.1f}°C (føles som {w['feels_like']}°C)")

    return "\n".join(lines)


def _wind_arrow(degrees: float) -> str:
    """Returnerer en pil-emoji som viser vindretning (retningen vinden KOMMER fra)."""
    arrows = ["⬇️", "↙️", "⬅️", "↖️", "⬆️", "↗️", "➡️", "↘️"]
    idx = round(degrees / 45) % 8
    return arrows[idx]
