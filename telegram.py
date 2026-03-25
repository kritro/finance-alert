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
from datetime import datetime, timedelta
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
    from price import fetch_brent_price
    price = fetch_brent_price()
    price_str = f"Brent nå: ${price:.2f}/fat" if price else "Brent-pris: hentes ved neste sjekk"

    payload = {
        "chat_id": chat_id,
        "text": (
            "🛢️ Oljepris-varsler startet!\n\n"
            f"📊 {price_str}\n"
            f"⚙️ Prisvarsel ved ±$3.00 endring\n"
            f"📡 Overvåker 12+ nyhetskilder hvert 5. minutt\n\n"
            "Du vil motta varsler når noe skjer."
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


# Holder styr på hvilken kommando som venter på GPS
_pending_location: dict[str, str] = {}


def run_command_listener(token: str, chat_id: str) -> None:
    """
    Lytter etter innkommende kommandoer i en egen tråd.
    Bruker Telegram long polling (blokkerer til ny melding kommer).
    Svarer instant – ingen ventetid.
    """
    last_update_id = 0

    # Tøm gamle meldinger først
    result = _api_call(token, "getUpdates", {"offset": -1, "limit": 1, "timeout": 0})
    if result and result.get("ok") and result.get("result"):
        last_update_id = result["result"][-1]["update_id"]

    logger.info("Kommando-lytter startet (instant-svar aktivert)")

    while True:
        try:
            result = _api_call(token, "getUpdates", {
                "offset": last_update_id + 1,
                "limit": 10,
                "timeout": 25,  # Long poll – venter opptil 25 sek på ny melding
            }, timeout=30)

            if not result or not result.get("ok"):
                continue

            for update in result.get("result", []):
                update_id = update.get("update_id", 0)
                last_update_id = max(last_update_id, update_id)

                msg = update.get("message", {})
                text = msg.get("text", "").strip().lower()
                msg_chat_id = str(msg.get("chat", {}).get("id", ""))

                if msg_chat_id != chat_id:
                    continue

                if text in ("/price", "/pris", "pris", "price", "oil", "olje"):
                    _handle_price_command(token, chat_id)
                elif text in ("/bårdfjord", "bårdfjord"):
                    _handle_wind_command(token, chat_id)
                elif text in ("/sotrabro", "sotrabro"):
                    _handle_sotrabro_command(token, chat_id)
                elif text in ("/tønsbergbåt", "tønsbergbåt", "/tonsbergbat"):
                    _handle_webcam_url_command(token, chat_id, "https://ollebukta.no/Ollebukta.jpg", "⛵ Ollebukta, Tønsberg")
                elif text in ("/tønsbergilene", "tønsbergilene", "/ilene"):
                    _handle_youtube_live_command(token, chat_id, "@fuglekamerailene", "🐦 Fuglekamera Ilene, Tønsberg")
                elif text in ("/bergenpuddefjord", "bergenpuddefjord"):
                    _handle_webcam_url_command(token, chat_id, "https://btweb.vosskom.no/bt_puddefjordsbroen.jpg", "🌉 Puddefjordsbroen, Bergen")
                elif text in ("/bergenfløyen", "bergenfløyen", "/bergenfloyen"):
                    _handle_webcam_url_command(token, chat_id, "https://btweb.vosskom.no/bt_floyen_vest.jpg", "⛰️ Fløyen, Bergen")
                elif text in ("/bergenulriken", "bergenulriken"):
                    _handle_webcam_url_command(token, chat_id, "https://images.stream.schibsted.media/users/bttts/images/a1dc26cff813577b947620d56f455247.jpg", "🏔️ Ulriken, Bergen")
                elif text in ("/bergenhavn", "bergenhavn"):
                    _handle_webcam_url_command(token, chat_id, "https://www.node.no/images/webcam/webcam.jpg", "🚢 Bergen havn")
                elif text in ("/oslorådhus", "oslorådhus", "/osloradhus"):
                    _handle_webcam_url_command(token, chat_id, "https://www.oslohavn.no/webcam/raadhusintranett.jpg", "🏛️ Rådhuskaia, Oslo")
                elif text in ("/talvik", "talvik"):
                    _handle_webcam_url_command(token, chat_id, "https://www.worldcam.pl/images/webcams/840x472/6932bac27d998.jpg", "🏔️ Talvik, Altafjorden")
                elif text in ("/sørøya", "sørøya", "/soroya"):
                    _handle_webcam_url_command(token, chat_id, "https://www.worldcam.pl/images/webcams/420x236/657037edbe16c.jpg", "🏝️ Sørøya, Breivikbotn")
                elif text in ("/alta", "alta"):
                    _handle_alta_command(token, chat_id)
                elif text in ("/tønsberg", "tønsberg", "/tonsberg", "tonsberg"):
                    _handle_tonsberg_command(token, chat_id)
                elif text in ("/iss", "iss"):
                    _handle_fun_command(token, chat_id, "iss")
                elif text in ("/nordlys", "nordlys", "/aurora"):
                    _handle_fun_command(token, chat_id, "nordlys")
                elif text in ("/fakta", "fakta", "/fact"):
                    _handle_fun_command(token, chat_id, "fakta")
                elif text in ("/andreasnese", "andreasnese"):
                    _handle_image_command(token, chat_id, "andreasnese.png", "👃 Andreas Nese")
                elif text in ("/dyr", "dyr"):
                    _pending_location[chat_id] = "dyr"
                    _request_location(token, chat_id, "🐾 Del posisjonen din så finner jeg dyr i nærheten!")
                elif text in ("/buss", "buss"):
                    _pending_location[chat_id] = "buss"
                    _request_location(token, chat_id, "🚌 Del posisjonen din så finner jeg neste bussavgang!")
                elif text in ("/luft", "luft"):
                    _pending_location[chat_id] = "luft"
                    _request_location(token, chat_id, "🌬️ Del posisjonen din så sjekker jeg luftkvaliteten!")
                elif text in ("/lading", "lading"):
                    _pending_location[chat_id] = "lading"
                    _request_location(token, chat_id, "⚡ Del posisjonen din så finner jeg nærmeste elbil-lader!")
                elif text in ("/uv", "uv"):
                    _pending_location[chat_id] = "uv"
                    _request_location(token, chat_id, "☀️ Del posisjonen din så sjekker jeg UV-strålingen!")
                elif text in ("/webcam", "webcam"):
                    _pending_location[chat_id] = "webcam"
                    _request_location(token, chat_id, "📷 Del posisjonen din så finner jeg nærmeste webkamera!")
                elif text in ("/navn", "navn"):
                    _pending_location[chat_id] = "navn"
                    _request_location(token, chat_id, "👶 Del posisjonen din så viser jeg populære babynavn!")
                elif text in ("/navnoslo",):
                    from gps_commands import format_names_report
                    _api_call(token, "sendMessage", {"chat_id": chat_id, "text": format_names_report(region="Oslo")})
                elif text in ("/navnvestland",):
                    from gps_commands import format_names_report
                    _api_call(token, "sendMessage", {"chat_id": chat_id, "text": format_names_report(region="Vestland")})
                elif text in ("/navnfinnmark",):
                    from gps_commands import format_names_report
                    _api_call(token, "sendMessage", {"chat_id": chat_id, "text": format_names_report(region="Finnmark")})
                elif text in ("/romfart", "romfart", "/space"):
                    _handle_fun_command(token, chat_id, "romfart")
                elif text in ("/bmi", "bmi"):
                    _handle_bmi_command(token, chat_id)

                # Sjekk om meldingen inneholder en lokasjon (GPS)
                location = msg.get("location")
                if location:
                    cmd = _pending_location.pop(chat_id, "dyr")
                    lat, lon = location["latitude"], location["longitude"]
                    if cmd == "dyr":
                        _handle_location(token, chat_id, lat, lon)
                    elif cmd == "buss":
                        from gps_commands import nearest_departures
                        _api_call(token, "sendMessage", {
                            "chat_id": chat_id,
                            "text": nearest_departures(lat, lon),
                            "reply_markup": json.dumps({"remove_keyboard": True}),
                        })
                    elif cmd == "luft":
                        from gps_commands import air_quality
                        _api_call(token, "sendMessage", {
                            "chat_id": chat_id,
                            "text": air_quality(lat, lon),
                            "reply_markup": json.dumps({"remove_keyboard": True}),
                        })
                    elif cmd == "lading":
                        from gps_commands import nearest_chargers
                        _api_call(token, "sendMessage", {
                            "chat_id": chat_id,
                            "text": nearest_chargers(lat, lon),
                            "reply_markup": json.dumps({"remove_keyboard": True}),
                        })
                    elif cmd == "uv":
                        from gps_commands import uv_index
                        _api_call(token, "sendMessage", {
                            "chat_id": chat_id,
                            "text": uv_index(lat, lon),
                            "reply_markup": json.dumps({"remove_keyboard": True}),
                        })
                    elif cmd == "webcam":
                        _handle_nearest_webcam(token, chat_id, lat, lon)
                    elif cmd == "navn":
                        from gps_commands import format_names_report
                        _api_call(token, "sendMessage", {
                            "chat_id": chat_id,
                            "text": format_names_report(lat=lat, lon=lon),
                            "reply_markup": json.dumps({"remove_keyboard": True}),
                        })
                elif text in ("/status", "status"):
                    _handle_status_command(token, chat_id)
                elif text in ("/help", "help", "hjelp", "/hjelp", "/start"):
                    _handle_help_command(token, chat_id)

        except Exception as e:
            logger.error(f"Kommando-lytter feil: {e}")
            import time
            time.sleep(5)  # Vent litt før retry


def _handle_price_command(token: str, chat_id: str) -> None:
    """Svarer med nåværende Brent-pris."""
    from price import fetch_brent_price, _load_ref

    current = fetch_brent_price()
    if current is None:
        _api_call(token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ Klarte ikke hente Brent-pris akkurat nå. Prøv igjen om litt.",
        })
        return

    ref = _load_ref()
    lines = [
        "🛢️ BRENT CRUDE",
        "",
        f"💰 ${current:.2f} per fat",
    ]

    if ref:
        change = current - ref["price"]
        pct = (change / ref["price"]) * 100
        emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
        lines.append(f"{emoji} {change:+.2f} USD ({pct:+.1f}%) fra referanse")

    _api_call(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "\n".join(lines),
    })


def _request_location(token: str, chat_id: str, text: str) -> None:
    """Sender en melding med knapp for å dele lokasjon."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": json.dumps({
            "keyboard": [[{"text": "📍 Del min posisjon", "request_location": True}]],
            "one_time_keyboard": True,
            "resize_keyboard": True,
        }),
    }
    _api_call(token, "sendMessage", payload)


def _handle_location(token: str, chat_id: str, lat: float, lon: float) -> None:
    """Henter dyreobservasjoner nær brukerens GPS-posisjon via GBIF."""
    import urllib.request as _req

    # Søk i radius ~5km rundt posisjonen
    delta = 0.05  # ca 5km
    url = (
        f"https://api.gbif.org/v1/occurrence/search?"
        f"decimalLatitude={lat - delta},{lat + delta}&"
        f"decimalLongitude={lon - delta},{lon + delta}&"
        f"country=NO&limit=15&orderBy=eventDate"
    )

    try:
        req = _req.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
        data = json.loads(_req.urlopen(req, timeout=10).read())

        results = data.get("results", [])
        total = data.get("count", 0)

        if not results:
            _api_call(token, "sendMessage", {
                "chat_id": chat_id,
                "text": "🤷 Ingen observasjoner funnet i nærheten.",
                "reply_markup": json.dumps({"remove_keyboard": True}),
            })
            return

        # Dedupliser på artsnavn, behold siste observasjon per art
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
            latin = r.get("scientificName", "")
            kingdom = r.get("kingdom", "")

            if kingdom == "Animalia":
                emoji = "🦌"
            elif kingdom == "Plantae":
                emoji = "🌿"
            elif kingdom == "Fungi":
                emoji = "🍄"
            else:
                emoji = "🔬"

            line = f"{emoji} {name}"
            if date:
                line += f" ({date})"
            lines.append(line)

        lines.append(f"\nKilde: GBIF.org")

        _api_call(token, "sendMessage", {
            "chat_id": chat_id,
            "text": "\n".join(lines),
            "reply_markup": json.dumps({"remove_keyboard": True}),
        })

    except Exception as e:
        logger.error(f"Dyr-søk feilet: {e}")
        _api_call(token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ Klarte ikke søke etter dyr akkurat nå.",
            "reply_markup": json.dumps({"remove_keyboard": True}),
        })


def _handle_bmi_command(token: str, chat_id: str) -> None:
    """Henter overvekt-statistikk fra FHI for Tønsberg, Bergen og Alta."""
    import urllib.request as _req

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
        req = _req.Request(
            "https://statistikk-data.fhi.no/api/open/v1/nokkel/Table/388/data",
            data=body,
            headers={"User-Agent": "oil-alert-bot/1.0", "Content-Type": "application/json"},
        )
        data = json.loads(_req.urlopen(req, timeout=10).read())

        # Parse json-stat2
        geo_labels = data["dimension"]["GEO"]["category"]["label"]
        geo_index = data["dimension"]["GEO"]["category"]["index"]
        kmi_index = data["dimension"]["KMI_KAT"]["category"]["index"]
        kmi_labels = data["dimension"]["KMI_KAT"]["category"]["label"]
        year_labels = data["dimension"]["AAR"]["category"]["label"]
        year = list(year_labels.values())[0]
        values = data["value"]
        sizes = data["size"]

        # Values layout: GEO × AAR × KJONN × ALDER × KMI_KAT × MEASURE
        # sizes: [4, 1, 1, 1, 2, 1] -> stride for GEO = 2, KMI_KAT = 1
        stride_kmi = 1
        stride_geo = len(kmi_index) * stride_kmi

        lines = [
            f"⚖️ OVERVEKT BLANT 17-ÅRINGER ({year})",
            "Kilde: FHI / Vernepliktsdata",
            "",
            f"{'Kommune':<14} {'Overvekt':>10} {'Fedme':>8}",
            f"{'─' * 14} {'─' * 10} {'─' * 8}",
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
                lines.append(f"{name:<14} {overvekt:>9.1f}% {fedme:>7.1f}%")
            else:
                lines.append(f"{name:<14} {'N/A':>10} {'N/A':>8}")

        lines += [
            "",
            "Overvekt = BMI > 25, Fedme = BMI > 30",
        ]

        _api_call(token, "sendMessage", {"chat_id": chat_id, "text": "\n".join(lines)})

    except Exception as e:
        logger.error(f"BMI feilet: {type(e).__name__}: {e}")
        _api_call(token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ Klarte ikke hente BMI-data fra FHI.",
        })


def _handle_image_command(token: str, chat_id: str, filename: str, caption: str) -> None:
    """Sender et statisk bilde fra repo."""
    import os
    import uuid

    # Finn bildefilen relativt til app-mappen
    for path in [f"/app/{filename}", filename, f"./{filename}"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                image_data = f.read()
            break
    else:
        _api_call(token, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Fant ikke bildet."})
        return

    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        logger.error(f"Bilde-sending feilet: {e}")


def _handle_fun_command(token: str, chat_id: str, cmd: str) -> None:
    """Håndterer morsomme kommandoer."""
    from fun import iss_status, aurora_forecast, random_fact, space_travel

    handlers = {
        "iss": iss_status,
        "nordlys": aurora_forecast,
        "fakta": random_fact,
        "romfart": space_travel,
    }
    fn = handlers.get(cmd)
    if fn:
        msg = fn()
        _api_call(token, "sendMessage", {"chat_id": chat_id, "text": msg})


def _handle_tonsberg_command(token: str, chat_id: str) -> None:
    """Vær og sjøtemperatur for Tønsberg/Revetal."""
    import urllib.request as _req
    import json as _json

    lines = ["🌤️ TØNSBERG / REVETAL – Akkurat nå", ""]

    # Vær
    try:
        r = _req.Request(
            "https://www.yr.no/api/v0/locations/1-46918/forecast/currenthour",
            headers={"User-Agent": "oil-alert-bot/1.0"},
        )
        data = _json.loads(_req.urlopen(r, timeout=10).read())
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
        r = _req.Request(
            "https://www.yr.no/api/v0/locations/1-46918/nearestwatertemperatures",
            headers={"User-Agent": "oil-alert-bot/1.0"},
        )
        data = _json.loads(_req.urlopen(r, timeout=10).read())
        nearest = data["_embedded"]["nearestLocations"][0]
        sea_temp = nearest["temperature"]
        sea_name = nearest["location"]["name"]
        lines += ["", f"🌊 Sjøtemperatur ({sea_name}): {sea_temp:.1f}°C"]
    except Exception:
        pass

    _api_call(token, "sendMessage", {"chat_id": chat_id, "text": "\n".join(lines)})


def _handle_alta_command(token: str, chat_id: str) -> None:
    """Sender live 360° panoramabilde fra Port of Alta (3 deler)."""
    import urllib.request

    # Bildene ligger på S3 med CET-tidsstempler (UTC+1)
    utc_now = datetime.utcnow()
    cet_now = utc_now + timedelta(hours=1)

    image_data = None
    time_str = ""

    for minutes_back in range(0, 15):
        t = cet_now - timedelta(minutes=minutes_back)
        url = (
            f"https://skaping.s3.gra.io.cloud.ovh.net/port-of-alta/"
            f"{t.strftime('%Y/%m/%d')}/large/{t.strftime('%H-%M')}.jpg"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
            data = urllib.request.urlopen(req, timeout=10).read()
            if len(data) > 10000:
                image_data = data
                time_str = t.strftime("%H:%M")
                break
        except Exception:
            continue

    if not image_data:
        _api_call(token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ Fant ingen ferske bilder fra Alta akkurat nå.",
        })
        return

    try:
        from io import BytesIO
        from PIL import Image

        img = Image.open(BytesIO(image_data))
        w, h = img.size
        part_w = w // 5
        parts = [
            ("Vest", img.crop((0, 0, part_w, h))),
            ("Nordvest", img.crop((part_w, 0, part_w * 2, h))),
            ("Nord", img.crop((part_w * 2, 0, part_w * 3, h))),
            ("Nordøst", img.crop((part_w * 3, 0, part_w * 4, h))),
            ("Øst", img.crop((part_w * 4, 0, w, h))),
        ]

        for label, part_img in parts:
            buf = BytesIO()
            part_img.save(buf, format="JPEG", quality=85)
            part_data = buf.getvalue()
            caption = f"🏔️ Alta havn – {label} – {time_str}"

            import uuid
            boundary = uuid.uuid4().hex
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="photo"; filename="alta.jpg"\r\n'
                f"Content-Type: image/jpeg\r\n\r\n"
            ).encode("utf-8") + part_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

            api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
            req2 = urllib.request.Request(api_url, data=body, headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            })
            urllib.request.urlopen(req2, timeout=15)

    except Exception as e:
        logger.error(f"Alta feilet: {type(e).__name__}: {e}")
        _api_call(token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ Klarte ikke prosessere Alta-bilde.",
        })


def _handle_nearest_webcam(token: str, chat_id: str, lat: float, lon: float) -> None:
    """Finner og sender bilde fra nærmeste webkamera via Yr.no."""
    import urllib.request
    import uuid

    try:
        # Finn nærmeste Yr-lokasjon
        url = f"https://www.yr.no/api/v0/locations/search?lat={lat}&lon={lon}&accuracy=100000&language=nb"
        req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=8).read())
        locs = data.get("_embedded", {}).get("location", [])

        if not locs:
            _api_call(token, "sendMessage", {
                "chat_id": chat_id,
                "text": "⚠️ Fant ingen lokasjon i nærheten.",
                "reply_markup": json.dumps({"remove_keyboard": True}),
            })
            return

        # Prøv lokasjonene til vi finner en med kameraer
        for loc in locs[:5]:
            loc_id = loc["id"]
            cam_url = f"https://www.yr.no/api/v0/locations/{loc_id}/cameras"
            req2 = urllib.request.Request(cam_url, headers={"User-Agent": "oil-alert-bot/1.0"})
            cam_data = json.loads(urllib.request.urlopen(req2, timeout=8).read())
            cameras = cam_data.get("cameras", [])

            if cameras:
                cam = cameras[0]
                cam_name = cam.get("name", "Ukjent")
                cam_dist = cam.get("distance", 0)
                views = cam.get("views", [])

                if not views:
                    continue

                img_url = views[0].get("images", {}).get("large", {}).get("url", "")
                if not img_url:
                    continue

                # Hent bildet
                req3 = urllib.request.Request(img_url, headers={"User-Agent": "oil-alert-bot/1.0"})
                image_data = urllib.request.urlopen(req3, timeout=10).read()

                if len(image_data) < 5000:
                    continue

                dist_km = cam_dist / 1000 if cam_dist > 1000 else 0
                if dist_km > 0:
                    caption = f"📷 {cam_name} ({dist_km:.1f} km unna)"
                else:
                    caption = f"📷 {cam_name} ({cam_dist:.0f}m unna)"

                boundary = uuid.uuid4().hex
                body = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="photo"; filename="webcam.jpg"\r\n'
                    f"Content-Type: image/jpeg\r\n\r\n"
                ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

                req4 = urllib.request.Request(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    data=body,
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                )
                urllib.request.urlopen(req4, timeout=15)

                _api_call(token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": f"Kilde: Yr.no",
                    "reply_markup": json.dumps({"remove_keyboard": True}),
                })
                return

        _api_call(token, "sendMessage", {
            "chat_id": chat_id,
            "text": "📷 Fant ingen webkameraer i nærheten.",
            "reply_markup": json.dumps({"remove_keyboard": True}),
        })

    except Exception as e:
        logger.error(f"Webcam-søk feilet: {e}")
        _api_call(token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ Klarte ikke finne webkamera.",
            "reply_markup": json.dumps({"remove_keyboard": True}),
        })


def _handle_youtube_live_command(token: str, chat_id: str, channel: str, caption: str) -> None:
    """Henter stillbilde fra en YouTube live-stream."""
    import urllib.request
    import uuid
    import re

    try:
        # Finn video-ID fra kanalens live-side
        req = urllib.request.Request(
            f"https://www.youtube.com/{channel}/live",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="replace")
        match = re.search(r'watch\?v=([a-zA-Z0-9_-]{11})', html)
        if not match:
            _api_call(token, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Ingen aktiv live-stream funnet."})
            return

        video_id = match.group(1)
        thumb_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault_live.jpg"

        req2 = urllib.request.Request(thumb_url, headers={"User-Agent": "oil-alert-bot/1.0"})
        image_data = urllib.request.urlopen(req2, timeout=10).read()

        if len(image_data) < 5000:
            _api_call(token, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Live-stream er ikke aktiv akkurat nå."})
            return

        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="live.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req3 = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        urllib.request.urlopen(req3, timeout=15)

    except Exception as e:
        logger.error(f"YouTube live feilet: {e}")
        _api_call(token, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Klarte ikke hente bilde fra live-stream."})


def _handle_webcam_url_command(token: str, chat_id: str, url: str, caption: str) -> None:
    """Henter og sender et webkamera-bilde fra en URL."""
    import urllib.request
    import uuid

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
        image_data = urllib.request.urlopen(req, timeout=15).read()

        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="cam.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req2 = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        urllib.request.urlopen(req2, timeout=15)
    except Exception as e:
        logger.error(f"Webcam feilet: {e}")
        _api_call(token, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ Klarte ikke hente bilde."})


def _handle_sotrabro_command(token: str, chat_id: str) -> None:
    """Sender live-bilde fra Sotrabrua-kameraet."""
    import urllib.request

    cam_urls = [
        ("Sotrabrua vest (retning 1)", "https://www.yr.no/webcams/3/2000/1229038_1"),
        ("Sotrabrua vest (retning 2)", "https://www.yr.no/webcams/3/2000/1229038_2"),
    ]

    for caption, url in cam_urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "oil-alert-bot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                image_data = resp.read()

            # Send bilde via Telegram multipart
            import uuid
            boundary = uuid.uuid4().hex
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="caption"\r\n\r\n🌉 {caption}\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="photo"; filename="sotra.jpg"\r\n'
                f"Content-Type: image/jpeg\r\n\r\n"
            ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

            api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
            req = urllib.request.Request(api_url, data=body, headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            })
            urllib.request.urlopen(req, timeout=15)
            logger.info(f"Sotrabro-bilde sendt: {caption}")

        except Exception as e:
            logger.error(f"Sotrabro-bilde feilet: {e}")
            _api_call(token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"⚠️ Klarte ikke hente bilde fra {caption}",
            })


def _handle_wind_command(token: str, chat_id: str) -> None:
    """Svarer med nåværende vind på Bårdfjordneset."""
    from weather import format_wind_report

    msg = format_wind_report()
    if msg is None:
        msg = "⚠️ Klarte ikke hente vinddata akkurat nå. Prøv igjen om litt."

    _api_call(token, "sendMessage", {
        "chat_id": chat_id,
        "text": msg,
    })


def _handle_status_command(token: str, chat_id: str) -> None:
    """Svarer med bot-status."""
    from seen import get_store
    store = get_store()
    stats = store.stats()

    lines = [
        "⚙️ BOT STATUS",
        "",
        f"📊 Artikler sett: {stats['total']}",
        f"💾 Persistent: {'ja' if stats['persistent'] else 'nei'}",
        f"📁 Fil: {stats['filepath']}",
        "",
        "🟢 Boten kjører normalt",
    ]

    _api_call(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "\n".join(lines),
    })


def _handle_help_command(token: str, chat_id: str) -> None:
    """Svarer med liste over kommandoer."""
    lines = [
        "🤖 KOMMANDOER",
        "",
        "📍 GPS-basert:",
        "  /buss – Nærmeste bussavgang",
        "  /dyr – Dyreliv i nærheten",
        "  /luft – Luftkvalitet",
        "  /lading – Nærmeste elbil-lader",
        "  /uv – UV-stråling",
        "  /navn – Populære babynavn i ditt fylke",
        "  /webcam – Nærmeste webkamera",
        "",
        "📷 Webkameraer:",
        "  /webcam – Nærmeste kamera (GPS)",
        "  /tønsbergbåt – Ollebukta marina",
        "  /tønsbergilene – Fuglekamera Ilene",
        "  /sotrabro – Sotrabrua trafikk",
        "  /alta – Alta havn panorama",
        "  /talvik – Talvik, Altafjorden",
        "  /sørøya – Breivikbotn, Sørøya",
        "  /bergenfløyen – Fløyen",
        "  /bergenulriken – Ulriken",
        "  /bergenpuddefjord – Puddefjordsbroen",
        "  /bergenhavn – Bergen havn",
        "  /oslorådhus – Rådhuskaia Oslo",
        "",
        "🌍 Vær:",
        "  /tønsberg – Vær og sjøtemp",
        "  /bårdfjord – Vind Bårdfjordneset",
        "",
        "📊 Info:",
        "  /price – Brent-oljepris",
        "  /bmi – Overvekt-statistikk",
        "  /navnoslo /navnvestland /navnfinnmark",
        "  /iss – Hvor er ISS?",
        "  /nordlys – Nordlys-varsling",
        "  /romfart – Din romreise i dag",
        "  /fakta – Tilfeldig fakta",
        "  /andreasnese – 👃",
    ]

    _api_call(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "\n".join(lines),
    })


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
