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

# ── Model: gemini-2.5-flash (latest stable as of 2026) ──────────────────────
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
MODEL = "gemini-2.5-flash"

# ── Rate limit guard (15 RPM free tier) ────────────────────────────────
_request_times: deque = deque()
RPM_LIMIT = 14
RPD_LIMIT = 490   # gemini-2.5-flash free: 500 RPD
_daily_count = {"date": "", "count": 0}

# ── System prompt ────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Levi Ackerman, captain of the Survey Corps and this Discord server's AI assistant.
You help admins and members with tasks like:
- Making announcements
- Muting or warning a specific user (admin only)
- Answering questions about the server
- Moderating on-demand when asked
- Any other server management task

Respond in Levi's curt, no-nonsense tone. Be helpful but brief.
If asked to make an announcement, draft a clean announcement message.
If asked to warn/mute a user, respond with the action plan in JSON:
{"action": "warn|mute|kick|ban", "target": "@username or user ID", "reason": "<reason>"}
Otherwise, respond naturally."""

# ── Per-guild config ──────────────────────────────────────────────────────
guild_config: dict[int, dict] = {}

# ── Warning counts ───────────────────────────────────────────────────────
warning_counts: dict[int, dict[int, int]] = {}


def _get_gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")


def _can_call_api() -> tuple[bool, str]:
    now = time.time()
    while _request_times and _request_times[0] < now - 60:
        _request_times.popleft()
    if len(_request_times) >= RPM_LIMIT:
        return False, "rpm"
    today = datetime.date.today().isoformat()
    if _daily_count["date"] != today:
        _daily_count["date"] = today
        _daily_count["count"] = 0
    if _daily_count["count"] >= RPD_LIMIT:
        return False, "rpd"
    return True, "ok"


async def call_gemini(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """Call Gemini 2.5 Flash (on-demand only)."""
    key = _get_gemini_key()
    if not key:
        return "⚠️ GEMINI_API_KEY is not set in .env!"

    allowed, reason = _can_call_api()
    if not allowed:
        if reason == "rpm":
            return "⏳ Too many requests this minute. Wait a moment, soldier."
        return "🚫 Daily API limit reached. Levi rests until midnight."

    _request_times.append(time.time())
    _daily_count["count"] += 1

    url = f"{GEMINI_API_URL}?key={key}"
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 512,
        }
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                elif resp.status == 429:
                    return "⏳ Rate limit hit. Try again in a moment."
                else:
                    text = await resp.text()
                    return f"[Gemini error {resp.status}: {text[:200]}]"
    except asyncio.TimeoutError:
        return "⏳ Gemini timed out. Try again."
    except Exception as e:
        return f"[Error: {e}]"


class AutoMod(commands.Cog):
    """
    On-demand AI assistant using Google Gemini 2.5 Flash.
    ─────────────────────────────────────────────────
    Gemini ONLY activates when:
      1. Someone @mentions the bot with a task/question
      2. Admin uses /ask or /announce
      3. Admin uses /warn, /mute, /kick commands
    ─────────────────────────────────────────────────
    No passive scanning. Zero quota waste.
    """

    def __init__(self, bot):
        self.bot = bot

    # ── !automod status ──────────────────────────────────────────────────
    @commands.command(name="automod")
    @commands.has_permissions(administrator=True)
    async def automod_status(self, ctx):
        """Check automod/AI assistant status."""
        today = datetime.date.today().isoformat()
        used = _daily_count["count"] if _daily_count["date"] == today else 0
        log_ch_id = guild_config.get(ctx.guild.id, {}).get("log_channel")
        log_ch = f"<#{log_ch_id}>" if log_ch_id else "Not set"
        embed = discord.Embed(
            title="🛡️ Levi AI — Status",
            color=discord.Color.dark_blue()
        )
        embed.add_field(name="Mode", value="🎯 On-demand only (@mention / slash commands)", inline=False)
        embed.add_field(name="Model", value=f"`{MODEL}` (Google Gemini)", inline=True)
        embed.add_field(name="Log Channel", value=log_ch, inline=True)
        embed.add_field(name="📊 API Calls Today", value=f"{used} / {RPD_LIMIT}", inline=True)
        embed.add_field(
            name="💡 How to use",
            value=(
                "`@ODM Striker make an announcement about maintenance`\n"
                "`@ODM Striker warn @user spamming`\n"
                "`/ask` — Any task\n"
                "`/announce` — Draft & post announcement\n"
                "`/warn` `/mute` — Moderation actions"
            ),
            inline=False
        )
        embed.set_footer(text="Free tier: 15 RPM • 500 RPD • No passive scanning")
        await ctx.send(embed=embed)

    # ── !setlogchannel ──────────────────────────────────────────────────
    @commands.command(name="setlogchannel", aliases=["setlog"])
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel where mod action logs are sent."""
        ch = channel or ctx.channel
        guild_config.setdefault(ctx.guild.id, {"log_channel": None})["log_channel"] = ch.id
        await ctx.send(f"📋 Mod logs will be sent to {ch.mention}. *Levi approves.*")

    # ── @mention handler ──────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if self.bot.user not in message.mentions:
            return  # Only activate on @mention — no passive scanning

        clean = (
            message.content
            .replace(f"<@{self.bot.user.id}>", "")
            .replace(f"<@!{self.bot.user.id}>", "")
            .strip()
        )
        if not clean:
            # Just a ping with no text — show help
            embed = discord.Embed(
                title="⚔️ Levi Ackerman — AI Assistant",
                description=(
                    "*Tch. You called?*\n\n"
                    "Tell me what to do. Examples:\n"
                    "• `@ODM Striker announce server maintenance tonight at 9 PM`\n"
                    "• `@ODM Striker warn @user for spamming`\n"
                    "• `@ODM Striker mute @user 10 minutes, reason: toxic`\n"
                    "• `@ODM Striker draft rules for #general`\n"
                    "• `@ODM Striker who has the most warnings?`"
                ),
                color=discord.Color.dark_red()
            )
            embed.set_footer(text=f"Model: {MODEL}")
            await message.reply(embed=embed, mention_author=False)
            return

        async with message.channel.typing():
            # Build rich context for Gemini
            roles = ', '.join(r.name for r in message.author.roles[1:]) or 'none'
            context = (
                f"Server: {message.guild.name}\n"
                f"Channel: #{message.channel.name}\n"
                f"User: {message.author.display_name} (ID: {message.author.id}, roles: {roles})\n"
                f"Request: {clean}"
            )
            response = await call_gemini(context)

        # Check if response is a mod action JSON
        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                action = result.get("action", "").lower()
                target_str = result.get("target", "")
                reason = result.get("reason", "No reason provided.")

                # Only execute mod actions if requester has admin/mod perms
                if action and message.author.guild_permissions.manage_messages:
                    await self._execute_mod_action(message, action, target_str, reason)
                    return
        except (json.JSONDecodeError, ValueError):
            pass

        # Natural language response
        # If it looks like an announcement draft, post it nicely
        if any(kw in clean.lower() for kw in ["announce", "announcement", "post", "notify"]):
            embed = discord.Embed(
                title="📣 Levi's Announcement Draft",
                description=response,
                color=discord.Color.dark_gold()
            )
            embed.set_footer(text="⚔️ Drafted by Levi Ackerman • Review before posting")
        else:
            embed = discord.Embed(
                title="⚔️ Levi Ackerman",
                description=response,
                color=discord.Color.dark_red()
            )
            embed.set_footer(text=f"Model: {MODEL} • On-demand only")
        await message.reply(embed=embed, mention_author=False)

    # ── /ask slash command ─────────────────────────────────────────────────
    @app_commands.command(name="ask", description="Ask Levi AI to do any server task ⚔️")
    @app_commands.describe(task="What should Levi do? e.g. 'announce server event at 8 PM'")
    async def ask_slash(self, interaction: discord.Interaction, task: str):
        await interaction.response.defer(thinking=True)
        roles = ', '.join(r.name for r in interaction.user.roles[1:]) or 'none'
        context = (
            f"Server: {interaction.guild.name}\n"
            f"Channel: #{interaction.channel.name}\n"
            f"User: {interaction.user.display_name} (roles: {roles})\n"
            f"Task: {task}"
        )
        response = await call_gemini(context)
        embed = discord.Embed(
            title="⚔️ Levi's Response",
            description=response,
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=f"Model: {MODEL} (Google Gemini)")
        await interaction.followup.send(embed=embed)

    # ── /announce slash command ──────────────────────────────────────────────
    @app_commands.command(name="announce", description="Let Levi draft and post an announcement 📣")
    @app_commands.describe(
        topic="What to announce e.g. 'server maintenance tonight at 9 PM'",
        channel="Channel to post in (default: current channel)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def announce(self, interaction: discord.Interaction, topic: str, channel: discord.TextChannel = None):
        await interaction.response.defer(thinking=True, ephemeral=True)
        target_ch = channel or interaction.channel

        prompt = (
            f"Draft a Discord server announcement for: {topic}\n"
            f"Server: {interaction.guild.name}\n"
            f"Keep it concise, AoT/Survey Corps themed if appropriate. No JSON."
        )
        draft = await call_gemini(prompt)

        embed = discord.Embed(
            title="📣 Announcement",
            description=draft,
            color=discord.Color.dark_gold(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text=f"⚔️ {interaction.guild.name} • Posted by Levi AI")
        await target_ch.send(embed=embed)
        await interaction.followup.send(f"✅ Announcement posted in {target_ch.mention}!", ephemeral=True)

    # ── /warn slash command ──────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member 🗡️")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @app_commands.default_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Violating server rules"):
        warning_counts.setdefault(interaction.guild.id, {}).setdefault(member.id, 0)
        warning_counts[interaction.guild.id][member.id] += 1
        count = warning_counts[interaction.guild.id][member.id]

        import random
        aot_warns = [
            f"⚔️ {member.mention} — **Levi's watching you.** Warning issued: *{reason}*",
            f"🗡️ {member.mention} — *Tch.* Clean up your behaviour. Reason: *{reason}*",
            f"🏰 {member.mention} — The walls have rules. Break them again and face consequences. *{reason}*",
        ]
        await interaction.response.send_message(
            f"{random.choice(aot_warns)} *(Warning #{count})*"
        )
        if count >= 3:
            await interaction.channel.send(
                f"🚨 {member.mention} has reached **3 warnings**. *Levi recommends escalation.*",
                delete_after=10
            )
        await self._log_action(interaction.guild, "WARN", member, interaction.user, reason)

    # ── /mute slash command ──────────────────────────────────────────────────
    @app_commands.command(name="mute", description="Timeout a member 🔇")
    @app_commands.describe(member="Member to mute", minutes="Duration in minutes (default 10)", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "Violating server rules"):
        try:
            until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
            await member.timeout(until, reason=reason)
            await interaction.response.send_message(
                f"🔇 {member.mention} timed out for **{minutes} min** by Levi. Reason: *{reason}*"
            )
            await self._log_action(interaction.guild, f"MUTE ({minutes}m)", member, interaction.user, reason)
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

    # ── /warnings ─────────────────────────────────────────────────────────────
    @app_commands.command(name="warnings", description="Check warnings for a member")
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
    @app_commands.default_permissions(administrator=True)
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        warning_counts.setdefault(interaction.guild.id, {})[member.id] = 0
        await interaction.response.send_message(
            f"✅ Warnings cleared for {member.mention}. *A clean slate, soldier.*", ephemeral=True
        )

    # ── Internal helpers ────────────────────────────────────────────────────────
    async def _execute_mod_action(self, message, action, target_str, reason):
        """Execute a moderation action parsed from AI response."""
        # Try to resolve mention or ID to member
        member = None
        id_match = re.search(r"\d{17,19}", target_str)
        if id_match:
            member = message.guild.get_member(int(id_match.group()))
        if not member and message.mentions:
            member = next((m for m in message.mentions if m != self.bot.user), None)

        if not member:
            await message.reply(f"⚔️ *{reason}* — *(Couldn't find the target member to act on.)*", mention_author=False)
            return

        if action == "warn":
            warning_counts.setdefault(message.guild.id, {}).setdefault(member.id, 0)
            warning_counts[message.guild.id][member.id] += 1
            count = warning_counts[message.guild.id][member.id]
            await message.channel.send(f"⚔️ {member.mention} — Warning issued by Levi: *{reason}* *(#{count})*")

        elif action == "mute" and message.guild.me.guild_permissions.moderate_members:
            until = discord.utils.utcnow() + datetime.timedelta(minutes=10)
            try:
                await member.timeout(until, reason=reason)
                await message.channel.send(f"🔇 {member.mention} timed out 10 min. Reason: *{reason}*")
            except (discord.Forbidden, discord.HTTPException):
                await message.channel.send("❌ I don't have permission to timeout that member.")

        elif action == "kick" and message.guild.me.guild_permissions.kick_members:
            try:
                await member.kick(reason=reason)
                await message.channel.send(f"👢 {member.mention} kicked. Reason: *{reason}*")
            except (discord.Forbidden, discord.HTTPException):
                await message.channel.send("❌ I don't have permission to kick that member.")

        elif action == "ban" and message.guild.me.guild_permissions.ban_members:
            try:
                await member.ban(reason=reason, delete_message_days=1)
                await message.channel.send(f"🔨 {member.mention} banned by Levi's order. Reason: *{reason}*")
            except (discord.Forbidden, discord.HTTPException):
                await message.channel.send("❌ I don't have permission to ban that member.")

        await self._log_action(message.guild, action.upper(), member, message.author, reason)

    async def _log_action(self, guild, action, target, moderator, reason):
        """Send a log embed to the configured log channel."""
        log_ch_id = guild_config.get(guild.id, {}).get("log_channel")
        if not log_ch_id:
            return
        log_ch = guild.get_channel(log_ch_id)
        if not log_ch:
            return
        embed = discord.Embed(
            title=f"📋 Mod Action — {action}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Target", value=f"{target.mention} (`{target.id}`)", inline=True)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Levi AI • {MODEL}")
        await log_ch.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
