import os
import re
import json
import asyncio
import datetime
import aiohttp
import discord
from discord.ext import commands, tasks
from discord import app_commands

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemma-4-31b-it:free"

# ── System prompt sent to Gemma for every moderation request ────────────────
SYSTEM_PROMPT = """You are Levi Ackerman, the captain of the Survey Corps and the server's strict AI moderator.
Your job is to:
1. Detect rule violations (hate speech, spam, NSFW content, toxicity, excessive caps, slurs, doxxing threats).
2. Respond to @mentions asking you to perform tasks like announcements, mutes, warnings, etc.
3. Watch member behaviour and recommend moderation actions.

When analyzing a message for rule violations, respond with JSON only:
{"violation": true/false, "severity": "low|medium|high", "reason": "<short reason>", "action": "warn|mute|kick|ban|none"}

When responding to a @mention task request, respond naturally in Levi's curt, no-nonsense tone.
Always stay in character — you are serving the Survey Corps (this Discord server).
"""

# ── Per-guild config: {guild_id: {"log_channel": int|None, "enabled": bool}} ─
guild_config: dict[int, dict] = {}

# ── User warning counts: {guild_id: {user_id: int}} ────────────────────────
warning_counts: dict[int, dict[int, int]] = {}


def get_openrouter_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "")


async def call_gemma(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """Call OpenRouter Gemma-4 model and return raw text response."""
    key = get_openrouter_key()
    if not key:
        return "{\"violation\": false, \"action\": \"none\"}"

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/subhobhai943/aot-game-discord-bot",
        "X-Title": "AoT Discord Bot",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 256,
        "temperature": 0.3,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    text = await resp.text()
                    return f"[OpenRouter error {resp.status}: {text[:200]}]"
    except asyncio.TimeoutError:
        return "[Timeout reaching OpenRouter]"
    except Exception as e:
        return f"[Error: {e}]"


class AutoMod(commands.Cog):
    """AI-powered auto-moderation using OpenRouter Gemma-4."""

    def __init__(self, bot):
        self.bot = bot

    # ── Enable/disable automod for a guild ──────────────────────────────────
    @commands.command(name="automod")
    @commands.has_permissions(administrator=True)
    async def automod_toggle(self, ctx, action: str = "status"):
        """Enable, disable, or check automod status. Usage: !automod enable|disable|status"""
        cfg = guild_config.setdefault(ctx.guild.id, {"log_channel": None, "enabled": False})
        action = action.lower()
        if action == "enable":
            cfg["enabled"] = True
            await ctx.send("⚔️ **Levi is now watching the server.** AutoMod enabled.")
        elif action == "disable":
            cfg["enabled"] = False
            await ctx.send("🚫 AutoMod disabled. *Levi is resting... for now.*")
        else:
            status = "🟢 Enabled" if cfg.get("enabled") else "🔴 Disabled"
            log_ch = f"<#{cfg['log_channel']}>" if cfg.get("log_channel") else "Not set"
            embed = discord.Embed(title="🛡️ AutoMod Status", color=discord.Color.dark_blue())
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Log Channel", value=log_ch, inline=True)
            embed.add_field(name="Model", value=f"`{MODEL}`", inline=False)
            await ctx.send(embed=embed)

    @commands.command(name="setlogchannel", aliases=["setlog"])
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel where automod logs are sent."""
        ch = channel or ctx.channel
        guild_config.setdefault(ctx.guild.id, {"log_channel": None, "enabled": False})["log_channel"] = ch.id
        await ctx.send(f"📋 AutoMod logs will be sent to {ch.mention}. *Levi approves.*")

    # ── Slash command: ask the bot to do something ───────────────────────────
    @app_commands.command(name="ask", description="Ask the AI bot to perform a task (announcements, moderation, etc.)")
    @app_commands.describe(task="What should Levi do? e.g. 'announce server maintenance at 8 PM'")
    async def ask_slash(self, interaction: discord.Interaction, task: str):
        await interaction.response.defer(thinking=True)
        context = (
            f"Server: {interaction.guild.name}\n"
            f"User: {interaction.user.display_name} (ID: {interaction.user.id})\n"
            f"Task requested: {task}"
        )
        response = await call_gemma(context, system=SYSTEM_PROMPT)
        embed = discord.Embed(
            title="⚔️ Levi's Response",
            description=response,
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=f"Powered by {MODEL} via OpenRouter")
        await interaction.followup.send(embed=embed)

    # ── Watch every message for violations ──────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cfg = guild_config.get(message.guild.id, {"enabled": False})

        # ── Handle @bot mention as a task request ────────────────────────────
        if self.bot.user in message.mentions:
            # Strip the bot mention from message
            clean_content = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
            if clean_content:
                await message.channel.typing()
                context = (
                    f"Server: {message.guild.name}\n"
                    f"Channel: #{message.channel.name}\n"
                    f"User: {message.author.display_name} (roles: {', '.join(r.name for r in message.author.roles[1:])})\n"
                    f"Task/Question: {clean_content}"
                )
                response = await call_gemma(context, system=SYSTEM_PROMPT)

                # Check if the response is JSON (moderation) or a natural reply
                try:
                    result = json.loads(response)
                    # It's a moderation JSON — format it nicely
                    if result.get("violation"):
                        embed = discord.Embed(
                            title="🚨 Violation Detected",
                            description=result.get("reason", "Rule violation."),
                            color=discord.Color.red()
                        )
                        embed.add_field(name="Severity", value=result.get("severity", "unknown").upper(), inline=True)
                        embed.add_field(name="Recommended Action", value=result.get("action", "warn").upper(), inline=True)
                    else:
                        embed = discord.Embed(description="✅ No violation detected.", color=discord.Color.green())
                    await message.reply(embed=embed, mention_author=False)
                except (json.JSONDecodeError, ValueError):
                    # Natural language response
                    embed = discord.Embed(
                        title="⚔️ Levi Ackerman",
                        description=response,
                        color=discord.Color.dark_red()
                    )
                    embed.set_footer(text=f"Model: {MODEL}")
                    await message.reply(embed=embed, mention_author=False)
            return

        # ── Auto-mod scan (only if enabled) ─────────────────────────────────
        if not cfg.get("enabled"):
            return

        # Skip very short messages
        if len(message.content.strip()) < 5:
            return

        prompt = (
            f"Analyze this Discord message for rule violations.\n"
            f"Server: {message.guild.name}\n"
            f"Author: {message.author.display_name}\n"
            f"Message: {message.content}\n"
            f"Respond with JSON only."
        )

        response = await call_gemma(prompt)

        try:
            # Extract JSON even if model adds extra text
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

        # ── Log the violation ────────────────────────────────────────────────
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
        log_embed.add_field(name="Message", value=message.content[:500] or "*empty*", inline=False)
        log_embed.set_footer(text=f"Model: {MODEL}")

        log_channel_id = cfg.get("log_channel")
        if log_channel_id:
            log_ch = message.guild.get_channel(log_channel_id)
            if log_ch:
                await log_ch.send(embed=log_embed)

        # ── Perform action ───────────────────────────────────────────────────
        aot_warn_messages = [
            f"⚔️ {message.author.mention} — **Levi's watching you.** This is a warning, soldier. Reason: *{reason}*",
            f"🗡️ {message.author.mention} — *Tch.* Disgusting. Clean up your behaviour. Warning issued: *{reason}*",
            f"🏰 {message.author.mention} — The walls have rules. Break them again and you face consequences. *{reason}*",
        ]
        import random

        if action == "warn" or severity == "low":
            # Add warning count
            warning_counts.setdefault(message.guild.id, {}).setdefault(message.author.id, 0)
            warning_counts[message.guild.id][message.author.id] += 1
            count = warning_counts[message.guild.id][message.author.id]
            warn_msg = random.choice(aot_warn_messages)
            await message.channel.send(f"{warn_msg} *(Warning #{count})*", delete_after=15)
            if count >= 3:
                await message.channel.send(
                    f"🚨 {message.author.mention} has reached **3 warnings**. *Levi recommends escalation.*",
                    delete_after=10
                )

        elif action == "mute" and message.guild.me.guild_permissions.moderate_members:
            try:
                mute_until = discord.utils.utcnow() + datetime.timedelta(minutes=10)
                await message.author.timeout(mute_until, reason=f"AutoMod: {reason}")
                await message.channel.send(
                    f"🔇 {message.author.mention} has been **timed out for 10 minutes** by Levi. Reason: *{reason}*",
                    delete_after=10
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        elif action == "kick" and message.guild.me.guild_permissions.kick_members:
            try:
                await message.author.kick(reason=f"AutoMod: {reason}")
                await message.channel.send(
                    f"👢 {message.author.mention} has been **kicked** by Levi. Reason: *{reason}*",
                    delete_after=10
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        elif action == "ban" and severity == "high" and message.guild.me.guild_permissions.ban_members:
            try:
                await message.author.ban(reason=f"AutoMod: {reason}", delete_message_days=1)
                await message.channel.send(
                    f"🔨 {message.author.mention} has been **banned** by Levi's order. Reason: *{reason}*",
                    delete_after=10
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        # Delete the violating message
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ── /warnings command ────────────────────────────────────────────────────
    @app_commands.command(name="warnings", description="Check warnings for a member 🗡️")
    @app_commands.describe(member="The member to check warnings for")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        count = warning_counts.get(interaction.guild.id, {}).get(target.id, 0)
        embed = discord.Embed(
            title=f"📋 Warnings for {target.display_name}",
            description=f"**{count}** warning(s) issued by Levi's AutoMod.",
            color=discord.Color.orange() if count > 0 else discord.Color.green()
        )
        embed.set_footer(text="⚔️ Stay in line, soldier.")
        await interaction.response.send_message(embed=embed)

    # ── /clearwarnings command ────────────────────────────────────────────────
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member (Admin only)")
    @app_commands.describe(member="The member to clear warnings for")
    @app_commands.default_permissions(administrator=True)
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        warning_counts.setdefault(interaction.guild.id, {})[member.id] = 0
        await interaction.response.send_message(
            f"✅ Warnings cleared for {member.mention}. *A clean slate, soldier.*",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
