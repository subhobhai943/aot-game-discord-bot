"""Beautiful paginated help menu with category buttons and a dropdown."""
import discord
from discord.ext import commands
from discord import app_commands

# ─── Category definitions ──────────────────────────────────────────────────────
CATEGORIES = [
    {
        "id": "battle",
        "label": "⚔️ Battle",
        "emoji": "⚔️",
        "color": 0xC0392B,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "Turn-based PvE battles against Titans & PvP duels against other soldiers.",
        "fields": [
            ("Aot fight <titan>",        "Start a PvE turn-based battle vs a Titan"),
            ("Aot flee",                  "Flee from your current PvE battle"),
            ("Aot slash / odmdash",       "Attack moves during PvE battle"),
            ("Aot battle @user",          "Challenge another player to a PvP duel"),
            ("/simulate <char> <titan>",  "Cinematic battle simulation (slash command)"),
        ],
    },
    {
        "id": "titans",
        "label": "👹 Titans",
        "emoji": "👹",
        "color": 0x8E44AD,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "Catch, collect, and command Titans — build your army!",
        "fields": [
            ("Aot catch",                "Catch the currently spawned Titan"),
            ("Aot collection [@user]",   "View your (or someone else's) titan collection"),
            ("Aot setactive <titan>",    "Set your active titan for battles"),
            ("Aot scout <titan>",        "View detailed stats on any titan"),
            ("Aot release <titan>",      "Release a titan from your collection"),
            ("Aot spawn",               "[Admin] Force a titan spawn in this channel"),
            ("Aot setspawn #channel",    "[Admin] Set the titan spawn channel"),
        ],
    },
    {
        "id": "reactions",
        "label": "🎭 Reactions",
        "emoji": "🎭",
        "color": 0xE74C3C,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "AoT-themed GIF reactions — social and combat. Use `Aot <cmd> @user`.",
        "fields": [
            ("Social",  "hug · pat · slap · bonk · wave · poke · kiss · cry · blush · bite · cuddle · dance · laugh · wink"),
            ("Combat",  "punch · transform · salute · scream · charge · slice · yeager"),
            ("Special", "kill · odm · thunder_spear · nape · titan_eat · rumble · levi_kick · founding · scout · omni · wall_break · colossal · war_hammer · armored · freedom"),
            ("Tip",     "`Aot reactions` — see all GIF commands in one place"),
        ],
    },
    {
        "id": "games",
        "label": "🎮 Games",
        "emoji": "🎮",
        "color": 0xF39C12,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "AoT mini-games, trivia, and ODM training challenges.",
        "fields": [
            ("/trivia",           "AoT trivia challenge"),
            ("/spawn_titan",      "Simulate a Titan spawning"),
            ("/odm_training",     "Test your ODM gear skill"),
            ("/daily_challenge",  "Daily AoT challenge for XP"),
            ("/aot_fact",         "Random Attack on Titan fact"),
        ],
    },
    {
        "id": "profile",
        "label": "🧙 Profile",
        "emoji": "🧙",
        "color": 0x1ABC9C,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "Your scout identity, stats, and character.",
        "fields": [
            ("/profile [@user]",     "View your profile card + Discord PFP"),
            ("/choose_scout <name>", "Choose your scout character"),
            ("Aot leaderboard",      "Server rankings: wins · level · titans · coins"),
            ("Aot myrank [@user]",   "Check your rank across all categories"),
        ],
    },
    {
        "id": "abilities",
        "label": "⚡ Abilities",
        "emoji": "⚡",
        "color": 0xE67E22,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "Special abilities, titan transformations, and ODM gear upgrades.",
        "fields": [
            ("/ability",           "Use your scout's signature ability"),
            ("/transform <titan>", "Transform into a Titan"),
            ("/gear_upgrade",      "View & upgrade your ODM gear"),
            ("/scout_ranking",     "Top 10 Scouts leaderboard"),
        ],
    },
    {
        "id": "lore",
        "label": "📖 Lore",
        "emoji": "📖",
        "color": 0xD4AC0D,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "Explore AoT lore — characters, titans, and iconic quotes.",
        "fields": [
            ("/character <name>",         "Look up an AoT character"),
            ("/titan <name>",             "Titan stats and abilities"),
            ("/quote [tag] [character]",  "Random AoT quote (tags: motivational, dark, wisdom)"),
        ],
    },
    {
        "id": "odm",
        "label": "🪂 ODM Gear",
        "emoji": "🪂",
        "color": 0x2E86C1,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "Simulate ODM gear physics and nape strikes in real-time.",
        "fields": [
            ("/odm_grapple <dist> [speed] [gas]", "Simulate an ODM grapple (10–200m)"),
            ("/odm_strike [armor] [abilities]",   "Simulate a nape strike"),
        ],
    },
    {
        "id": "mikasa",
        "label": "🧣 Mikasa",
        "emoji": "🧣",
        "color": 0x922B21,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "Mikasa Ackerman-themed interactions and devotion commands.",
        "fields": [
            ("/mikasa <action> [@user]", "Mikasa actions: red_scarf, protect, devotion..."),
            ("/ackerman_bond <user>",    "Check your Ackerman-style bond"),
            ("/mikasa_stats",            "Mikasa's combat stats"),
            ("/red_scarf [@user]",       "Wrap the red scarf around someone"),
        ],
    },
    {
        "id": "moderation",
        "label": "🛡️ Moderation",
        "emoji": "🛡️",
        "color": 0x5D6D7E,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "Server moderation, AFK management, and AutoMod configuration.",
        "fields": [
            ("Aot afk [message]",        "Set yourself AFK with an AoT-themed message"),
            ("Aot afklist",              "List all currently AFK soldiers"),
            ("Aot automod",              "View AutoMod settings"),
            ("Aot setlogchannel",        "Set the mod log channel"),
            ("Aot activaterumbling",     "⚠️ Nuke the server (identity confirmation required)"),
        ],
    },
    {
        "id": "settings",
        "label": "⚙️ Settings",
        "emoji": "⚙️",
        "color": 0x7F8C8D,
        "thumbnail": "https://i.imgur.com/9V9p7hZ.png",
        "desc": "Server and bot configuration (some require Manage Server).",
        "fields": [
            ("/set_prefix <prefix>", "Set a custom command prefix for this server"),
            ("/prefix",              "Check the current server prefix"),
            ("Aot colors",           "Change your name color role"),
            ("Aot lookup <number>",  "Look up a phone number"),
        ],
    },
]

CAT_MAP = {c["id"]: c for c in CATEGORIES}


# ─── Embed builders ───────────────────────────────────────────────────────────
def _overview_embed() -> discord.Embed:
    embed = discord.Embed(
        title="<:wings:1234> AoT Game Bot",
        description=(
            "Welcome, **Soldier**. Your orders await.\n"
            "Powered by [aot-toolkit](https://github.com/subhobhai943/aot-toolkit) · "
            "Prefix: **Aot** · Slash: **/help**\n\n"
            "Use the **buttons below** to browse categories, "
            "or the **dropdown** for quick access."
        ),
        color=0xC0392B,
    )
    # Two-column fields for compact overview
    for cat in CATEGORIES:
        cmd_preview = " · ".join(f[0].split()[0] for f in cat["fields"][:3])
        if len(cat["fields"]) > 3:
            cmd_preview += f" +{len(cat['fields']) - 3} more"
        embed.add_field(
            name=f"{cat['emoji']} {cat['label'].split(' ', 1)[1]}",
            value=cmd_preview,
            inline=True,
        )
    embed.set_footer(text="\U0001fab9 AoT Game Bot  •  © 2026 Subhadip Sarkar  •  Use buttons below")
    embed.set_thumbnail(url="https://i.imgur.com/9V9p7hZ.png")
    return embed


def _category_embed(cat_id: str) -> discord.Embed:
    cat = CAT_MAP[cat_id]
    embed = discord.Embed(
        title=f"{cat['emoji']}  {cat['label'].split(' ', 1)[1]} Commands",
        description=cat["desc"],
        color=cat["color"],
    )
    for name, value in cat["fields"]:
        embed.add_field(name=f"`{name}`" if not name[0].isupper() or name.startswith("/") or name.startswith("Aot") else name,
                        value=value, inline=False)
    embed.set_footer(text="\U0001fab9 AoT Game Bot  •  Use buttons or dropdown to navigate")
    embed.set_thumbnail(url=cat["thumbnail"])
    return embed


# ─── UI Components ────────────────────────────────────────────────────────────
class HelpDropdown(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="🏠 Overview", value="overview", description="Bot overview and all categories")]
        for cat in CATEGORIES:
            options.append(discord.SelectOption(
                label=cat["label"],
                value=cat["id"],
                description=cat["desc"][:50],
            ))
        super().__init__(placeholder="📂 Jump to a category…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        embed = _overview_embed() if val == "overview" else _category_embed(val)
        # Update button styles to highlight current page
        view: HelpView = self.view  # type: ignore
        view.current = val
        view._refresh_buttons()
        await interaction.response.edit_message(embed=embed, view=view)


class HelpView(discord.ui.View):
    # We show max 5 buttons per row; first row = prev/home/next + 2 quick jumps
    QUICK = ["battle", "titans", "reactions", "games", "profile"]  # 5 pinned quick-access

    def __init__(self, current: str = "overview", author_id: int = 0):
        super().__init__(timeout=180)
        self.current = current
        self.author_id = author_id
        self.all_ids = ["overview"] + [c["id"] for c in CATEGORIES]
        self._build()

    # ── Build all items ──────────────────────────────────────────────────────
    def _build(self):
        self.clear_items()
        # Row 0: navigation  ◀  🏠  ▶
        idx = self.all_ids.index(self.current)
        prev_id = self.all_ids[idx - 1] if idx > 0 else self.all_ids[-1]
        next_id = self.all_ids[idx + 1] if idx < len(self.all_ids) - 1 else self.all_ids[0]

        self.add_item(NavButton("◀", prev_id, discord.ButtonStyle.secondary, row=0))
        self.add_item(NavButton("🏠 Overview", "overview",
                                discord.ButtonStyle.danger if self.current == "overview" else discord.ButtonStyle.secondary,
                                row=0))
        self.add_item(NavButton("▶", next_id, discord.ButtonStyle.secondary, row=0))

        # Row 1: 5 quick-access category buttons
        for cat_id in self.QUICK:
            cat = CAT_MAP[cat_id]
            style = discord.ButtonStyle.primary if self.current == cat_id else discord.ButtonStyle.secondary
            self.add_item(NavButton(cat["label"], cat_id, style, row=1))

        # Row 2: dropdown
        self.add_item(HelpDropdown())

    def _refresh_buttons(self):
        """Rebuild the whole view so button styles reflect the new current page."""
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Allow anyone to use the help menu
        return True


class NavButton(discord.ui.Button):
    def __init__(self, label: str, target: str, style: discord.ButtonStyle, row: int):
        super().__init__(label=label, style=style, row=row)
        self.target = target

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view  # type: ignore
        view.current = self.target
        view._refresh_buttons()
        embed = _overview_embed() if self.target == "overview" else _category_embed(self.target)
        await interaction.response.edit_message(embed=embed, view=view)


# ─── Cog ─────────────────────────────────────────────────────────────────────
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Suppress the default help command so 'Aot help' routes to ours
        bot.remove_command("help")

    # Prefix command: Aot help [category]
    @commands.command(name="help", aliases=["cmds", "commands"])
    async def help_prefix(self, ctx, *, category: str = None):
        """Show the AoT bot help menu."""
        if category:
            cat_id = category.lower().strip()
            # fuzzy match label or id
            matched = next(
                (c["id"] for c in CATEGORIES
                 if c["id"] == cat_id or c["label"].lower().find(cat_id) != -1),
                None
            )
            if matched:
                embed = _category_embed(matched)
                view = HelpView(current=matched, author_id=ctx.author.id)
            else:
                await ctx.send(f"❌ Unknown category `{category}`. Use `Aot help` to browse all.", delete_after=10)
                return
        else:
            embed = _overview_embed()
            view = HelpView(author_id=ctx.author.id)
        await ctx.send(embed=embed, view=view)

    # Slash command: /help
    @app_commands.command(name="help", description="Show all AoT bot commands")
    @app_commands.describe(category="Jump directly to a category")
    @app_commands.choices(category=[
        app_commands.Choice(name=cat["label"], value=cat["id"])
        for cat in CATEGORIES
    ])
    async def help_slash(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str] = None,
    ):
        if category:
            embed = _category_embed(category.value)
            view = HelpView(current=category.value, author_id=interaction.user.id)
        else:
            embed = _overview_embed()
            view = HelpView(author_id=interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Help(bot))
