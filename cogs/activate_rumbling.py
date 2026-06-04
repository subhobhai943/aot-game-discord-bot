import asyncio
import discord
from discord.ext import commands


class ActivateRumbling(commands.Cog):
    """💀 The most destructive command — Activate The Rumbling."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="activate_rumbling")
    @commands.has_permissions(administrator=True)
    async def activate_rumbling(self, ctx):
        """Nuke the entire server after a series of identity confirmations."""

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        # ── Step 1: Consciousness check (ask twice) ──────────────────────────
        for i in range(2):
            await ctx.send(
                "⚠️ **ARE YOU CONSCIOUS?**\n"
                "Reply with `yes` to confirm or `no` to abort."
            )
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                return await ctx.send("⏰ Timed out. Rumbling aborted.")

            if msg.content.strip().lower() == "no":
                return await ctx.send("❌ Rumbling aborted.")
            elif msg.content.strip().lower() != "yes":
                return await ctx.send("❌ Invalid response. Rumbling aborted.")

        # ── Step 2: Subconscious state check ─────────────────────────────────
        await ctx.send(
            "🧠 **ARE YOU IN A SUBCONSCIOUS STATE?**\n"
            "Reply with `yes` to confirm or `no` to abort."
        )
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send("⏰ Timed out. Rumbling aborted.")

        if msg.content.strip().lower() != "yes":
            return await ctx.send("❌ Rumbling aborted.")

        # ── Step 3: Identity verification (3 rounds) ─────────────────────────
        identities = ["subho", "eren", "obito"]
        prompts = [
            "🔐 **WHO ARE YOU?** (1st time)",
            "🔐 **WHO ARE YOU?** (2nd time)",
            "🔐 **WHO ARE YOU?** (3rd time)",
        ]

        for expected, prompt in zip(identities, prompts):
            await ctx.send(prompt)
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                return await ctx.send("⏰ Timed out. Rumbling aborted.")

            if msg.content.strip().lower() != expected:
                return await ctx.send(
                    f"❌ Wrong identity. Expected `{expected}`. Rumbling aborted."
                )

        # ── Step 4: Final countdown 10 → 0 ───────────────────────────────────
        await ctx.send(
            "☠️ **ALL IDENTITIES CONFIRMED.**\n"
            "**THE RUMBLING BEGINS IN...**"
        )
        for i in range(10, -1, -1):
            await ctx.send(f"**{i}...**")
            await asyncio.sleep(1)

        await ctx.send(
            "💀 **THE RUMBLING HAS BEGUN — TITANS MARCH!** 💀\n"
            "🌍 Nuking the server..."
        )

        # ── Step 5: Nuke — delete all channels and roles ──────────────────────
        guild = ctx.guild

        # Delete all channels
        for channel in list(guild.channels):
            try:
                await channel.delete(reason="The Rumbling — server nuke")
            except Exception:
                pass

        # Delete all roles (skip @everyone and roles above bot's top role)
        bot_top_role = guild.me.top_role
        for role in list(guild.roles):
            if role.is_default():
                continue
            if role >= bot_top_role:
                continue
            try:
                await role.delete(reason="The Rumbling — server nuke")
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(ActivateRumbling(bot))
