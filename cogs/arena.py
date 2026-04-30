import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import GameState, TITANS, MOVES, calc_move, titan_ai_move
from utils.image_gen import generate_battle_image
import io


def _battle_phase(scout_hp: int, scout_max: int, titan_hp: int, titan_max: int) -> str:
    sp = scout_hp / scout_max
    tp = titan_hp / titan_max
    if sp < 0.25 or tp < 0.25:
        return "intense"
    if scout_hp <= 0:
        return "defeat"
    if titan_hp <= 0:
        return "victory"
    return "mid"


def _build_battle_embed(session, title: str, desc: str, color) -> discord.Embed:
    embed = discord.Embed(title=title, description=desc, color=color)
    sp_pct = session.scout_hp / session.scout_max_hp
    tp_pct = session.titan_hp / session.titan_max_hp
    hp_bar = lambda pct, n=16: "\U0001f7e9" * int(pct*n) + "\u2b1b" * (n - int(pct*n))
    embed.add_field(
        name=f"\U0001fa7a {session.scout_name}",
        value=f"{hp_bar(sp_pct)}  `{session.scout_hp}/{session.scout_max_hp} HP`",
        inline=False,
    )
    embed.add_field(
        name=f"\U0001f479 {session.titan_name}",
        value=f"{hp_bar(tp_pct)}  `{session.titan_hp}/{session.titan_max_hp} HP`",
        inline=False,
    )
    embed.set_footer(text=f"Round {session.round_num}  \u2022  Use the buttons below to act!")
    return embed


class MoveView(discord.ui.View):
    def __init__(self, player_id: str, bot):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.bot = bot
        for key, data in MOVES.items():
            btn = discord.ui.Button(
                label=data["label"],
                style=discord.ButtonStyle.danger if key in ("thunder_spear","titan_smash") else discord.ButtonStyle.primary,
                custom_id=f"move_{key}",
            )
            btn.callback = self._make_callback(key)
            self.add_item(btn)

    def _make_callback(self, move_key: str):
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.player_id:
                await interaction.response.send_message(
                    "\u274c This is not your battle!", ephemeral=True)
                return
            await self._process_move(interaction, move_key)
        return callback

    async def _process_move(self, interaction: discord.Interaction, move_key: str):
        session = GameState.get_battle(self.player_id)
        if not session or not session.active:
            await interaction.response.send_message("\u274c No active battle! Use `/fight`.", ephemeral=True)
            return

        log_lines = []

        # ── Player turn ───────────────────────────────────────────────────
        if move_key == "defend":
            heal = 20
            session.scout_hp = min(session.scout_max_hp, session.scout_hp + heal)
            log_lines.append(f"\U0001f6e1\ufe0f **{session.scout_name}** takes a defensive stance and recovers **{heal} HP**!")
        else:
            dmg, missed, desc = calc_move(move_key, attacker_is_scout=True)
            if missed:
                log_lines.append(f"\U0001f4a8 **{session.scout_name}** {desc} **(MISS!)**")
            else:
                session.titan_hp = max(0, session.titan_hp - dmg)
                log_lines.append(f"\u2694\ufe0f **{session.scout_name}** {desc} \u2192 **{dmg} dmg** to {session.titan_name}!")

        # ── Check titan death ────────────────────────────────────────────
        if session.titan_hp <= 0:
            session.active = False
            session.last_action = " | ".join(log_lines)
            phase = "victory"
            player = GameState.get_player(self.player_id, interaction.user.display_name)
            player.wins += 1
            player.kills += 1
            levelled = player.add_xp(80)
            GameState.save_player(player)
            GameState.end_battle(self.player_id)

            img = generate_battle_image(
                session.scout_name, session.titan_name,
                session.scout_hp, session.scout_max_hp,
                0, session.titan_max_hp,
                phase=phase, last_action=session.last_action,
                round_num=session.round_num,
            )
            file = discord.File(fp=img, filename="battle.png")
            embed = discord.Embed(
                title="\U0001f3c6 VICTORY!",
                description="\n".join(log_lines) + f"\n\n**{session.titan_name} has been slain!** +80 XP" + (" \u2b06\ufe0f Level Up!" if levelled else ""),
                color=discord.Color.green()
            )
            embed.set_image(url="attachment://battle.png")
            await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
            return

        # ── Titan turn ────────────────────────────────────────────────────
        t_dmg, t_missed, t_desc = titan_ai_move()
        if t_missed:
            log_lines.append(f"\U0001f4a8 **{session.titan_name}** {t_desc} **(MISS!)**")
        else:
            session.scout_hp = max(0, session.scout_hp - t_dmg)
            log_lines.append(f"\U0001f9f1 **{session.titan_name}** {t_desc} \u2192 **{t_dmg} dmg** to {session.scout_name}!")

        session.round_num += 1
        session.last_action = " | ".join(log_lines)

        # ── Check scout death ─────────────────────────────────────────────
        if session.scout_hp <= 0:
            session.active = False
            phase = "defeat"
            player = GameState.get_player(self.player_id, interaction.user.display_name)
            player.losses += 1
            player.add_xp(20)
            GameState.save_player(player)
            GameState.end_battle(self.player_id)

            img = generate_battle_image(
                session.scout_name, session.titan_name,
                0, session.scout_max_hp,
                session.titan_hp, session.titan_max_hp,
                phase=phase, last_action=session.last_action,
                round_num=session.round_num,
            )
            file = discord.File(fp=img, filename="battle.png")
            embed = discord.Embed(
                title="\u2620\ufe0f FALLEN IN BATTLE",
                description="\n".join(log_lines) + f"\n\n**{session.scout_name} has fallen.** +20 XP",
                color=discord.Color.red()
            )
            embed.set_image(url="attachment://battle.png")
            await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
            return

        # ── Battle continues ──────────────────────────────────────────────
        phase = _battle_phase(session.scout_hp, session.scout_max_hp,
                              session.titan_hp, session.titan_max_hp)
        img = generate_battle_image(
            session.scout_name, session.titan_name,
            session.scout_hp, session.scout_max_hp,
            session.titan_hp, session.titan_max_hp,
            phase=phase, last_action=session.last_action,
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
        await interaction.response.edit_message(embed=embed, attachments=[file], view=new_view)


class Arena(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fight", description="Start a turn-based battle against a Titan!")
    @app_commands.describe(titan="Choose your titan opponent")
    @app_commands.choices(titan=[
        app_commands.Choice(name=t, value=t) for t in TITANS
    ])
    async def fight(self, interaction: discord.Interaction,
                    titan: app_commands.Choice[str]):
        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        existing = GameState.get_battle(str(interaction.user.id))
        if existing and existing.active:
            await interaction.response.send_message(
                "\u26a0\ufe0f You already have an active battle! Finish it first.",
                ephemeral=True
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
            last_action="The battle begins!",
            round_num=1,
        )
        file = discord.File(fp=img, filename="battle.png")
        embed = _build_battle_embed(
            session,
            title=f"\u2694\ufe0f {session.scout_name} vs {session.titan_name}",
            desc=f"**{interaction.user.mention} vs the {titan.value}!**\nChoose your move below!",
            color=discord.Color.red(),
        )
        embed.set_image(url="attachment://battle.png")
        view = MoveView(str(interaction.user.id), self.bot)
        await interaction.response.send_message(embed=embed, file=file, view=view)

    @app_commands.command(name="flee", description="Flee from your current battle (counts as a loss)")
    async def flee(self, interaction: discord.Interaction):
        session = GameState.get_battle(str(interaction.user.id))
        if not session or not session.active:
            await interaction.response.send_message("\u274c You have no active battle.", ephemeral=True)
            return
        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        player.losses += 1
        GameState.save_player(player)
        GameState.end_battle(str(interaction.user.id))
        await interaction.response.send_message(
            f"\U0001f3c3 **{session.scout_name}** fled from **{session.titan_name}**! (Loss recorded)"
        )

async def setup(bot):
    await bot.add_cog(Arena(bot))
