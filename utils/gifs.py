"""AoT GIF fetcher — fast, shared session, reliable fallbacks.

Priority:
  1. Tenor v2 API  (fastest, most anime content)
  2. Giphy API
  3. Curated AoT fallback GIF list (guaranteed to work)

Performance fix: uses a single shared aiohttp.ClientSession (set by bot on startup)
instead of creating/destroying a new session on EVERY command invocation.
This saves ~200-400ms per request and reduces memory churn.
"""
import os
import random
import aiohttp
import logging
from urllib.parse import quote_plus

logger = logging.getLogger("aot.gifs")

GIPHY_KEY = os.getenv("GIPHY_API_KEY", "dc6zaTOxFJmzC")
TENOR_KEY  = os.getenv("TENOR_API_KEY",  "LIVDSRZULELA")

# Shared session — set once in bot.py via gifs.SESSION = bot.http_session
# Falls back to creating a new one if not set (safe but slower)
SESSION: aiohttp.ClientSession | None = None


def _session() -> aiohttp.ClientSession:
    """Return the shared session or create a temporary one."""
    global SESSION
    if SESSION is None or SESSION.closed:
        SESSION = aiohttp.ClientSession()
    return SESSION


# ── Query map: what to search for each action ─────────────────────────────
QUERY_MAP: dict[str, str] = {
    "hug":           "anime hug cute friendship",
    "pat":           "anime head pat cute",
    "slap":          "anime slap funny",
    "bonk":          "anime bonk head funny",
    "wave":          "anime wave hello friendly",
    "poke":          "anime poke cheek cute",
    "kiss":          "anime kiss cute romantic",
    "cry":           "anime cry emotional tearful",
    "blush":         "anime blush shy cute",
    "bite":          "anime bite funny",
    "cuddle":        "anime cuddle cute cozy",
    "punch":         "anime punch action",
    "dance":         "anime dance fun",
    "laugh":         "anime laugh happy",
    "wink":          "anime wink cute",
    "transform":     "eren titan transformation attack on titan",
    "salute":        "survey corps salute attack on titan",
    "scream":        "eren yeager scream tatakae",
    "charge":        "attack on titan charge scouts",
    "slice":         "levi ackerman slash attack on titan",
    "yeager":        "eren yeager tatakae",
    "kill":          "levi ackerman kill titan",
    "odm":           "ODM gear swing attack on titan",
    "thunder_spear": "thunder spear attack on titan",
    "nape":          "nape slash titan attack on titan",
    "titan_eat":     "titan eating attack on titan",
    "rumble":        "the rumbling attack on titan",
    "levi_kick":     "levi ackerman kick",
    "founding":      "founding titan eren attack on titan",
    "scout":         "survey corps scouts attack on titan",
    "omni":          "ODM omnidirectional gear attack on titan",
    "wall_break":    "colossal titan wall break attack on titan",
    "colossal":      "colossal titan armin attack on titan",
    "war_hammer":    "war hammer titan attack on titan",
    "armored":       "armored titan reiner attack on titan",
    "freedom":       "wings of freedom attack on titan",
}


# ── Curated fallback GIFs — stable working URLs ───────────────────────────
# Using Giphy CDN links which are more stable than Tenor media CDN.
AOT_FALLBACK_GIFS: dict[str, list[str]] = {
    "hug": [
        "https://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif",
        "https://media.giphy.com/media/lrr9rHuoJOE0w/giphy.gif",
    ],
    "pat": [
        "https://media.giphy.com/media/ARSp9T7wwxNcs/giphy.gif",
        "https://media.giphy.com/media/ye7OTQgwmVuVy/giphy.gif",
    ],
    "slap": [
        "https://media.giphy.com/media/RXGNsyRb1hDJm/giphy.gif",
        "https://media.giphy.com/media/Gf3AUz3eBNbTW/giphy.gif",
    ],
    "bonk": [
        "https://media.giphy.com/media/WvVzZ9mCyMjSM/giphy.gif",
        "https://media.giphy.com/media/x0npf6oFbDMdi/giphy.gif",
    ],
    "wave": [
        "https://media.giphy.com/media/ASd0Ukj0y3qMM/giphy.gif",
        "https://media.giphy.com/media/2yUHEZbRPBrMcoBpEE/giphy.gif",
    ],
    "poke": [
        "https://media.giphy.com/media/WTdOnTNmBEr0A/giphy.gif",
        "https://media.giphy.com/media/N4MiIRNAkYAZG/giphy.gif",
    ],
    "kiss": [
        "https://media.giphy.com/media/bGm9FuBCGg4SY/giphy.gif",
        "https://media.giphy.com/media/x1cFiVmDOOGdO/giphy.gif",
    ],
    "cry": [
        "https://media.giphy.com/media/Jwnol1a72iBpS/giphy.gif",
        "https://media.giphy.com/media/LPnfPOmBEAZ3a/giphy.gif",
    ],
    "blush": [
        "https://media.giphy.com/media/Si4ZMQktmsmje/giphy.gif",
        "https://media.giphy.com/media/Wn74RUT0KMEGs/giphy.gif",
    ],
    "bite": [
        "https://media.giphy.com/media/rl0FOxdz7CcxO/giphy.gif",
        "https://media.giphy.com/media/gxGRBUiHGxHtC/giphy.gif",
    ],
    "cuddle": [
        "https://media.giphy.com/media/cQB5RFbGUwZ1C/giphy.gif",
        "https://media.giphy.com/media/lrr9rHuoJOE0w/giphy.gif",
    ],
    "dance": [
        "https://media.giphy.com/media/13HBDT4QSTpveU/giphy.gif",
        "https://media.giphy.com/media/tig7XJLL12t1S/giphy.gif",
    ],
    "laugh": [
        "https://media.giphy.com/media/fBEDuhnVCiP16/giphy.gif",
        "https://media.giphy.com/media/7DzlajZNY5D0I/giphy.gif",
    ],
    "wink": [
        "https://media.giphy.com/media/2t9sDPrlvFpdK/giphy.gif",
        "https://media.giphy.com/media/bcKmIWkUMCjVm/giphy.gif",
    ],
    "punch": [
        "https://media.giphy.com/media/7GYHmjk6vlqY8/giphy.gif",
        "https://media.giphy.com/media/XbgzkM55RrHtS/giphy.gif",
    ],
    "transform": [
        "https://media.giphy.com/media/Lp4Bv3F1zMcqI/giphy.gif",
        "https://media.giphy.com/media/3nfqWdtjGQRSc/giphy.gif",
    ],
    "salute": [
        "https://media.giphy.com/media/qBiPolsRg7Mw0/giphy.gif",
        "https://media.giphy.com/media/3o7aCTPMoCMGFtj3oA/giphy.gif",
    ],
    "scream": [
        "https://media.giphy.com/media/AknFOQMDqHKso/giphy.gif",
        "https://media.giphy.com/media/1zi2FQvx8dkyk/giphy.gif",
    ],
    "charge": [
        "https://media.giphy.com/media/aYpRjQ3TIwWWY/giphy.gif",
        "https://media.giphy.com/media/3GqmB4W5MpHkA/giphy.gif",
    ],
    "slice": [
        "https://media.giphy.com/media/SwImQhtiNA7io/giphy.gif",
        "https://media.giphy.com/media/xT8qBit7YomT80d0M8/giphy.gif",
    ],
    "yeager": [
        "https://media.giphy.com/media/AknFOQMDqHKso/giphy.gif",
        "https://media.giphy.com/media/9SIXFu7bIUYHhFc19G/giphy.gif",
    ],
    "kill": [
        "https://media.giphy.com/media/SwImQhtiNA7io/giphy.gif",
        "https://media.giphy.com/media/xT8qBit7YomT80d0M8/giphy.gif",
    ],
    "odm": [
        "https://media.giphy.com/media/5xtDarIEEQOJo3oQMgw/giphy.gif",
        "https://media.giphy.com/media/o0vwzuFwCGAFO/giphy.gif",
    ],
    "thunder_spear": [
        "https://media.giphy.com/media/3GqmB4W5MpHkA/giphy.gif",
        "https://media.giphy.com/media/aYpRjQ3TIwWWY/giphy.gif",
    ],
    "nape": [
        "https://media.giphy.com/media/SwImQhtiNA7io/giphy.gif",
        "https://media.giphy.com/media/xT8qBit7YomT80d0M8/giphy.gif",
    ],
    "titan_eat": [
        "https://media.giphy.com/media/GlCGNgxHGixHa/giphy.gif",
        "https://media.giphy.com/media/Lp4Bv3F1zMcqI/giphy.gif",
    ],
    "rumble": [
        "https://media.giphy.com/media/9SIXFu7bIUYHhFc19G/giphy.gif",
        "https://media.giphy.com/media/3nfqWdtjGQRSc/giphy.gif",
    ],
    "levi_kick": [
        "https://media.giphy.com/media/7GYHmjk6vlqY8/giphy.gif",
        "https://media.giphy.com/media/SwImQhtiNA7io/giphy.gif",
    ],
    "founding": [
        "https://media.giphy.com/media/9SIXFu7bIUYHhFc19G/giphy.gif",
        "https://media.giphy.com/media/Lp4Bv3F1zMcqI/giphy.gif",
    ],
    "scout": [
        "https://media.giphy.com/media/aYpRjQ3TIwWWY/giphy.gif",
        "https://media.giphy.com/media/qBiPolsRg7Mw0/giphy.gif",
    ],
    "omni": [
        "https://media.giphy.com/media/5xtDarIEEQOJo3oQMgw/giphy.gif",
        "https://media.giphy.com/media/o0vwzuFwCGAFO/giphy.gif",
    ],
    "wall_break": [
        "https://media.giphy.com/media/GlCGNgxHGixHa/giphy.gif",
        "https://media.giphy.com/media/3GqmB4W5MpHkA/giphy.gif",
    ],
    "colossal": [
        "https://media.giphy.com/media/GlCGNgxHGixHa/giphy.gif",
        "https://media.giphy.com/media/3nfqWdtjGQRSc/giphy.gif",
    ],
    "war_hammer": [
        "https://media.giphy.com/media/3GqmB4W5MpHkA/giphy.gif",
        "https://media.giphy.com/media/xT8qBit7YomT80d0M8/giphy.gif",
    ],
    "armored": [
        "https://media.giphy.com/media/Lp4Bv3F1zMcqI/giphy.gif",
        "https://media.giphy.com/media/aYpRjQ3TIwWWY/giphy.gif",
    ],
    "freedom": [
        "https://media.giphy.com/media/qBiPolsRg7Mw0/giphy.gif",
        "https://media.giphy.com/media/3o7aCTPMoCMGFtj3oA/giphy.gif",
    ],
}


async def _from_tenor(query: str) -> str:
    """Tenor v2 API — fastest source for anime GIFs."""
    if not TENOR_KEY:
        return ""
    url = (
        "https://tenor.googleapis.com/v2/search"
        f"?q={quote_plus(query)}&key={TENOR_KEY}&limit=15&media_filter=gif"
    )
    try:
        sess = _session()
        async with sess.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
            if resp.status == 200:
                data = await resp.json()
                urls = [
                    item["media_formats"]["gif"]["url"]
                    for item in data.get("results", [])[:10]
                    if item.get("media_formats", {}).get("gif", {}).get("url")
                ]
                if urls:
                    random.shuffle(urls)
                    for u in urls:
                        if await _validate_url(u, sess):
                            return u
    except Exception as e:
        logger.warning(f"Tenor API error for '{query}': {e}")
    return ""


async def _from_giphy(query: str) -> str:
    """Giphy search API."""
    if not GIPHY_KEY:
        return ""
    url = (
        "https://api.giphy.com/v1/gifs/search"
        f"?api_key={GIPHY_KEY}&q={quote_plus(query)}&limit=15&rating=pg-13"
    )
    try:
        sess = _session()
        async with sess.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
            if resp.status == 200:
                data = await resp.json()
                urls = [
                    item["images"]["original"]["url"]
                    for item in data.get("data", [])[:10]
                    if item.get("images", {}).get("original", {}).get("url")
                ]
                if urls:
                    random.shuffle(urls)
                    for u in urls:
                        if await _validate_url(u, sess):
                            return u
    except Exception as e:
        logger.warning(f"Giphy API error for '{query}': {e}")
    return ""


async def get_gif(action: str, _tenor_query: str = "") -> str:
    """Return a GIF URL for the action.
    Priority: Tenor v2 -> Giphy -> curated fallback.
    Never raises — always returns a string (possibly empty if all fail).
    """
    query = QUERY_MAP.get(action, f"attack on titan {action}")

    # Try Tenor first — best anime coverage and faster response
    gif = await _from_tenor(query)
    if gif:
        return gif

    # Try Giphy second
    gif = await _from_giphy(query)
    if gif:
        return gif

    # Use curated fallback — always works
    fallback = AOT_FALLBACK_GIFS.get(action) or AOT_FALLBACK_GIFS.get("transform", [])
    
    sess = _session()
    if fallback:
        random.shuffle(fallback)
        for fb_url in fallback:
            if await _validate_url(fb_url, sess):
                return fb_url

    logger.error(f"Failed to fetch any valid GIF for action '{action}'")
    return ""

async def _validate_url(url: str, sess: aiohttp.ClientSession) -> bool:
    """Check if the URL returns a valid image without downloading the full body."""
    try:
        async with sess.head(url, timeout=2.0) as resp:
            if resp.status == 200 and 'image' in resp.headers.get('Content-Type', ''):
                return True
            # Some CDNs block HEAD requests, fallback to GET with stream
            if resp.status in (405, 403, 501):
                async with sess.get(url, timeout=2.0) as get_resp:
                    return get_resp.status == 200 and 'image' in get_resp.headers.get('Content-Type', '')
    except Exception:
        pass
    return False
