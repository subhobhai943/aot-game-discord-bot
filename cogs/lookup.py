import os
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands

NUMBER_VERIFY_API_KEY = os.getenv("NUMBER_VERIFY_API_KEY")
# New APILayer v2 endpoint — key goes in the "apikey" HEADER, not as a query param
NUMBER_VERIFY_URL = "https://api.apilayer.com/number_verification/validate"


class Lookup(commands.Cog):
    """📞 Phone Number Lookup using APILayer Number Verification API."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Slash command ──────────────────────────────────────────────────────
    @app_commands.command(
        name="lookup",
        description="Look up a phone number's validity, carrier, location & more."
    )
    @app_commands.describe(phone="Phone number with country code (e.g. +917001234567)")
    async def lookup(self, interaction: discord.Interaction, phone: str):
        await interaction.response.defer()
        embed = await self._fetch_number_info(phone)
        await interaction.followup.send(embed=embed)

    # ── Prefix command (!lookup) ───────────────────────────────────────────
    @commands.command(name="lookup", help="Look up a phone number. Usage: !lookup +917001234567")
    async def lookup_prefix(self, ctx: commands.Context, *, phone: str):
        async with ctx.typing():
            embed = await self._fetch_number_info(phone)
        await ctx.send(embed=embed)

    # ── Core API call ──────────────────────────────────────────────────────
    async def _fetch_number_info(self, phone: str) -> discord.Embed:
        if not NUMBER_VERIFY_API_KEY:
            return discord.Embed(
                title="⚠️ API Key Missing",
                description="`NUMBER_VERIFY_API_KEY` is not set in environment variables.\n"
                            "Add it to your `.env` file and restart the bot.",
                color=discord.Color.red()
            )

        # v2 API: key goes in the header, phone number as query param
        headers = {"apikey": NUMBER_VERIFY_API_KEY}
        params = {"number": phone}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    NUMBER_VERIFY_URL,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 401:
                        return self._error_embed("invalid_access_key — Invalid API key. Check your `NUMBER_VERIFY_API_KEY`.")
                    if resp.status != 200:
                        return self._error_embed(f"API returned HTTP {resp.status}")
                    data = await resp.json()
        except aiohttp.ClientError as e:
            return self._error_embed(f"Network error: {e}")
        except Exception as e:
            return self._error_embed(f"Unexpected error: {e}")

        valid = data.get("valid", False)
        color = discord.Color.green() if valid else discord.Color.orange()

        embed = discord.Embed(title="📞 Number Lookup Result", color=color)
        embed.add_field(name="📱 Number",       value=data.get("number", phone),               inline=True)
        embed.add_field(name="✅ Valid",         value="Yes" if valid else "No",                inline=True)
        embed.add_field(name="🌍 Country",       value=data.get("country_name", "N/A"),         inline=True)
        embed.add_field(name="🏳️ Country Code",  value=data.get("country_code", "N/A"),         inline=True)
        embed.add_field(name="📍 Location",      value=data.get("location", "N/A"),             inline=True)
        embed.add_field(name="📶 Carrier",       value=data.get("carrier", "N/A"),              inline=True)
        embed.add_field(name="📡 Line Type",     value=data.get("line_type", "N/A"),            inline=True)
        embed.add_field(name="🔢 Intl Format",   value=data.get("international_format", "N/A"), inline=True)
        embed.add_field(name="🏠 Local Format",  value=data.get("local_format", "N/A"),         inline=True)
        embed.set_footer(text="Powered by APILayer Number Verification API v2")
        return embed

    @staticmethod
    def _error_embed(message: str) -> discord.Embed:
        return discord.Embed(
            title="❌ Lookup Failed",
            description=message,
            color=discord.Color.red()
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Lookup(bot))
