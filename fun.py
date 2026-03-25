"""
fun.py – Morsomme kommandoer: ISS, nordlys, fakta, romfart.
Alle API-er er gratis uten nøkkel.
"""

import json
import logging
import math
import urllib.request
from datetime import datetime

logger = logging.getLogger(__name__)

REVETAL_LAT = 59.3
REVETAL_LON = 10.3


def iss_status() -> str:
    """Hvor er ISS akkurat nå, og hvor langt unna Revetal?"""
    try:
        req = urllib.request.Request(
            "https://api.wheretheiss.at/v1/satellites/25544",
            headers={"User-Agent": "oil-alert-bot/1.0"},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        iss_lat = data["latitude"]
        iss_lon = data["longitude"]
        alt = data["altitude"]
        speed = data["velocity"]

        # Beregn avstand fra Revetal (haversine)
        dist = _haversine(REVETAL_LAT, REVETAL_LON, iss_lat, iss_lon)

        # Finn hvilket land/område ISS er over
        if -90 < iss_lat < 90:
            over = _rough_location(iss_lat, iss_lon)
        else:
            over = "ukjent"

        lines = [
            "🛰️ ISS – Akkurat nå",
            "",
            f"📍 Posisjon: {iss_lat:.1f}°{'N' if iss_lat >= 0 else 'S'}, {iss_lon:.1f}°{'E' if iss_lon >= 0 else 'W'}",
            f"🌍 Over: {over}",
            f"📏 Høyde: {alt:.0f} km",
            f"⚡ Fart: {speed:.0f} km/t",
            f"📐 Avstand fra Revetal: {dist:.0f} km",
        ]

        if dist < 2000:
            lines.append("\n👀 Ganske nære! Se opp i kveld hvis det er klart!")
        elif dist < 5000:
            lines.append(f"\n🔭 Passerer kanskje i løpet av noen timer")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"ISS feilet: {e}")
        return "⚠️ Klarte ikke hente ISS-data akkurat nå."


def aurora_forecast() -> str:
    """Nordlys-varsling for Revetal/Tønsberg."""
    try:
        req = urllib.request.Request(
            "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json",
            headers={"User-Agent": "oil-alert-bot/1.0"},
        )
        entries = json.loads(urllib.request.urlopen(req, timeout=10).read())

        # Finn nåværende Kp-verdi (hopp over header-rad)
        kp_val = 0
        for entry in entries[1:]:
            try:
                kp_val = max(kp_val, float(entry[1]))
            except (ValueError, IndexError):
                continue

        # Vurdering for Sør-Norge (trenger Kp ~5+ for å se nordlys)
        if kp_val >= 7:
            verdict = "🟢 STOR SJANSE! Nordlys kan være synlig fra Revetal i natt!"
            emoji = "🌌"
        elif kp_val >= 5:
            verdict = "🟡 Mulig! Se mot nord hvis det er klart i kveld."
            emoji = "✨"
        elif kp_val >= 3:
            verdict = "🟠 Lite sannsynlig fra Revetal, men mulig i Nord-Norge."
            emoji = "🔭"
        else:
            verdict = "🔴 Ingen nordlys-aktivitet akkurat nå."
            emoji = "😴"

        lines = [
            f"{emoji} NORDLYS-VARSLING",
            "",
            f"🧲 Kp-indeks: {kp_val:.1f} / 9.0",
            f"📍 For Revetal/Tønsberg (59°N):",
            "",
            verdict,
            "",
            "ℹ️ Kp 5+ = synlig i Sør-Norge",
            "ℹ️ Kp 7+ = synlig over hele Norge",
        ]

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Nordlys feilet: {e}")
        return "⚠️ Klarte ikke hente nordlys-data akkurat nå."


def random_fact() -> str:
    """Tilfeldig ubrukelig fakta på norsk."""
    try:
        req = urllib.request.Request(
            "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en",
            headers={"User-Agent": "oil-alert-bot/1.0"},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        fact = data.get("text", "Ingen fakta tilgjengelig")

        # Oversett via enkel prompt til norsk (bruker MyMemory free API)
        try:
            import urllib.parse as _uparse
            encoded = _uparse.quote(fact)
            treq = urllib.request.Request(
                f"https://api.mymemory.translated.net/get?q={encoded}&langpair=en|no",
                headers={"User-Agent": "oil-alert-bot/1.0"},
            )
            tdata = json.loads(urllib.request.urlopen(treq, timeout=10).read())
            translated = tdata.get("responseData", {}).get("translatedText", "")
            if translated and "MYMEMORY" not in translated.upper():
                fact = translated
        except Exception:
            pass  # Bruk engelsk som fallback

        return f"🤓 VISSTE DU AT...\n\n{fact}"

    except Exception as e:
        logger.error(f"Fakta feilet: {e}")
        return "⚠️ Klarte ikke hente fakta akkurat nå."


def space_travel() -> str:
    """Hvor langt har du reist gjennom verdensrommet i dag?"""
    now = datetime.utcnow()
    hours_today = now.hour + now.minute / 60.0

    # 1. Jordrotasjon (avhenger av breddegrad)
    earth_circum = 40075  # km
    rotation_speed = earth_circum * math.cos(math.radians(REVETAL_LAT)) / 24  # km/t
    rotation_today = rotation_speed * hours_today

    # 2. Jordens bane rundt sola
    orbit_speed = 107280 / 24  # km/t (107 280 km/dag)
    orbit_today = orbit_speed * hours_today

    # 3. Solsystemets bevegelse gjennom galaksen
    galaxy_speed = 792000 / 24  # km/t (792 000 km/dag, ~220 km/s)
    galaxy_today = galaxy_speed * hours_today

    total = rotation_today + orbit_today + galaxy_today

    lines = [
        "🚀 DIN ROMREISE I DAG",
        f"(siden midnatt, {hours_today:.1f} timer)",
        "",
        f"🌍 Jordrotasjon: {rotation_today:,.0f} km ({rotation_speed:.0f} km/t)",
        f"☀️ Rundt sola: {orbit_today:,.0f} km ({orbit_speed:,.0f} km/t)",
        f"🌌 Gjennom galaksen: {galaxy_today:,.0f} km ({galaxy_speed:,.0f} km/t)",
        "",
        f"📊 TOTALT: {total:,.0f} km",
        f"⚡ Akkurat nå: {(rotation_speed + orbit_speed + galaxy_speed):,.0f} km/t",
    ]

    return "\n".join(lines)


def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Beregner avstand i km mellom to punkter."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _rough_location(lat, lon) -> str:
    """Grov plassering basert på koordinater."""
    if 55 < lat < 72 and 3 < lon < 32:
        return "Skandinavia 🇳🇴"
    elif 35 < lat < 72 and -25 < lon < 45:
        return "Europa 🇪🇺"
    elif 24 < lat < 50 and -130 < lon < -60:
        return "Nord-Amerika 🇺🇸"
    elif -56 < lat < 13 and -82 < lon < -34:
        return "Sør-Amerika 🌎"
    elif -10 < lat < 55 and 25 < lon < 145:
        return "Asia 🌏"
    elif -47 < lat < 37 and -20 < lon < 55:
        return "Afrika 🌍"
    elif -50 < lat < -10 and 110 < lon < 180:
        return "Australia/Oseania 🦘"
    elif lat < -60:
        return "Antarktis 🧊"
    elif lat > 66:
        return "Arktis ❄️"
    else:
        # Sannsynligvis over havet
        if -80 < lon < 0:
            return "Atlanterhavet 🌊"
        elif 20 < lon < 150:
            return "Indiahavet/Stillehavet 🌊"
        else:
            return "Stillehavet 🌊"
