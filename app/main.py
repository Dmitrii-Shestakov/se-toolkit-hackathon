from __future__ import annotations

import itertools
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "wardrobe.db"
STATIC_DIR = BASE_DIR / "app" / "static"

load_dotenv(BASE_DIR / ".env")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("outfit_picker")
LAST_LLM_DEBUG: dict[str, Any] = {"status": "not_started"}

ALLOWED_TYPES = {"top", "bottom", "shoes", "jacket", "accessory"}
STYLE_PREFERENCES = {
    "casual": ["jeans", "hoodie", "t-shirt", "tee", "sneakers", "jacket", "джинс", "худи", "футбол", "куртк"],
    "sporty": ["joggers", "tracksuit", "hoodie", "sneakers", "windbreaker", "джоггер", "кроссов", "ветров", "спортив"],
    "minimal": ["shirt", "trousers", "coat", "white", "black", "boots", "рубаш", "брюк", "пальто", "ботин"],
}
WEATHER_CODE_LABELS = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "rain",
    65: "heavy rain",
    71: "slight snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
}
WEATHER_LABELS_RU = {
    "clear sky": "ясно",
    "mainly clear": "в основном ясно",
    "partly cloudy": "переменная облачность",
    "overcast": "пасмурно",
    "overcast (demo mode)": "пасмурно (демо-режим)",
    "fog": "туман",
    "depositing rime fog": "изморозь и туман",
    "light drizzle": "лёгкая морось",
    "drizzle": "морось",
    "dense drizzle": "сильная морось",
    "slight rain": "небольшой дождь",
    "rain": "дождь",
    "heavy rain": "сильный дождь",
    "slight snow": "небольшой снег",
    "snow": "снег",
    "heavy snow": "сильный снег",
    "rain showers": "ливни",
    "violent rain showers": "сильные ливни",
    "thunderstorm": "гроза",
}

TOP_WORDS = [
    "t-shirt", "tee", "shirt", "hoodie", "sweater", "jumper", "top", "polo", "blouse", "cardigan",
    "longsleeve", "long sleeve", "sweatshirt", "thermal", "fleece", "майк", "футбол", "рубаш", "худи",
    "свитер", "кофта", "поло", "блуз", "кардиган", "лонгслив", "толстов", "термо", "флис"
]
BOTTOM_WORDS = [
    "jeans", "trousers", "pants", "joggers", "shorts", "skirt", "leggings", "cargo", "chinos", "sweatpants",
    "джинс", "брюк", "штаны", "джоггер", "шорты", "юбка", "леггин", "карго", "чинос", "спортивн"
]
SHOES_WORDS = [
    "sneakers", "boots", "shoes", "trainers", "loafers", "sandals", "flip-flops", "flip flops", "slides",
    "slippers", "mules", "heels", "кроссов", "ботин", "туфл", "обув", "сандал", "сланц", "шлеп",
    "шлёп", "тапк", "сабо", "каблу"
]
JACKET_WORDS = [
    "jacket", "coat", "windbreaker", "parka", "blazer", "raincoat", "trench", "bomber", "puffer",
    "down jacket", "overshirt", "denim jacket", "vest", "anorak", "куртк", "пальто", "ветров",
    "парка", "пиджак", "плащ", "тренч", "бомбер", "пухов", "джинсовк", "жилет", "анорак"
]
ACCESSORY_WORDS = [
    "hat", "cap", "beanie", "gloves", "mittens", "scarf", "shawl", "sunglasses", "umbrella", "bucket hat",
    "panama", "кепк", "шапк", "перчат", "вареж", "шарф", "палантин", "очки", "зонт", "панама"
]
VERY_WARM_WORDS = ["coat", "parka", "puffer", "down jacket", "пухов", "пальто", "парка"]
WIND_RAIN_WORDS = ["jacket", "windbreaker", "coat", "boots", "raincoat", "куртк", "ветров", "плащ", "ботин"]
HOT_WEATHER_WORDS = ["t-shirt", "tee", "shirt", "shorts", "sandals", "flip-flops", "slides", "майк", "футбол", "шорты", "сланц", "сандал", "шлеп"]
COLD_WEATHER_WORDS = ["hoodie", "sweater", "coat", "boots", "gloves", "scarf", "beanie", "худи", "свитер", "пальто", "ботин", "перчат", "шарф", "шапк"]
SUMMER_UNFRIENDLY = ["flip-flops", "flip flops", "slides", "сланц", "шлеп", "шлёп", "тапк"]
ACCESSORY_COLD = ["hat", "beanie", "gloves", "mittens", "scarf", "шапк", "перчат", "вареж", "шарф"]
ACCESSORY_HOT = ["cap", "sunglasses", "bucket hat", "panama", "кепк", "очки", "панама"]


class WardrobeItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: Literal["top", "bottom", "shoes", "jacket", "accessory"] | None = None
    user_id: str = Field(default="demo", max_length=50)


class GenerateOutfitRequest(BaseModel):
    user_id: str = Field(default="demo", max_length=50)
    city: str | None = Field(default=None, max_length=80)
    latitude: float | None = None
    longitude: float | None = None
    style: Literal["casual", "sporty", "minimal"] = "casual"
    multiple: bool = False
    lang: Literal["ru", "en"] = "ru"


class SaveFavoriteRequest(BaseModel):
    user_id: str = Field(default="demo", max_length=50)
    city: str | None = Field(default=None, max_length=80)
    style: str = Field(default="casual", max_length=30)
    weather_summary: str = Field(max_length=200)
    items: list[dict[str, Any]]
    explanation: str = Field(max_length=1000)


@dataclass
class WeatherInfo:
    location_name: str
    temperature: float
    apparent_temperature: float
    wind_speed: float
    precipitation: float
    weather_code: int
    weather_label: str
    source: str = "live"
    provider: str = "Open-Meteo"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wardrobe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'demo',
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS favorite_outfits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'demo',
                city TEXT,
                style TEXT NOT NULL,
                weather_summary TEXT NOT NULL,
                items_json TEXT NOT NULL,
                explanation TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEMO_CITIES = {
    "innopolis": (55.7522, 48.7446, "Innopolis, Tatarstan, Russia"),
    "kazan": (55.7963, 49.1088, "Kazan, Tatarstan, Russia"),
    "moscow": (55.7558, 37.6173, "Moscow, Russia"),
    "zurich": (47.3769, 8.5417, "Zurich, Switzerland"),
    "london": (51.5072, -0.1276, "London, United Kingdom"),
}


def weather_label_for_lang(label: str, lang: str) -> str:
    return WEATHER_LABELS_RU.get(label, label) if lang == "ru" else label


def render_weather_summary(weather: WeatherInfo, lang: str) -> str:
    if lang == "ru":
        return (
            f"{weather.location_name}: {weather.temperature:.1f}°C, ощущается как {weather.apparent_temperature:.1f}°C, "
            f"ветер {weather.wind_speed:.1f} км/ч, {weather_label_for_lang(weather.weather_label, lang)}"
        )
    return (
        f"{weather.location_name}: {weather.temperature:.1f}°C, feels like {weather.apparent_temperature:.1f}°C, "
        f"wind {weather.wind_speed:.1f} km/h, {weather.weather_label}"
    )


def geocode_city(city: str) -> tuple[float, float, str]:
    try:
        response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results") or []
        if results:
            result = results[0]
            pretty_name = ", ".join(
                part for part in [result.get("name"), result.get("admin1"), result.get("country")] if part
            )
            return float(result["latitude"]), float(result["longitude"]), pretty_name
    except requests.RequestException:
        pass

    demo = DEMO_CITIES.get(city.strip().lower())
    if demo:
        return demo

    raise HTTPException(status_code=404, detail=f"City '{city}' was not found.")


def fetch_weather(city: str | None, latitude: float | None, longitude: float | None) -> WeatherInfo:
    if city:
        latitude, longitude, location_name = geocode_city(city)
    elif latitude is not None and longitude is not None:
        location_name = f"{latitude:.4f}, {longitude:.4f}"
    else:
        latitude, longitude, location_name = 55.7522, 48.7446, "Innopolis, Tatarstan, Russia"

    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": [
                    "temperature_2m",
                    "apparent_temperature",
                    "wind_speed_10m",
                    "precipitation",
                    "weather_code",
                ],
                "wind_speed_unit": "kmh",
            },
            timeout=10,
        )
        response.raise_for_status()
        current = response.json().get("current")
        if not current:
            raise HTTPException(status_code=502, detail="Weather service returned no current weather.")

        code = int(current.get("weather_code", 0))
        return WeatherInfo(
            location_name=location_name,
            temperature=float(current["temperature_2m"]),
            apparent_temperature=float(current["apparent_temperature"]),
            wind_speed=float(current["wind_speed_10m"]),
            precipitation=float(current.get("precipitation", 0.0)),
            weather_code=code,
            weather_label=WEATHER_CODE_LABELS.get(code, "unknown conditions"),
            source="live",
            provider="Open-Meteo",
        )
    except requests.RequestException:
        return WeatherInfo(
            location_name=location_name,
            temperature=11.0,
            apparent_temperature=8.0,
            wind_speed=18.0,
            precipitation=0.0,
            weather_code=3,
            weather_label="overcast (demo mode)",
            source="demo",
            provider="Open-Meteo",
        )


def fetch_wardrobe(user_id: str) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, user_id, name, type, created_at FROM wardrobe WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def lower_name(item_name: str) -> str:
    return item_name.lower().strip()


def contains_any(value: str, words: list[str]) -> bool:
    return any(word in value for word in words)


def detect_item_type(name: str) -> str | None:
    value = lower_name(name)
    if contains_any(value, SHOES_WORDS):
        return "shoes"
    if contains_any(value, JACKET_WORDS):
        return "jacket"
    if contains_any(value, BOTTOM_WORDS):
        return "bottom"
    if contains_any(value, ACCESSORY_WORDS):
        return "accessory"
    if contains_any(value, TOP_WORDS):
        return "top"
    return None


def score_item(item_name: str, style: str, weather: WeatherInfo, item_type: str) -> int:
    name = lower_name(item_name)
    score = 0

    for keyword in STYLE_PREFERENCES.get(style, []):
        if keyword in name:
            score += 3

    if weather.apparent_temperature <= 10 and contains_any(name, COLD_WEATHER_WORDS):
        score += 4
    if weather.apparent_temperature >= 22 and contains_any(name, HOT_WEATHER_WORDS):
        score += 4
    if weather.precipitation > 0.1 and contains_any(name, WIND_RAIN_WORDS):
        score += 3
    if weather.wind_speed >= 20 and contains_any(name, WIND_RAIN_WORDS):
        score += 2

    if item_type == "jacket":
        if weather.apparent_temperature < 14 or weather.wind_speed >= 20 or weather.precipitation > 0.1:
            score += 3
        else:
            score -= 4
        if weather.apparent_temperature > 18 and contains_any(name, VERY_WARM_WORDS):
            score -= 6

    if item_type == "accessory":
        if weather.apparent_temperature <= 7 and contains_any(name, ACCESSORY_COLD):
            score += 4
        elif weather.apparent_temperature >= 20 and contains_any(name, ACCESSORY_COLD):
            score -= 5
        if weather.apparent_temperature >= 18 and contains_any(name, ACCESSORY_HOT):
            score += 2
        if weather.precipitation > 0.1 and ("umbrella" in name or "зонт" in name):
            score += 4

    if item_type == "shoes":
        if contains_any(name, SUMMER_UNFRIENDLY) and (weather.apparent_temperature < 18 or weather.precipitation > 0.1):
            score -= 8
        if weather.precipitation > 0.1 and ("boots" in name or "ботин" in name):
            score += 3

    if item_type == "bottom":
        if weather.apparent_temperature < 16 and ("shorts" in name or "шорты" in name):
            score -= 8

    return score


def select_best_items(items: list[dict[str, Any]], style: str, weather: WeatherInfo) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {"top": [], "bottom": [], "shoes": [], "jacket": [], "accessory": []}
    for item in items:
        grouped[item["type"]].append(item)

    for item_type, bucket in grouped.items():
        bucket.sort(key=lambda item: score_item(item["name"], style, weather, item_type), reverse=True)

    return grouped


def combo_penalty(parts: list[dict[str, Any]], weather: WeatherInfo) -> int:
    penalty = 0
    names = [lower_name(part["name"]) for part in parts]
    top_names = [lower_name(part["name"]) for part in parts if part["type"] == "top"]
    jacket_names = [lower_name(part["name"]) for part in parts if part["type"] == "jacket"]

    if any(contains_any(name, SUMMER_UNFRIENDLY) for name in names) and (weather.apparent_temperature < 18 or weather.precipitation > 0.1):
        penalty -= 10
    if any(("shorts" in name or "шорты" in name) for name in names) and weather.apparent_temperature < 16:
        penalty -= 10
    if weather.apparent_temperature > 20 and any(contains_any(name, ACCESSORY_COLD) for name in names):
        penalty -= 6
    if weather.apparent_temperature > 18 and any(contains_any(name, VERY_WARM_WORDS) for name in names):
        penalty -= 8
    if weather.apparent_temperature >= 18 and jacket_names:
        if any(("coat" in name or "пальто" in name or "puffer" in name or "пухов" in name or "parka" in name or "парка" in name) for name in jacket_names):
            penalty -= 12
    if jacket_names and top_names:
        if any(("hoodie" in name or "худи" in name or "sweater" in name or "свитер" in name) for name in top_names):
            if any(("denim jacket" in name or "джинсовк" in name or "bomber" in name or "бомбер" in name) for name in jacket_names):
                penalty -= 4
    if weather.precipitation > 0.1:
        if any(contains_any(name, SUMMER_UNFRIENDLY) for name in names):
            penalty -= 12
    return penalty


def build_candidate_outfits(items: list[dict[str, Any]], style: str, weather: WeatherInfo) -> list[list[dict[str, Any]]]:
    grouped = select_best_items(items, style, weather)

    required = ["top", "bottom", "shoes"]
    missing = [item_type for item_type in required if not grouped[item_type]]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough wardrobe items. Please add at least one item for: {', '.join(missing)}.",
        )

    strong_outerwear_need = weather.apparent_temperature < 10 or weather.precipitation > 0.1 or weather.wind_speed >= 24
    light_outerwear_need = weather.apparent_temperature < 16 or weather.wind_speed >= 18
    accessory_need = weather.apparent_temperature < 7 or weather.precipitation > 0.1 or weather.apparent_temperature >= 18

    jacket_choices: list[dict[str, Any] | None]
    if strong_outerwear_need and grouped["jacket"]:
        jacket_choices = grouped["jacket"][:4]
    elif light_outerwear_need and grouped["jacket"]:
        jacket_choices = [None, *grouped["jacket"][:3]]
    else:
        jacket_choices = [None]

    accessory_choices: list[dict[str, Any] | None] = [None]
    if accessory_need and grouped["accessory"]:
        accessory_choices.extend(grouped["accessory"][:4])

    combos = list(
        itertools.product(
            grouped["top"][:5],
            grouped["bottom"][:5],
            grouped["shoes"][:5],
            jacket_choices,
            accessory_choices,
        )
    )

    def combo_score(combo: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]) -> int:
        parts = [part for part in combo if part is not None]
        return sum(score_item(part["name"], style, weather, part["type"]) for part in parts) + combo_penalty(parts, weather)

    combos.sort(key=combo_score, reverse=True)

    unique: list[list[dict[str, Any]]] = []
    seen_signatures: set[tuple[int, ...]] = set()
    for combo in combos:
        parts = [part for part in combo if part is not None]
        signature = tuple(sorted(part["id"] for part in parts))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique.append(parts)
        if len(unique) >= 12:
            break

    if not unique:
        raise HTTPException(status_code=400, detail="Could not build an outfit from the wardrobe.")

    return unique


def describe_conditions(weather: WeatherInfo, lang: str) -> list[str]:
    if lang == "ru":
        bits: list[str] = []
        if weather.apparent_temperature < 8:
            bits.append("на улице холодно")
        elif weather.apparent_temperature < 17:
            bits.append("на улице прохладно")
        elif weather.apparent_temperature < 26:
            bits.append("на улице комфортно")
        else:
            bits.append("на улице тепло")
        if weather.wind_speed >= 20:
            bits.append("ветрено")
        if weather.precipitation > 0.1:
            bits.append("есть осадки")
        return bits
    bits = []
    if weather.apparent_temperature < 8:
        bits.append("it feels cold outside")
    elif weather.apparent_temperature < 17:
        bits.append("the weather is cool")
    elif weather.apparent_temperature < 26:
        bits.append("the weather is comfortable")
    else:
        bits.append("it is warm outside")
    if weather.wind_speed >= 20:
        bits.append("it is windy")
    if weather.precipitation > 0.1:
        bits.append("there is precipitation")
    return bits


def style_label(style: str, lang: str) -> str:
    if lang == "ru":
        return {
            "casual": "повседневного",
            "sporty": "спортивного",
            "minimal": "минималистичного",
        }.get(style, style)
    return style


def explain_outfit(weather: WeatherInfo, style: str, parts: list[dict[str, Any]], lang: str) -> str:
    names = ", ".join(part["name"] for part in parts)
    conditions = describe_conditions(weather, lang)
    if lang == "ru":
        return f"Для {style_label(style, lang)} образа подойдут {names}, потому что {', '.join(conditions)}."
    return f"For a {style} look, {names} work well because {', '.join(conditions)}."


def enrich_explanation(text: str, parts: list[dict[str, Any]], lang: str) -> str:
    names = ", ".join(part["name"] for part in parts)
    base = (text or "").strip()
    if lang == "ru":
        prefix = f"Выбрано: {names}."
    else:
        prefix = f"Selected: {names}."
    if not base:
        return prefix
    if base.lower().startswith(prefix.lower()):
        return base
    return f"{prefix} {base}"


def build_prompt(weather: WeatherInfo, style: str, candidates: list[list[dict[str, Any]]], wardrobe: list[dict[str, Any]], lang: str, multiple: bool) -> str:
    wardrobe_list = ", ".join(f"{item['name']} ({item['type']})" for item in wardrobe)
    candidate_lines = []
    for index, outfit in enumerate(candidates, start=1):
        outfit_list = ", ".join(f"{item['name']} ({item['type']})" for item in outfit)
        candidate_lines.append(f"c{index}: {outfit_list}")
    return (
        "You are an outfit assistant. "
        f"Weather: {render_weather_summary(weather, 'en')}. "
        f"Preferred style: {style}. "
        f"Language for explanation: {lang}. "
        f"Need multiple options: {str(multiple).lower()}. "
        f"Available wardrobe: {wardrobe_list}. "
        f"Candidate outfits: {' | '.join(candidate_lines)}. "
        "Pick the most practical outfit or best 3 options. Avoid contradictory layering or weather-inappropriate items."
    )


def llm_settings() -> dict[str, str] | None:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("LLM_MODEL", "").strip()

    if not api_key or not base_url or not model:
        return None

    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    return {"api_key": api_key, "endpoint": endpoint, "model": model}



def parse_llm_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.lower().startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def extract_message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}

    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text_value = part.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
        return "".join(parts).strip()

    for key in ["reasoning_content", "text", "output_text"]:
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def update_llm_debug(**kwargs: Any) -> None:
    global LAST_LLM_DEBUG
    safe = dict(kwargs)
    if "response_text" in safe and isinstance(safe["response_text"], str):
        safe["response_text"] = safe["response_text"][:1000]
    LAST_LLM_DEBUG = safe


def rank_with_llm(weather: WeatherInfo, style: str, candidates: list[list[dict[str, Any]]], wardrobe: list[dict[str, Any]], lang: str, multiple: bool) -> tuple[list[int], dict[int, str]] | None:
    settings = llm_settings()
    if not settings:
        update_llm_debug(status="disabled", reason="missing_env")
        return None

    candidate_payload = []
    for index, option in enumerate(candidates, start=1):
        candidate_payload.append(
            {
                "id": index,
                "items": [item["name"] for item in option],
            }
        )

    system = (
        "You rank outfit candidates. "
        "Return valid JSON only with keys selected_ids and explanations. "
        "selected_ids must be an array of candidate ids in best-to-worst order. "
        "explanations must map candidate id strings to one short explanation in the requested language. "
        "Do not use markdown. Do not add extra keys. "
        "Use only Russian if language is ru. Use only English if language is en. "
        "Avoid mixed-language output. Avoid contradictory layering. "
        "Each explanation must mention all selected clothing items by name. "
        "Each explanation must be 1 or 2 short sentences."
    )
    user = {
        "language": lang,
        "style": style,
        "weather": {
            "location": weather.location_name,
            "temperature": weather.temperature,
            "apparent_temperature": weather.apparent_temperature,
            "wind_speed": weather.wind_speed,
            "precipitation": weather.precipitation,
            "weather_label": weather.weather_label,
        },
        "multiple": multiple,
        "pick_count": 3 if multiple else 1,
        "candidates": candidate_payload,
        "rules": [
            "Prefer one coherent outdoor outfit.",
            "Avoid clearly weather-inappropriate items.",
            "Do not invent clothing items.",
            "Use short natural explanations.",
            "Mention every selected clothing item by name.",
            "Explain the outfit as a whole, not just one item.",
        ],
    }

    base_payload = {
        "model": settings["model"],
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
    }

    payloads = [
        ("json_mode", {**base_payload, "response_format": {"type": "json_object"}}),
        ("plain_mode", base_payload),
    ]

    last_error = None

    for mode, payload in payloads:
        try:
            response = requests.post(
                settings["endpoint"],
                headers={
                    "Authorization": f"Bearer {settings['api_key']}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=25,
            )
            response_text = response.text
            if response.status_code >= 400:
                update_llm_debug(
                    status="http_error",
                    mode=mode,
                    endpoint=settings["endpoint"],
                    model=settings["model"],
                    status_code=response.status_code,
                    response_text=response_text,
                )
                logger.warning("LLM HTTP error mode=%s status=%s body=%s", mode, response.status_code, response_text[:500])
                last_error = f"http_{response.status_code}"
                continue

            data = response.json()
            content = extract_message_content(data)
            parsed = parse_llm_json(content)

            if not parsed:
                update_llm_debug(
                    status="parse_error",
                    mode=mode,
                    endpoint=settings["endpoint"],
                    model=settings["model"],
                    status_code=response.status_code,
                    response_text=response_text,
                    content=content,
                )
                logger.warning("LLM parse error mode=%s body=%s content=%s", mode, response_text[:500], content[:500])
                last_error = "parse_error"
                continue

            selected_ids = parsed.get("selected_ids") or []
            explanations = parsed.get("explanations") or {}
            clean_ids: list[int] = []
            for value in selected_ids:
                try:
                    item_id = int(value)
                except (TypeError, ValueError):
                    continue
                if 1 <= item_id <= len(candidates) and item_id not in clean_ids:
                    clean_ids.append(item_id)

            clean_explanations: dict[int, str] = {}
            for key, value in explanations.items():
                try:
                    candidate_id = int(key)
                except (TypeError, ValueError):
                    continue
                if 1 <= candidate_id <= len(candidates) and isinstance(value, str) and value.strip():
                    clean_explanations[candidate_id] = value.strip()

            if not clean_ids:
                update_llm_debug(
                    status="empty_selection",
                    mode=mode,
                    endpoint=settings["endpoint"],
                    model=settings["model"],
                    status_code=response.status_code,
                    response_text=response_text,
                    content=content,
                    parsed=parsed,
                )
                logger.warning("LLM empty selection mode=%s parsed=%s", mode, parsed)
                last_error = "empty_selection"
                continue

            update_llm_debug(
                status="ok",
                mode=mode,
                endpoint=settings["endpoint"],
                model=settings["model"],
                status_code=response.status_code,
                content=content,
                parsed=parsed,
            )
            logger.info("LLM success mode=%s selected_ids=%s", mode, clean_ids)
            return clean_ids, clean_explanations

        except requests.RequestException as exc:
            update_llm_debug(
                status="request_exception",
                mode=mode,
                endpoint=settings["endpoint"],
                model=settings["model"],
                error=str(exc),
            )
            logger.warning("LLM request exception mode=%s error=%s", mode, exc)
            last_error = str(exc)
            continue
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            update_llm_debug(
                status="response_exception",
                mode=mode,
                endpoint=settings["endpoint"],
                model=settings["model"],
                error=str(exc),
            )
            logger.warning("LLM response exception mode=%s error=%s", mode, exc)
            last_error = str(exc)
            continue

    if last_error:
        logger.warning("LLM fallback to rules: %s", last_error)
    return None


app = FastAPI(title="Outfit", version="2.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    settings = llm_settings()
    return {
        "llm_enabled": bool(settings),
        "llm_model": settings["model"] if settings else None,
        "weather_provider": "Open-Meteo",
    }


@app.get("/api/llm-debug")
def get_llm_debug() -> dict[str, Any]:
    return LAST_LLM_DEBUG


@app.post("/api/wardrobe")
def add_item(item: WardrobeItemCreate) -> dict[str, Any]:
    item_type = item.type or detect_item_type(item.name)
    if item_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Could not detect clothing type.")

    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO wardrobe (user_id, name, type, created_at) VALUES (?, ?, ?, ?)",
            (item.user_id, item.name.strip(), item_type, utc_now_iso()),
        )
        conn.commit()
        item_id = cursor.lastrowid

    return {
        "id": item_id,
        "user_id": item.user_id,
        "name": item.name.strip(),
        "type": item_type,
        "message": "Item added successfully.",
    }


@app.get("/api/wardrobe")
def get_wardrobe(user_id: str = "demo") -> dict[str, Any]:
    items = fetch_wardrobe(user_id)
    return {"items": items, "count": len(items)}


@app.delete("/api/wardrobe/{item_id}")
def delete_wardrobe_item(item_id: int) -> dict[str, str]:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM wardrobe WHERE id = ?", (item_id,))
        conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Wardrobe item not found.")
    return {"message": "Item deleted."}


@app.post("/api/generate-outfit")
def generate_outfit(payload: GenerateOutfitRequest) -> dict[str, Any]:
    wardrobe = fetch_wardrobe(payload.user_id)
    if not wardrobe:
        raise HTTPException(status_code=400, detail="Wardrobe is empty. Add some clothes first.")

    weather = fetch_weather(payload.city, payload.latitude, payload.longitude)
    candidate_outfits = build_candidate_outfits(wardrobe, payload.style, weather)

    ranked_by_llm = rank_with_llm(weather, payload.style, candidate_outfits, wardrobe, payload.lang, payload.multiple)
    if ranked_by_llm:
        selected_ids, explanations = ranked_by_llm
        selected_count = 3 if payload.multiple else 1
        chosen_indexes = selected_ids[:selected_count]
        generation_mode = "llm"
    else:
        chosen_indexes = list(range(1, (3 if payload.multiple else 1) + 1))
        generation_mode = "rules"
        explanations = {}

    results = []
    for candidate_id in chosen_indexes:
        outfit = candidate_outfits[candidate_id - 1]
        explanation = explanations.get(candidate_id) or explain_outfit(weather, payload.style, outfit, payload.lang)
        results.append(
            {
                "items": outfit,
                "explanation": enrich_explanation(explanation, outfit, payload.lang),
                "prompt": build_prompt(weather, payload.style, candidate_outfits[:6], wardrobe, payload.lang, payload.multiple),
            }
        )

    return {
        "weather": {
            "location": weather.location_name,
            "temperature": weather.temperature,
            "apparent_temperature": weather.apparent_temperature,
            "wind_speed": weather.wind_speed,
            "precipitation": weather.precipitation,
            "weather_code": weather.weather_code,
            "weather_label": weather_label_for_lang(weather.weather_label, payload.lang),
            "summary": render_weather_summary(weather, payload.lang),
            "source": weather.source,
            "provider": weather.provider,
        },
        "style": payload.style,
        "multiple": payload.multiple,
        "language": payload.lang,
        "generation_mode": generation_mode,
        "options": results,
    }


@app.post("/api/favorites")
def save_favorite(payload: SaveFavoriteRequest) -> dict[str, Any]:
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO favorite_outfits (user_id, city, style, weather_summary, items_json, explanation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.user_id,
                payload.city,
                payload.style,
                payload.weather_summary,
                json.dumps(payload.items, ensure_ascii=False),
                payload.explanation,
                utc_now_iso(),
            ),
        )
        conn.commit()

    return {"id": cursor.lastrowid, "message": "Favorite outfit saved."}


@app.get("/api/favorites")
def get_favorites(user_id: str = "demo") -> dict[str, Any]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, user_id, city, style, weather_summary, items_json, explanation, created_at FROM favorite_outfits WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()

    favorites = []
    for row in rows:
        favorite = dict(row)
        favorite["items"] = json.loads(favorite.pop("items_json"))
        favorites.append(favorite)

    return {"items": favorites, "count": len(favorites)}
