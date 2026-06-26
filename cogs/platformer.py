"""
2D Side-scrolling Platformer: Titan Run.
Players use ODM Gear to grapple across ruins and slash Titans in a turn-based side-scroller.
"""
from __future__ import annotations
import math
import random
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from utils.game_state import GameState

# Level maps definition
# . = Air/sky, # = Solid brick, ^ = Rubble/spikes, G = Grapple ring, C = Coin, T = Titan, F = Finish
LEVEL_MAPS = [
    # Level 1: Trost Outskirts (Easy)
    [
        "............................................................",
        "............................................................",
        "....G.................G.................G.................G.",
        "............................................................",
        "........C......T............C....T............C....T........",
        "......#####...###.........#####.###.........#####.###.......",
        "....#.......#.....#.....#..........#.....#..........#......F",
        "############################################################"
    ],
    # Level 2: Trost Ruins (Medium)
    [
        "............................................................",
        "......G.................G.................G.................",
        "..................G.................G.................G.....",
        "...........C.................C.................C............",
        ".....###..###..#.......###..###..#.......###..###..#........",
        "....#...........#.....#...........#.....#...........#......F",
        "###...^^^^^^^....#####...^^^^^^^....#####...^^^^^^^....#####",
        "############################################################"
    ],
    # Level 3: Giant Tree Forest (Hard)
    [
        "....G.................G.................G.................G.",
        "..................G.................G.................G.....",
        "........C...................C.................C.............",
        "......#####...T...........#####...T.........#####...T.......",
        ".............###.................###.................###....",
        "....#.......#...#.......#.......#...#.......#.......#...#..F",
        "#####.......#####.......#####.......#####.......#####......#",
        ".....^^^^^^^.....^^^^^^^.....^^^^^^^.....^^^^^^^.....^^^^^^^"
    ]
]

LEVEL_NAMES = [
    "Trost Outskirts",
    "Ruined Streets of Trost",
    "Forest of Giant Trees"
]

SCREEN_WIDTH = 20
SCREEN_HEIGHT = 8


class TitanRunView(discord.ui.View):
    def __init__(self, user: discord.User, level_idx: int, char_name: str, player_data):
        super().__init__(timeout=180)
        self.user = user
        self.level = level_idx + 1
        self.map_name = LEVEL_NAMES[level_idx]
        self.char_name = char_name
        self.player_data = player_data

        # Load map
        self.current_map = [list(row) for row in LEVEL_MAPS[level_idx]]

        # Setup stats depending on Scout choice
        if self.char_name == "Eren":
            self.health = 120
            self.max_health = 120
            self.gas = 100
            self.blades = 100
            self.hardening_active = True  # Eren's unique survival trait
        else:  # Levi
            self.health = 80
            self.max_health = 80
            self.gas = 120
            self.blades = 120
            self.hardening_active = False

        # Spawn coordinates
        self.px = 1
        self.py = 6

        # Combat/Game metrics
        self.coins_collected = 0
        self.kills = 0
        self.score = 0
        self.status = "PLAYING"
        self.log_messages = ["🧗 Use ODM Gear & slash Titans to reach the gate!"]

    def is_walkable(self, x: int, y: int) -> bool:
        if x < 0 or x >= len(self.current_map[0]) or y < 0 or y >= len(self.current_map):
            return False
        return self.current_map[y][x] != '#'

    def respawn_player(self):
        # Backtrack from px to find a safe block standing on solid ground
        for x in range(self.px, 0, -1):
            for y in range(len(self.current_map) - 2, 0, -1):
                if self.current_map[y][x] == '.' and self.current_map[y+1][x] == '#':
                    self.px = x
                    self.py = y
                    return
        self.px = 1
        self.py = 6

    def render_viewport(self) -> str:
        # Horizontally scroll screen with player
        cam_x = max(0, min(len(self.current_map[0]) - SCREEN_WIDTH, self.px - SCREEN_WIDTH // 2))

        color_buffer = [[None for _ in range(SCREEN_WIDTH)] for _ in range(SCREEN_HEIGHT)]

        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                mx = cam_x + x
                my = y
                char_on_map = self.current_map[my][mx]

                # Render details
                if self.px == mx and self.py == my:
                    # Player scout representation
                    if self.char_name == "Eren":
                        bg, fg, char = 42, 37, "ER"  # Green
                    else:
                        bg, fg, char = 46, 37, "LE"  # Cyan
                elif char_on_map == '#':
                    # Ground block
                    bg, fg, char = 43, 30, "██"
                elif char_on_map == '^':
                    # Rubble spikes
                    bg, fg, char = 41, 37, "▲▲"
                elif char_on_map == 'G':
                    # Grapple anchor
                    bg, fg, char = 44, 33, "()"
                elif char_on_map == 'C':
                    # Coin
                    bg, fg, char = 44, 33, "©©"
                elif char_on_map == 'T':
                    # Titan enemy
                    bg, fg, char = 41, 33, "OO"
                elif char_on_map == 'F':
                    # Finish gate
                    bg, fg, char = 42, 37, "||"
                else:
                    # Sky gradient
                    if y < 2:
                        bg, fg, char = 44, 37, "░░"
                    elif y < 4:
                        bg, fg, char = 44, 34, "██"
                    elif y < 6:
                        bg, fg, char = 46, 36, "██"
                    else:
                        bg, fg, char = 40, 30, "██"

                color_buffer[y][x] = {"bg": bg, "fg": fg, "char": char}

        # Compile optimized ANSI string
        lines = []
        for y in range(SCREEN_HEIGHT):
            row_str = []
            cur_bg = None
            cur_fg = None
            for x in range(SCREEN_WIDTH):
                cell = color_buffer[y][x]
                bg = cell["bg"]
                fg = cell["fg"]
                char = cell["char"]
                if bg != cur_bg or fg != cur_fg:
                    row_str.append(f"\u001b[0;{fg};{bg}m")
                    cur_bg = bg
                    cur_fg = fg
                row_str.append(char)
            row_str.append("\u001b[0m")
            lines.append("".join(row_str))

        return "\n".join(lines)

    def make_progress_bar(self) -> str:
        # Draw current coordinate map progress bar
        total_cols = len(self.current_map[0])
        pct = int((self.px / (total_cols - 1)) * 10)
        pct = max(0, min(10, pct))
        return f"`[{'█' * pct}{'░' * (10 - pct)}]`"

    def make_stat_bar(self, val: int, max_val: int = 100) -> str:
        filled = round((val / max_val) * 10)
        filled = max(0, min(10, filled))
        return f"`[{'█' * filled}{'░' * (10 - filled)}]`"

    def build_embed(self) -> discord.Embed:
        render = self.render_viewport()
        is_lost = self.status.startswith("LOST")
        is_won = self.status == "WON"
        color = discord.Color.red() if is_lost else discord.Color.green() if is_won else discord.Color.blurple()

        embed = discord.Embed(
            title=f"🏃 Titan Run: Escape Trost — Level {self.level}",
            description=f"🌎 **Map Region:** {self.map_name}\n\n```ansi\n{render}\n```",
            color=color
        )

        # Scout HUD Info
        hud = (
            f"👤 **Scout:** {self.char_name}\n"
            f"❤️ **HP:** {self.health}/{self.max_health}\n{self.make_stat_bar(self.health, self.max_health)}\n"
            f"💨 **Gas:** {self.gas}%\n{self.make_stat_bar(self.gas)}\n"
            f"⚔️ **Blades:** {self.blades}%\n{self.make_stat_bar(self.blades)}"
        )
        embed.add_field(name="📊 Scout Stats", value=hud, inline=True)

        # Level Metrics
        metrics = (
            f"🪙 **Coins:** {self.coins_collected}\n"
            f"🎯 **Score:** {self.score}\n"
            f"💀 **Titan Kills:** {self.kills}\n"
            f"🏁 **Progress:** {self.make_progress_bar()}"
        )
        embed.add_field(name="🏁 Mission Details", value=metrics, inline=True)

        # Log
        recent_logs = "\n".join(self.log_messages[-3:])
        embed.add_field(name="📜 Mission Log", value=recent_logs, inline=False)

        embed.set_footer(text=f"Player: {self.user.display_name} • Controls below")
        return embed

    def apply_gravity(self):
        on_ground = False
        if self.py + 1 < len(self.current_map):
            if self.current_map[self.py + 1][self.px] == '#':
                on_ground = True

        if not on_ground:
            # Fall down 1 cell
            if self.py + 1 < len(self.current_map) and self.is_walkable(self.px, self.py + 1):
                self.py += 1
                self.log_messages.append("💨 Falling...")

                # Fall down 2nd cell if still in mid-air
                on_ground2 = False
                if self.py + 1 < len(self.current_map):
                    if self.current_map[self.py + 1][self.px] == '#':
                        on_ground2 = True
                if not on_ground2:
                    if self.py + 1 < len(self.current_map) and self.is_walkable(self.px, self.py + 1):
                        self.py += 1

    def check_collisions(self):
        # Landed on elements check
        if self.py < len(self.current_map):
            cell = self.current_map[self.py][self.px]
            if cell == '^':
                self.health -= 20
                self.log_messages.append("💥 Landed on debris spikes! Took 20 damage.")
            elif cell == 'C':
                self.coins_collected += 10
                self.current_map[self.py][self.px] = '.'
                self.score += 10
                self.log_messages.append("🪙 Collected a Survey Corps coin!")
            elif cell == 'T':
                # Landing directly from above stomps/kills the Titan
                self.current_map[self.py][self.px] = '.'
                self.kills += 1
                self.score += 25
                self.log_messages.append("💥 Landed on a Titan and slashed its nape!")
            elif cell == 'F':
                self.status = "WON"
                self.log_messages.append("🏆 Escaped the Titan threat and reached the gate!")
                return

        # Check side collisions with Titans
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                tx = self.px + dx
                ty = self.py + dy
                if 0 <= tx < len(self.current_map[0]) and 0 <= ty < len(self.current_map):
                    if self.current_map[ty][tx] == 'T':
                        if dx != 0 or dy != 0:
                            self.health -= 25
                            self.log_messages.append("👹 Collided with a Titan! Took 25 damage.")
                            # Knock player back slightly
                            if self.is_walkable(self.px - dx, self.py):
                                self.px -= dx
                            break

        # Check pit fall
        if self.py >= len(self.current_map) - 1:
            if self.current_map[self.py][self.px] != '#':
                if self.char_name == "Eren" and self.hardening_active:
                    self.health = 30
                    self.hardening_active = False
                    self.log_messages.append("⭐ Eren's Attack Titan hardening saved him from the abyss! HP set to 30.")
                else:
                    self.health -= 25
                    self.log_messages.append("💨 Fell into the abyss! Rescued by ODM gear but took 25 damage.")
                self.respawn_player()

        # Check resources
        if self.gas <= 0 and self.blades <= 0 and self.health > 0:
            self.status = "LOST_RESOURCES"
            self.log_messages.append("💀 Out of Gas and Blades! Retreat was impossible.")

        if self.health <= 0:
            self.health = 0
            self.status = "LOST_DEAD"
            self.log_messages.append("💀 You were eaten by the Titans.")

    async def update_message(self, interaction: discord.Interaction):
        if self.status == "WON":
            self.disable_all()
            xp_gain = 100 * self.level
            coins_gain = 50 * self.level + self.coins_collected
            levelled = self.player_data.add_xp(xp_gain)
            self.player_data.coins += coins_gain
            self.player_data.wins += 1
            self.player_data.kills += self.kills
            await GameState.save_player(self.player_data)

            embed = self.build_embed()
            embed.title = "🏆 VICTORY! Level Cleared!"
            embed.add_field(name="💰 Mission Rewards", value=f"+{xp_gain} XP\n+{coins_gain} Coins", inline=False)
            if levelled:
                embed.add_field(name="⭐ Level Up!", value=f"You reached Level **{self.player_data.level}**!", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
            return

        elif self.status.startswith("LOST"):
            self.disable_all()
            self.player_data.losses += 1
            await GameState.save_player(self.player_data)

            embed = self.build_embed()
            embed.title = "💀 DEFEAT! Mission Failed."
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
            return

        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    def disable_all(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This is not your mission!", ephemeral=True)
            return False
        return True

    # ── Button Handlers ────────────────────────────────────────────────────────────

    @discord.ui.button(label="◀️ Left", style=discord.ButtonStyle.secondary, row=0)
    async def go_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_x = self.px - 1
        if self.is_walkable(new_x, self.py):
            self.px = new_x
            self.log_messages.append("👣 Moved left.")
        else:
            self.log_messages.append("💥 Blocked by a wall!")

        self.apply_gravity()
        self.check_collisions()
        await self.update_message(interaction)

    @discord.ui.button(label="▶️ Right", style=discord.ButtonStyle.primary, row=0)
    async def go_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_x = self.px + 1
        if self.is_walkable(new_x, self.py):
            self.px = new_x
            self.log_messages.append("👣 Moved right.")
        else:
            self.log_messages.append("💥 Blocked by a wall!")

        self.apply_gravity()
        self.check_collisions()
        await self.update_message(interaction)

    @discord.ui.button(label="🦘 Jump", style=discord.ButtonStyle.success, row=0)
    async def do_jump(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.gas <= 0:
            self.log_messages.append("💨 No Gas to jump!")
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            return

        target_x = self.px + 1
        target_y = self.py - 2

        if self.is_walkable(target_x, target_y) and self.is_walkable(self.px, self.py - 1):
            self.px = target_x
            self.py = target_y
            self.gas -= 2
            self.log_messages.append("🦘 Jumped up and forward!")
        elif self.is_walkable(self.px, self.py - 2):
            self.py -= 2
            self.gas -= 2
            self.log_messages.append("🦘 Jumped straight up!")
        else:
            self.log_messages.append("💥 Blocked by a ceiling!")

        self.apply_gravity()
        self.check_collisions()
        await self.update_message(interaction)

    @discord.ui.button(label="⚓ Grapple", style=discord.ButtonStyle.primary, row=1)
    async def do_grapple(self, interaction: discord.Interaction, button: discord.ui.Button):
        gas_cost = 3 if self.char_name == "Levi" else 5
        if self.gas < gas_cost:
            self.log_messages.append("💨 Not enough Gas to grapple!")
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            return

        nearest_g = None
        min_dist = 999.0
        for y in range(len(self.current_map)):
            for x in range(len(self.current_map[0])):
                if self.current_map[y][x] == 'G':
                    dist = math.sqrt((x - self.px)**2 + (y - self.py)**2)
                    if dist <= 6.0:
                        if x >= self.px - 1 and dist < min_dist:
                            min_dist = dist
                            nearest_g = (x, y)

        if nearest_g:
            gx, gy = nearest_g
            target_x = gx
            target_y = gy + 1
            if target_y < len(self.current_map) and self.is_walkable(target_x, target_y):
                self.px = target_x
                self.py = target_y
                self.gas -= gas_cost
                self.log_messages.append(f"⚓ ODM Grappled to anchor ({gx}, {gy})!")
            else:
                self.log_messages.append("💥 Anchor position is blocked!")
        else:
            self.log_messages.append("⚠️ No grapple points in range (max 6 blocks)!")

        self.apply_gravity()
        self.check_collisions()
        await self.update_message(interaction)

    @discord.ui.button(label="⚔️ Slash", style=discord.ButtonStyle.danger, row=1)
    async def do_slash(self, interaction: discord.Interaction, button: discord.ui.Button):
        blade_cost = 5 if self.char_name == "Levi" else 10
        if self.blades < blade_cost:
            self.log_messages.append("⚠️ Blades completely shattered!")
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            return

        attacked = False
        # Search all adjacent and diagonal cells
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                tx = self.px + dx
                ty = self.py + dy
                if 0 <= tx < len(self.current_map[0]) and 0 <= ty < len(self.current_map):
                    if self.current_map[ty][tx] == 'T':
                        self.current_map[ty][tx] = '.'
                        self.kills += 1
                        self.score += 25
                        self.blades -= blade_cost
                        self.log_messages.append("⚔️ Slashed a Titan's nape! Target neutralized.")
                        attacked = True
                        break

        if not attacked:
            self.log_messages.append("💨 Slashed the air... No Titans nearby.")

        self.check_collisions()
        await self.update_message(interaction)

    @discord.ui.button(label="🔄 Restart", style=discord.ButtonStyle.secondary, row=1)
    async def restart_level(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Reset level
        self.current_map = [list(row) for row in LEVEL_MAPS[self.level - 1]]
        if self.char_name == "Eren":
            self.health = 120
            self.gas = 100
            self.blades = 100
            self.hardening_active = True
        else:
            self.health = 80
            self.gas = 120
            self.blades = 120
            self.hardening_active = False

        self.px = 1
        self.py = 6
        self.coins_collected = 0
        self.kills = 0
        self.score = 0
        self.status = "PLAYING"
        self.log_messages = ["🧗 Level restarted. Save your resources!"]
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class Platformer(commands.Cog):
    """🧗 Turn-based 2D side-scrolling platformer with ODM Gear."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="titanrun", description="Play a 2D side-scrolling platformer with ODM Gear! 🧗")
    @app_commands.describe(
        level="Select the level/stage to play (1: Outskirts, 2: Trost Ruins, 3: Giant Tree Forest)",
        character="Select your scout (Eren or Levi)"
    )
    @app_commands.choices(
        level=[
            app_commands.Choice(name="Level 1: Outskirts (Easy)", value=1),
            app_commands.Choice(name="Level 2: Trost Ruins (Medium)", value=2),
            app_commands.Choice(name="Level 3: Giant Tree Forest (Hard)", value=3)
        ],
        character=[
            app_commands.Choice(name="Eren Yeager (High HP, Titan Hardening)", value="Eren"),
            app_commands.Choice(name="Levi Ackerman (Fast Grapple, Low Blade Cost)", value="Levi")
        ]
    )
    async def titanrun_slash(
        self,
        interaction: discord.Interaction,
        level: Optional[int] = 1,
        character: Optional[str] = "Eren"
    ):
        player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        view = TitanRunView(interaction.user, level - 1, character, player)
        await interaction.response.send_message(embed=view.build_embed(), view=view)

    @commands.command(name="titanrun", help="Play a 2D side-scrolling platformer! Usage: >titanrun [level] [character]")
    async def titanrun_prefix(self, ctx: commands.Context, level: Optional[int] = 1, character: Optional[str] = "Eren"):
        if level not in (1, 2, 3):
            level = 1
        if character not in ("Eren", "Levi"):
            character = "Eren"

        player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        view = TitanRunView(ctx.author, level - 1, character, player)
        await ctx.send(embed=view.build_embed(), view=view)


async def setup(bot):
    await bot.add_cog(Platformer(bot))
