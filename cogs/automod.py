import os
import re
import json
import asyncio
import datetime
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from collections import deque
import time

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MODEL = "gemini-2.0-flash"

# ── Free tier limits: 15 RPM, 1500 RPD ──────────────────────────────────────
# We keep a rolling window of timestamps to enforce the rate limit locally
_request_times: deque = deque()  # timestamps of recent API calls
RPM_LIMIT = 14        # stay 1 below the 15 RPM hard cap
RPD_LIMIT = 1490      # stay 10 below the 1500 RPD hard cap
_daily_count = {"date": "", "count": 0}  # track daily usage

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Levi Ackerman, the captain of the Survey Corps and this Discord server's strict AI moderator.
Your job is to:
1. Detect rule violations: hate speech, spam, NSFW content, toxicity, slurs, doxxing threats, excessive caps.
2. Respond to @mentions asking you to perform tasks like announcements, warnings, mutes, etc.
3. Watch member behaviour and recommend moderation actions.

When analyzing a message for rule violations, respond with VALID JSON only, no extra text:
{"violation": true/false, "severity": "low|medium|high", "reason": "<short reason>", "action": "warn|mute|kick|ban|none"}

When responding to a @mention task request, respond naturally in Levi's curt, no-nonsense tone.
Always stay in character. You serve the Survey Corps (this Discord server)."""

# ── Per-guild config ─────────────────────────────────────────────────────────
guild_config: dict[int, dict] = {}

# ── Warning counts ───────────────────────────────────────────────────────────
warning_counts: dict[int, dict[int, int]] = {}


def _get_gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")


def _can_call_api() -> tuple[bool, str]:
    """Check rate limits before making a call. Returns (allowed, reason)."""
    now = time.time()

    # Clean up timestamps older than 60 seconds
    while _request_times and _request_times[0] < now - 60:
        _request_times.popleft()

    # RPM check
    if len(_request_times) >= RPM_LIMIT:
        return False, "rate_limit_rpm"

    # Daily count check
    today = datetime.date.today().isoformat()
    if _daily_count["date"] != today:
        _daily_count["date"] = today
        _daily_count["count"] = 0
    if _daily_count["count"] >= RPD_LIMIT:
        return False, "rate_limit_rpd"

    return True, "ok"


async def call_gemini(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """Call Gemini 2.0 Flash and return raw text response."""
    key = _get_gemini_key()
    if not key:
        return '{"violation": false, "action": "none"}'

    allowed, reason = _can_call_api()
    if not allowed:
        if reason == "rate_limit_rpm":
            return "[Rate limit: too many requests this minute. Try again shortly.]"
        return "[Daily API quota reached. Resets at midnight.]"

    # Record this call
    _request_times.append(time.time())
    _daily_count["count"] += 1

    url = f"{GEMINI_API_URL}?key={key}"
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 300,
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                elif resp.status == 429:
                    return "[Gemini rate limit hit. Slowing down...]"
                else:
                    text = await resp.text()
                    return f"[Gemini error {resp.status}: {text[:200]}]"
    except asyncio.TimeoutError:
        return "[Timeout reaching Gemini API]"
    except Exception as e:
        return f"[Error: {e}]"


class AutoMod(commands.Cog):
    """AI-powered auto-moderation using Google Gemini 2.0 Flash."""

    def __init__(self, bot):
        self.bot = bot

    # ── !automod enable|disable|status ──────────────────────────────────────
    @commands.command(name="automod")
    @commands.has_permissions(administrator=True)
    async def automod_toggle(self, ctx, action: str = "status"):
        """Enable, disable, or check automod. Usage: !automod enable|disable|status"""
        cfg = guild_config.setdefault(ctx.guild.id, {"log_channel": None, "enabled": False})
        action = action.lower()
        if action == "enable":
            cfg["enabled"] = True
            await ctx.send("⚔️ **Levi is now watching the server.** AutoMod enabled. *(Gemini 2.0 Flash)*")
        elif action == "disable":
            cfg["enabled"] = False
            await ctx.send("🚫 AutoMod disabled. *Levi is resting... for now.*")
        else:
            status = "🟢 Enabled" if cfg.get("enabled") else "🔴 Disabled"
            log_ch = f"<#{cfg['log_channel']}>" if cfg.get("log_channel") else "Not set"
            today = datetime.date.today().isoformat()
            used = _daily_count["count"] if _daily_count["date"] == today else 0
            embed = discord.Embed(title="🛡️ AutoMod Status", color=discord.Color.dark_blue())
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Log Channel", value=log_ch, inline=True)
            embed.add_field(name="Model", value=f"`{MODEL}` (Google Gemini)", inline=False)
            embed.add_field(name="📊 API Calls Today", value=f"{used} / {RPD_LIMIT}", inline=True)
            embed.set_footer(text="Free tier: 15 RPM • 1,500 RPD")
            await ctx.send(embed=embed)

    # ── !setlogchannel ────────────────────────────────────────────────────────
    @commands.command(name="setlogchannel", aliases=["setlog"])
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel where automod logs are sent."""
        ch = channel or ctx.channel
        guild_config.setdefault(ctx.guild.id, {"log_channel": None, "enabled": False})["log_channel"] = ch.id
        await ctx.send(f"📋 AutoMod logs will be sent to {ch.mention}. *Levi approves.*")

    # ── /ask slash command ────────────────────────────────────────────────────
    @app_commands.command(name="ask", description="Ask Levi (AI) to do something ⚔️")
    @app_commands.describe(task="What should Levi do? e.g. 'announce server event at 8 PM'")
    async def ask_slash(self, interaction: discord.Interaction, task: str):
        await interaction.response.defer(thinking=True)
        context = (
            f"Server: {interaction.guild.name}\n"
            f"User: {interaction.user.display_name} (ID: {interaction.user.id})\n"
            f"Task requested: {task}"
        )
        response = await call_gemini(context)
        embed = discord.Embed(
            title="⚔️ Levi's Response",
            description=response,
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=f"Powered by {MODEL} (Google Gemini)")
        await interaction.followup.send(embed=embed)

    # ── on_message: @mention handler + auto-mod scan ─────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cfg = guild_config.get(message.guild.id, {"enabled": False})

        # ── @bot mention → treat as a task/question ──────────────────────────
        if self.bot.user in message.mentions:
            clean = (
                message.content
                .replace(f"<@{self.bot.user.id}>", "")
                .replace(f"<@!{self.bot.user.id}>", "")
                .strip()
            )
            if not clean:
                return

            async with message.channel.typing():
                context = (
                    f"Server: {message.guild.name}\n"
                    f"Channel: #{message.channel.name}\n"
                    f"User: {message.author.display_name} "
                    f"(roles: {', '.join(r.name for r in message.author.roles[1:])})\n"
                    f"Task/Question: {clean}"
                )
                response = await call_gemini(context)

            # Try to parse as JSON (moderation result) or send as natural reply
            try:
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                result = json.loads(json_match.group()) if json_match else None
                if result and result.get("violation"):
                    embed = discord.Embed(
                        title="🚨 Violation Detected",
                        description=result.get("reason", "Rule violation."),
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Severity", value=result.get("severity", "??").upper(), inline=True)
                    embed.add_field(name="Recommended Action", value=result.get("action", "warn").upper(), inline=True)
                else:
                    raise ValueError("Not a violation JSON")
                await message.reply(embed=embed, mention_author=False)
            except (json.JSONDecodeError, ValueError, AttributeError):
                embed = discord.Embed(
                    title="⚔️ Levi Ackerman",
                    description=response,
                    color=discord.Color.dark_red()
                )
                embed.set_footer(text=f"Model: {MODEL}")
                await message.reply(embed=embed, mention_author=False)
            return

        # ── Auto-mod scan (only when enabled) ────────────────────────────────
        if not cfg.get("enabled"):
            return

        # Skip very short or system messages
        content = message.content.strip()
        if len(content) < 8:
            return

        # Quick local pre-filter to save API calls on obviously safe messages
        # Only call Gemini if the message has potential red flags
        RED_FLAGS = re.compile(
            r"(kill|hate|die|stupid|idiot|slur|nsfw|sex|porn|spam|\b[A-Z]{6,}\b|@everyone|@here)",
            re.IGNORECASE
        )
        if not RED_FLAGS.search(content):
            return  # Message looks clean, skip API call to preserve quota

        prompt = (
            f"Analyze this Discord message for rule violations.\n"
            f"Server: {message.guild.name}\n"
            f"Author: {message.author.display_name}\n"
            f"Message: {content}\n"
            f"Respond with valid JSON only, no extra text."
        )

        response = await call_gemini(prompt)

        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if not json_match:
                return
            result = json.loads(json_match.group())
        except (json.JSONDecodeError, ValueError):
            return

        if not result.get("violation"):
            return

        severity = result.get("severity", "low")
        action = result.get("action", "warn")
        reason = result.get("reason", "Rule violation detected by AI moderator.")

        # ── Log to mod channel ────────────────────────────────────────────────
        log_embed = discord.Embed(
            title="🚨 AutoMod Alert — Rule Violation",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        log_embed.add_field(name="User", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        log_embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        log_embed.add_field(name="Severity", value=severity.upper(), inline=True)
        log_embed.add_field(name="Action", value=action.upper(), inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.add_field(name="Message", value=content[:500], inline=False)
        log_embed.set_footer(text=f"Model: {MODEL} (Google Gemini)")

        log_channel_id = cfg.get("log_channel")
        if log_channel_id:
            log_ch = message.guild.get_channel(log_channel_id)
            if log_ch:
                await log_ch.send(embed=log_embed)

        # ── Enforce action ────────────────────────────────────────────────────
        import random
        aot_warns = [
            f"⚔️ {message.author.mention} — **Levi's watching you.** Warning issued: *{reason}*",
            f"🗡️ {message.author.mention} — *Tch.* Disgusting behaviour. Clean it up: *{reason}*",
            f"🏰 {message.author.mention} — The walls have rules. Break them again and face consequences. *{reason}*",
        ]

        if action == "warn" or severity == "low":
            warning_counts.setdefault(message.guild.id, {}).setdefault(message.author.id, 0)
            warning_counts[message.guild.id][message.author.id] += 1
            count = warning_counts[message.guild.id][message.author.id]
            await message.channel.send(
                f"{random.choice(aot_warns)} *(Warning #{count})*",
                delete_after=15
            )
            if count >= 3:
                await message.channel.send(
                    f"🚨 {message.author.mention} has reached **3 warnings**. *Levi recommends escalation.*",
                    delete_after=10
                )

        elif action == "mute" and message.guild.me.guild_permissions.moderate_members:
            try:
                until = discord.utils.utcnow() + datetime.timedelta(minutes=10)
                await message.author.timeout(until, reason=f"AutoMod: {reason}")
                await message.channel.send(
                    f"🔇 {message.author.mention} timed out **10 min** by Levi. Reason: *{reason}*",
                    delete_after=10
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        elif action == "kick" and message.guild.me.guild_permissions.kick_members:
            try:
                await message.author.kick(reason=f"AutoMod: {reason}")
                await message.channel.send(
                    f"👢 {message.author.mention} was **kicked** by Levi. Reason: *{reason}*",
                    delete_after=10
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        elif action == "ban" and severity == "high" and message.guild.me.guild_permissions.ban_members:
            try:
                await message.author.ban(reason=f"AutoMod: {reason}", delete_message_days=1)
                await message.channel.send(
                    f"🔨 {message.author.mention} was **banned** by Levi's order. Reason: *{reason}*",
                    delete_after=10
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ── /warnings ─────────────────────────────────────────────────────────────
    @app_commands.command(name="warnings", description="Check warnings for a member 🗡️")
    @app_commands.describe(member="The member to check")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        count = warning_counts.get(interaction.guild.id, {}).get(target.id, 0)
        embed = discord.Embed(
            title=f"📋 Warnings — {target.display_name}",
            description=f"**{count}** warning(s) on record.",
            color=discord.Color.orange() if count > 0 else discord.Color.green()
        )
        embed.set_footer(text="⚔️ Stay in line, soldier.")
        await interaction.response.send_message(embed=embed)

    # ── /clearwarnings ────────────────────────────────────────────────────────
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member (Admin only)")
    @app_commands.describe(member="Member to clear warnings for")
    @app_commands.default_permissions(administrator=True)
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        warning_counts.setdefault(interaction.guild.id, {})[member.id] = 0
        await interaction.response.send_message(
            f"✅ Warnings cleared for {member.mention}. *A clean slate, soldier.*",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
