"""Beautiful paginated help menu with category buttons and a dropdown."""
import discord
from discord.ext import commands
from discord import app_commands

# ─── Category definitions ─────────────────────────────────────────────────────────────────────────────
CATEGORIES = [
    {
        "id": "battle",
        "label": "⚔️ Battle",
        "emoji": "⚔️",
        "color": 0xC0392B,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Turn-based PvE battles against Titans & PvP duels against other soldiers.",
        "fields": [
            ("Aot fight <titan>",        "Start a PvE turn-based battle vs a Titan"),
            ("Aot flee",                  "Flee from your current PvE battle"),
            ("Aot slash / odmdash",       "Attack moves during PvE battle"),
            ("Aot battle @user",          "Challenge another player to a PvP duel"),
            ("/simulate <char> <titan>",  "Cinematic battle simulation (slash command)"),
            ("/raid  |  >raid",           "Start a multiplayer co-op PvE Titan Raid"),
        ],
    },
    {
        "id": "titans",
        "label": "👹 Titans",
        "emoji": "👹",
        "color": 0x8E44AD,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
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
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
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
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "AoT mini-games, trivia, and ODM training challenges.",
        "fields": [
            ("/trivia",           "AoT trivia challenge"),
            ("/spawn-titan",      "Simulate a Titan spawning"),
            ("/odm-training",     "Test your ODM gear skill"),
            ("/daily-challenge",  "Daily AoT challenge for XP"),
            ("/aot-fact",         "Random Attack on Titan fact"),
            ("/titan3d | >titan3d", "Play a 3D first-person Titan Hunt maze game!"),
        ],
    },
    {
        "id": "among_titans",
        "label": "🗡️ Titan Shifters",
        "emoji": "🗡️",
        "color": 0x34495E,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "AoT-themed social deduction game! Find the Titan Shifters before they eat the Survey Corps.",
        "fields": [
            ("Aot titan-game create",    "Create a new game lobby"),
            ("Aot titan-game join",      "Join the active lobby"),
            ("Aot titan-game start",     "Start the game (Host only)"),
            ("Aot eliminate @user",      "Eat a crewmate (Titan Shifters only)"),
            ("Aot meeting",              "Call an emergency meeting to vote"),
            ("Aot vote @user",           "Vote to execute a suspected shifter"),
            ("Aot titan-game status",    "Check the game status"),
        ],
    },
    {
        "id": "profile",
        "label": "🧙 Profile",
        "emoji": "🧙",
        "color": 0x1ABC9C,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Your scout identity, stats, and character.",
        "fields": [
            ("/profile [@user]",     "View your profile card + Discord PFP"),
            ("/choose-scout <name>", "Choose your scout character"),
            ("/shop  |  >shop",      "Regiment supplies and Titan recruitment shop"),
            ("Aot leaderboard",      "Server rankings: wins · level · titans · coins"),
            ("Aot myrank [@user]",   "Check your rank across all categories"),
        ],
    },
    {
        "id": "squad",
        "label": "🛡️ Squads",
        "emoji": "🛡️",
        "color": 0x2E86C1,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Survey Corps Vanguard Squads — team up, donate coins, and unlock global regiment boosts.",
        "fields": [
            ("/squad-create <name> |  >squad create", "Create a new squad (Costs 500 coins)"),
            ("/squad-join <name>   |  >squad join",   "Join an existing vanguard squad"),
            ("/squad-info [name]   |  >squad info",   "View squad stats and active buffs"),
            ("/squad-donate <amt>  |  >squad donate", "Donate coins to upgrade level & unlock buffs"),
            ("/squad-leave         |  >squad leave",  "Leave squad (disbands if creator)"),
        ],
    },
    {
        "id": "regiment",
        "label": "🎖️ Regiments",
        "emoji": "🎖️",
        "color": 0x34495E,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Military Regiments — Join a branch (Survey Corps, Garrison, Military Police) to gain combat stat buffs and roles.",
        "fields": [
            ("/regiment-join <choice>|  >regiment join", "Enlist in a regiment (Free first time, 500 coins transfer)"),
            ("/regiment-info [user]  |  >regiment info", "View military record, upgrades, and active buffs"),
            ("/regiment-list         |  >regiment list", "List branches, buffs, and soldier counts"),
            ("/regiment-setup-gate   |  >regiment setupgate", "[Admin] Dispatch the visual onboarding gates panel"),
            ("/regiment-link-role    |  >regiment linkrole", "[Admin] Link a regiment to a Discord role"),
            ("/regiment-set-channels |  >regiment setchannel", "[Admin] Configure welcome alerts and gate channels"),
        ],
    },
    {
        "id": "abilities",
        "label": "⚡ Abilities",
        "emoji": "⚡",
        "color": 0xE67E22,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Special abilities, titan transformations, and ODM gear upgrades.",
        "fields": [
            ("/ability",           "Use your scout's signature ability"),
            ("/transform <titan>", "Transform into a Titan"),
            ("/melt <titan>  |  >melt <titan>",   "Recycle a duplicate Titan into Shifter Serum"),
            ("/laboratory   |  >laboratory",      "Open the Shifter Serum upgrade laboratory"),
            ("/gear-upgrade",      "View & upgrade your ODM gear"),
            ("/scout-ranking",     "Top 10 Scouts leaderboard"),
        ],
    },
    {
        "id": "lore",
        "label": "📖 Lore",
        "emoji": "📖",
        "color": 0xD4AC0D,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
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
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Simulate ODM gear physics and nape strikes in real-time.",
        "fields": [
            ("/odm-grapple <dist> [speed] [gas]", "Simulate an ODM grapple (10–200m)"),
            ("/odm-strike [armor] [abilities]",   "Simulate a nape strike"),
        ],
    },
    {
        "id": "mikasa",
        "label": "🧣 Mikasa",
        "emoji": "🧣",
        "color": 0x922B21,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Mikasa Ackerman-themed interactions and devotion commands.",
        "fields": [
            ("/mikasa <action> [@user]", "Mikasa actions: red-scarf, protect, devotion..."),
            ("/ackerman-bond <user>",    "Check your Ackerman-style bond"),
            ("/mikasa-stats",            "Mikasa's combat stats"),
            ("/red-scarf [@user]",       "Wrap the red scarf around someone"),
        ],
    },
    {
        "id": "music",
        "label": "🎵 Music",
        "emoji": "🎵",
        "color": 0x1DB954,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Stream music into a voice channel from YouTube, Spotify names, or any direct URL.",
        "fields": [
            ("/play <query>  |  >p <query>",     "Join VC and play a song (YouTube / Spotify name / URL)"),
            ("/mood-music <mood> | @bot play...", "AI finds & plays music matching your mood/request"),
            ("/loop          |  >loop",           "Toggle loop mode: off ➔ song ➔ queue"),
            ("/aot           |  >aot",            "Play the complete Attack on Titan playlist"),
            ("/deathnote     |  >deathnote",      "Play the complete Death Note playlist"),
            ("/naruto        |  >naruto",         "Play the complete Naruto playlist"),
            ("/demonslayer   |  >demonslayer",    "Play the complete Demon Slayer playlist"),
            ("/berserk       |  >berserk",        "Play the complete Berserk playlist"),
            ("/vinlandsaga   |  >vinlandsaga",    "Play the complete Vinland Saga playlist"),
            ("/tokyorevengers |  >tokyorevengers","Play the complete Tokyo Revengers playlist"),
            ("/jujutsukaisen |  >jujutsukaisen",  "Play the complete Jujutsu Kaisen playlist"),
            ("/skip          |  >skip",           "Skip the current song and play the next in queue"),
            ("/pause         |  >pause",          "Pause playback"),
            ("/resume        |  >resume",         "Resume a paused track"),
            ("/stop          |  >stop",           "Stop music, clear the queue, and disconnect"),
            ("/queue         |  >queue / >q",     "Show the current music queue"),
            ("Tip", "You must be in a voice channel to use music commands."),
        ],
    },

    {
        "id": "moderation",
        "label": "🛡️ Moderation",
        "emoji": "🛡️",
        "color": 0x5D6D7E,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Server moderation, AFK management, and AutoMod configuration.",
        "fields": [
            ("/purge [amount] | >purge [amount]", "Purge messages from this channel (moderator only)"),
            ("/warn <member> [reason]",  "Warn a server member (moderator only)"),
            ("/mute <member> [mins]",    "Timeout a member (moderator only)"),
            ("/warnings [member]",       "Check warning count for a member"),
            ("/clearwarnings <member>",  "Clear all warnings for a member (Admin only)"),
            ("Aot afk [message]",        "Set yourself AFK with an AoT-themed message"),
            ("Aot afklist",              "List all currently AFK soldiers"),
            ("Aot automod",              "View AutoMod settings"),
            ("Aot setlogchannel",        "Set the mod log channel"),
            ("Aot activaterumbling",     "⚠️ Nuke the server (identity confirmation required)"),
        ],
    },
    {
        "id": "settings",
        "label": "⚙️ Utility & Settings",
        "emoji": "⚙️",
        "color": 0x7F8C8D,
        "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png",
        "desc": "Server utility tools, interactive polls, and bot settings.",
        "fields": [
            ("/set-prefix <prefix>", "Set a custom command prefix for this server"),
            ("/prefix",              "Check the current server prefix"),
            ("/ping          |  >ping",           "Check the bot's response time and API latency"),
            ("/serverinfo    |  >serverinfo",     "Get detailed statistics about this server"),
            ("/userinfo      |  >userinfo [@user]","Get details about a server member"),
            ("/avatar        |  >avatar [@user]",  "Get a user's high-resolution avatar picture"),
            ("/poll          |  >poll <q> <opts>","Create an interactive multiple-choice poll"),
            ("/snipe [index] |  >snipe [index]",  "Snipe a recently deleted message (1-10)"),
            ("/snipelist     |  >snipelist",      "List the last 10 deleted messages in this channel"),
            ("/resources     |  >resources",       "Check the current server resource usage and load"),
            ("/provider <choice> |  >provider <choice>", "Switch the active AI provider (Gemini or NVIDIA NIM)"),
            ("/models [model]    |  >models [model]",    "Choose or view the active NVIDIA NIM model"),
            ("/aimode <choice>   |  >aimode <choice>",   "Switch AI assistant mood (Captain, Friendly, Funny, Anime)"),
            ("Aot colors",           "Change your name color role"),
            ("Aot lookup <number>",  "Look up a phone number"),
        ],
    },
]

CAT_MAP = {c["id"]: c for c in CATEGORIES}


# ─── Embed builders ─────────────────────────────────────────────────────────────────────────────
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
    embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png")
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


# ─── UI Components ─────────────────────────────────────────────────────────────────────────────
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
        view: HelpView = self.view  # type: ignore
        view.current = val
        view._refresh_buttons()
        await interaction.response.edit_message(embed=embed, view=view)


class HelpView(discord.ui.View):
    # Row 1: 5 pinned quick-access category buttons
    QUICK = ["battle", "titans", "reactions", "music", "games"]

    def __init__(self, current: str = "overview", author_id: int = 0):
        super().__init__(timeout=180)
        self.current = current
        self.author_id = author_id
        self.all_ids = ["overview"] + [c["id"] for c in CATEGORIES]
        self._build()

    # ── Build all items ─────────────────────────────────────────────────────────────────────────────
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

        # Row 1: 5 quick-access category buttons (battle / titans / reactions / music / games)
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


# ─── Cog ─────────────────────────────────────────────────────────────────────────────────────────
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
