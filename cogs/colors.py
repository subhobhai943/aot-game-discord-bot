"""Color role picker — /color_list and /set_color commands.
After successfully assigning a color role the bot reply auto-deletes in 5 s.
"""
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# ── Color catalogue ────────────────────────────────────────────────────────────
# Format: (display_name, hex_value)
# Matches the list shown in the COLOR TITAN bot embed (numbers 1-48).
COLORS: list[tuple[str, int]] = [
    ("Silver",          0xC0C0C0),
    ("SlateGray",       0x708090),
    ("DimGray",         0x696969),
    ("Gainsboro",       0xDCDCDC),
    ("RoyaleBlue",      0x4169E1),
    ("CornflowerBlue",  0x6495ED),
    ("DeepskyBlue",     0x00BFFF),
    ("SkyBlue",         0x87CEEB),
    ("PowderBlue",      0xB0E0E6),
    ("LightScoGreen",   0x90EE90),
    ("AquaMarine",      0x7FFFD4),
    ("Aqua",            0x00FFFF),
    ("LightGreen",      0x90EE90),
    ("GreenYellow",     0xADFF2F),
    ("YellowGreen",     0x9ACD32),
    ("Yellow",          0xFFFF00),
    ("Gold",            0xFFD700),
    ("GoldenRodYellow", 0xFAFAD2),
    ("PapayaWhip",      0xFFEFD5),
    ("LemonChiffon",    0xFFFACD),
    ("PeachPuff",       0xFFDAB9),
    ("LightSalmon",     0xFFA07A),
    ("Coral",           0xFF7F50),
    ("DarkOrange",      0xFF8C00),
    ("OrangeRed",       0xFF4500),
    ("Crimson",         0xDC143C),
    ("Tomato",          0xFF6347),
    ("Red",             0xFF0000),
    ("LightRed",        0xFF6666),
    ("Salmon",          0xFA8072),
    ("IndianRed",       0xCD5C5C),
    ("Pink",            0xFFC0CB),
    ("HotPink",         0xFF69B4),
    ("Chestnut",        0x954535),
    ("LightPink",       0xFFB6C1),
    ("RosyBrown",       0xBC8F8F),
    ("Chocolate",       0xD2691E),
    ("LightTaupe",      0xB38B6D),
    ("Tan",             0xD2B48C),
    ("AntiqueBlue",     0x4682B4),
    ("AntiqueWhite",    0xFAEBD7),
    ("Peru",            0xCD853F),
    ("Bisque",          0xFFE4C4),
    ("MintCream",       0xF5FFFA),
]


def _make_color_list_embed() -> discord.Embed:
    """Build the numbered color list embed (3 columns, 16 rows each)."""
    embed = discord.Embed(
        title="🎨 Color List",
        description="Use `/set_color number:<number>` to pick your color!",
        color=discord.Color.blurple(),
    )
    col1, col2, col3 = [], [], []
    for i, (name, _) in enumerate(COLORS, start=1):
        entry = f"{i}. {name}"
        if i <= 16:
            col1.append(entry)
        elif i <= 32:
            col2.append(entry)
        else:
            col3.append(entry)

    embed.add_field(name="\u200b", value="\n".join(col1), inline=True)
    embed.add_field(name="\u200b", value="\n".join(col2), inline=True)
    embed.add_field(name="\u200b", value="\n".join(col3), inline=True)
    embed.set_footer(text="⚔️ Wings of Freedom Color Picker")
    return embed


async def _get_or_create_color_role(
    guild: discord.Guild,
    name: str,
    color_value: int,
) -> discord.Role:
    """Return existing role with that name or create it."""
    existing = discord.utils.get(guild.roles, name=name)
    if existing:
        return existing
    return await guild.create_role(
        name=name,
        color=discord.Color(color_value),
        reason="Auto-created by color picker",
    )


async def _remove_old_color_roles(member: discord.Member) -> None:
    """Strip all color roles the bot manages from this member."""
    color_names = {name for name, _ in COLORS}
    roles_to_remove = [r for r in member.roles if r.name in color_names]
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove, reason="Color role swap")


class Colors(commands.Cog):
    """Color role management commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /color_list ────────────────────────────────────────────────────────────
    @app_commands.command(
        name="color_list",
        description="Show all available color numbers you can pick",
    )
    async def color_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=_make_color_list_embed())

    # ── /set_color ─────────────────────────────────────────────────────────────
    @app_commands.command(
        name="set_color",
        description="Pick your color role by number (use /color_list to see all numbers)",
    )
    @app_commands.describe(number="The color number from /color_list (1-48)")
    async def set_color(
        self,
        interaction: discord.Interaction,
        number: int,
    ) -> None:
        # ── Validation ─────────────────────────────────────────────────────────
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        if not (1 <= number <= len(COLORS)):
            await interaction.response.send_message(
                f"❌ Invalid number. Please pick between **1** and **{len(COLORS)}**.\n"
                "Use `/color_list` to see all available colors.",
                ephemeral=True,
            )
            return

        color_name, color_hex = COLORS[number - 1]
        member = interaction.user  # type: discord.Member

        # ── Check bot permissions ───────────────────────────────────────────────
        bot_member = interaction.guild.me
        if not bot_member.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ I don't have **Manage Roles** permission. Please give it to me first.",
                ephemeral=True,
            )
            return

        # ── Defer so we can do async work before replying ──────────────────────
        await interaction.response.defer(thinking=True)

        try:
            # Remove old color roles first
            await _remove_old_color_roles(member)
            # Get or create the target role
            role = await _get_or_create_color_role(
                interaction.guild, color_name, color_hex
            )
            # Assign
            await member.add_roles(role, reason="Color role picker")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I couldn't assign the role — make sure my role is **above** color roles in the role list.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Something went wrong: {e}", ephemeral=True
            )
            return

        # ── Success reply — auto-deletes after 5 seconds ───────────────────────
        color_swatch = discord.Color(color_hex)
        embed = discord.Embed(
            description=f"{interaction.user.mention} your color is now **{color_name}**.",
            color=color_swatch,
        )
        embed.set_footer(text="🎨 This message will vanish in 5 seconds…")

        msg = await interaction.followup.send(embed=embed, wait=True)

        # Wait then delete
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except (discord.NotFound, discord.HTTPException):
            pass  # Already gone — no problem


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Colors(bot))
