"""
gps_commands.py – GPS-baserte kommandoer: buss, luft, lading.
"""

import json
import logging
import math
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)


def top_names(year: str = "2025") -> dict:
    """Returnerer topp babynavn per fylke (hardkodet fra SSB 2025)."""
    return _NAMES_2025


# SSB navnestatistikk per fylke 2025 (kilde: ssb.no/befolkning/navn)
_NAMES_2025 = {
    "Oslo": {"girls": [("Sofia",72),("Frida",70),("Emma",60),("Sofie",57),("Hennie",55),("Nora",54),("Astrid",53),("Alma",49),("Eva",48)], "boys": [("Mohammad",82),("Jakob",73),("Oskar",73),("William",63),("Emil",60),("Theodor",59),("Filip",58),("Gustav",58),("Jens",54)]},
    "Akershus": {"girls": [("Sofia",57),("Maja",49),("Emma",47),("Hennie",47),("Olivia",46),("Nora",42),("Leah",41),("Sofie",41),("Ellinor",40)], "boys": [("Lucas",65),("Noah",62),("William",60),("Oskar",58),("Filip",53),("Elias",52),("Jakob",52),("Emil",47),("Liam",45)]},
    "Østfold": {"girls": [("Ellinor",24),("Olivia",24),("Ella",23),("Alma",22),("Selma",22),("Leah",21),("Hedvig",20),("Emma",18),("Sofie",16)], "boys": [("Noah",29),("Liam",28),("Elias",21),("Victor",21),("William",21),("Jakob",20),("Theodor",20),("Gustav",16),("Johannes",16)]},
    "Buskerud": {"girls": [("Emma",24),("Olivia",21),("Sofie",21),("Hedda",18),("Astrid",16),("Hedvig",16),("Hennie",16),("Ingrid",16),("Maja",16)], "boys": [("William",24),("Lucas",22),("Johannes",18),("Theodor",18),("Oskar",17),("Elias",16),("Emil",16),("Isak",16),("Jakob",16)]},
    "Vestfold": {"girls": [("Ella",22),("Nora",20),("Sofie",20),("Astrid",16),("Frida",16),("Olivia",15),("Sofia",15),("Hennie",14),("Iben",14)], "boys": [("Ludvig",19),("Herman",17),("Isak",17),("Jakob",17),("Noah",17),("Oskar",17),("Lucas",16),("Victor",15),("Birk",14)]},
    "Telemark": {"girls": [("Emma",20),("Frida",13),("Olivia",12),("Ellinor",11),("Hedvig",11),("Sofie",11),("Emilie",10),("Selma",10),("Ella",9)], "boys": [("Isak",16),("Noah",16),("Olav",13),("William",13),("Johannes",12),("Mathias",12),("Emil",11),("Theo",11),("Theodor",11)]},
    "Agder": {"girls": [("Olivia",30),("Leah",27),("Nora",26),("Emma",25),("Sofie",25),("Frida",21),("Ella",19),("Ingrid",19),("Sofia",19)], "boys": [("Noah",40),("Isak",33),("Elias",29),("Jakob",28),("Lucas",27),("Emil",26),("Johannes",21),("William",20),("Filip",19)]},
    "Rogaland": {"girls": [("Nora",43),("Frida",40),("Ella",39),("Leah",39),("Alma",37),("Sofia",37),("Sofie",34),("Iben",33),("Sara",33)], "boys": [("Noah",42),("Emil",39),("Tobias",39),("Isak",38),("Elias",37),("Kasper",37),("Liam",37),("Lucas",37),("Filip",34)]},
    "Vestland": {"girls": [("Emma",53),("Olivia",51),("Hedda",46),("Frida",45),("Ellinor",43),("Ella",42),("Mathilde",42),("Leah",41),("Nora",40),("Alma",39)], "boys": [("Noah",78),("Oskar",56),("Lucas",54),("Emil",51),("William",51),("Jakob",50),("Magnus",50),("Olav",49),("Oliver",49),("Johannes",46)]},
    "Innlandet": {"girls": [("Leah",29),("Hedda",24),("Emma",23),("Nora",23),("Alma",22),("Oline",22),("Frida",21),("Astrid",20),("Tiril",19)], "boys": [("Emil",29),("Lucas",29),("Oliver",29),("Isak",28),("Håkon",27),("Noah",26),("Oskar",26),("Henrik",25),("Johannes",22)]},
    "Møre og Romsdal": {"girls": [("Sofie",23),("Olivia",21),("Jenny",18),("Ella",17),("Emma",17),("Nora",17),("Hedda",16),("Astrid",15),("Leah",15)], "boys": [("Lucas",28),("Noah",27),("Elias",25),("Oliver",24),("Ludvig",23),("Liam",20),("Emil",19),("Isak",19),("Birk",18)]},
    "Trøndelag": {"girls": [("Nora",43),("Astrid",41),("Sofie",40),("Olivia",36),("Ellinor",35),("Hedda",34),("Ella",31),("Leah",30),("Amalie",27),("Maja",27)], "boys": [("Emil",45),("Johannes",42),("Oliver",42),("Lucas",36),("Jakob",35),("Ludvig",35),("Isak",34),("Noah",34),("Even",33),("Sverre",30)]},
    "Nordland": {"girls": [("Aurora",22),("Astrid",19),("Nora",19),("Leah",18),("Ella",17),("Ellinor",17),("Olivia",16),("Hedda",15),("Sofia",13)], "boys": [("Jakob",22),("Noah",22),("Ulrik",22),("Ludvig",21),("Kasper",19),("Emil",18),("Oskar",16),("Aksel",15),("Elias",15)]},
    "Troms": {"girls": [("Emma",15),("Astrid",14),("Ella",14),("Eva",13),("Ellinor",12),("Olivia",12),("Sofie",11),("Alma",10),("Frida",10),("Hedvig",9)], "boys": [("Jakob",19),("Kasper",18),("Henrik",16),("Noah",15),("Emil",14),("Johannes",13),("Ulrik",13),("Isak",12),("Iver",12),("Ludvig",12)]},
    "Finnmark": {"girls": [("Eva",7),("Selma",7),("Ella",6),("Leah",6),("Marie",6),("Amalie",5),("Emma",5),("Ingrid",5),("Malin",5),("Olivia",5)], "boys": [("Emil",9),("Isak",9),("Markus",8),("Olav",7),("Sander",7),("Elias",6),("Henrik",6),("Johannes",6),("Matheo",6),("Mikkel",6)]},
}


def municipality_from_gps(lat: float, lon: float) -> Optional[dict]:
    """Finner kommune fra GPS via Kartverket."""
    import urllib.request as _req
    try:
        url = f"https://ws.geonorge.no/kommuneinfo/v1/punkt?nord={lat}&ost={lon}&koordsys=4326"
        req = _req.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
        return json.loads(_req.urlopen(req, timeout=8).read())
    except Exception:
        return None


def format_names_report(lat: float = None, lon: float = None, region: str = None) -> str:
    """Formaterer navnestatistikk per fylke for Telegram."""
    try:
        fylke = region

        if lat and lon and not fylke:
            muni = municipality_from_gps(lat, lon)
            if muni:
                fylke = muni.get("fylkesnavn")

        if not fylke or fylke not in _NAMES_2025:
            # Prøv fuzzy match
            for key in _NAMES_2025:
                if fylke and fylke.lower() in key.lower():
                    fylke = key
                    break
            else:
                fylke = None

        if not fylke:
            return "⚠️ Fant ikke navnestatistikk for dette fylket."

        data = _NAMES_2025[fylke]

        lines = [
            f"👶 POPULÆRE BABYNAVN I {fylke.upper()} (2025)",
            "",
            "👧 Jenter:",
        ]
        for i, (name, count) in enumerate(data["girls"][:10], 1):
            lines.append(f"  {i:2d}. {name} ({count})")

        lines.append("")
        lines.append("👦 Gutter:")
        for i, (name, count) in enumerate(data["boys"][:10], 1):
            lines.append(f"  {i:2d}. {name} ({count})")

        lines.append("\nKilde: SSB")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Navn feilet: {e}")
        return "⚠️ Klarte ikke hente navnestatistikk."
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
