import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import GameState, TITANS, MOVES, calc_move, titan_ai_move
from utils.image_gen import generate_battle_image
import os


def _battle_phase(scout_hp: int, scout_max: int,
                  titan_hp: int, titan_max: int) -> str:
    sp = scout_hp / max(scout_max, 1)
    tp = titan_hp / max(titan_max, 1)
    if scout_hp <= 0:
        return "defeat"
    if titan_hp <= 0:
        return "victory"
    if sp < 0.25 or tp < 0.25:
        return "intense"
    return "mid"


def _hp_bar(hp: int, max_hp: int, n: int = 16) -> str:
    filled = int(max(0, hp / max(max_hp, 1)) * n)
    return "\U0001f7e9" * filled + "\u2b1b" * (n - filled)


def _build_battle_embed(
    session, title: str, desc: str, color
) -> discord.Embed:
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.add_field(
        name=f"\U0001fa7a {session.scout_name}",
        value=f"{_hp_bar(session.scout_hp, session.scout_max_hp)}  "
              f"`{session.scout_hp}/{session.scout_max_hp} HP`",
        inline=False,
    )
    embed.add_field(
        name=f"\U0001f479 {session.titan_name}",
        value=f"{_hp_bar(session.titan_hp, session.titan_max_hp)}  "
              f"`{session.titan_hp}/{session.titan_max_hp} HP`",
        inline=False,
    )
    embed.set_footer(
        text=f"Round {session.round_num}  \u2022  Choose your move!"
    )
    return embed


class MoveView(discord.ui.View):
    def __init__(self, player_id: str, bot):
        super().__init__(timeout=90)
        self.player_id = player_id
        self.bot = bot
        styles = {
            "slash":         discord.ButtonStyle.primary,
            "odm_dash":      discord.ButtonStyle.primary,
            "thunder_spear": discord.ButtonStyle.danger,
            "spiral_cut":    discord.ButtonStyle.primary,
            "titan_smash":   discord.ButtonStyle.danger,
            "defend":        discord.ButtonStyle.secondary,
        }
        for key, data in MOVES.items():
            btn = discord.ui.Button(
                label=data["label"],
                style=styles.get(key, discord.ButtonStyle.primary),
            )
            btn.callback = self._make_callback(key)
            self.add_item(btn)

    def _make_callback(self, move_key: str):
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.player_id:
                await interaction.response.send_message(
                    "\u274c This is not your battle!", ephemeral=True
                )
                return
            await self._process_move(interaction, move_key)
        return callback

    async def _process_move(
        self, interaction: discord.Interaction, move_key: str
    ):
        session = GameState.get_battle(self.player_id)
        if not session or not session.active:
            await interaction.response.send_message(
                "\u274c No active battle! Use `/fight` to start.",
                ephemeral=True,
            )
            return

        # Defer immediately to avoid timeout
        await interaction.response.defer()

        log_lines = []

        # ── Player move ────────────────────────────────────────────────────
        if move_key == "defend":
            heal = 20
            session.scout_hp = min(session.scout_max_hp, session.scout_hp + heal)
            log_lines.append(
                f"\U0001f6e1\ufe0f **{session.scout_name}** defends and recovers **{heal} HP**!"
            )
        else:
            dmg, missed, desc = calc_move(move_key, attacker_is_scout=True)
            if missed:
                log_lines.append(f"\U0001f4a8 **{session.scout_name}** {desc} **(MISS!)**")
            else:
                session.titan_hp = max(0, session.titan_hp - dmg)
                log_lines.append(
                    f"\u2694\ufe0f **{session.scout_name}** {desc} "
                    f"\u2192 **{dmg} dmg** to {session.titan_name}!"
                )

        # ── Titan dies ─────────────────────────────────────────────────────
        if session.titan_hp <= 0:
            session.last_action = " | ".join(log_lines)
            session.active = False
            player = GameState.get_player(
                self.player_id, interaction.user.display_name
            )
            player.wins += 1
            player.kills += 1
            levelled = player.add_xp(80)
            GameState.save_player(player)
            GameState.end_battle(self.player_id)

            img = generate_battle_image(
                session.scout_name, session.titan_name,
                session.scout_hp, session.scout_max_hp,
                0, session.titan_max_hp,
                phase="victory",
                last_action=session.last_action,
                round_num=session.round_num,
            )
            file = discord.File(fp=img, filename="battle.png")
            lv_txt = "  \u2b06\ufe0f **Level Up!**" if levelled else ""
            embed = discord.Embed(
                title="\U0001f3c6 VICTORY!",
                description=(
                    "\n".join(log_lines)
                    + f"\n\n\U0001f479 **{session.titan_name}** has been slain!"
                    + f"  +80 XP{lv_txt}"
                ),
                color=discord.Color.green(),
            )
            embed.set_image(url="attachment://battle.png")
            await interaction.edit_original_response(
                embed=embed, attachments=[file], view=None
            )
            return

        # ── Titan counter-attack ────────────────────────────────────────────
        t_dmg, t_missed, t_desc = titan_ai_move()
        if t_missed:
            log_lines.append(
                f"\U0001f4a8 **{session.titan_name}** {t_desc} **(MISS!)**"
            )
        else:
            session.scout_hp = max(0, session.scout_hp - t_dmg)
            log_lines.append(
                f"\U0001f9f1 **{session.titan_name}** {t_desc} "
                f"\u2192 **{t_dmg} dmg** to {session.scout_name}!"
            )

        session.round_num += 1
        session.last_action = " | ".join(log_lines)

        # ── Scout dies ─────────────────────────────────────────────────────
        if session.scout_hp <= 0:
            session.active = False
            player = GameState.get_player(
                self.player_id, interaction.user.display_name
            )
            player.losses += 1
            player.add_xp(20)
            GameState.save_player(player)
            GameState.end_battle(self.player_id)

            img = generate_battle_image(
                session.scout_name, session.titan_name,
                0, session.scout_max_hp,
                session.titan_hp, session.titan_max_hp,
                phase="defeat",
                last_action=session.last_action,
                round_num=session.round_num,
            )
            file = discord.File(fp=img, filename="battle.png")
            embed = discord.Embed(
                title="\u2620\ufe0f FALLEN IN BATTLE",
                description=(
                    "\n".join(log_lines)
                    + f"\n\n**{session.scout_name}** has fallen.  +20 XP"
                ),
                color=discord.Color.red(),
            )
            embed.set_image(url="attachment://battle.png")
            await interaction.edit_original_response(
                embed=embed, attachments=[file], view=None
            )
            return

        # ── Battle continues ───────────────────────────────────────────────
        phase = _battle_phase(
            session.scout_hp, session.scout_max_hp,
            session.titan_hp, session.titan_max_hp,
        )
        img = generate_battle_image(
            session.scout_name, session.titan_name,
            session.scout_hp, session.scout_max_hp,
            session.titan_hp, session.titan_max_hp,
            phase=phase,
            last_action=session.last_action,
            round_num=session.round_num,
        )
        file = discord.File(fp=img, filename="battle.png")
        embed = _build_battle_embed(
            session,
            title=f"\u2694\ufe0f {session.scout_name} vs {session.titan_name}",
            desc="\n".join(log_lines),
            color=discord.Color.red(),
        )
        embed.set_image(url="attachment://battle.png")
        new_view = MoveView(self.player_id, self.bot)
        await interaction.edit_original_response(
            embed=embed, attachments=[file], view=new_view
        )

    async def on_timeout(self):
        """Auto-end battle on view timeout."""
        session = GameState.get_battle(self.player_id)
        if session and session.active:
            session.active = False
            GameState.end_battle(self.player_id)


class Arena(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("data", exist_ok=True)  # Ensure data dir exists

    @app_commands.command(
        name="fight",
        description="Start a turn-based battle against a Titan with live battle images!",
    )
    @app_commands.describe(titan="Choose your titan opponent")
    @app_commands.choices(titan=[
        app_commands.Choice(name=t, value=t) for t in TITANS
    ])
    async def fight(
        self,
        interaction: discord.Interaction,
        titan: app_commands.Choice[str],
    ):
        player = GameState.get_player(
            str(interaction.user.id), interaction.user.display_name
        )
        existing = GameState.get_battle(str(interaction.user.id))
        if existing and existing.active:
            await interaction.response.send_message(
                "\u26a0\ufe0f You already have an active battle! "
                "Finish it or use `/flee` first.",
                ephemeral=True,
            )
            return

        session = GameState.start_battle(
            str(interaction.user.id),
            player.scout_name,
            titan.value,
            interaction.channel_id,
        )

        img = generate_battle_image(
            session.scout_name, session.titan_name,
            session.scout_hp, session.scout_max_hp,
            session.titan_hp, session.titan_max_hp,
            phase="start",
            last_action="The battle begins! Choose your move.",
            round_num=1,
        )
        file = discord.File(fp=img, filename="battle.png")
        embed = _build_battle_embed(
            session,
            title=f"\u2694\ufe0f {session.scout_name} vs {titan.value}",
            desc=(
                f"**{interaction.user.mention}** has entered the battle!\n"
                f"Face the **{titan.value}** and fight for humanity!"
            ),
            color=discord.Color.red(),
        )
        embed.set_image(url="attachment://battle.png")
        view = MoveView(str(interaction.user.id), self.bot)
        await interaction.response.send_message(embed=embed, file=file, view=view)

    @app_commands.command(
        name="flee",
        description="Flee from your current battle (counts as a loss)",
    )
    async def flee(self, interaction: discord.Interaction):
        session = GameState.get_battle(str(interaction.user.id))
        if not session or not session.active:
            await interaction.response.send_message(
                "\u274c You have no active battle.", ephemeral=True
            )
            return
        player = GameState.get_player(
            str(interaction.user.id), interaction.user.display_name
        )
        player.losses += 1
        GameState.save_player(player)
        GameState.end_battle(str(interaction.user.id))
        await interaction.response.send_message(
            f"\U0001f3c3 **{session.scout_name}** fled from "
            f"**{session.titan_name}**! *(Loss recorded)*"
        )


async def setup(bot):
    await bot.add_cog(Arena(bot))
