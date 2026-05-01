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



QUERY_MAP: dict[str, str] = {
    "hug": "anime hug cute friendship",
    "pat": "anime pat head cute friendly",
    "slap": "anime slap funny comedy",
    "bonk": "anime bonk head funny",
    "wave": "anime wave hello friendly waving",
    "poke": "anime poke cheek cute",
    "kiss": "anime kiss cute romantic",
    "cry": "anime crying emotional tearful",
    "blush": "anime blush shy cute",
    "bite": "anime bite funny cute",
    "cuddle": "anime cuddle cute cozy",
    "punch": "anime punch action comedy",
    "dance": "anime dance cute fun",
    "laugh": "anime laugh happy fun",
    "wink": "anime wink cute playful",
    "transform": "eren titan transformation attack on titan",
    "salute": "survey corps salute attack on titan",
    "scream": "eren yeager scream tatakae",
    "charge": "attack on titan charge scout regiment",
    "slice": "levi ackerman clean slice action",
    "yeager": "eren yeager tatakae scream",
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
