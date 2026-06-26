"""
3D Game System: Implements a Wolfenstein-style first-person raycaster in ASCII for Discord.
Players hunt Titans in 3D ruins using interactable buttons.
"""
from __future__ import annotations
import math
import random
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from utils.game_state import GameState, SURVEY_CORPS_ICON

# Game maps definition
MAPS = [
    # Map 1: Training Grounds (Stone Castle & Debris/Banners)
    [
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 0, 0, 0, 2, 0, 0, 0, 0, 1],
        [1, 0, 1, 0, 2, 0, 1, 1, 0, 1],
        [1, 0, 1, 0, 0, 0, 0, 2, 0, 1],
        [1, 0, 2, 2, 1, 1, 0, 2, 0, 1],
        [1, 0, 0, 0, 0, 1, 0, 0, 0, 1],
        [1, 1, 2, 0, 0, 2, 1, 1, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 1, 0, 1],
        [1, 0, 1, 1, 1, 1, 0, 0, 0, 1],
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    ],
    # Map 2: Trost District Ruins (Red Bricks & Windows)
    [
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 2, 1, 0, 0, 1, 2, 0, 1],
        [1, 0, 1, 0, 0, 0, 0, 1, 0, 1],
        [1, 0, 0, 0, 2, 2, 0, 0, 0, 1],
        [1, 0, 0, 0, 2, 2, 0, 0, 0, 1],
        [1, 0, 1, 0, 0, 0, 0, 1, 0, 1],
        [1, 0, 2, 1, 0, 0, 1, 2, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    ],
    # Map 3: Forest of Giant Trees (Leaves & Trunks)
    [
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 2, 0, 2, 0, 2, 0, 2, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 2, 0, 2, 0, 2, 0, 2, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 2, 0, 2, 0, 2, 0, 2, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 2, 0, 2, 0, 2, 0, 2, 1],
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
     ]
]

MAP_NAMES = ["District Ruins", "Trost District", "Giant Tree Forest"]

FOV = math.pi / 3  # 60 degrees Field of View
SCREEN_WIDTH = 24
SCREEN_HEIGHT = 10

# 8x8 Textures
TEXTURE_STONE = [
    "########",
    "  #     ",
    "  #     ",
    "########",
    "    #   ",
    "    #   ",
    "########",
    "  #     "
]

TEXTURE_STONE_DEBRIS = [
    "########",
    "#+      ",
    "# +++++ ",
    "# +   + ",
    "# +++++ ",
    "# +   + ",
    "# +++++ ",
    "########"
]

TEXTURE_BRICK = [
    "########",
    "   #   #",
    "   #   #",
    "########",
    " #   #  ",
    " #   #  ",
    "########",
    "   #   #"
]

TEXTURE_WINDOW = [
    "########",
    "#++++++#",
    "#+ ++ +#",
    "#++++++#",
    "#+ ++ +#",
    "#++++++#",
    "#++++++#",
    "########"
]

TEXTURE_LEAVES = [
    " + + + +",
    "+ + + + ",
    " + + + +",
    "+ + + + ",
    " + + + +",
    "+ + + + ",
    " + + + +",
    "+ + + + "
]

TEXTURE_TRUNK = [
    " | | | |",
    " | | | |",
    " | | | |",
    " | | | |",
    " | | | |",
    " | | | |",
    " | | | |",
    " | | | |"
]

TITAN_TEXTURE = [
    "..HHHH..",
    ".HHHHHH.",
    "HHSSEESH",
    "HSSSSSSH",
    ".SSMMSS.",
    "..BBBB..",
    ".BBBBBB.",
    "..BBBB.."
]


def get_wall_pixel(map_idx: int, wall_type: int, tx: int, ty: int, d: float) -> tuple[int, int, str]:
    if map_idx == 0:
        tex = TEXTURE_STONE_DEBRIS if wall_type == 2 else TEXTURE_STONE
    elif map_idx == 1:
        tex = TEXTURE_WINDOW if wall_type == 2 else TEXTURE_BRICK
    else:  # map_idx == 2
        tex = TEXTURE_TRUNK if wall_type == 2 else TEXTURE_LEAVES

    char_symbol = tex[ty][tx]

    if map_idx == 0:  # Stone Castle (Grey/White)
        if d < 2.5:
            if char_symbol == "#":
                return 40, 37, "▒▒"  # Dark gray joint
            elif char_symbol == "+":
                return 47, 34, "██"  # Blue detail/crest
            else:
                return 47, 37, "██"  # Solid white brick
        elif d < 5.0:
            if char_symbol == "#":
                return 40, 37, "  "
            elif char_symbol == "+":
                return 47, 34, "▒▒"
            else:
                return 47, 37, "▒▒"
        elif d < 8.0:
            if char_symbol == "#":
                return 40, 30, "  "
            elif char_symbol == "+":
                return 46, 30, "░░"
            else:
                return 46, 30, "░░"
        else:
            return 40, 30, "░░"

    elif map_idx == 1:  # Trost District (Red/Yellow Brick & Windows)
        if d < 2.5:
            if char_symbol == "#":
                return 40, 31, "▒▒"  # Red joint
            elif char_symbol == "+":
                return 46, 37, "██"  # Bright glass window
            else:
                return 41, 33, "██"  # Red brick
        elif d < 5.0:
            if char_symbol == "#":
                return 40, 31, "  "
            elif char_symbol == "+":
                return 46, 36, "▒▒"  # Glass window
            else:
                return 41, 33, "▒▒"  # Medium red brick
        elif d < 8.0:
            if char_symbol == "#":
                return 40, 30, "  "
            elif char_symbol == "+":
                return 40, 36, "░░"
            else:
                return 43, 31, "░░"  # Darker yellow/red brick
        else:
            return 40, 30, "░░"

    else:  # Giant Tree Forest (Green Leaves & Brown Trunks)
        if d < 2.5:
            if wall_type == 2:  # Trunk
                if char_symbol == "|":
                    return 40, 33, "██"  # Dark bark vertical lines
                else:
                    return 43, 33, "██"  # Yellow/brown trunk
            else:  # Leaves
                if char_symbol == "+":
                    return 42, 37, "██"  # High-light leaf
                else:
                    return 42, 32, "██"  # Green leaf
        elif d < 5.0:
            if wall_type == 2:  # Trunk
                if char_symbol == "|":
                    return 40, 33, "▒▒"
                else:
                    return 43, 33, "▒▒"
            else:  # Leaves
                if char_symbol == "+":
                    return 42, 32, "▒▒"
                else:
                    return 42, 30, "▒▒"
        elif d < 8.0:
            if wall_type == 2:  # Trunk
                return 40, 33, "░░"
            else:  # Leaves
                return 40, 32, "░░"
        else:
            return 40, 30, "░░"


def get_titan_pixel(char_symbol: str, d: float) -> Optional[tuple[int, int, str]]:
    if char_symbol == ".":
        return None

    if d < 3.0:
        if char_symbol == "H":
            return 40, 30, "██"  # Black hair
        elif char_symbol == "S":
            return 43, 37, "██"  # Yellow/pink skin
        elif char_symbol == "E":
            return 41, 31, "██"  # Red eyes
        elif char_symbol == "M":
            return 40, 31, "▒▒"  # Teeth/mouth dark red
        elif char_symbol == "B":
            return 41, 31, "▓▓"  # Body raw red muscles
    elif d < 6.0:
        if char_symbol == "H":
            return 40, 30, "▓▓"
        elif char_symbol == "S":
            return 43, 33, "▒▒"
        elif char_symbol == "E":
            return 41, 31, "▒▒"
        elif char_symbol == "M":
            return 40, 30, "  "
        elif char_symbol == "B":
            return 41, 31, "░░"
    else:
        if char_symbol == "H":
            return 40, 30, "░░"
        elif char_symbol == "S":
            return 40, 33, "░░"
        elif char_symbol == "E":
            return 41, 30, "░░"
        elif char_symbol == "M":
            return 40, 30, "  "
        elif char_symbol == "B":
            return 40, 31, "░░"
            
    return 40, 30, "  "


def make_bar(value: int, max_val: int = 100, size: int = 10) -> str:
    filled = round((value / max_val) * size)
    filled = max(0, min(size, filled))
    return f"`[{'█' * filled}{'░' * (size - filled)}]`"


class Titan3DView(discord.ui.View):
    def __init__(self, user: discord.User, map_idx: int, player_data):
        super().__init__(timeout=120)
        self.user = user
        self.map_idx = map_idx
        self.map_data = MAPS[map_idx]
        self.map_name = MAP_NAMES[map_idx]
        self.player_data = player_data

        # Setup positions
        self.px = 1.5
        self.py = 1.5
        self.pa = 0.0  # Radians

        # Spawn Titan at a far location
        self.tx, self.ty = self._get_titan_spawn()
        self.titan_hp = 100
        self.health = 100
        self.gas = 100
        self.blades = 100
        
        self.status = "PLAYING"
        self.log_messages = ["⚔️ Find and strike the Titan!"]

    def _get_titan_spawn(self) -> tuple[float, float]:
        # Keep searching for a valid spawning cell far from the player
        for _ in range(100):
            rx = random.randint(4, len(self.map_data[0]) - 2)
            ry = random.randint(4, len(self.map_data) - 2)
            if self.map_data[ry][rx] == 0:
                return float(rx) + 0.5, float(ry) + 0.5
        return 7.5, 7.5

    def can_move_to(self, new_x: float, new_y: float, is_titan: bool = False) -> bool:
        radius = 0.35 if is_titan else 0.25
        h = len(self.map_data)
        w = len(self.map_data[0])
        for dx in [-radius, radius]:
            for dy in [-radius, radius]:
                cx = int(new_x + dx)
                cy = int(new_y + dy)
                if cx < 0 or cx >= w or cy < 0 or cy >= h:
                    return False
                if self.map_data[cy][cx] >= 1:
                    return False
        return True

    def render_3d(self) -> str:
        # Initialize color buffer with Sky and Floor gradients
        color_buffer = [[None for _ in range(SCREEN_WIDTH)] for _ in range(SCREEN_HEIGHT)]
        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                if y < SCREEN_HEIGHT // 2:
                    # Sky
                    if y == 0:
                        bg, fg, char = 44, 37, "░░"
                    elif y == 1:
                        bg, fg, char = 44, 34, "██"
                    elif y == 2:
                        bg, fg, char = 44, 36, "▒▒"
                    elif y == 3:
                        bg, fg, char = 46, 34, "░░"
                    else:
                        bg, fg, char = 46, 36, "██"
                else:
                    # Floor
                    if y == 5:
                        bg, fg, char = 40, 30, "██"
                    elif y == 6:
                        bg, fg, char = 40, 32, "░░"
                    elif y == 7:
                        bg, fg, char = 42, 30, "▒▒"
                    elif y == 8:
                        bg, fg, char = 42, 32, "▓▓"
                    else:
                        bg, fg, char = 42, 37, "▒▒"
                color_buffer[y][x] = {"bg": bg, "fg": fg, "char": char}

        depths = [99.0] * SCREEN_WIDTH

        # 1. Cast Rays for Walls
        for col in range(SCREEN_WIDTH):
            ray_angle = self.pa - FOV/2 + (col / (SCREEN_WIDTH - 1)) * FOV
            cos_r = math.cos(ray_angle)
            sin_r = math.sin(ray_angle)
            
            dist = 0.0
            hit = False
            wall_type = 0
            while dist < 12.0 and not hit:
                dist += 0.06
                rx = self.px + cos_r * dist
                ry = self.py + sin_r * dist
                
                mx = int(rx)
                my = int(ry)
                if 0 <= mx < len(self.map_data[0]) and 0 <= my < len(self.map_data):
                    if self.map_data[my][mx] >= 1:
                        hit = True
                        wall_type = self.map_data[my][mx]
            
            # Correct fish-eye
            corrected_dist = dist * math.cos(ray_angle - self.pa)
            depths[col] = corrected_dist
            
            if corrected_dist > 0.05:
                wall_h = min(SCREEN_HEIGHT, int(SCREEN_HEIGHT / corrected_dist))
            else:
                wall_h = SCREEN_HEIGHT
                
            start = (SCREEN_HEIGHT - wall_h) // 2
            end = start + wall_h
            
            # Recalculate hit coords for texturing
            rx = self.px + cos_r * dist
            ry = self.py + sin_r * dist
            mx = int(rx)
            my = int(ry)
            
            dx_boundary = abs(rx - round(rx))
            dy_boundary = abs(ry - round(ry))
            
            if dx_boundary < dy_boundary:
                hit_pos = ry - my
            else:
                hit_pos = rx - mx
                
            hit_pos = hit_pos - math.floor(hit_pos)
            tx_col = int(hit_pos * 8)
            tx_col = max(0, min(7, tx_col))

            for y in range(start, end):
                if 0 <= y < SCREEN_HEIGHT:
                    if end > start + 1:
                        ty_row = int((y - start) / (end - start - 1) * 7)
                    else:
                        ty_row = 3
                    ty_row = max(0, min(7, ty_row))
                    
                    bg_color, fg_color, char_pattern = get_wall_pixel(self.map_idx, wall_type, tx_col, ty_row, corrected_dist)
                    color_buffer[y][col] = {"bg": bg_color, "fg": fg_color, "char": char_pattern}

        # 2. Render Titan Sprite (if alive)
        if self.titan_hp > 0:
            dx = self.tx - self.px
            dy = self.ty - self.py
            titan_dist = math.sqrt(dx*dx + dy*dy)
            
            titan_angle = math.atan2(dy, dx)
            angle_diff = titan_angle - self.pa
            while angle_diff > math.pi:
                angle_diff -= 2 * math.pi
            while angle_diff < -math.pi:
                angle_diff += 2 * math.pi
                
            if abs(angle_diff) < FOV / 2:
                sprite_col = int((SCREEN_WIDTH - 1) * (angle_diff + FOV/2) / FOV)
                sprite_h = min(SCREEN_HEIGHT - 2, int(SCREEN_HEIGHT / titan_dist))
                sprite_w = max(1, min(SCREEN_WIDTH // 3, int(SCREEN_WIDTH / (2 * titan_dist))))
                
                if depths[sprite_col] > titan_dist - 0.5:
                    start_y = (SCREEN_HEIGHT - sprite_h) // 2
                    for col_offset in range(-sprite_w // 2, (sprite_w + 1) // 2):
                        c = sprite_col + col_offset
                        if 0 <= c < SCREEN_WIDTH and depths[c] > titan_dist:
                            if sprite_w > 1:
                                tx = int((col_offset + sprite_w // 2) / (sprite_w - 1) * 7)
                            else:
                                tx = 3
                            tx = max(0, min(7, tx))

                            for y in range(start_y, start_y + sprite_h):
                                if 0 <= y < SCREEN_HEIGHT:
                                    if sprite_h > 1:
                                        ty = int((y - start_y) / (sprite_h - 1) * 7)
                                    else:
                                        ty = 3
                                    ty = max(0, min(7, ty))
                                    
                                    symbol = TITAN_TEXTURE[ty][tx]
                                    pixel_data = get_titan_pixel(symbol, titan_dist)
                                    if pixel_data is not None:
                                        color_buffer[y][c] = pixel_data

        # Build optimized string
        lines = []
        for y in range(SCREEN_HEIGHT):
            row_str = []
            cur_bg = None
            cur_fg = None
            cur_bold = None
            for x in range(SCREEN_WIDTH):
                cell = color_buffer[y][x]
                bg = cell.get("bg", 40)
                fg = cell.get("fg", 37)
                bold = cell.get("bold", False)
                char = cell.get("char", "  ")
                
                if bg != cur_bg or fg != cur_fg or bold != cur_bold:
                    code_parts = ["0"]
                    code_parts.append(str(fg))
                    code_parts.append(str(bg))
                    if bold:
                        code_parts.append("1")
                    row_str.append(f"\u001b[{';'.join(code_parts)}m")
                    cur_bg = bg
                    cur_fg = fg
                    cur_bold = bold
                row_str.append(char)
            row_str.append("\u001b[0m")
            lines.append("".join(row_str))
        
        return "\n".join(lines)

    def build_minimap(self) -> str:
        rows = []
        for y in range(len(self.map_data)):
            row_str = []
            for x in range(len(self.map_data[0])):
                if int(self.px) == x and int(self.py) == y:
                    normalized_a = self.pa % (2 * math.pi)
                    if 1.75 * math.pi <= normalized_a or normalized_a < 0.25 * math.pi:
                        dir_char = ">"
                    elif 0.25 * math.pi <= normalized_a < 0.75 * math.pi:
                        dir_char = "v"
                    elif 0.75 * math.pi <= normalized_a < 1.25 * math.pi:
                        dir_char = "<"
                    else:
                        dir_char = "^"
                    row_str.append(dir_char)
                elif int(self.tx) == x and int(self.ty) == y and self.titan_hp > 0:
                    row_str.append("T")
                elif self.map_data[y][x] >= 1:
                    row_str.append("#")
                else:
                    row_str.append(".")
            rows.append(" ".join(row_str))
        return "\n".join(rows)

    def build_embed(self) -> discord.Embed:
        # Generate 3D perspective
        render = self.render_3d()
        minimap = self.build_minimap()
        
        embed = discord.Embed(
            title=f"🗡️ 3D Titan Maze Hunter — {self.map_name}",
            color=discord.Color.red() if self.status.startswith("LOST") else discord.Color.green() if self.status == "WON" else discord.Color.blurple()
        )
        
        embed.description = f"**First-Person View:**\n```ansi\n{render}\n```"
        
        # Grid fields
        embed.add_field(name="🗺️ Minimap", value=f"```\n{minimap}\n```", inline=True)
        
        # Stats fields
        stats_info = (
            f"❤️ **HP:** {self.health}/100\n{make_bar(self.health)}\n"
            f"💨 **Gas:** {self.gas}%\n{make_bar(self.gas)}\n"
            f"⚔️ **Blades:** {self.blades}%\n{make_bar(self.blades)}\n"
            f"👹 **Titan HP:** {self.titan_hp}%\n{make_bar(self.titan_hp)}"
        )
        embed.add_field(name="📊 Status", value=stats_info, inline=True)
        
        # Logs
        recent_logs = "\n".join(self.log_messages[-3:])
        embed.add_field(name="📜 Combat Log", value=recent_logs, inline=False)
        
        embed.set_footer(text=f"Player: {self.user.display_name} • Controls below")
        return embed

    async def update_message(self, interaction: discord.Interaction):
        # Check game states
        if self.status == "WON":
            self.disable_all()
            xp_gain = 125
            coins_gain = 75
            levelled = self.player_data.add_xp(xp_gain)
            self.player_data.coins += coins_gain
            self.player_data.wins += 1
            self.player_data.kills += 1
            await GameState.save_player(self.player_data)
            
            embed = self.build_embed()
            embed.title = "🏆 VICTORY! Titan Slain!"
            embed.add_field(name="💰 Rewards", value=f"+{xp_gain} XP\n+{coins_gain} Coins", inline=False)
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
            embed.title = "💀 DEFEAT! Levi is unimpressed."
            if self.status == "LOST_DEAD":
                reason = "You were eaten by the Titan."
            else:
                reason = "Your blades shattered and you ran out of resources."
            embed.add_field(name="💀 Cause of Death", value=reason, inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
            return

        elif self.status == "SURRENDERED":
            self.disable_all()
            self.player_data.losses += 1
            await GameState.save_player(self.player_data)
            
            embed = self.build_embed()
            embed.title = "🏳️ Retreat! Mission Abandoned."
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
            return
            
        # Re-render active state
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    def disable_all(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    def process_titan_turn(self):
        # Check Titan action
        dx = self.px - self.tx
        dy = self.py - self.ty
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist < 1.2:
            # Titan attacks
            dmg = random.randint(15, 30)
            self.health -= dmg
            self.log_messages.append(f"👹 Titan grabbed you! Took {dmg} damage.")
            if self.health <= 0:
                self.health = 0
                self.status = "LOST_DEAD"
        else:
            # Titan moves
            if random.random() < 0.65:
                # Step towards player
                step_x = self.tx + (dx / dist) * 0.45
                step_y = self.ty + (dy / dist) * 0.45
                if self.can_move_to(step_x, step_y, is_titan=True):
                    self.tx = step_x
                    self.ty = step_y
            else:
                # Step randomly
                ang = random.random() * 2 * math.pi
                step_x = self.tx + math.cos(ang) * 0.4
                step_y = self.ty + math.sin(ang) * 0.4
                if self.can_move_to(step_x, step_y, is_titan=True):
                    self.tx = step_x
                    self.ty = step_y

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This is not your training session!", ephemeral=True)
            return False
        return True

    # ── Button Handlers ────────────────────────────────────────────────────────────

    @discord.ui.button(label="◀️ Turn Left", style=discord.ButtonStyle.secondary, row=0)
    async def turn_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pa -= math.pi / 8
        self.log_messages.append("↩️ Turned left.")
        self.process_titan_turn()
        await self.update_message(interaction)

    @discord.ui.button(label="🔼 Forward", style=discord.ButtonStyle.primary, row=0)
    async def move_forward(self, interaction: discord.Interaction, button: discord.ui.Button):
        cos_a = math.cos(self.pa)
        sin_a = math.sin(self.pa)
        next_x = self.px + cos_a * 0.5
        next_y = self.py + sin_a * 0.5
        
        if self.can_move_to(next_x, next_y):
            self.px = next_x
            self.py = next_y
            self.gas -= 2
            self.log_messages.append("👣 Moved forward.")
            if self.gas <= 0:
                self.gas = 0
        else:
            self.log_messages.append("💥 Bumped into a wall!")
            
        self.process_titan_turn()
        
        # Check resources depletion
        if self.gas <= 0 and self.blades <= 0:
            self.status = "LOST_OUT_OF_RESOURCES"
            
        await self.update_message(interaction)

    @discord.ui.button(label="▶️ Turn Right", style=discord.ButtonStyle.secondary, row=0)
    async def turn_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pa += math.pi / 8
        self.log_messages.append("↪️ Turned right.")
        self.process_titan_turn()
        await self.update_message(interaction)

    @discord.ui.button(label="🔽 Backward", style=discord.ButtonStyle.secondary, row=1)
    async def move_backward(self, interaction: discord.Interaction, button: discord.ui.Button):
        cos_a = math.cos(self.pa)
        sin_a = math.sin(self.pa)
        next_x = self.px - cos_a * 0.5
        next_y = self.py - sin_a * 0.5
        
        if self.can_move_to(next_x, next_y):
            self.px = next_x
            self.py = next_y
            self.gas -= 2
            self.log_messages.append("👣 Backed up.")
            if self.gas <= 0:
                self.gas = 0
        else:
            self.log_messages.append("💥 Bumped into a wall behind you!")
            
        self.process_titan_turn()
        
        if self.gas <= 0 and self.blades <= 0:
            self.status = "LOST_OUT_OF_RESOURCES"
            
        await self.update_message(interaction)

    @discord.ui.button(label="⚔️ Strike Nape", style=discord.ButtonStyle.danger, row=1)
    async def strike(self, interaction: discord.Interaction, button: discord.ui.Button):
        dx = self.tx - self.px
        dy = self.ty - self.py
        dist = math.sqrt(dx*dx + dy*dy)
        
        titan_angle = math.atan2(dy, dx)
        angle_diff = titan_angle - self.pa
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
            
        if dist < 2.5 and abs(angle_diff) < FOV / 2:
            # Successful strike
            dmg = random.randint(35, 55)
            self.titan_hp -= dmg
            self.blades -= random.randint(10, 20)
            self.log_messages.append(f"⚔️ Slashed Titan's nape! Dealt {dmg} damage.")
            if self.titan_hp <= 0:
                self.titan_hp = 0
                self.status = "WON"
            if self.blades <= 0:
                self.blades = 0
                self.log_messages.append("⚠️ Blades shattered!")
        else:
            if dist >= 2.5:
                self.log_messages.append("💨 Too far to strike! Get closer.")
            else:
                self.log_messages.append("💨 Titan is not in sight!")

        self.process_titan_turn()
        
        if self.blades <= 0 and self.titan_hp > 0:
            self.status = "LOST_OUT_OF_RESOURCES"
            
        await self.update_message(interaction)

    @discord.ui.button(label="🏳️ Retreat", style=discord.ButtonStyle.secondary, row=1)
    async def retreat(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.status = "SURRENDERED"
        await self.update_message(interaction)


class Games3D(commands.Cog):
    """⚔️ High-Performance 3D ASCII Minigames inside Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="titan3d", description="Play a 3D first-person Titan Hunt maze game! 🧹")
    async def titan3d_slash(self, interaction: discord.Interaction):
        # Load user profile
        player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        
        # Choose a random map
        map_idx = random.randint(0, len(MAPS) - 1)
        view = Titan3DView(interaction.user, map_idx, player)
        
        await interaction.response.send_message(embed=view.build_embed(), view=view)

    @commands.command(name="titan3d", help="Play a 3D first-person Titan Hunt maze game! Usage: >titan3d")
    async def titan3d_prefix(self, ctx: commands.Context):
        # Load user profile
        player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        
        # Choose a random map
        map_idx = random.randint(0, len(MAPS) - 1)
        view = Titan3DView(ctx.author, map_idx, player)
        
        msg = await ctx.send(embed=view.build_embed(), view=view)


async def setup(bot):
    await bot.add_cog(Games3D(bot))
