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

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
MODEL = "gemini-2.5-flash"

_request_times: deque = deque()
RPM_LIMIT = 14
RPD_LIMIT = 490
_daily_count = {"date": "", "count": 0}

SYSTEM_PROMPT = """You are Levi Ackerman, captain of the Survey Corps and this Discord server's AI assistant.
You help with:
- Making announcements (write a detailed, well-formatted announcement when asked)
- Moderating users on demand (warn/mute/kick/ban)
- Answering server questions
- Any server management task

Respond in Levi's curt, no-nonsense tone.
If asked to make an announcement, write a DETAILED, well-formatted announcement (at least 4-6 lines). 
Include emojis, a title line starting with 📣, the body details, and a closing line. Make it look professional.
Do NOT write JSON for announcements — just write the announcement text directly.
If asked to warn/mute/kick/ban a user, respond ONLY with this JSON (no other text):
{"action": "warn|mute|kick|ban", "target": "<@userID or username>", "reason": "<reason>"}
Otherwise respond naturally."""

guild_config: dict[int, dict] = {}
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
    key = _get_gemini_key()
    if not key:
        return "⚠️ GEMINI_API_KEY is not set in .env!"
    allowed, reason = _can_call_api()
    if not allowed:
        return "⏳ Too many requests this minute. Wait a moment." if reason == "rpm" else "🚫 Daily API limit reached."
    _request_times.append(time.time())
    _daily_count["count"] += 1
    url = f"{GEMINI_API_URL}?key={key}"
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 768}
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


def _extract_channel(message: discord.Message, clean_text: str) -> discord.TextChannel | None:
    """
    Try to find a target channel from:
    1. #channel mentions in the message
    2. Channel name mentioned in the text e.g. 'in #announcements' or 'to general'
    """
    # From actual Discord #channel mention objects
    if message.channel_mentions:
        return message.channel_mentions[0]
    # From text pattern like "in #announcements" or "to #general"
    name_match = re.search(r"(?:in|to|at|into|on)\s+#?([-\w]+)", clean_text, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).lower()
        found = discord.utils.find(
            lambda c: isinstance(c, discord.TextChannel) and c.name.lower() == name,
            message.guild.channels
        )
        if found:
            return found
    return None


def _is_announcement_request(text: str) -> bool:
    keywords = ["announce", "announcement", "post", "notify", "broadcast", "tell everyone", "inform"]
    return any(kw in text.lower() for kw in keywords)


async def _send_announcement(
    guild: discord.Guild,
    target_ch: discord.TextChannel,
    draft: str,
    posted_by: discord.Member,
    ping_everyone: bool = True
):
    """Build a rich announcement embed and send it with @everyone to target_ch."""
    embed = discord.Embed(
        description=draft,
        color=discord.Color.from_rgb(200, 60, 40),  # AoT red
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_author(
        name=f"⚔️ {guild.name} — Official Announcement",
        icon_url=guild.icon.url if guild.icon else None
    )
    embed.set_footer(text=f"Posted by {posted_by.display_name} via Levi AI • {MODEL}")
    # @everyone mention BEFORE the embed so it shows as a ping
    ping = "@everyone" if ping_everyone else ""
    await target_ch.send(content=ping if ping else None, embed=embed)


class AutoMod(commands.Cog):
    """On-demand AI assistant using Google Gemini 2.5 Flash."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="automod")
    @commands.has_permissions(administrator=True)
    async def automod_status(self, ctx):
        today = datetime.date.today().isoformat()
        used = _daily_count["count"] if _daily_count["date"] == today else 0
        log_ch_id = guild_config.get(ctx.guild.id, {}).get("log_channel")
        log_ch = f"<#{log_ch_id}>" if log_ch_id else "Not set"
        embed = discord.Embed(title="🛡️ Levi AI — Status", color=discord.Color.dark_blue())
        embed.add_field(name="Mode", value="🎯 On-demand only (@mention / slash commands)", inline=False)
        embed.add_field(name="Model", value=f"`{MODEL}`", inline=True)
        embed.add_field(name="Log Channel", value=log_ch, inline=True)
        embed.add_field(name="📊 API Calls Today", value=f"{used} / {RPD_LIMIT}", inline=True)
        embed.add_field(
            name="💡 Usage Examples",
            value=(
                "`@ODM Striker announce maintenance at 9PM in #announcements`\n"
                "`@ODM Striker warn @user for spamming`\n"
                "`/announce` — Slash command with channel picker\n"
                "`/warn` `/mute` — Moderation actions"
            ),
            inline=False
        )
        embed.set_footer(text="Free tier: 15 RPM • 500 RPD")
        await ctx.send(embed=embed)

    @commands.command(name="setlogchannel", aliases=["setlog"])
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        ch = channel or ctx.channel
        guild_config.setdefault(ctx.guild.id, {"log_channel": None})["log_channel"] = ch.id
        await ctx.send(f"📋 Mod logs will be sent to {ch.mention}. *Levi approves.*")

    # ── @mention handler ──────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if self.bot.user not in message.mentions:
            return

        clean = (
            message.content
            .replace(f"<@{self.bot.user.id}>", "")
            .replace(f"<@!{self.bot.user.id}>", "")
            .strip()
        )

        if not clean:
            embed = discord.Embed(
                title="⚔️ Levi Ackerman — AI Assistant",
                description=(
                    "*Tch. You called?*\n\n"
                    "**Examples:**\n"
                    "• `@ODM Striker announce maintenance tonight at 9 PM in #announcements`\n"
                    "• `@ODM Striker warn @user for spamming`\n"
                    "• `@ODM Striker mute @user 10 minutes`\n"
                    "• Use `/announce` for the slash command version"
                ),
                color=discord.Color.dark_red()
            )
            embed.set_footer(text=f"Model: {MODEL}")
            await message.reply(embed=embed, mention_author=False)
            return

        # ── Detect if this is an announcement request BEFORE calling AI ─────
        is_announce = _is_announcement_request(clean)
        target_ch = _extract_channel(message, clean) if is_announce else None

        async with message.channel.typing():
            roles = ', '.join(r.name for r in message.author.roles[1:]) or 'none'
            # Tell Gemini explicitly if it's an announcement
            if is_announce:
                prompt = (
                    f"Server: {message.guild.name}\n"
                    f"User: {message.author.display_name} (roles: {roles})\n"
                    f"Task: Write a detailed announcement for — {clean}\n"
                    f"Write ONLY the announcement body text (no JSON, no explanation)."
                )
            else:
                prompt = (
                    f"Server: {message.guild.name}\n"
                    f"Channel: #{message.channel.name}\n"
                    f"User: {message.author.display_name} (roles: {roles})\n"
                    f"Request: {clean}"
                )
            response = await call_gemini(prompt)

        # ── Handle announcement: post to detected channel or current channel ──
        if is_announce:
            post_ch = target_ch or message.channel
            # Check permissions
            perms = post_ch.permissions_for(message.guild.me)
            if not perms.send_messages:
                await message.reply(
                    f"❌ I don't have permission to send messages in {post_ch.mention}.",
                    mention_author=False
                )
                return
            # Check if requester has permission to ping @everyone
            can_ping = message.author.guild_permissions.mention_everyone
            await _send_announcement(message.guild, post_ch, response, message.author, ping_everyone=can_ping)
            # Confirm in the command channel if different
            if post_ch != message.channel:
                await message.reply(
                    f"✅ Announcement posted in {post_ch.mention}!",
                    mention_author=False
                )
            return

        # ── Check if response is a mod action JSON ───────────────────────────
        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                action = result.get("action", "").lower()
                target_str = result.get("target", "")
                reason = result.get("reason", "No reason provided.")
                if action and message.author.guild_permissions.manage_messages:
                    await self._execute_mod_action(message, action, target_str, reason)
                    return
        except (json.JSONDecodeError, ValueError):
            pass

        # ── General AI response ────────────────────────────────────────────
        embed = discord.Embed(
            title="⚔️ Levi Ackerman",
            description=response,
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=f"Model: {MODEL} • On-demand only")
        await message.reply(embed=embed, mention_author=False)

    # ── /announce slash command ──────────────────────────────────────────────
    @app_commands.command(name="announce", description="Draft and post an announcement with @everyone 📣")
    @app_commands.describe(
        topic="What to announce e.g. 'server maintenance tonight at 9 PM IST'",
        channel="Channel to post in (default: current channel)",
        ping_everyone="Ping @everyone? (default: yes)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def announce(self, interaction: discord.Interaction, topic: str,
                       channel: discord.TextChannel = None, ping_everyone: bool = True):
        await interaction.response.defer(thinking=True, ephemeral=True)
        target_ch = channel or interaction.channel

        perms = target_ch.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            await interaction.followup.send(f"❌ I don't have permission to post in {target_ch.mention}.", ephemeral=True)
            return

        prompt = (
            f"Write a detailed, well-formatted Discord announcement for: {topic}\n"
            f"Server: {interaction.guild.name}\n"
            f"Make it at least 5-8 lines. Use emojis. Include a title line starting with 📣, details, and a closing line.\n"
            f"Write ONLY the announcement text, no JSON, no extra explanation."
        )
        draft = await call_gemini(prompt)

        can_ping = ping_everyone and interaction.user.guild_permissions.mention_everyone
        await _send_announcement(interaction.guild, target_ch, draft, interaction.user, ping_everyone=can_ping)
        await interaction.followup.send(
            f"✅ Announcement posted in {target_ch.mention}{'with @everyone!' if can_ping else '.'}",
            ephemeral=True
        )

    # ── /ask slash command ───────────────────────────────────────────────────
    @app_commands.command(name="ask", description="Ask Levi AI to do any server task ⚔️")
    @app_commands.describe(task="What should Levi do?")
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
        embed = discord.Embed(title="⚔️ Levi's Response", description=response, color=discord.Color.dark_red())
        embed.set_footer(text=f"Model: {MODEL}")
        await interaction.followup.send(embed=embed)

    # ── /warn slash command ───────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member 🗡️")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @app_commands.default_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Violating server rules"):
        import random
        warning_counts.setdefault(interaction.guild.id, {}).setdefault(member.id, 0)
        warning_counts[interaction.guild.id][member.id] += 1
        count = warning_counts[interaction.guild.id][member.id]
        aot_warns = [
            f"⚔️ {member.mention} — **Levi's watching you.** Warning: *{reason}*",
            f"🗡️ {member.mention} — *Tch.* Clean it up. Reason: *{reason}*",
            f"🏰 {member.mention} — The walls have rules. *{reason}*",
        ]
        await interaction.response.send_message(f"{random.choice(aot_warns)} *(Warning #{count})*")
        if count >= 3:
            await interaction.channel.send(f"🚨 {member.mention} has reached **3 warnings**. *Levi recommends escalation.*", delete_after=10)
        await self._log_action(interaction.guild, "WARN", member, interaction.user, reason)

    # ── /mute slash command ───────────────────────────────────────────────────
    @app_commands.command(name="mute", description="Timeout a member 🔇")
    @app_commands.describe(member="Member to mute", minutes="Duration in minutes", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "Violating server rules"):
        try:
            until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
            await member.timeout(until, reason=reason)
            await interaction.response.send_message(f"🔇 {member.mention} timed out **{minutes} min**. Reason: *{reason}*")
            await self._log_action(interaction.guild, f"MUTE ({minutes}m)", member, interaction.user, reason)
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

    # ── /warnings & /clearwarnings ──────────────────────────────────────────────
    @app_commands.command(name="warnings", description="Check warnings for a member")
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

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        warning_counts.setdefault(interaction.guild.id, {})[member.id] = 0
        await interaction.response.send_message(f"✅ Warnings cleared for {member.mention}.", ephemeral=True)

    # ── Internal helpers ─────────────────────────────────────────────────────────
    async def _execute_mod_action(self, message, action, target_str, reason):
        member = None
        id_match = re.search(r"\d{17,19}", target_str)
        if id_match:
            member = message.guild.get_member(int(id_match.group()))
        if not member:
            member = next((m for m in message.mentions if m != self.bot.user), None)
        if not member:
            await message.reply(f"⚔️ Action: **{action}** — Reason: *{reason}* \n*(Couldn't find the target member.)*", mention_author=False)
            return
        import random
        if action == "warn":
            warning_counts.setdefault(message.guild.id, {}).setdefault(member.id, 0)
            warning_counts[message.guild.id][member.id] += 1
            count = warning_counts[message.guild.id][member.id]
            await message.channel.send(f"⚔️ {member.mention} — Warning by Levi: *{reason}* *(#{count})*")
        elif action == "mute" and message.guild.me.guild_permissions.moderate_members:
            try:
                await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=10), reason=reason)
                await message.channel.send(f"🔇 {member.mention} timed out 10 min. Reason: *{reason}*")
            except (discord.Forbidden, discord.HTTPException):
                await message.channel.send("❌ No permission to timeout that member.")
        elif action == "kick" and message.guild.me.guild_permissions.kick_members:
            try:
                await member.kick(reason=reason)
                await message.channel.send(f"👢 {member.mention} kicked. Reason: *{reason}*")
            except (discord.Forbidden, discord.HTTPException):
                await message.channel.send("❌ No permission to kick that member.")
        elif action == "ban" and message.guild.me.guild_permissions.ban_members:
            try:
                await member.ban(reason=reason, delete_message_days=1)
                await message.channel.send(f"🔨 {member.mention} banned. Reason: *{reason}*")
            except (discord.Forbidden, discord.HTTPException):
                await message.channel.send("❌ No permission to ban that member.")
        await self._log_action(message.guild, action.upper(), member, message.author, reason)

    async def _log_action(self, guild, action, target, moderator, reason):
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
