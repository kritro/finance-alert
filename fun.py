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
    """Hvor er ISS akkurat nå, og hvor langt unna Revetal? (fallback uten GPS)"""
    return iss_status_gps(REVETAL_LAT, REVETAL_LON)


def iss_status_gps(lat: float, lon: float) -> str:
    """Hvor er ISS akkurat nå, og hvor langt unna deg?"""
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

        dist = _haversine(lat, lon, iss_lat, iss_lon)

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
            f"📐 Avstand fra deg: {dist:.0f} km",
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
    """Nordlys-varsling (fallback uten GPS)."""
    return aurora_forecast_gps(REVETAL_LAT, REVETAL_LON)


def aurora_forecast_gps(lat: float, lon: float) -> str:
    """Nordlys-varsling basert på GPS-posisjon."""
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

        # Minimum Kp for å se nordlys avhenger av breddegrad
        # 70°N: Kp 1-2, 65°N: Kp 3, 60°N: Kp 5, 55°N: Kp 7
        if lat >= 70:
            kp_needed = 2
            region = "Nord-Norge"
        elif lat >= 67:
            kp_needed = 3
            region = "Nordland/Troms"
        elif lat >= 63:
            kp_needed = 4
            region = "Midt-Norge"
        elif lat >= 59:
            kp_needed = 5
            region = "Sør-Norge"
        else:
            kp_needed = 7
            region = "Sørlandet"

        margin = kp_val - kp_needed

        if margin >= 2:
            verdict = f"🟢 STOR SJANSE for nordlys fra din posisjon!"
            emoji = "🌌"
        elif margin >= 0:
            verdict = f"🟡 Mulig! Se mot nord hvis det er klart i kveld."
            emoji = "✨"
        elif margin >= -2:
            verdict = f"🟠 Lite sannsynlig herfra. Trenger Kp {kp_needed}+, nå er det {kp_val:.0f}."
            emoji = "🔭"
        else:
            verdict = "🔴 Ingen nordlys-sjanse herfra akkurat nå."
            emoji = "😴"

        lines = [
            f"{emoji} NORDLYS-VARSLING",
            f"📍 {lat:.1f}°N ({region})",
            "",
            f"🧲 Kp-indeks nå: {kp_val:.1f} / 9.0",
            f"🎯 Trenger Kp {kp_needed}+ for din breddegrad",
            "",
            verdict,
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
