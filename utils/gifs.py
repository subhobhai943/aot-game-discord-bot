"""AoT GIF fetcher.

Priority:
  1. Giphy search with public beta key
  2. Tenor search (v2 API)
  3. Curated AoT GIF fallback list (ALWAYS defined — was missing before, causing crashes)
"""
import os
import random
import aiohttp
from urllib.parse import quote_plus

GIPHY_KEY = os.getenv("GIPHY_API_KEY", "dc6zaTOxFJmzC")
TENOR_KEY  = os.getenv("TENOR_API_KEY", "AIzaSyAyimkuEcdFq3sAXQlBGBXk-sTOSCMQ-vc")


# ── Curated AoT GIF fallback list ─────────────────────────────────────────
# These are all publicly accessible GIF URLs that never expire.
# Used when both Giphy and Tenor API calls fail.
AOT_FALLBACK_GIFS: dict[str, list[str]] = {
    "hug": [
        "https://media.tenor.com/x8v1oNUOmg4AAAAM/anime-hug.gif",
        "https://media.tenor.com/I_e6UXqCo4MAAAAM/hug-anime.gif",
    ],
    "pat": [
        "https://media.tenor.com/dkGPxOFBWHMAAAAM/head-pat-anime.gif",
        "https://media.tenor.com/OXGH_LQ1MtkAAAAM/anime-pat.gif",
    ],
    "slap": [
        "https://media.tenor.com/Bxq2G8V_YssAAAAM/slap-anime.gif",
        "https://media.tenor.com/oKaBQ32dJMoAAAAM/anime-slap.gif",
    ],
    "bonk": [
        "https://media.tenor.com/tNxhFJHKU7MAAAAM/anime-bonk.gif",
        "https://media.tenor.com/MYCiSdFjFuwAAAAM/bonk-anime.gif",
    ],
    "wave": [
        "https://media.tenor.com/OoFbNJMYPL0AAAAM/anime-wave.gif",
        "https://media.tenor.com/7_r-b5J94EQAAAAM/wave-anime.gif",
    ],
    "poke": [
        "https://media.tenor.com/qVqzZwrnaOAAAAAM/poke-anime.gif",
        "https://media.tenor.com/0NkANtxzKi8AAAAM/anime-poke.gif",
    ],
    "kiss": [
        "https://media.tenor.com/F6XWCnFPSfsAAAAM/anime-kiss.gif",
        "https://media.tenor.com/1SKDKnhwMdEAAAAM/kiss-anime.gif",
    ],
    "cry": [
        "https://media.tenor.com/N0yfJ8U3E3MAAAAM/anime-crying.gif",
        "https://media.tenor.com/kMXKQJnrWvEAAAAM/cry-anime.gif",
    ],
    "blush": [
        "https://media.tenor.com/Rj94PkfLXqIAAAAM/blush-anime.gif",
        "https://media.tenor.com/2KGXXaHU8MUAAAAM/anime-blush.gif",
    ],
    "bite": [
        "https://media.tenor.com/djhqPYAqaHQAAAAM/anime-bite.gif",
        "https://media.tenor.com/KA5PFn7mFLAAAAAM/bite-anime.gif",
    ],
    "cuddle": [
        "https://media.tenor.com/7dv4_o3baTIAAAAM/cuddle-anime.gif",
        "https://media.tenor.com/SYRfJjKWvYcAAAAM/anime-cuddle.gif",
    ],
    "dance": [
        "https://media.tenor.com/PPCGn2Gs7zsAAAAM/anime-dance.gif",
        "https://media.tenor.com/Wji3ypDzAukAAAAM/dance-anime.gif",
    ],
    "laugh": [
        "https://media.tenor.com/jTzqopUTDG4AAAAM/anime-laugh.gif",
        "https://media.tenor.com/a9ICfkMXvHcAAAAM/laugh-anime.gif",
    ],
    "wink": [
        "https://media.tenor.com/mJfhZcj_s5kAAAAM/anime-wink.gif",
        "https://media.tenor.com/rqfMjzFq3MEAAAAM/wink-anime.gif",
    ],
    "punch": [
        "https://media.tenor.com/BtHfTf-FGvUAAAAM/anime-punch.gif",
        "https://media.tenor.com/E01LSWP0zEkAAAAM/punch-anime.gif",
    ],
    "transform": [
        "https://media.tenor.com/XarJhHKlM0MAAAAM/eren-titan-transformation.gif",
        "https://media.tenor.com/JWj0zPBKKMkAAAAM/aot-titan-transform.gif",
    ],
    "salute": [
        "https://media.tenor.com/C8bR47u3cZgAAAAM/attack-on-titan-salute.gif",
        "https://media.tenor.com/AHLGM8MgVpUAAAAM/sasageyo-survey-corps.gif",
    ],
    "scream": [
        "https://media.tenor.com/AQ9dlO-TlKEAAAAM/eren-tatakae-scream.gif",
        "https://media.tenor.com/uo_H8ZU_bXoAAAAM/tatakae-eren-yeager.gif",
    ],
    "charge": [
        "https://media.tenor.com/7u3IoCLAJGIAAAAM/attack-on-titan-charge.gif",
        "https://media.tenor.com/xWMy9JajQxgAAAAM/scout-regiment-aot.gif",
    ],
    "slice": [
        "https://media.tenor.com/l-Vm3CMM2UQAAAAM/levi-ackerman-slash.gif",
        "https://media.tenor.com/UBViBZU8YNsAAAAM/levi-blade-aot.gif",
    ],
    "yeager": [
        "https://media.tenor.com/9-hL5zUE5S0AAAAM/eren-yeager-tatakae.gif",
        "https://media.tenor.com/uo_H8ZU_bXoAAAAM/tatakae-eren-yeager.gif",
    ],
    "kill": [
        "https://media.tenor.com/l-Vm3CMM2UQAAAAM/levi-ackerman-slash.gif",
        "https://media.tenor.com/UBViBZU8YNsAAAAM/levi-blade-aot.gif",
    ],
    "odm": [
        "https://media.tenor.com/1KXDvHdH0CUAAAAM/odm-gear-attack-on-titan.gif",
        "https://media.tenor.com/SXqMYIkR-CQAAAAM/aot-odm-gear.gif",
    ],
    "thunder_spear": [
        "https://media.tenor.com/3EEMjFqz9CMAAAAM/thunder-spear-aot.gif",
        "https://media.tenor.com/EW6L_W5bPk8AAAAM/attack-on-titan-explosion.gif",
    ],
    "nape": [
        "https://media.tenor.com/l-Vm3CMM2UQAAAAM/levi-ackerman-slash.gif",
        "https://media.tenor.com/UBViBZU8YNsAAAAM/levi-blade-aot.gif",
    ],
    "titan_eat": [
        "https://media.tenor.com/CUFqXn-mGe8AAAAM/titan-eating-aot.gif",
        "https://media.tenor.com/OKkqKRFXMvIAAAAM/attack-on-titan-eat.gif",
    ],
    "rumble": [
        "https://media.tenor.com/3eGJGMkRYJkAAAAM/the-rumbling-aot.gif",
        "https://media.tenor.com/N1AMbfRK75IAAAAM/rumbling-attack-on-titan.gif",
    ],
    "levi_kick": [
        "https://media.tenor.com/BtHfTf-FGvUAAAAM/anime-punch.gif",
        "https://media.tenor.com/E01LSWP0zEkAAAAM/punch-anime.gif",
    ],
    "founding": [
        "https://media.tenor.com/3eGJGMkRYJkAAAAM/the-rumbling-aot.gif",
        "https://media.tenor.com/XarJhHKlM0MAAAAM/eren-titan-transformation.gif",
    ],
    "scout": [
        "https://media.tenor.com/7u3IoCLAJGIAAAAM/attack-on-titan-charge.gif",
        "https://media.tenor.com/C8bR47u3cZgAAAAM/attack-on-titan-salute.gif",
    ],
    "omni": [
        "https://media.tenor.com/1KXDvHdH0CUAAAAM/odm-gear-attack-on-titan.gif",
        "https://media.tenor.com/SXqMYIkR-CQAAAAM/aot-odm-gear.gif",
    ],
    "wall_break": [
        "https://media.tenor.com/9UQ-LmfGCEsAAAAM/colossal-titan-wall.gif",
        "https://media.tenor.com/CUFqXn-mGe8AAAAM/titan-eating-aot.gif",
    ],
    "colossal": [
        "https://media.tenor.com/9UQ-LmfGCEsAAAAM/colossal-titan-wall.gif",
        "https://media.tenor.com/EW6L_W5bPk8AAAAM/attack-on-titan-explosion.gif",
    ],
    "war_hammer": [
        "https://media.tenor.com/3EEMjFqz9CMAAAAM/thunder-spear-aot.gif",
        "https://media.tenor.com/EW6L_W5bPk8AAAAM/attack-on-titan-explosion.gif",
    ],
    "armored": [
        "https://media.tenor.com/SXqMYIkR-CQAAAAM/aot-odm-gear.gif",
        "https://media.tenor.com/7u3IoCLAJGIAAAAM/attack-on-titan-charge.gif",
    ],
    "freedom": [
        "https://media.tenor.com/C8bR47u3cZgAAAAM/attack-on-titan-salute.gif",
        "https://media.tenor.com/AHLGM8MgVpUAAAAM/sasageyo-survey-corps.gif",
    ],
}


QUERY_MAP: dict[str, str] = {
    "hug":           "anime hug cute friendship",
    "pat":           "anime pat head cute friendly",
    "slap":          "anime slap funny comedy",
    "bonk":          "anime bonk head funny",
    "wave":          "anime wave hello friendly waving",
    "poke":          "anime poke cheek cute",
    "kiss":          "anime kiss cute romantic",
    "cry":           "anime crying emotional tearful",
    "blush":         "anime blush shy cute",
    "bite":          "anime bite funny cute",
    "cuddle":        "anime cuddle cute cozy",
    "punch":         "anime punch action comedy",
    "dance":         "anime dance cute fun",
    "laugh":         "anime laugh happy fun",
    "wink":          "anime wink cute playful",
    "transform":     "eren titan transformation attack on titan",
    "salute":        "survey corps salute attack on titan",
    "scream":        "eren yeager scream tatakae",
    "charge":        "attack on titan charge scout regiment",
    "slice":         "levi ackerman clean slice action",
    "yeager":        "eren yeager tatakae scream",
    "kill":          "levi ackerman kill titan attack on titan",
    "odm":           "ODM gear swing attack on titan survey corps",
    "thunder_spear": "thunder spear attack on titan explosion",
    "nape":          "nape slash titan attack on titan kill",
    "titan_eat":     "titan eating attack on titan horror",
    "rumble":        "the rumbling attack on titan titans march",
    "levi_kick":     "levi ackerman kick attack on titan",
    "founding":      "founding titan eren attack on titan colossal",
    "scout":         "survey corps scouts running attack on titan",
    "omni":          "omnidirectional mobility gear attack on titan",
    "wall_break":    "colossal titan wall break attack on titan",
    "colossal":      "colossal titan attack on titan armin",
    "war_hammer":    "war hammer titan attack on titan",
    "armored":       "armored titan reiner attack on titan",
    "freedom":       "attack on titan wings of freedom survey corps",
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
    """Tenor v2 API (replaces deprecated v1)."""
    if not TENOR_KEY:
        return ""
    # v2 endpoint
    url = (
        "https://tenor.googleapis.com/v2/search"
        f"?q={quote_plus(query)}&key={TENOR_KEY}&limit=15&media_filter=gif"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("results", [])
                    urls = []
                    for item in items[:10]:
                        media_formats = item.get("media_formats", {})
                        gif_data = media_formats.get("gif", {})
                        gif_url = gif_data.get("url")
                        if gif_url:
                            urls.append(gif_url)
                    if urls:
                        return random.choice(urls)
    except Exception:
        pass
    return ""


async def get_gif(action: str, tenor_query: str = "") -> str:
    """Return an AoT-specific GIF URL for the requested action.
    Falls back gracefully through Giphy -> Tenor v2 -> curated fallback list.
    This function NEVER raises — it always returns a string (possibly empty).
    """
    query = QUERY_MAP.get(action, tenor_query or f"attack on titan {action}")

    gif = await _from_giphy(query)
    if gif:
        return gif

    gif = await _from_tenor(query)
    if gif:
        return gif

    # Curated fallback — always defined above
    fallback = AOT_FALLBACK_GIFS.get(action, [])
    if fallback:
        return random.choice(fallback)

    # Last resort: use transform fallback
    generic = AOT_FALLBACK_GIFS.get("transform", [])
    return random.choice(generic) if generic else ""
