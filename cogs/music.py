import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import re
from collections import deque

# yt-dlp options for extracting audio
YTDLP_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "opus",
        "preferredquality": "192",
    }],
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

# Spotify URL pattern — extract track/playlist name for YouTube search
SPOTIFY_PATTERN = re.compile(r"https?://open\.spotify\.com/(track|playlist|album)/([a-zA-Z0-9]+)")


def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


async def extract_info(query: str, loop: asyncio.AbstractEventLoop) -> dict | None:
    """
    Extracts audio source URL and metadata from a YouTube link, search term,
    or other yt-dlp supported URL. Spotify links are converted to a YouTube search.
    """
    # Handle Spotify — convert to search query
    spotify_match = SPOTIFY_PATTERN.match(query)
    if spotify_match:
        # We can't stream Spotify directly; search YouTube by track name instead
        track_id = spotify_match.group(2)
        query = f"ytsearch:{track_id} spotify"

    opts = dict(YTDLP_OPTS)
    if not is_url(query) and not query.startswith("ytsearch:"):
        opts["default_search"] = "ytsearch"

    def _extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if info is None:
                return None
            if "entries" in info:
                # Playlist or search result — take first entry
                info = info["entries"][0]
            return info

    return await loop.run_in_executor(None, _extract)


class MusicQueue:
    def __init__(self):
        self.queue: deque[dict] = deque()
        self.current: dict | None = None

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

    def __len__(self):
        return len(self.queue)


# Guild queues
_queues: dict[int, MusicQueue] = {}


def get_queue(guild_id: int) -> MusicQueue:
    if guild_id not in _queues:
        _queues[guild_id] = MusicQueue()
    return _queues[guild_id]


class Music(commands.Cog):
    """🎵 Music commands — play audio from YouTube, Spotify names, or any URL."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────

    async def _join_channel(self, ctx_or_interaction) -> discord.VoiceClient | None:
        """Joins the author's voice channel. Works for both prefix & slash ctx."""
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
        """Plays the next song in the queue, or announces queue end."""
        queue = get_queue(guild.id)
        info = queue.next()
        if info is None:
            await channel.send("✅ Queue finished! Use `p <song>` or `/play` to add more.")
            return

        vc: discord.VoiceClient = guild.voice_client
        if not vc or not vc.is_connected():
            return

        source = await discord.FFmpegOpusAudio.from_probe(info["url"], **FFMPEG_OPTIONS)
        
        def after_play(error):
            if error:
                print(f"[Music] Playback error: {error}")
            asyncio.run_coroutine_threadsafe(self._play_next(guild, channel), self.bot.loop)

        vc.play(source, after=after_play)
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
        """Core play logic used by both prefix and slash commands."""
        queue = get_queue(guild.id)

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

    # ─────────────────────────────────────────────
    # Prefix commands
    # ─────────────────────────────────────────────

    @commands.command(name="p", aliases=["play"], help="Play a song from YouTube/Spotify/name. Usage: p <link or name>")
    async def play_prefix(self, ctx: commands.Context, *, query: str):
        """Prefix play: `p <link or song name>`"""
        vc = await self._join_channel(ctx)
        if vc is None:
            return
        await self._handle_play(ctx.guild, ctx.author, ctx.channel, query, vc)

    @commands.command(name="skip", aliases=["s"], help="Skip the current song.")
    async def skip_prefix(self, ctx: commands.Context):
        vc: discord.VoiceClient = ctx.guild.voice_client
        if vc and vc.is_playing():
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
            embed.add_field(
                name="▶️ Now Playing",
                value=f"`{queue.current.get('title', 'Unknown')}`",
                inline=False,
            )
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
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: **{latency_ms}ms**",
            color=color,
        )
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # Slash commands
    # ─────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song from YouTube, Spotify, or search by name.")
    @app_commands.describe(query="YouTube link, Spotify link, or song name")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self._join_channel(interaction)
        if vc is None:
            return
        await self._handle_play(interaction.guild, interaction.user, interaction.channel, query, vc)

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip_slash(self, interaction: discord.Interaction):
        vc: discord.VoiceClient = interaction.guild.voice_client
        if vc and vc.is_playing():
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
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: **{latency_ms}ms**",
            color=color,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
