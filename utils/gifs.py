"""AoT GIF fetcher.

Priority:
  1. Tenor API  — AoT-specific GIFs  (requires TENOR_API_KEY in .env)
  2. nekos.best — anime reaction GIFs (always free, no key needed)

Usage:
    gif_url = await get_gif("hug", "hug embrace")
"""
import os
import random
import aiohttp

TENOR_KEY = os.getenv("TENOR_API_KEY", "")

# nekos.best v2 supported actions (free, always works)
NEKOS_ACTIONS = {
    "hug", "pat", "slap", "wave", "poke", "kiss", "cry", "blush", "bonk",
    "bite", "cuddle", "dance", "happy", "highfive", "kick", "laugh",
    "punch", "shoot", "shrug", "sleep", "smile", "think", "thumbsup", "wink",
}


async def get_gif(nekos_action: str, tenor_query: str = "") -> str:
    """Fetch a GIF URL.

    Args:
        nekos_action: nekos.best action name (used as fallback).
        tenor_query:  Tenor search term, e.g. 'mikasa slash blade'.

    Returns:
        A direct .gif URL, or empty string on failure.
    """
    # ── Tenor (AoT-specific) ────────────────────────────────────────────────
    if TENOR_KEY:
        q = f"attack on titan {tenor_query or nekos_action}".replace(" ", "+")
        url = (
            f"https://tenor.googleapis.com/v2/search"
            f"?q={q}&key={TENOR_KEY}&limit=20&media_filter=gif"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            item = random.choice(results[:10])
                            return item["media_formats"]["gif"]["url"]
        except Exception:
            pass

    # ── nekos.best fallback ───────────────────────────────────────────────────
    safe_action = nekos_action if nekos_action in NEKOS_ACTIONS else "hug"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://nekos.best/api/v2/{safe_action}",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        return results[0]["url"]
    except Exception:
        pass

    return ""
