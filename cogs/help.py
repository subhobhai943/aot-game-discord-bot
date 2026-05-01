"""Comprehensive /help command with category navigation via Select menu."""
import discord
from discord.ext import commands
from discord import app_commands


HELP_PAGES = {
    "⚔️ Battle": {
        "color": discord.Color.red(),
        "emoji": "⚔️",
        "desc": "Fight titans in turn-based combat with live battle images!",
        "commands": [
            ("/fight <titan>",          "Start a turn-based battle against a Titan"),
            ("/flee",                    "Flee from your active battle (counts as a loss)"),
            ("/simulate <char> <titan>", "Get a cinematic narrative battle simulation"),
        ],
    },
    "🧙 Player": {
        "color": discord.Color.teal(),
        "emoji": "🧙",
        "desc": "Manage your scout profile, stats, and character selection.",
        "commands": [
            ("/profile [@user]",      "View your own or another user's profile card + Discord PFP"),
            ("/choose_scout <name>",  "Choose your scout character for battles"),
        ],
    },
    "🧩 Mikasa": {
        "color": discord.Color.dark_red(),
        "emoji": "🧩",
        "desc": "Mikasa Ackerman-themed interactions and devotion commands.",
        "commands": [
            ("/mikasa <action> [@user]",  "Mikasa actions: red_scarf, protect, devotion, etc."),
            ("/ackerman_bond <user>",     "Check your Ackerman-style bond with another user"),
            ("/mikasa_stats",             "View Mikasa's combat statistics and profile"),
            ("/red_scarf [@user]",        "Wrap the iconic red scarf around someone"),
        ],
    },
    "🎮 Games": {
        "color": discord.Color.gold(),
        "emoji": "🎮",
        "desc": "Fun minigames: AoT trivia, titan spawn, ODM training, and more!",
        "commands": [
            ("/trivia",             "Play an AoT trivia challenge"),
            ("/spawn_titan",        "Simulate a Titan spawning in the wasteland"),
            ("/odm_training",       "Test your ODM gear skills in training"),
            ("/daily_challenge",    "Get today's AoT daily challenge for XP"),
            ("/aot_fact",           "Get a random Attack on Titan fact"),
        ],
    },
    "⚡ Abilities": {
        "color": discord.Color.orange(),
        "emoji": "⚡",
        "desc": "Special abilities, titan transformations, and gear upgrades.",
        "commands": [
            ("/ability",           "Use your scout's signature special ability"),
            ("/transform <titan>", "Transform into a Titan (simulation)"),
            ("/gear_upgrade",      "View and upgrade your ODM gear components"),
            ("/scout_ranking",     "View the top 10 Scouts on the leaderboard"),
        ],
    },
    "📖 Lore": {
        "color": discord.Color.gold(),
        "emoji": "📖",
        "desc": "Explore offline AoT lore — characters, titans, and quotes.",
        "commands": [
            ("/character <name>",          "Look up an AoT character (fuzzy search)"),
            ("/titan <name>",              "Look up a titan's stats and abilities"),
            ("/quote [tag] [character]",   "Get a random AoT quote (tags: motivational, dark, wisdom)"),
        ],
    },
    "🪂 ODM Gear": {
        "color": discord.Color.dark_teal(),
        "emoji": "🪂",
        "desc": "Simulate ODM gear physics and nape strikes.",
        "commands": [
            ("/odm_grapple <dist> [speed] [gas]", "Simulate an ODM grapple (10–200m, slow/normal/fast)"),
            ("/odm_strike [armor] [abilities]",   "Simulate a nape strike with armor/abilities"),
        ],
    },
    "⚙️ Settings": {
        "color": discord.Color.blurple(),
        "emoji": "⚙️",
        "desc": "Server configuration options (admin only for some).",
        "commands": [
            ("/set_prefix <prefix>", "Set a custom prefix for this server (requires Manage Server)"),
            ("/prefix",              "Check the current server prefix"),
            ("/help [category]",     "Show this help menu"),
        ],
    },
}


def _build_embed(category: str) -> discord.Embed:
    page = HELP_PAGES[category]
    embed = discord.Embed(
        title=f"{page['emoji']}  {category} Commands",
        description=page["desc"],
        color=page["color"],
    )
    for cmd, desc in page["commands"]:
        embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
    embed.set_footer(text="🪽 AoT Game Bot  •  Use the menu below to switch categories")
    return embed


def _build_overview_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🪽 AoT Game Bot — Help",
        description=(
            "Welcome to the **Attack on Titan Game Bot**!\n"
            "Powered by [aot-toolkit](https://github.com/subhobhai943/aot-toolkit)\n\n"
            "Use the **dropdown below** to browse command categories, "
            "or pick one directly with `/help <category>`."
        ),
        color=discord.Color.dark_red(),
    )
    for cat, data in HELP_PAGES.items():
        cmds = ", ".join(f"`{c[0].split()[0]}`" for c in data["commands"])
        embed.add_field(name=f"{data['emoji']} {cat}", value=cmds, inline=False)
    embed.set_footer(text="🪽 AoT Game Bot  •  All rights reserved © 2026 Subhadip Sarkar")
    return embed


class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Overview",   emoji="🏠", description="Bot overview and all categories"),
        ] + [
            discord.SelectOption(
                label=cat,
                emoji=data["emoji"],
                description=data["desc"][:50],
            )
            for cat, data in HELP_PAGES.items()
        ]
        super().__init__(
            placeholder="📚 Select a category...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "Overview":
            embed = _build_overview_embed()
        else:
            embed = _build_embed(selected)
        await interaction.response.edit_message(embed=embed)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(HelpSelect())


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all commands and how to use the bot")
    @app_commands.describe(category="Jump directly to a category")
    @app_commands.choices(category=[
        app_commands.Choice(name=cat, value=cat) for cat in HELP_PAGES
    ])
    async def help(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str] = None,
    ):
        if category:
            embed = _build_embed(category.value)
        else:
            embed = _build_overview_embed()
        await interaction.response.send_message(embed=embed, view=HelpView())


async def setup(bot):
    await bot.add_cog(Help(bot))
