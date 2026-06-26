import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import re
import os
import json
import aiohttp
import shlex
from collections import deque

# ── yt-dlp YouTube bot-detection bypass ───────────────────────────────────────
#
# YouTube (2026) aggressively blocks unauthenticated requests from all
# yt-dlp player clients (web, ios, android). The ONLY reliable fix is to
# pass real logged-in browser cookies.
#
# Priority order (first match wins):
#   1. YTDLP_COOKIES_FILE env var  → path to a cookies.txt (Netscape format)
#   2. cookies.txt in project root → same format
#   3. Auto-read from browser      → set YTDLP_BROWSER env var to one of:
#                                    chrome / firefox / brave / edge / chromium
#
# How to export cookies.txt:
#   - Install the "Get cookies.txt LOCALLY" Chrome/Firefox extension
#   - Go to youtube.com while logged in → click the extension → Export
#   - Save as cookies.txt in the bot's root folder (same dir as bot.py)
#
# The tv_embedded + web fallback client is the most permissive combination
# for server-side (headless) use in 2026.
# ─────────────────────────────────────────────────────────────────────────────

_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE", "cookies.txt")
_BROWSER      = os.getenv("YTDLP_BROWSER", "")   # e.g. "chrome", "firefox"

def _build_ytdlp_opts() -> dict:
    opts = {
        "format": "bestaudio[acodec=opus]/bestaudio[acodec=aac]/bestaudio/best",
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "js_runtimes": {"node": {}},
        # ── Speed optimizations ──
        "skip_download": True,
        "geo_bypass": True,
        "socket_timeout": 10,
        "retries": 3,
        # Prefer pre-muxed streams for faster start
        "prefer_free_formats": True,
    }

    # 1. Explicit cookies file
    if os.path.isfile(_COOKIES_FILE):
        opts["cookiefile"] = _COOKIES_FILE

    # 2. Auto-extract cookies from an installed browser (overrides file if set)
    elif _BROWSER:
        opts["cookiesfrombrowser"] = (_BROWSER,)  # tuple: (browser_name,)

    return opts


YTDLP_OPTS = _build_ytdlp_opts()

# ── FFmpeg options for high-quality, stable audio ──────────────────────────────
# - reconnect: auto-reconnect on network drops (critical for long tracks)
# - reconnect_at_eof: reconnect if connection is closed by server (e.g. YouTube throttling)
FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_at_eof 1 -reconnect_delay_max 5"
    ),
    "options": "-vn",
}


# ── Spotify Integration ──────────────────────────────────────────────────────
SPOTIFY_PATTERN = re.compile(r"https?://open\.spotify\.com/(track|playlist|album)/([a-zA-Z0-9]+)")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

_spotify_client = None
if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        _spotify_client = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET
            )
        )
        print("[Music] Official Spotify client initialized successfully.")
    except Exception as e:
        print(f"[Music] Error initializing official Spotify API client: {e}")


async def resolve_spotify_track(track_id: str) -> str | None:
    """Resolve a single Spotify track to a search query 'Artist - Song' without API keys."""
    url = f"https://open.spotify.com/embed/track/{track_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                        entity = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity", {})
                        title = entity.get("title") or entity.get("name")
                        artists = [a.get("name") for a in entity.get("artists", []) if a.get("name")]
                        if title and artists:
                            return f"{artists[0]} - {title}"
        except Exception as e:
            print(f"[Music] Spotify embed resolve error: {e}")
    return None


async def resolve_spotify(query: str, loop: asyncio.AbstractEventLoop) -> tuple[list[dict] | None, str | None]:
    """
    Checks if query is a Spotify link. Returns a tuple of:
    - List of dicts: [{'title': '...', 'query': '...', 'url': None}, ...] if matched and resolved
    - Error message string if matched but resolution failed
    Returns (None, None) if the query is not a Spotify link.
    """
    match = SPOTIFY_PATTERN.match(query)
    if not match:
        return None, None

    link_type = match.group(1)
    item_id = match.group(2)

    # 1. Use official Spotify client if credentials exist in .env
    if _spotify_client:
        def _fetch():
            try:
                if link_type == "track":
                    track = _spotify_client.track(item_id)
                    artist = track["artists"][0]["name"]
                    name = track["name"]
                    return [{"title": f"{artist} - {name}", "query": f"{artist} - {name}", "url": None}], None
                elif link_type == "album":
                    album = _spotify_client.album(item_id)
                    artist = album["artists"][0]["name"]
                    tracks = []
                    for item in album["tracks"]["items"]:
                        tname = item["name"]
                        tracks.append({"title": f"{artist} - {tname}", "query": f"{artist} - {tname}", "url": None})
                    return tracks, None
                elif link_type == "playlist":
                    results = _spotify_client.playlist_items(item_id)
                    tracks = []
                    while results:
                        for item in results["items"]:
                            if item.get("track"):
                                track = item["track"]
                                artist = track["artists"][0]["name"]
                                name = track["name"]
                                tracks.append({"title": f"{artist} - {name}", "query": f"{artist} - {name}", "url": None})
                        if results["next"]:
                            results = _spotify_client.next(results)
                        else:
                            break
                    return tracks, None
            except Exception as e:
                # If track fetch fails (e.g. 403 active premium subscription required), fall back to public embed scraper!
                if link_type == "track":
                    print(f"[Music] Official API failed: {e}. Falling back to guest resolver...")
                    return None, "FALLBACK_TO_SCRAPER"
                
                # Check for the known 403 Premium account restriction
                err_msg = str(e)
                if "Active premium subscription required" in err_msg or "403" in err_msg:
                    return None, (
                        "Official Spotify API returned 403 Forbidden. "
                        "Spotify now requires the owner of the Developer App to have an active Spotify Premium subscription.\n"
                        "Since your Spotify account is on the Free tier, Spotify blocks API playlist/album retrieval."
                    )
                return None, f"Official Spotify API error: {e}"
            return None, "Unsupported Spotify link type."

        tracks_res, error_res = await loop.run_in_executor(None, _fetch)
        if error_res == "FALLBACK_TO_SCRAPER":
            pass
        elif tracks_res is not None or error_res is not None:
            return tracks_res, error_res

    # 2. No credentials / fallback resolver
    if link_type == "track":
        res = await resolve_spotify_track(item_id)
        if res:
            return [{"title": res, "query": res, "url": None}], None
        return None, "Could not extract Spotify track metadata. Make sure the link is valid."
    
    # Explain how to configure playlist/album resolution
    return None, (
        "Spotify playlists and albums require official API credentials from a Spotify Premium account.\n"
        "Please edit your `.env` file to add your `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` of a Premium user!"
    )


def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


async def extract_info(query: str, loop: asyncio.AbstractEventLoop) -> dict | None:
    """
    Extracts audio source URL and metadata from a YouTube link, search term,
    or other yt-dlp supported URL.
    """
    opts = dict(YTDLP_OPTS)
    if not is_url(query) and not query.startswith("ytsearch:"):
        opts["default_search"] = "ytsearch"

    def _extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if info is None:
                return None
            if "entries" in info:
                info = info["entries"][0]
            return info

    return await loop.run_in_executor(None, _extract)


class MusicQueue:
    def __init__(self):
        self.queue: deque[dict] = deque()
        self.current: dict | None = None
        self.loop: str = "off"          # 'off', 'song', 'queue'
        self.bypass_loop: bool = False

    def add(self, info: dict):
        self.queue.append(info)

    def next(self) -> dict | None:
        if self.queue:
            self.current = self.queue.popleft()
            return self.current
        self.current = None
        return None

    def clear(self):
        self.queue.clear()
        self.current = None
        self.loop = "off"
        self.bypass_loop = False

    def __len__(self):
        return len(self.queue)


AOT_PLAYLIST = [
    # Openings
    {"title": "Linked Horizon - Guren no Yumiya (AOT OP1)", "query": "Linked Horizon Guren no Yumiya", "url": None},
    {"title": "Linked Horizon - Jiyuu no Tsubasa (AOT OP2)", "query": "Linked Horizon Jiyuu no Tsubasa", "url": None},
    {"title": "Linked Horizon - Shinzou wo Sasageyo! (AOT OP3)", "query": "Linked Horizon Shinzou wo Sasageyo", "url": None},
    {"title": "Yoshiki feat. Hyde - Red Swan (AOT OP4)", "query": "Yoshiki feat Hyde Red Swan", "url": None},
    {"title": "Linked Horizon - Shoukei to Shikabane no Michi (AOT OP5)", "query": "Linked Horizon Shoukei to Shikabane no Michi", "url": None},
    {"title": "Shinsei Kamattechan - My War / Boku no Sensou (AOT OP6)", "query": "Shinsei Kamattechan My War", "url": None},
    {"title": "SiM - The Rumbling (AOT OP7)", "query": "SiM The Rumbling", "url": None},
    {"title": "SiM - Under the Tree (AOT OP8)", "query": "SiM Under the Tree", "url": None},
    {"title": "Linked Horizon - The Last Titan / Saigo no Kyojin (AOT OP9)", "query": "Linked Horizon The Last Titan", "url": None},
    
    # Endings
    {"title": "Yoko Hikasa - Utsukushiki Zankoku na Sekai (AOT ED1)", "query": "Yoko Hikasa Utsukushiki Zankoku na Sekai", "url": None},
    {"title": "Cinema Staff - Great Escape (AOT ED2)", "query": "cinema staff Great Escape", "url": None},
    {"title": "Linked Horizon - Requiem der Morgenroete (AOT ED3)", "query": "Linked Horizon Requiem der Morgenroete", "url": None},
    {"title": "Cinema Staff - Name of Love (AOT ED4)", "query": "cinema staff Name of Love", "url": None},
    {"title": "Shinsei Kamattechan - Yuugure no Tori (AOT ED5)", "query": "Shinsei Kamattechan Yuugure no Tori", "url": None},
    {"title": "Yuko Ando - Shock / Shougeki (AOT ED6)", "query": "Yuko Ando Shock Shougeki", "url": None},
    {"title": "Ai Higuchi - Akuma no Ko (AOT ED7)", "query": "Ai Higuchi Akuma no Ko", "url": None},
    {"title": "Linked Horizon - To You in 2,000... or 20,000 Years... (AOT ED8)", "query": "Linked Horizon To You in 2000 or 20000 Years", "url": None},
    
    # Soundtrack Masterpieces
    {"title": "Hiroyuki Sawano - YouSeeBIGGIRL/T:T (AOT OST)", "query": "Sawano Hiroyuki YouSeeBIGGIRL", "url": None},
    {"title": "Hiroyuki Sawano - Vogel im Kaefig (AOT OST)", "query": "Sawano Hiroyuki Vogel im Kaefig", "url": None},
    {"title": "Hiroyuki Sawano - Ashes on The Fire (AOT OST)", "query": "Sawano Hiroyuki Ashes on The Fire", "url": None},
    {"title": "Hiroyuki Sawano - Footsteps of Doom (Rumbling Theme OST)", "query": "Sawano Hiroyuki Footsteps of Doom", "url": None},
    {"title": "Hiroyuki Sawano - XL-TT (Colossal Titan OP Theme)", "query": "Sawano Hiroyuki XL-TT", "url": None},
    {"title": "Hiroyuki Sawano - Counter Attack-Mankind (OST)", "query": "Sawano Hiroyuki Counter Attack-Mankind", "url": None},
    {"title": "Hiroyuki Sawano - Barricades (OST)", "query": "Sawano Hiroyuki Barricades", "url": None},
    {"title": "Hiroyuki Sawano - Apple Seed (OST)", "query": "Sawano Hiroyuki Apple Seed", "url": None},
    {"title": "Hiroyuki Sawano - Before Lights Out (OST)", "query": "Sawano Hiroyuki Before Lights Out", "url": None},
    {"title": "Hiroyuki Sawano - DOA (OST)", "query": "Sawano Hiroyuki DOA", "url": None},
    {"title": "Hiroyuki Sawano - The Reluctant Heroes (OST)", "query": "Sawano Hiroyuki The Reluctant Heroes", "url": None},
    {"title": "Hiroyuki Sawano - Bauklötze (OST)", "query": "Sawano Hiroyuki Bauklötze", "url": None},
    {"title": "Hiroyuki Sawano - Call your name (OST)", "query": "Sawano Hiroyuki Call your name", "url": None},
    {"title": "Hiroyuki Sawano - So ist es immer (OST)", "query": "Sawano Hiroyuki So ist es immer", "url": None},
    {"title": "Hiroyuki Sawano - Call of Silence (OST)", "query": "Sawano Hiroyuki Call of Silence", "url": None},
    {"title": "Hiroyuki Sawano - Attack on Titan (WM-Idol Main Theme)", "query": "Sawano Hiroyuki Attack on Titan main theme", "url": None},
    {"title": "Kohta Yamamoto - Splinter Wolf (OST)", "query": "Kohta Yamamoto Splinter Wolf", "url": None}
]

DEATHNOTE_PLAYLIST = [
    {"title": "Nightmare - The World (Death Note OP1)", "query": "Nightmare The World Death Note OP", "url": None},
    {"title": "Maximum the Hormone - What's up, people?! (Death Note OP2)", "query": "Maximum the Hormone Whats up people", "url": None},
    {"title": "Nightmare - Alumina (Death Note ED1)", "query": "Nightmare Alumina Death Note ED", "url": None},
    {"title": "Maximum the Hormone - Zetsubou Billy (Death Note ED2)", "query": "Maximum the Hormone Zetsubou Billy", "url": None},
    {"title": "Yoshihisa Hirano - L's Theme (Death Note OST)", "query": "Yoshihisa Hirano Ls Theme Death Note", "url": None},
    {"title": "Yoshihisa Hirano - Light's Theme (Death Note OST)", "query": "Yoshihisa Hirano Lights Theme Death Note", "url": None},
    {"title": "Yoshihisa Hirano - Low of Solipsism (Death Note OST)", "query": "Yoshihisa Hirano Low of Solipsism", "url": None},
    {"title": "Yoshihisa Hirano - Kyrie (Death Note OST)", "query": "Yoshihisa Hirano Kyrie Death Note", "url": None},
    {"title": "Yoshihisa Hirano - Death Note Theme (Death Note OST)", "query": "Yoshihisa Hirano Death Note Theme", "url": None},
    {"title": "Yoshihisa Hirano - L's Theme B (Death Note OST)", "query": "Yoshihisa Hirano Ls Theme B", "url": None}
]

NARUTO_PLAYLIST = [
    {"title": "KANA-BOON - Silhouette (Naruto Shippuden OP16)", "query": "KANA BOON Silhouette", "url": None},
    {"title": "Ikimono-gakari - Blue Bird (Naruto Shippuden OP3)", "query": "Ikimono gakari Blue Bird", "url": None},
    {"title": "Asian Kung-Fu Generation - Haruka Kanata (Naruto OP2)", "query": "Asian Kung Fu Generation Haruka Kanata", "url": None},
    {"title": "FLOW - Sign (Naruto Shippuden OP6)", "query": "FLOW Sign", "url": None},
    {"title": "FLOW - Go!!! (Naruto OP4)", "query": "FLOW Go Naruto", "url": None},
    {"title": "Toshio Masuda - Sadness and Sorrow (Naruto OST)", "query": "Toshio Masuda Sadness and Sorrow", "url": None},
    {"title": "Toshio Masuda - The Rising Fighting Spirit (Naruto OST)", "query": "Toshio Masuda The Rising Fighting Spirit", "url": None},
    {"title": "Akeboshi - Wind (Naruto ED1)", "query": "Akeboshi Wind Naruto", "url": None},
    {"title": "DOES - Guren (Naruto Shippuden OP15)", "query": "DOES Guren Naruto", "url": None},
    {"title": "mihimaru GT - Hero's Come Back!! (Naruto Shippuden OP1)", "query": "mihimaru GT Heros Come Back", "url": None}
]

DEMONSLAYER_PLAYLIST = [
    {"title": "LiSA - Gurenge (Demon Slayer OP1)", "query": "LiSA Gurenge", "url": None},
    {"title": "LiSA - Homura (Mugen Train Movie Theme)", "query": "LiSA Homura", "url": None},
    {"title": "Aimer - Zankyou Sancka (Demon Slayer OP2)", "query": "Aimer Zankyou Sancka", "url": None},
    {"title": "Go Shiina feat. Nami Nakagawa - Kamado Tanjiro no Uta (Demon Slayer OST)", "query": "Kamado Tanjiro no Uta", "url": None},
    {"title": "MAN WITH A MISSION x milet - Kizouna (Demon Slayer OP3)", "query": "MAN WITH A MISSION milet Kizouna", "url": None},
    {"title": "LiSA - Akeboshi (Demon Slayer OP4)", "query": "LiSA Akeboshi", "url": None},
    {"title": "LiSA - Shirogane (Demon Slayer ED4)", "query": "LiSA Shirogane", "url": None},
    {"title": "Aimer - Asa ga Kuru (Demon Slayer ED2)", "query": "Aimer Asa ga Kuru", "url": None}
]

BERSERK_PLAYLIST = [
    {"title": "Penpals - Tell Me Why (Berserk 1997 OP)", "query": "Penpals Tell Me Why Berserk", "url": None},
    {"title": "Silver Fins - Waiting So Long (Berserk 1997 ED)", "query": "Silver Fins Waiting So Long", "url": None},
    {"title": "Susumu Hirasawa - Guts Theme (Berserk OST)", "query": "Susumu Hirasawa Guts Theme", "url": None},
    {"title": "Susumu Hirasawa - Forces (Berserk OST)", "query": "Susumu Hirasawa Forces", "url": None},
    {"title": "Susumu Hirasawa - Behelit (Berserk OST)", "query": "Susumu Hirasawa Behelit", "url": None},
    {"title": "Susumu Hirasawa - Hai Yo (Berserk 2016 OST)", "query": "Susumu Hirasawa Hai Yo", "url": None},
    {"title": "Susumu Hirasawa - Ash Crow (Berserk OST)", "query": "Susumu Hirasawa Ash Crow", "url": None},
    {"title": "Susumu Hirasawa - Sign (Berserk Game Theme)", "query": "Susumu Hirasawa Sign Berserk", "url": None},
    {"title": "Shiro Sagisu - Blood and Guts (Berserk Movie OST)", "query": "Shiro Sagisu Blood and Guts", "url": None},
    {"title": "Shiro Sagisu - My Brother (Berserk Movie OST)", "query": "Shiro Sagisu My Brother", "url": None}
]

VINLANDSAGA_PLAYLIST = [
    {"title": "Survive Said The Prophet - Mukanjyo (Vinland Saga OP1)", "query": "Survive Said The Prophet Mukanjyo", "url": None},
    {"title": "MAN WITH A MISSION - Dark Crow (Vinland Saga OP2)", "query": "MAN WITH A MISSION Dark Crow", "url": None},
    {"title": "Aimer - Torches (Vinland Saga ED1)", "query": "Aimer Torches Vinland Saga", "url": None},
    {"title": "milet - Drown (Vinland Saga ED2)", "query": "milet Drown Vinland Saga", "url": None},
    {"title": "Anonymouz - River (Vinland Saga S2 OP1)", "query": "Anonymouz River Vinland Saga", "url": None},
    {"title": "Survive Said The Prophet - Paradox (Vinland Saga S2 OP2)", "query": "Survive Said The Prophet Paradox", "url": None},
    {"title": "LMYK - Without Love (Vinland Saga S2 ED1)", "query": "LMYK Without Love", "url": None},
    {"title": "haju:harmonics - Ember (Vinland Saga S2 ED2)", "query": "hajuharmonics Ember Vinland Saga", "url": None}
]

TOKYOREVENGERS_PLAYLIST = [
    {"title": "Official HIGE DANdism - Cry Baby (Tokyo Revengers OP1)", "query": "Official HIGE DANdism Cry Baby Tokyo Revengers OP", "url": None},
    {"title": "Official HIGE DANdism - White Noise (Tokyo Revengers OP2)", "query": "Official HIGE DANdism White Noise Tokyo Revengers OP", "url": None},
    {"title": "eill - Koko de Iki wo Shite (Tokyo Revengers ED1)", "query": "eill Koko de Iki wo Shite Tokyo Revengers ED", "url": None},
    {"title": "Nakimushi - Tokyo Wonder. (Tokyo Revengers ED2)", "query": "Nakimushi Tokyo Wonder Tokyo Revengers ED", "url": None},
    {"title": "Tuyu - Kizutsukedo, Aishiteru. (Tokyo Revengers Christmas Showdown ED)", "query": "Tuyu Kizutsukedo Aishiteru Tokyo Revengers ED", "url": None}
]

JUJUTSUKAISEN_PLAYLIST = [
    {"title": "Eve - Kaikai Kitan (Jujutsu Kaisen OP1)", "query": "Eve Kaikai Kitan Jujutsu Kaisen OP", "url": None},
    {"title": "Who-ya Extended - VIVID VICE (Jujutsu Kaisen OP2)", "query": "Who ya Extended VIVID VICE Jujutsu Kaisen OP", "url": None},
    {"title": "ALI feat. AKLO - Lost in Paradise (Jujutsu Kaisen ED1)", "query": "ALI Lost in Paradise Jujutsu Kaisen ED", "url": None},
    {"title": "Cö shu Nie - Give it Back (Jujutsu Kaisen ED2)", "query": "Co shu Nie Give it Back Jujutsu Kaisen ED", "url": None},
    {"title": "Tatsuya Kitani - Ao no Sumika (Jujutsu Kaisen S2 OP1)", "query": "Tatsuya Kitani Ao no Sumika Jujutsu Kaisen OP", "url": None},
    {"title": "King Gnu - Specialz (Jujutsu Kaisen S2 OP2)", "query": "King Gnu Specialz Jujutsu Kaisen OP", "url": None},
    {"title": "Soushi Sakiyama - Akari (Jujutsu Kaisen S2 ED1)", "query": "Soushi Sakiyama Akari Jujutsu Kaisen ED", "url": None},
    {"title": "Hitsujibungaku - More Than Words (Jujutsu Kaisen S2 ED2)", "query": "Hitsujibungaku More Than Words Jujutsu Kaisen ED", "url": None}
]

ANIME_PLAYLISTS = {
    "AOT": {"name": "Attack on Titan", "color": discord.Color.red(), "tracks": AOT_PLAYLIST, "icon": "⚔️"},
    "DEATHNOTE": {"name": "Death Note", "color": discord.Color.purple(), "tracks": DEATHNOTE_PLAYLIST, "icon": "📓"},
    "NARUTO": {"name": "Naruto", "color": discord.Color.orange(), "tracks": NARUTO_PLAYLIST, "icon": "🦊"},
    "DEMONSLAYER": {"name": "Demon Slayer", "color": discord.Color.blue(), "tracks": DEMONSLAYER_PLAYLIST, "icon": "🌊"},
    "BERSERK": {"name": "Berserk", "color": discord.Color.dark_gray(), "tracks": BERSERK_PLAYLIST, "icon": "💀"},
    "VINLANDSAGA": {"name": "Vinland Saga", "color": discord.Color.gold(), "tracks": VINLANDSAGA_PLAYLIST, "icon": "🛡️"},
    "TOKYOREVENGERS": {"name": "Tokyo Revengers", "color": discord.Color.from_rgb(241, 196, 15), "tracks": TOKYOREVENGERS_PLAYLIST, "icon": "🏍️"},
    "JUJUTSUKAISEN": {"name": "Jujutsu Kaisen", "color": discord.Color.from_rgb(44, 62, 80), "tracks": JUJUTSUKAISEN_PLAYLIST, "icon": "🔮"}
}


_queues: dict[int, MusicQueue] = {}


def get_queue(guild_id: int) -> MusicQueue:
    if guild_id not in _queues:
        _queues[guild_id] = MusicQueue()
    return _queues[guild_id]


class Music(commands.Cog):
    """🎵 Music commands — play audio from YouTube, Spotify names, or any URL."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _join_channel(self, ctx_or_interaction) -> discord.VoiceClient | None:
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
        author = ctx_or_interaction.user if is_interaction else ctx_or_interaction.author
        guild  = ctx_or_interaction.guild

        if not author.voice or not author.voice.channel:
            msg = "❌ You need to be in a voice channel first!"
            if is_interaction:
                await ctx_or_interaction.followup.send(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)
            return None

        vc: discord.VoiceClient | None = guild.voice_client
        if vc and vc.is_connected():
            if vc.channel != author.voice.channel:
                await vc.move_to(author.voice.channel)
        else:
            vc = await author.voice.channel.connect()
        return vc

    async def _play_next(self, guild: discord.Guild, channel: discord.TextChannel):
        queue = get_queue(guild.id)
        
        # Determine next track based on loop settings
        if queue.bypass_loop:
            queue.bypass_loop = False
            info = queue.next()
        elif queue.loop == "song" and queue.current is not None:
            info = queue.current
        elif queue.loop == "queue" and queue.current is not None:
            queue.add(queue.current)
            info = queue.next()
        else:
            info = queue.next()

        if info is None:
            await channel.send("✅ Queue finished! Use `p <song>` or `/play` to add more.")
            return

        vc: discord.VoiceClient = guild.voice_client
        if not vc or not vc.is_connected():
            return

        # If it is a lazy-resolved query (like Spotify tracks loaded dynamically)
        if info.get("url") is None:
            search_query = info.get("query")
            try:
                resolved_info = await extract_info(search_query, self.bot.loop)
                if resolved_info:
                    info.update(resolved_info)
                else:
                    await channel.send(f"⚠️ Could not resolve song: `{search_query}`. Skipping...")
                    await self._play_next(guild, channel)
                    return
            except Exception as e:
                await channel.send(f"❌ Error resolving song: `{search_query}` ({e}). Skipping...")
                await self._play_next(guild, channel)
                return

        # Get headers from yt-dlp to bypass 429 blocks
        headers = info.get("http_headers", {})
        headers_str = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        
        ffmpeg_options = {
            "before_options": (
                f'-reconnect 1 -reconnect_streamed 1 -reconnect_at_eof 1 -reconnect_delay_max 5 '
                f'-headers {shlex.quote(headers_str)}'
            ),
            "options": "-vn",
        }

        try:
            source = await discord.FFmpegOpusAudio.from_probe(info["url"], **ffmpeg_options)
        except Exception as e:
            print(f"[Music] Error creating audio source: {e}")
            await channel.send("❌ Error preparing playback source.")
            await self._play_next(guild, channel)
            return

        def after_play(error):
            if error:
                print(f"[Music] Playback error: {error}")
            asyncio.run_coroutine_threadsafe(self._play_next(guild, channel), self.bot.loop)

        vc.play(source, after=after_play)
        
        # Dynamically maximize voice client encoder bitrate to channel limits
        try:
            if hasattr(vc, "encoder") and vc.encoder:
                target_bitrate = min(vc.channel.bitrate, 512000)
                vc.encoder.set_bitrate(target_bitrate)
                print(f"[Music] Set encoder bitrate to {target_bitrate // 1000}kbps (Channel Max: {vc.channel.bitrate // 1000}kbps)")
        except Exception as e:
            print(f"[Music] Failed to dynamically adjust voice bitrate: {e}")
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**[{info.get('title', 'Unknown')}]({info.get('webpage_url', '#')})** "
                        f"\n⏱️ {self._fmt_duration(info.get('duration'))} | 👤 {info.get('uploader', 'Unknown')}",
            color=discord.Color.green(),
        )
        thumbnail = info.get("thumbnail")
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        await channel.send(embed=embed)

    @staticmethod
    def _fmt_duration(seconds) -> str:
        if not seconds:
            return "Live"
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    async def _handle_play(self, guild, author, channel, query: str, vc: discord.VoiceClient):
        queue = get_queue(guild.id)
        
        # Intercept Anime playlists command
        playlist_key = query.strip().upper().replace(" ", "")
        if playlist_key in ANIME_PLAYLISTS:
            playlist_info = ANIME_PLAYLISTS[playlist_key]
            import copy
            tracks_to_add = copy.deepcopy(playlist_info["tracks"])
            is_first = not (vc.is_playing() or vc.is_paused() or len(queue) > 0)
            
            # Resolve the first song immediately if nothing is currently playing
            if is_first:
                await channel.send(f"🔍 Resolving and playing first track: `{tracks_to_add[0]['title']}`...")
                try:
                    resolved = await extract_info(tracks_to_add[0]["query"], self.bot.loop)
                    if resolved:
                        tracks_to_add[0].update(resolved)
                except Exception as e:
                    print(f"[Music] Error resolving first track of {playlist_info['name']}: {e}")
            
            for track in tracks_to_add:
                queue.add(track)
                
            embed = discord.Embed(
                title=f"{playlist_info['icon']} {playlist_info['name']} Playlist Loaded",
                description=f"Added **{len(tracks_to_add)}** epic tracks to the queue.",
                color=playlist_info["color"],
            )
            await channel.send(embed=embed)
            
            if is_first:
                await self._play_next(guild, channel)
            return

        # 1. Check if the query is a Spotify link
        spotify_tracks, spotify_error = await resolve_spotify(query, self.bot.loop)
        if spotify_error:
            await channel.send(f"❌ {spotify_error}")
            return
            
        if spotify_tracks is not None:
            # We matched Spotify!
            if not spotify_tracks:
                await channel.send("❌ No tracks found in that Spotify link.")
                return
                
            is_playlist_or_album = len(spotify_tracks) > 1
            
            # Resolve the first song immediately if nothing is currently playing
            if not (vc.is_playing() or vc.is_paused() or len(queue) > 0):
                await channel.send(f"🔍 Resolving and playing first track: `{spotify_tracks[0]['title']}`...")
                try:
                    resolved = await extract_info(spotify_tracks[0]["query"], self.bot.loop)
                    if resolved:
                        spotify_tracks[0].update(resolved)
                except Exception as e:
                    print(f"[Music] Error resolving first Spotify track: {e}")
            
            # Add all resolved/unresolved tracks to the queue
            for track in spotify_tracks:
                queue.add(track)
                
            if is_playlist_or_album:
                embed = discord.Embed(
                    title="🎶 Spotify Playlist/Album Loaded",
                    description=f"Added **{len(spotify_tracks)}** tracks to the queue.",
                    color=discord.Color.green(),
                )
                await channel.send(embed=embed)
            else:
                track = spotify_tracks[0]
                if vc.is_playing() or vc.is_paused() or len(queue) > 1:
                    embed = discord.Embed(
                        title="➕ Added to Queue (Spotify)",
                        description=f"**{track.get('title')}**\nPosition in queue: **#{len(queue)}**",
                        color=discord.Color.blurple(),
                    )
                    await channel.send(embed=embed)
            
            # Start playing if not already
            if not vc.is_playing() and not vc.is_paused():
                await self._play_next(guild, channel)
            return

        # 2. Standard non-Spotify flow (YouTube link, search term, etc.)
        await channel.send(f"🔍 Searching for: `{query}`...")
        try:
            info = await extract_info(query, self.bot.loop)
        except Exception as e:
            await channel.send(f"❌ Error fetching audio: `{e}`")
            return

        if not info:
            await channel.send("❌ Couldn't find anything for that query.")
            return

        if vc.is_playing() or vc.is_paused() or len(queue) > 0:
            queue.add(info)
            embed = discord.Embed(
                title="➕ Added to Queue",
                description=f"**{info.get('title', 'Unknown')}** "
                            f"[{self._fmt_duration(info.get('duration'))}]\n"
                            f"Position in queue: **#{len(queue)}**",
                color=discord.Color.blurple(),
            )
            await channel.send(embed=embed)
        else:
            queue.add(info)
            await self._play_next(guild, channel)

    # ── Prefix commands ──────────────────────────────────────────────────────

    @commands.command(name="p", aliases=["play"], help="Play a song from YouTube/Spotify/name. Usage: p <link or name>")
    async def play_prefix(self, ctx: commands.Context, *, query: str):
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, query, vc)

    @commands.command(name="aot", help="Play the full Attack on Titan playlist automatically.")
    async def aot_prefix(self, ctx: commands.Context):
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, "AOT", vc)

    @commands.command(name="deathnote", help="Play the full Death Note playlist automatically.")
    async def deathnote_prefix(self, ctx: commands.Context):
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, "DEATHNOTE", vc)

    @commands.command(name="naruto", help="Play the full Naruto playlist automatically.")
    async def naruto_prefix(self, ctx: commands.Context):
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, "NARUTO", vc)

    @commands.command(name="demonslayer", help="Play the full Demon Slayer playlist automatically.")
    async def demonslayer_prefix(self, ctx: commands.Context):
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, "DEMONSLAYER", vc)

    @commands.command(name="berserk", help="Play the full Berserk playlist automatically.")
    async def berserk_prefix(self, ctx: commands.Context):
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, "BERSERK", vc)

    @commands.command(name="vinlandsaga", help="Play the full Vinland Saga playlist automatically.")
    async def vinlandsaga_prefix(self, ctx: commands.Context):
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, "VINLANDSAGA", vc)

    @commands.command(name="tokyorevengers", help="Play the full Tokyo Revengers playlist automatically.")
    async def tokyorevengers_prefix(self, ctx: commands.Context):
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, "TOKYOREVENGERS", vc)

    @commands.command(name="jujutsukaisen", aliases=["jjk"], help="Play the full Jujutsu Kaisen playlist automatically.")
    async def jujutsukaisen_prefix(self, ctx: commands.Context):
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, "JUJUTSUKAISEN", vc)

    @commands.command(name="loop", help="Toggle loop mode: off, song (repeat current song), queue (repeat entire queue).")
    async def loop_prefix(self, ctx: commands.Context):
        queue = get_queue(ctx.guild.id)
        if queue.loop == "off":
            queue.loop = "song"
            await ctx.send("🔂 Loop enabled: **Single Song**")
        elif queue.loop == "song":
            queue.loop = "queue"
            await ctx.send("🔁 Loop enabled: **Queue**")
        else:
            queue.loop = "off"
            await ctx.send("❌ Loop disabled.")

    @commands.command(name="skip", aliases=["s"], help="Skip the current song.")
    async def skip_prefix(self, ctx: commands.Context):
        vc: discord.VoiceClient = ctx.guild.voice_client
        if vc and vc.is_playing():
            queue = get_queue(ctx.guild.id)
            queue.bypass_loop = True
            vc.stop()
            await ctx.send("⏭️ Skipped!")
        else:
            await ctx.send("❌ Nothing is playing right now.")

    @commands.command(name="pause", help="Pause the current song.")
    async def pause_prefix(self, ctx: commands.Context):
        vc: discord.VoiceClient = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸️ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="resume", help="Resume the paused song.")
    async def resume_prefix(self, ctx: commands.Context):
        vc: discord.VoiceClient = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ Resumed!")
        else:
            await ctx.send("❌ Nothing is paused.")

    @commands.command(name="stop", help="Stop music and clear the queue.")
    async def stop_prefix(self, ctx: commands.Context):
        queue = get_queue(ctx.guild.id)
        queue.clear()
        vc: discord.VoiceClient = ctx.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
        await ctx.send("⏹️ Stopped and cleared the queue.")

    @commands.command(name="queue", aliases=["q"], help="Show the current music queue.")
    async def queue_prefix(self, ctx: commands.Context):
        queue = get_queue(ctx.guild.id)
        embed = discord.Embed(title="🎶 Music Queue", color=discord.Color.blurple())
        if queue.current:
            embed.add_field(name="▶️ Now Playing", value=f"`{queue.current.get('title', 'Unknown')}`", inline=False)
        if queue.queue:
            tracks = "\n".join(
                f"`{i+1}.` {t.get('title', 'Unknown')} [{self._fmt_duration(t.get('duration'))}]"
                for i, t in enumerate(list(queue.queue)[:10])
            )
            if len(queue) > 10:
                tracks += f"\n...and {len(queue) - 10} more"
            embed.add_field(name="📋 Up Next", value=tracks, inline=False)
        else:
            embed.description = "Queue is empty!"
        await ctx.send(embed=embed)

    @commands.command(name="ping", help="Check the bot's latency.")
    async def ping_prefix(self, ctx: commands.Context):
        latency_ms = round(self.bot.latency * 1000)
        color = discord.Color.green() if latency_ms < 100 else (discord.Color.yellow() if latency_ms < 200 else discord.Color.red())
        embed = discord.Embed(title="🏓 Pong!", description=f"Bot latency: **{latency_ms}ms**", color=color)
        await ctx.send(embed=embed)

    # ── Slash commands ───────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song from YouTube, Spotify, or search by name.")
    @app_commands.describe(query="YouTube link, Spotify link, or song name")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, query, vc)

    @app_commands.command(name="aot", description="Play the full Attack on Titan playlist automatically.")
    async def aot_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, "AOT", vc)

    @app_commands.command(name="deathnote", description="Play the full Death Note playlist automatically.")
    async def deathnote_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, "DEATHNOTE", vc)

    @app_commands.command(name="naruto", description="Play the full Naruto playlist automatically.")
    async def naruto_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, "NARUTO", vc)

    @app_commands.command(name="demonslayer", description="Play the full Demon Slayer playlist automatically.")
    async def demonslayer_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, "DEMONSLAYER", vc)

    @app_commands.command(name="berserk", description="Play the full Berserk playlist automatically.")
    async def berserk_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, "BERSERK", vc)

    @app_commands.command(name="vinlandsaga", description="Play the full Vinland Saga playlist automatically.")
    async def vinlandsaga_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, "VINLANDSAGA", vc)

    @app_commands.command(name="tokyorevengers", description="Play the full Tokyo Revengers playlist automatically.")
    async def tokyorevengers_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, "TOKYOREVENGERS", vc)

    @app_commands.command(name="jujutsukaisen", description="Play the full Jujutsu Kaisen playlist automatically.")
    async def jujutsukaisen_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, "JUJUTSUKAISEN", vc)

    @app_commands.command(name="loop", description="Toggle loop mode: off, song, queue")
    async def loop_slash(self, interaction: discord.Interaction):
        queue = get_queue(interaction.guild_id)
        if queue.loop == "off":
            queue.loop = "song"
            await interaction.response.send_message("🔂 Loop enabled: **Single Song**")
        elif queue.loop == "song":
            queue.loop = "queue"
            await interaction.response.send_message("🔁 Loop enabled: **Queue**")
        else:
            queue.loop = "off"
            await interaction.response.send_message("❌ Loop disabled.")

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip_slash(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client
        if vc and vc.is_playing():
            queue = get_queue(interaction.guild_id)
            queue.bypass_loop = True
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped!")
        else:
            await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause the current song.")
    async def pause_slash(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume paused music.")
    async def resume_slash(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed!")
        else:
            await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)

    @app_commands.command(name="stop", description="Stop music and clear the queue.")
    async def stop_slash(self, interaction: discord.Interaction):
        queue = get_queue(interaction.guild.id)
        queue.clear()
        vc: discord.VoiceClient = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
        await interaction.response.send_message("⏹️ Stopped and cleared the queue.")

    @app_commands.command(name="queue", description="Show the current music queue.")
    async def queue_slash(self, interaction: discord.Interaction):
        queue = get_queue(interaction.guild.id)
        embed = discord.Embed(title="🎶 Music Queue", color=discord.Color.blurple())
        if queue.current:
            embed.add_field(name="▶️ Now Playing", value=f"`{queue.current.get('title', 'Unknown')}`", inline=False)
        if queue.queue:
            tracks = "\n".join(
                f"`{i+1}.` {t.get('title', 'Unknown')} [{self._fmt_duration(t.get('duration'))}]"
                for i, t in enumerate(list(queue.queue)[:10])
            )
            embed.add_field(name="📋 Up Next", value=tracks, inline=False)
        else:
            embed.description = "Queue is empty!"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Check the bot's current latency.")
    async def ping_slash(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)
        color = discord.Color.green() if latency_ms < 100 else (discord.Color.yellow() if latency_ms < 200 else discord.Color.red())
        embed = discord.Embed(title="🏓 Pong!", description=f"Bot latency: **{latency_ms}ms**", color=color)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
