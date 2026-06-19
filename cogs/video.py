"""Video streaming cog — streams video into a Discord voice channel using
discord-video-stream-py. Supports YouTube, local files, and any yt-dlp URL.

Commands (prefix + slash):
  vplay  <url/query>  — join VC and stream video + audio (Go Live)
  vstop               — stop the stream and disconnect
  vqueue              — show the video queue
  vskip               — skip the current video
  vpause / vresume    — pause / resume the stream
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy-import helpers so the cog loads even if the library isn't installed
# ---------------------------------------------------------------------------

def _import_dvs():
    """Return (Streamer, VideoPlayer, Resolution, Codec, StreamType) or raise."""
    try:
        from discord_video_stream import (
            Streamer, VideoPlayer, Resolution, Codec, StreamType,
        )
        return Streamer, VideoPlayer, Resolution, Codec, StreamType
    except ImportError as exc:
        raise RuntimeError(
            "discord-video-stream-py is not installed.\n"
            "Run: pip install discord-video-stream-py"
        ) from exc


# ---------------------------------------------------------------------------
# Per-guild video queue
# ---------------------------------------------------------------------------

class VideoQueue:
    def __init__(self):
        self.queue: deque[str] = deque()   # resolved URLs / file paths
        self.titles: deque[str] = deque()  # display titles
        self.current_url: Optional[str] = None
        self.current_title: Optional[str] = None

    def add(self, url: str, title: str):
        self.queue.append(url)
        self.titles.append(title)

    def next(self) -> tuple[Optional[str], Optional[str]]:
        if self.queue:
            self.current_url = self.queue.popleft()
            self.current_title = self.titles.popleft()
            return self.current_url, self.current_title
        self.current_url = self.current_title = None
        return None, None

    def clear(self):
        self.queue.clear()
        self.titles.clear()
        self.current_url = self.current_title = None

    def __len__(self):
        return len(self.queue)


_video_queues: dict[int, VideoQueue] = {}

def get_video_queue(guild_id: int) -> VideoQueue:
    if guild_id not in _video_queues:
        _video_queues[guild_id] = VideoQueue()
    return _video_queues[guild_id]


# ---------------------------------------------------------------------------
# Per-guild streamer state
# ---------------------------------------------------------------------------

class StreamState:
    """Holds per-guild Streamer + VideoPlayer so they survive across commands."""

    def __init__(self):
        self.streamer = None
        self.player   = None
        self.paused   = False
        self._play_task: Optional[asyncio.Task] = None

    def is_active(self) -> bool:
        return self.streamer is not None

    async def stop(self):
        self.paused = False
        if self._play_task and not self._play_task.done():
            self._play_task.cancel()
            try:
                await self._play_task
            except (asyncio.CancelledError, Exception):
                pass
        if self.player:
            try:
                await self.player.stop()
            except Exception:
                pass
        if self.streamer:
            try:
                await self.streamer.stop_stream()
            except Exception:
                pass
        self.player = self.streamer = None


_stream_states: dict[int, StreamState] = {}

def get_stream_state(guild_id: int) -> StreamState:
    if guild_id not in _stream_states:
        _stream_states[guild_id] = StreamState()
    return _stream_states[guild_id]


# ---------------------------------------------------------------------------
# URL resolution helper
# ---------------------------------------------------------------------------

async def _resolve(query: str, loop: asyncio.AbstractEventLoop) -> tuple[str, str]:
    """
    Returns (direct_url, display_title).
    If the query looks like a local path or direct URL, pass it through.
    Otherwise, resolve via yt-dlp.
    """
    import os
    import yt_dlp  # available as a dependency of discord-video-stream-py

    # Local file or direct URL — skip yt-dlp
    is_direct = (
        os.path.exists(query)
        or query.lower().startswith(("rtmp://", "rtmps://", "rtsp://"))
    )
    direct_exts = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts", ".m3u8")
    is_direct = is_direct or any(query.lower().endswith(e) for e in direct_exts)

    if is_direct:
        title = os.path.basename(query) if os.path.exists(query) else query[:60]
        return query, title

    # Prefix bare search terms with ytsearch:
    search_query = query if query.startswith("http") else f"ytsearch:{query}"

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "noplaylist": True,
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            if info is None:
                return None, None
            if "entries" in info:
                info = info["entries"][0]
            url   = info.get("url") or info.get("manifest_url") or query
            title = info.get("title", query[:60])
            return url, title

    return await loop.run_in_executor(None, _extract)


# ---------------------------------------------------------------------------
# The cog
# ---------------------------------------------------------------------------

class Video(commands.Cog):
    """📹 Video streaming commands — stream video into a Discord Go Live session."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── helpers ─────────────────────────────────────────────────────────────

    def _author_vc(self, ctx_or_interaction) -> Optional[discord.VoiceChannel]:
        is_i = isinstance(ctx_or_interaction, discord.Interaction)
        member = ctx_or_interaction.user if is_i else ctx_or_interaction.author
        return member.voice.channel if member.voice else None

    async def _send(self, ctx_or_interaction, content=None, embed=None, ephemeral=False):
        is_i = isinstance(ctx_or_interaction, discord.Interaction)
        if is_i:
            try:
                await ctx_or_interaction.followup.send(
                    content, embed=embed, ephemeral=ephemeral
                )
            except Exception:
                pass
        else:
            await ctx_or_interaction.send(content, embed=embed)

    # ── core stream logic ───────────────────────────────────────────────────

    async def _start_stream(
        self,
        ctx_or_interaction,
        guild: discord.Guild,
        channel: discord.TextChannel,
        vc_channel: discord.VoiceChannel,
        query: str,
    ):
        Streamer, VideoPlayer, Resolution, Codec, StreamType = _import_dvs()

        state = get_stream_state(guild.id)
        queue = get_video_queue(guild.id)

        # Resolve URL
        await self._send(ctx_or_interaction, f"🔍 Resolving: `{query}`...")
        try:
            url, title = await _resolve(query, self.bot.loop)
        except Exception as exc:
            await self._send(ctx_or_interaction, f"❌ Could not resolve: `{exc}`", ephemeral=True)
            return

        if not url:
            await self._send(ctx_or_interaction, "❌ No results found.", ephemeral=True)
            return

        # If already streaming — queue it
        if state.is_active():
            queue.add(url, title)
            embed = discord.Embed(
                title="➕ Added to Video Queue",
                description=f"**{title}**\nPosition: **#{len(queue)}**",
                color=discord.Color.blurple(),
            )
            await self._send(ctx_or_interaction, embed=embed)
            return

        # Fresh stream — join VC and start
        try:
            state.streamer = Streamer(self.bot)
            await state.streamer.join_voice(
                guild_id=guild.id,
                channel_id=vc_channel.id,
            )
            udp = await state.streamer.create_stream(
                resolution=Resolution.R720P,
                fps=30,
                codec=Codec.H264,
                stream_type=StreamType.GO_LIVE,
            )
            state.player = VideoPlayer(url, udp)
        except Exception as exc:
            await state.stop()
            await self._send(ctx_or_interaction, f"❌ Stream setup failed: `{exc}`", ephemeral=True)
            return

        queue.current_url = url
        queue.current_title = title

        embed = discord.Embed(
            title="📹 Now Streaming",
            description=f"**{title}**\n"
                        f"🎥 720p · 30fps · H.264 · Go Live",
            color=discord.Color.red(),
        )
        embed.set_footer(text="Use >vstop to end · >vskip to skip · >vqueue to see queue")
        await self._send(ctx_or_interaction, embed=embed)

        # Play and auto-advance queue
        async def _play_loop():
            nonlocal url, title
            try:
                while url:
                    state.player = VideoPlayer(url, udp)
                    await state.player.play()
                    # Advance queue
                    url, title = queue.next()
                    if url:
                        embed = discord.Embed(
                            title="📹 Next in Queue",
                            description=f"**{title}**",
                            color=discord.Color.orange(),
                        )
                        await channel.send(embed=embed)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                log.exception("Stream playback error: %s", exc)
                await channel.send(f"❌ Stream error: `{exc}`")
            finally:
                await state.stop()
                queue.clear()
                await channel.send("✅ Stream ended.")

        state._play_task = asyncio.create_task(_play_loop())

    # ── prefix commands ──────────────────────────────────────────────────────

    @commands.command(name="vplay", aliases=["vs", "stream"],
                      help="Stream a video into a voice channel (Go Live). Usage: vplay <url or search>")
    async def vplay_prefix(self, ctx: commands.Context, *, query: str):
        """Start a video stream. Accepts YouTube URLs, search terms, or local files."""
        vc = self._author_vc(ctx)
        if not vc:
            return await ctx.send("❌ Join a voice channel first!")
        await self._start_stream(ctx, ctx.guild, ctx.channel, vc, query)

    @commands.command(name="vstop", aliases=["vdisconnect"],
                      help="Stop the current video stream and disconnect.")
    async def vstop_prefix(self, ctx: commands.Context):
        state = get_stream_state(ctx.guild.id)
        if not state.is_active():
            return await ctx.send("❌ No stream is active.")
        get_video_queue(ctx.guild.id).clear()
        await state.stop()
        await ctx.send("⏹️ Stream stopped.")

    @commands.command(name="vskip", help="Skip the current video and play the next one in queue.")
    async def vskip_prefix(self, ctx: commands.Context):
        state = get_stream_state(ctx.guild.id)
        if not state.is_active():
            return await ctx.send("❌ No stream is active.")
        if state.player:
            await state.player.stop()
        await ctx.send("⏭️ Skipped!")

    @commands.command(name="vpause", help="Pause the current video stream.")
    async def vpause_prefix(self, ctx: commands.Context):
        state = get_stream_state(ctx.guild.id)
        if not state.is_active() or not state.player:
            return await ctx.send("❌ No stream is active.")
        if state.paused:
            return await ctx.send("⚠️ Already paused.")
        try:
            await state.player.pause()
            state.paused = True
            await ctx.send("⏸️ Stream paused.")
        except Exception as exc:
            await ctx.send(f"❌ Could not pause: `{exc}`")

    @commands.command(name="vresume", help="Resume a paused video stream.")
    async def vresume_prefix(self, ctx: commands.Context):
        state = get_stream_state(ctx.guild.id)
        if not state.is_active() or not state.player:
            return await ctx.send("❌ No stream is active.")
        if not state.paused:
            return await ctx.send("⚠️ Stream is not paused.")
        try:
            await state.player.resume()
            state.paused = False
            await ctx.send("▶️ Stream resumed.")
        except Exception as exc:
            await ctx.send(f"❌ Could not resume: `{exc}`")

    @commands.command(name="vqueue", aliases=["vq"], help="Show the current video queue.")
    async def vqueue_prefix(self, ctx: commands.Context):
        queue = get_video_queue(ctx.guild.id)
        embed = discord.Embed(title="📹 Video Queue", color=discord.Color.red())
        if queue.current_title:
            embed.add_field(name="▶️ Now Streaming", value=f"`{queue.current_title}`", inline=False)
        if queue.titles:
            items = "\n".join(
                f"`{i+1}.` {t}" for i, t in enumerate(list(queue.titles)[:10])
            )
            if len(queue) > 10:
                items += f"\n...and {len(queue) - 10} more"
            embed.add_field(name="📋 Up Next", value=items, inline=False)
        else:
            embed.description = "Queue is empty!"
        await ctx.send(embed=embed)

    # ── slash commands ───────────────────────────────────────────────────────

    @app_commands.command(name="vplay", description="Stream a video into a Discord voice channel (Go Live).")
    @app_commands.describe(query="YouTube URL, search term, or direct video URL")
    async def vplay_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = self._author_vc(interaction)
        if not vc:
            return await interaction.followup.send("❌ Join a voice channel first!", ephemeral=True)
        await self._start_stream(interaction, interaction.guild, interaction.channel, vc, query)

    @app_commands.command(name="vstop", description="Stop the current video stream.")
    async def vstop_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        state = get_stream_state(interaction.guild.id)
        if not state.is_active():
            return await interaction.followup.send("❌ No stream is active.", ephemeral=True)
        get_video_queue(interaction.guild.id).clear()
        await state.stop()
        await interaction.followup.send("⏹️ Stream stopped.")

    @app_commands.command(name="vskip", description="Skip the current video.")
    async def vskip_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        state = get_stream_state(interaction.guild.id)
        if not state.is_active():
            return await interaction.followup.send("❌ No stream is active.", ephemeral=True)
        if state.player:
            await state.player.stop()
        await interaction.followup.send("⏭️ Skipped!")

    @app_commands.command(name="vpause", description="Pause the current video stream.")
    async def vpause_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        state = get_stream_state(interaction.guild.id)
        if not state.is_active() or not state.player:
            return await interaction.followup.send("❌ No stream is active.", ephemeral=True)
        if state.paused:
            return await interaction.followup.send("⚠️ Already paused.", ephemeral=True)
        try:
            await state.player.pause()
            state.paused = True
            await interaction.followup.send("⏸️ Stream paused.")
        except Exception as exc:
            await interaction.followup.send(f"❌ Could not pause: `{exc}`", ephemeral=True)

    @app_commands.command(name="vresume", description="Resume a paused video stream.")
    async def vresume_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        state = get_stream_state(interaction.guild.id)
        if not state.is_active() or not state.player:
            return await interaction.followup.send("❌ No stream is active.", ephemeral=True)
        if not state.paused:
            return await interaction.followup.send("⚠️ Stream is not paused.", ephemeral=True)
        try:
            await state.player.resume()
            state.paused = False
            await interaction.followup.send("▶️ Stream resumed.")
        except Exception as exc:
            await interaction.followup.send(f"❌ Could not resume: `{exc}`", ephemeral=True)

    @app_commands.command(name="vqueue", description="Show the video queue.")
    async def vqueue_slash(self, interaction: discord.Interaction):
        queue = get_video_queue(interaction.guild.id)
        embed = discord.Embed(title="📹 Video Queue", color=discord.Color.red())
        if queue.current_title:
            embed.add_field(name="▶️ Now Streaming", value=f"`{queue.current_title}`", inline=False)
        if queue.titles:
            items = "\n".join(
                f"`{i+1}.` {t}" for i, t in enumerate(list(queue.titles)[:10])
            )
            embed.add_field(name="📋 Up Next", value=items, inline=False)
        else:
            embed.description = "Queue is empty!"
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Video(bot))
