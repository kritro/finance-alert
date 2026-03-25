"""
gps_commands.py – GPS-baserte kommandoer: buss, luft, lading.
"""

import json
import logging
import math
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)


def nearest_departures(lat: float, lon: float) -> str:
    """Finner nærmeste holdeplass og neste avganger via Entur."""
    try:
        # Finn nærmeste holdeplass
        url = f"https://api.entur.io/geocoder/v1/reverse?point.lat={lat}&point.lon={lon}&size=3&layers=venue"
        req = urllib.request.Request(url, headers={"ET-Client-Name": "oil-alert-bot"})
        data = json.loads(urllib.request.urlopen(req, timeout=8).read())

        features = data.get("features", [])
        if not features:
            return "🤷 Fant ingen holdeplasser i nærheten."

        # Bruk nærmeste stopp
        stop = features[0]["properties"]
        stop_id = stop["id"]
        stop_name = stop["name"]
        dist = stop.get("distance", 0) * 1000  # km -> m

        # Hent avganger
        query = (
            '{ stopPlace(id: "%s") { name estimatedCalls(numberOfDepartures: 8, timeRange: 14400) '
            '{ expectedDepartureTime destinationDisplay { frontText } '
            'serviceJourney { line { publicCode transportMode } } } } }' % stop_id
        )
        req2 = urllib.request.Request(
            "https://api.entur.io/journey-planner/v3/graphql",
            data=json.dumps({"query": query}).encode(),
            headers={"ET-Client-Name": "oil-alert-bot", "Content-Type": "application/json"},
        )
        result = json.loads(urllib.request.urlopen(req2, timeout=8).read())
        calls = result["data"]["stopPlace"]["estimatedCalls"]

        lines = [
            f"🚌 {stop_name} ({dist:.0f}m unna)",
            "",
        ]

        if not calls:
            lines.append("Ingen avganger de neste timene.")
        else:
            for c in calls[:8]:
                time = c["expectedDepartureTime"][11:16]
                dest = c["destinationDisplay"]["frontText"]
                line_nr = c["serviceJourney"]["line"]["publicCode"]
                mode = c["serviceJourney"]["line"]["transportMode"]
                emoji = "🚌" if mode == "bus" else "🚆" if mode == "rail" else "🚊"
                lines.append(f"{emoji} {time}  Linje {line_nr} → {dest}")

        lines.append("\nKilde: Entur")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Buss feilet: {e}")
        return "⚠️ Klarte ikke hente bussavganger."


def air_quality(lat: float, lon: float) -> str:
    """Henter luftkvalitet via Open-Meteo."""
    try:
        url = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality?"
            f"latitude={lat}&longitude={lon}"
            f"&current=pm2_5,pm10,nitrogen_dioxide,ozone,european_aqi"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=8).read())
        current = data.get("current", {})

        aqi = current.get("european_aqi", 0)
        pm25 = current.get("pm2_5", 0)
        pm10 = current.get("pm10", 0)
        no2 = current.get("nitrogen_dioxide", 0)
        o3 = current.get("ozone", 0)

        # Vurdering basert på European AQI
        if aqi <= 20:
            verdict = "🟢 Svært god"
        elif aqi <= 40:
            verdict = "🟢 God"
        elif aqi <= 60:
            verdict = "🟡 Middels"
        elif aqi <= 80:
            verdict = "🟠 Dårlig"
        elif aqi <= 100:
            verdict = "🔴 Svært dårlig"
        else:
            verdict = "🟣 Ekstremt dårlig"

        lines = [
            f"🌬️ LUFTKVALITET",
            f"📍 {lat:.2f}°N, {lon:.2f}°E",
            "",
            f"📊 European AQI: {aqi:.0f} – {verdict}",
            "",
            f"PM2.5: {pm25:.1f} µg/m³",
            f"PM10:  {pm10:.1f} µg/m³",
            f"NO₂:   {no2:.1f} µg/m³",
            f"O₃:    {o3:.1f} µg/m³",
            "",
            "Kilde: Open-Meteo / CAMS",
        ]
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Luft feilet: {e}")
        return "⚠️ Klarte ikke hente luftkvalitet."


def nearest_chargers(lat: float, lon: float) -> str:
    """Finner nærmeste elbil-ladere via Open Charge Map."""
    try:
        url = (
            f"https://api.openchargemap.io/v3/poi?"
            f"latitude={lat}&longitude={lon}&distance=10&distanceunit=km"
            f"&maxresults=5&compact=true&verbose=false&countrycode=NO"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=8).read())

        if not data:
            return "🤷 Fant ingen ladestasjoner i nærheten."

        lines = [
            f"⚡ NÆRMESTE ELBIL-LADERE",
            f"📍 {lat:.3f}°N, {lon:.3f}°E",
            "",
        ]

        for station in data[:5]:
            info = station.get("AddressInfo", {})
            name = info.get("Title", "Ukjent")
            address = info.get("AddressLine1", "")
            dist = info.get("Distance", 0)
            town = info.get("Town", "")

            connections = station.get("Connections", [])
            max_kw = 0
            for conn in connections:
                kw = conn.get("PowerKW") or 0
                if kw > max_kw:
                    max_kw = kw

            kw_str = f"{max_kw:.0f} kW" if max_kw > 0 else "?"

            if max_kw >= 150:
                emoji = "⚡⚡"
            elif max_kw >= 50:
                emoji = "⚡"
            else:
                emoji = "🔌"

            lines.append(f"{emoji} {name}")
            if address:
                lines.append(f"   {address}, {town}")
            lines.append(f"   {dist:.1f} km – {kw_str}")
            lines.append("")

        lines.append("Kilde: Open Charge Map")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Lading feilet: {e}")
        return "⚠️ Klarte ikke hente ladestasjon-data."
