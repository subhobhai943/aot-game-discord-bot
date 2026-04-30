"""AoT GIF fetcher.

Priority:
  1. Giphy search with public beta key
  2. Tenor search with public test key
  3. Curated AoT GIF fallback list

This keeps GIFs AoT-specific even when private API keys are unavailable.
"""
import os
import random
import aiohttp
from urllib.parse import quote_plus

GIPHY_KEY = os.getenv("GIPHY_API_KEY", "dc6zaTOxFJmzC")
TENOR_KEY = os.getenv("TENOR_API_KEY", "LIVDSRZULELA")

AOT_FALLBACK_GIFS: dict[str, list[str]] = {
    "hug": [
        "https://media.tenor.com/5E6YXPLkZX8AAAAC/attack-on-titan-aot.gif",
        "https://media.tenor.com/yC1iOYUO5S8AAAAC/aot-attack-on-titan.gif",
    ],
    "pat": [
        "https://media.tenor.com/KU6uV8WQ2bcAAAAC/attack-on-titan.gif",
        "https://media.tenor.com/eU6zFqzZo0gAAAAC/aot-anime.gif",
    ],
    "slap": [
        "https://media.tenor.com/2k7PJZJNBeQAAAAC/levi-ackerman-levi-aot.gif",
        "https://media.tenor.com/AXTSXVbBdOIAAAAC/leviackerman-attackontitan.gif",
    ],
    "bonk": [
        "https://media.tenor.com/QwynhrOhI3wAAAAC/levi-ackerman-beast-titan.gif",
    ],
    "wave": [
        "https://media.tenor.com/4etW2iS9g1sAAAAC/attack-on-titan-scout-regiment.gif",
    ],
    "poke": [
        "https://media.tenor.com/AXTSXVbBdOIAAAAC/leviackerman-attackontitan.gif",
    ],
    "kiss": [
        "https://media.tenor.com/0r4O0nGr1vAAAAAC/mikasa-eren.gif",
    ],
    "cry": [
        "https://media.tenor.com/x8hA8N0i8L4AAAAC/attack-on-titan-mikasa.gif",
        "https://media.tenor.com/USV4W3N2e9QAAAAC/eren-crying.gif",
    ],
    "blush": [
        "https://media.tenor.com/0r4O0nGr1vAAAAAC/mikasa-eren.gif",
    ],
    "bite": [
        "https://media.tenor.com/yy0R8l3rwf8AAAAC/attack-on-titan-titan.gif",
    ],
    "cuddle": [
        "https://media.tenor.com/yC1iOYUO5S8AAAAC/aot-attack-on-titan.gif",
    ],
    "punch": [
        "https://media.tenor.com/2k7PJZJNBeQAAAAC/levi-ackerman-levi-aot.gif",
        "https://media.tenor.com/QwynhrOhI3wAAAAC/levi-ackerman-beast-titan.gif",
    ],
    "dance": [
        "https://media.tenor.com/98f8dKQfK7IAAAAC/attack-on-titan-funny.gif",
    ],
    "laugh": [
        "https://media.tenor.com/98f8dKQfK7IAAAAC/attack-on-titan-funny.gif",
    ],
    "wink": [
        "https://media.tenor.com/aO6JtTjvG1sAAAAC/annie-leonhart-aot.gif",
    ],
    "transform": [
        "https://media.tenor.com/UgJ7sLY9D1AAAAAC/eren-yeager-attack-on-titan.gif",
        "https://media.tenor.com/Jk0kTgN2v2EAAAAC/attack-on-titan-eren.gif",
    ],
    "salute": [
        "https://media.tenor.com/4etW2iS9g1sAAAAC/attack-on-titan-scout-regiment.gif",
    ],
    "scream": [
        "https://media.tenor.com/8l5zQ1n6R5UAAAAC/eren-yeager-tatakae.gif",
    ],
    "charge": [
        "https://media.tenor.com/7r4Y9HnA7w4AAAAC/attack-on-titan-charge.gif",
    ],
    "slice": [
        "https://media.tenor.com/QwynhrOhI3wAAAAC/levi-ackerman-beast-titan.gif",
        "https://media.tenor.com/AXTSXVbBdOIAAAAC/leviackerman-attackontitan.gif",
    ],
    "yeager": [
        "https://media.tenor.com/8l5zQ1n6R5UAAAAC/eren-yeager-tatakae.gif",
    ],
}

QUERY_MAP: dict[str, str] = {
    "hug": "attack on titan hug anime",
    "pat": "attack on titan cute anime",
    "slap": "attack on titan slap anime",
    "bonk": "levi ackerman hit attack on titan",
    "wave": "attack on titan salute scout regiment",
    "poke": "levi ackerman attack on titan",
    "kiss": "eren mikasa attack on titan",
    "cry": "attack on titan crying anime",
    "blush": "mikasa blush attack on titan",
    "bite": "attack on titan titan bite",
    "cuddle": "attack on titan cute mikasa eren",
    "punch": "attack on titan punch anime",
    "dance": "attack on titan funny anime",
    "laugh": "attack on titan funny laugh",
    "wink": "annie leonhart attack on titan",
    "transform": "eren titan transformation attack on titan",
    "salute": "survey corps salute attack on titan",
    "scream": "eren yeager scream tatakae",
    "charge": "attack on titan charge scout regiment",
    "slice": "levi ackerman slash attack on titan",
    "yeager": "eren yeager tatakae attack on titan",
}


async def _from_giphy(query: str) -> str:
    if not GIPHY_KEY:
        return ""
    url = (
        "https://api.giphy.com/v1/gifs/search"
        f"?api_key={GIPHY_KEY}&q={quote_plus(query)}&limit=15&rating=pg-13"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("data", [])
                    urls = []
                    for item in items[:10]:
                        img = item.get("images", {}).get("original", {})
                        gif = img.get("url")
                        if gif:
                            urls.append(gif)
                    if urls:
                        return random.choice(urls)
    except Exception:
        pass
    return ""


async def _from_tenor(query: str) -> str:
    if not TENOR_KEY:
        return ""
    url = (
        "https://api.tenor.com/v1/search"
        f"?q={quote_plus(query)}&key={TENOR_KEY}&limit=15&media_filter=minimal"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("results", [])
                    urls = []
                    for item in items[:10]:
                        media = item.get("media", [])
                        if media and media[0].get("gif", {}).get("url"):
                            urls.append(media[0]["gif"]["url"])
                    if urls:
                        return random.choice(urls)
    except Exception:
        pass
    return ""


async def get_gif(action: str, tenor_query: str = "") -> str:
    """Return an AoT-specific GIF URL for the requested action."""
    query = QUERY_MAP.get(action, tenor_query or f"attack on titan {action}")

    gif = await _from_giphy(query)
    if gif:
        return gif

    gif = await _from_tenor(query)
    if gif:
        return gif

    fallback = AOT_FALLBACK_GIFS.get(action, [])
    if fallback:
        return random.choice(fallback)

    generic = AOT_FALLBACK_GIFS.get("transform", [])
    return random.choice(generic) if generic else ""
