"""
api.py – HTTP API for info-kommandoer (PWA backend).
Gjenbruker eksisterende funksjoner fra gps_commands.py, fun.py, price.py, weather.py.
"""

import json
import logging
import re
import urllib.request
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

app = FastAPI(title="TrondInfo API", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Hjelpefunksjoner
# ──────────────────────────────────────────────

def _json_ok(text: str, extra: dict = None) -> dict:
    """Standard JSON-respons med tekst."""
    resp = {"ok": True, "text": text}
    if extra:
        resp.update(extra)
    return resp


def _json_err(msg: str) -> dict:
    return {"ok": False, "error": msg}


# ──────────────────────────────────────────────
# GPS-baserte endepunkter
# ──────────────────────────────────────────────

@app.get("/api/buss")
def api_buss(lat: float = Query(...), lon: float = Query(...)):
    from gps_commands import nearest_departures
    return _json_ok(nearest_departures(lat, lon))


@app.get("/api/dyr")
def api_dyr(lat: float = Query(...), lon: float = Query(...)):
    """Dyreliv i nærheten via GBIF."""
    delta = 0.05
    url = (
        f"https://api.gbif.org/v1/occurrence/search?"
        f"decimalLatitude={lat - delta},{lat + delta}&"
        f"decimalLongitude={lon - delta},{lon + delta}&"
        f"country=NO&limit=15&orderBy=eventDate"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        results = data.get("results", [])
        total = data.get("count", 0)

        if not results:
            return _json_ok("🤷 Ingen observasjoner funnet i nærheten.")

        seen_species = {}
        for r in results:
            name = r.get("vernacularName") or r.get("species") or r.get("scientificName", "Ukjent")
            if name not in seen_species:
                seen_species[name] = r

        lines = [
            f"🐾 DYRELIV I NÆRHETEN ({total:,} obs totalt)",
            f"📍 {lat:.3f}°N, {lon:.3f}°E",
            "",
        ]

        for name, r in list(seen_species.items())[:10]:
            date = (r.get("eventDate") or "")[:10]
            kingdom = r.get("kingdom", "")
            emoji = {"Animalia": "🦌", "Plantae": "🌿", "Fungi": "🍄"}.get(kingdom, "🔬")
            line = f"{emoji} {name}"
            if date:
                line += f" ({date})"
            lines.append(line)

        lines.append("\nKilde: GBIF.org")
        return _json_ok("\n".join(lines))

    except Exception as e:
        logger.error(f"Dyr API feilet: {e}")
        return _json_err("Klarte ikke søke etter dyr.")


@app.get("/api/luft")
def api_luft(lat: float = Query(...), lon: float = Query(...)):
    from gps_commands import air_quality
    return _json_ok(air_quality(lat, lon))


@app.get("/api/lading")
def api_lading(lat: float = Query(...), lon: float = Query(...)):
    from gps_commands import nearest_chargers
    return _json_ok(nearest_chargers(lat, lon))


@app.get("/api/uv")
def api_uv(lat: float = Query(...), lon: float = Query(...)):
    from gps_commands import uv_index
    return _json_ok(uv_index(lat, lon))


@app.get("/api/navn")
def api_navn(lat: float = Query(...), lon: float = Query(...)):
    from gps_commands import format_names_report
    return _json_ok(format_names_report(lat=lat, lon=lon))


@app.get("/api/geologi")
def api_geologi(lat: float = Query(...), lon: float = Query(...)):
    from gps_commands import geology
    return _json_ok(geology(lat, lon))


@app.get("/api/nordlys")
def api_nordlys(lat: float = Query(...), lon: float = Query(...)):
    from fun import aurora_forecast_gps
    return _json_ok(aurora_forecast_gps(lat, lon))


@app.get("/api/webcam")
def api_webcam_nearest(lat: float = Query(...), lon: float = Query(...)):
    """Finner nærmeste webkamera via Yr.no, returnerer bilde-URL og info."""
    try:
        url = f"https://www.yr.no/api/v0/locations/search?lat={lat}&lon={lon}&accuracy=100000&language=nb"
        req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=8).read())
        locs = data.get("_embedded", {}).get("location", [])

        for loc in locs[:5]:
            loc_id = loc["id"]
            cam_url = f"https://www.yr.no/api/v0/locations/{loc_id}/cameras"
            req2 = urllib.request.Request(cam_url, headers={"User-Agent": "oil-alert-bot/1.0"})
            cam_data = json.loads(urllib.request.urlopen(req2, timeout=8).read())
            cameras = cam_data.get("cameras", [])

            if cameras:
                cam = cameras[0]
                views = cam.get("views", [])
                if not views:
                    continue
                img_url = views[0].get("images", {}).get("large", {}).get("url", "")
                if not img_url:
                    continue
                return {
                    "ok": True,
                    "name": cam.get("name", "Ukjent"),
                    "distance": cam.get("distance", 0),
                    "image_url": img_url,
                }

        return _json_err("Fant ingen webkameraer i nærheten.")
    except Exception as e:
        logger.error(f"Webcam API feilet: {e}")
        return _json_err("Klarte ikke finne webkamera.")


# ──────────────────────────────────────────────
# Endepunkter uten GPS
# ──────────────────────────────────────────────

@app.get("/api/price")
def api_price():
    from price import fetch_brent_price, _load_ref
    current = fetch_brent_price()
    if current is None:
        return _json_err("Klarte ikke hente Brent-pris.")

    ref = _load_ref()
    lines = ["🛢️ BRENT CRUDE", "", f"💰 ${current:.2f} per fat"]
    if ref:
        change = current - ref["price"]
        pct = (change / ref["price"]) * 100
        emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
        lines.append(f"{emoji} {change:+.2f} USD ({pct:+.1f}%) fra referanse")

    return _json_ok("\n".join(lines), {"price": current})


@app.get("/api/iss")
def api_iss():
    from fun import iss_status
    return _json_ok(iss_status())


@app.get("/api/fakta")
def api_fakta():
    from fun import random_fact
    return _json_ok(random_fact())


@app.get("/api/romfart")
def api_romfart():
    from fun import space_travel
    return _json_ok(space_travel())


@app.get("/api/bmi")
def api_bmi():
    """Overvekt-statistikk fra FHI."""
    body = json.dumps({
        "dimensions": [
            {"code": "GEO", "filter": "item", "values": ["0", "39", "46", "56"]},
            {"code": "AAR", "filter": "bottom", "values": ["1"]},
            {"code": "KJONN", "filter": "item", "values": ["0"]},
            {"code": "ALDER", "filter": "item", "values": ["17_17"]},
            {"code": "KMI_KAT", "filter": "item", "values": ["overv_inkl_fedme", "fedme"]},
            {"code": "MEASURE_TYPE", "filter": "item", "values": ["RATE"]},
        ],
        "response": {"format": "json-stat2"},
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://statistikk-data.fhi.no/api/open/v1/nokkel/Table/388/data",
            data=body,
            headers={"User-Agent": "oil-alert-bot/1.0", "Content-Type": "application/json"},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())

        geo_labels = data["dimension"]["GEO"]["category"]["label"]
        geo_index = data["dimension"]["GEO"]["category"]["index"]
        kmi_index = data["dimension"]["KMI_KAT"]["category"]["index"]
        year_labels = data["dimension"]["AAR"]["category"]["label"]
        year = list(year_labels.values())[0]
        values = data["value"]
        stride_geo = len(kmi_index)

        lines = [
            f"⚖️ OVERVEKT BLANT 17-ÅRINGER ({year})",
            "Kilde: FHI / Vernepliktsdata",
            "",
        ]

        for i, geo_code in enumerate(geo_index):
            name = geo_labels[geo_code]
            if name == "Hele landet":
                name = "🇳🇴 Norge"
            elif "Vestfold" in name:
                name = "📍 Vestfold"
            elif "Vestland" in name:
                name = "📍 Vestland"
            elif "Finnmark" in name:
                name = "📍 Finnmark"

            overvekt = values[i * stride_geo]
            fedme = values[i * stride_geo + 1]
            if overvekt is not None:
                lines.append(f"{name}: {overvekt:.1f}% overvekt, {fedme:.1f}% fedme")
            else:
                lines.append(f"{name}: N/A")

        lines.append("\nOvervekt = BMI > 25, Fedme = BMI > 30")
        return _json_ok("\n".join(lines))

    except Exception as e:
        logger.error(f"BMI API feilet: {e}")
        return _json_err("Klarte ikke hente BMI-data.")


@app.get("/api/andreasnese")
def api_andreasnese():
    """Returnerer Andreas Nese-bildet."""
    import os
    for path in ["/app/andreasnese.png", "andreasnese.png", "./andreasnese.png"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return Response(content=f.read(), media_type="image/png",
                                headers={"Cache-Control": "public, max-age=3600"})
    return Response(status_code=404)


@app.get("/api/tonsberg")
def api_tonsberg():
    """Vær og sjøtemperatur for Tønsberg/Revetal."""
    lines = ["🌤️ TØNSBERG / REVETAL – Akkurat nå", ""]

    # Vær
    try:
        req = urllib.request.Request(
            "https://www.yr.no/api/v0/locations/1-46918/forecast/currenthour",
            headers={"User-Agent": "oil-alert-bot/1.0"},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        temp = data["temperature"]["value"]
        feels = data["temperature"]["feelsLike"]
        wind_speed = data["wind"]["speed"]
        wind_gust = data["wind"]["gust"]
        wind_dir = data["wind"]["direction"]
        precip = data["precipitation"]["value"]
        symbol = data.get("symbolCode", {}).get("next1Hour", "")

        weather_emojis = {
            "clearsky": "☀️", "fair": "🌤️", "partlycloudy": "⛅",
            "cloudy": "☁️", "rain": "🌧️", "heavyrain": "🌧️🌧️",
            "lightrain": "🌦️", "sleet": "🌨️", "snow": "❄️",
            "heavysnow": "❄️❄️", "fog": "🌫️", "thunder": "⛈️",
        }
        base_symbol = symbol.replace("_day", "").replace("_night", "").replace("_polartwilight", "")
        emoji = weather_emojis.get(base_symbol, "🌡️")

        from weather import _degrees_to_direction, _wind_description
        wind_dir_str = _degrees_to_direction(wind_dir)
        wind_desc = _wind_description(wind_speed)

        lines += [
            f"{emoji} {temp:.1f}°C (føles som {feels}°C)",
            f"💨 {wind_speed:.1f} m/s fra {wind_dir_str}, kast {wind_gust:.1f} m/s ({wind_desc})",
        ]
        if precip > 0:
            lines.append(f"🌧️ Nedbør: {precip:.1f} mm neste time")
        else:
            lines.append("☂️ Opphold neste time")
    except Exception as e:
        lines.append(f"⚠️ Klarte ikke hente vær: {e}")

    # Sjøtemperatur
    try:
        req = urllib.request.Request(
            "https://www.yr.no/api/v0/locations/1-46918/nearestwatertemperatures",
            headers={"User-Agent": "oil-alert-bot/1.0"},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        nearest = data["_embedded"]["nearestLocations"][0]
        sea_temp = nearest["temperature"]
        sea_name = nearest["location"]["name"]
        lines += ["", f"🌊 Sjøtemperatur ({sea_name}): {sea_temp:.1f}°C"]
    except Exception:
        pass

    return _json_ok("\n".join(lines))


@app.get("/api/bardfjord")
def api_bardfjord():
    """Vind på Bårdfjordneset."""
    from weather import format_wind_report
    msg = format_wind_report()
    if msg is None:
        return _json_err("Klarte ikke hente vinddata.")
    return _json_ok(msg)


@app.get("/api/navn/{region}")
def api_navn_region(region: str):
    """Babynavn for en spesifikk region."""
    from gps_commands import format_names_report
    # Map URL-vennlige navn til riktig region
    region_map = {
        "oslo": "Oslo", "akershus": "Akershus", "ostfold": "Østfold",
        "buskerud": "Buskerud", "vestfold": "Vestfold", "telemark": "Telemark",
        "agder": "Agder", "rogaland": "Rogaland", "vestland": "Vestland",
        "innlandet": "Innlandet", "moreogromsdal": "Møre og Romsdal",
        "trondelag": "Trøndelag", "nordland": "Nordland", "troms": "Troms",
        "finnmark": "Finnmark",
    }
    mapped = region_map.get(region.lower(), region)
    return _json_ok(format_names_report(region=mapped))


@app.post("/api/feature")
async def api_feature_request(request_body: dict = None):
    """Mottar feature requests og lagrer til fil."""
    from fastapi import Request
    import os
    from pathlib import Path

    text = (request_body or {}).get("text", "").strip()
    if not text:
        return _json_err("Tomt ønske.")

    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    feature_file = data_dir / "feature_requests.log"

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(feature_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {text}\n")

    logger.info(f"Feature request: {text[:100]}")
    return {"ok": True}


# ──────────────────────────────────────────────
# Webkameraer – statiske
# ──────────────────────────────────────────────

WEBCAMS = {
    "tonsbergbat": {"name": "⛵ Ollebukta, Tønsberg", "url": "https://ollebukta.no/Ollebukta.jpg"},
    "sotrabro1": {"name": "🌉 Sotrabrua (retning 1)", "url": "https://www.yr.no/webcams/3/2000/1229038_1"},
    "sotrabro2": {"name": "🌉 Sotrabrua (retning 2)", "url": "https://www.yr.no/webcams/3/2000/1229038_2"},
    "vidden": {"name": "🏔️ Vidden, Bergen", "url": "https://www.yr.no/webcams/1/2000/enbg/3.jpg"},    "bergenulriken": {"name": "🏔️ Ulriken, Bergen", "url": "https://images.stream.schibsted.media/users/bttts/images/a1dc26cff813577b947620d56f455247.jpg"},
    "bergenhavn": {"name": "🚢 Bergen havn", "url": "https://www.node.no/images/webcam/webcam.jpg"},
    "osloradhus": {"name": "🏛️ Rådhuskaia, Oslo", "url": "https://www.oslohavn.no/webcam/raadhusintranett.jpg"},
    "talvik": {"name": "🏔️ Talvik, Altafjorden", "url": "https://www.worldcam.pl/images/webcams/840x472/6932bac27d998.jpg"},
    "soroya": {"name": "🏝️ Sørøya, Breivikbotn", "url": "https://www.worldcam.pl/images/webcams/420x236/657037edbe16c.jpg"},
}


@app.get("/api/webcams")
def api_webcams_list():
    """Returnerer liste over alle tilgjengelige webkameraer."""
    cams = [{"id": k, "name": v["name"]} for k, v in WEBCAMS.items()]
    # Legg til Alta som spesialtilfelle
    cams.append({"id": "alta", "name": "🏔️ Alta havn (panorama)"})
    return {"ok": True, "webcams": cams}


@app.get("/api/webcam/{cam_id}")
def api_webcam_by_id(cam_id: str):
    """Returnerer bilde-URL (eller proxyet bilde) for et spesifikt kamera."""
    if cam_id == "alta":
        return _get_alta_image_url()

    cam = WEBCAMS.get(cam_id)
    if not cam:
        return _json_err(f"Ukjent kamera: {cam_id}")

    return {"ok": True, "name": cam["name"], "image_url": cam["url"]}


def _get_alta_image_url() -> dict:
    """Finner ferskeste Alta panorama-bilde URL."""
    utc_now = datetime.utcnow()
    cet_now = utc_now + timedelta(hours=1)

    for minutes_back in range(0, 15):
        t = cet_now - timedelta(minutes=minutes_back)
        url = (
            f"https://skaping.s3.gra.io.cloud.ovh.net/port-of-alta/"
            f"{t.strftime('%Y/%m/%d')}/large/{t.strftime('%H-%M')}.jpg"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
            resp = urllib.request.urlopen(req, timeout=5)
            if int(resp.headers.get("Content-Length", 0)) > 10000:
                return {"ok": True, "name": "🏔️ Alta havn (panorama)", "image_url": url, "time": t.strftime("%H:%M")}
        except Exception:
            continue

    return _json_err("Fant ingen ferske bilder fra Alta.")


@app.get("/api/webcam/{cam_id}/image")
def api_webcam_image(cam_id: str):
    """Proxyer webkamera-bilde (for å unngå CORS-problemer i PWA).
    NB: Denne er sync (def, ikke async) slik at FastAPI kjører den i threadpool
    og urllib.request ikke blokkerer event-loopen.
    """
    if cam_id == "alta":
        info = _get_alta_image_url()
        if not info.get("ok"):
            return Response(status_code=404)
        img_url = info["image_url"]
    else:
        cam = WEBCAMS.get(cam_id)
        if not cam:
            return Response(status_code=404)
        img_url = cam["url"]

    try:
        req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0 (compatible; oil-alert-bot/1.0)"})
        image_data = urllib.request.urlopen(req, timeout=15).read()
        content_type = "image/jpeg"
        if img_url.endswith(".png"):
            content_type = "image/png"
        return Response(content=image_data, media_type=content_type,
                        headers={"Cache-Control": "public, max-age=30"})
    except Exception as e:
        logger.error(f"Webcam proxy feilet for {cam_id}: {e}")
        return Response(status_code=502)


# ──────────────────────────────────────────────
# Monter statiske filer (PWA) – gjøres fra main.py
# ──────────────────────────────────────────────
