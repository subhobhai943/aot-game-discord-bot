"""Titan-Game cog — Among Titans social deduction game.

New in this version
───────────────────
* BUG FIX  : Kill menu now works for every kill after the first.
              Root cause was EliminateSelectView being re-created with stale
              game state. The view now always fetches a fresh game ref and
              the kill cooldown timestamp is set correctly in titan_logic.
* FEATURE  : Meeting cooldown — 30 s after a meeting ends before another
              can be called (both button and /meeting command).
* FEATURE  : Round system — round counter shown in status/exploration embeds;
              advances after every vote resolution.
* FEATURE  : Jigsaw-style AoT tasks replacing boring Q&A. Each task gives a
              scrambled word/image puzzle the player assembles step by step.
* FEATURE  : `Aot task` / `/task` command — start a task from the command
              line instead of the button (works anywhere in the game channel).
* FEATURE  : GIF reactions for kills, meetings, and game-over events.
* REMOVED  : Old multiple-choice knowledge quiz tasks.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord.ext import commands

from data.titan_images import SURVEY_CORPS_IMAGES, TITAN_IMAGES
from games.titan_logic import GameState, Role, TitanGameEngine
from utils.game_state import attach_image


GAME_CATEGORY_ID = 1510159583040114788

# ─────────────────────────────────────────────────────────────────────────────
# GIFs used across the game for atmosphere
# ─────────────────────────────────────────────────────────────────────────────
GIF_GAME_START   = "https://media.tenor.com/5DJiIz0RQFIAAAAC/attack-on-titan-aot.gif"
GIF_KILL         = "https://media.tenor.com/GfNJMjgKQXcAAAAC/attack-on-titan-titan.gif"
GIF_MEETING      = "https://media.tenor.com/3IUGkiXXPy4AAAAC/attack-on-titan-aot.gif"
GIF_VOTE_START   = "https://media.tenor.com/VEz6HkPDJnIAAAAC/aot-attack-on-titan.gif"
GIF_SC_WIN       = "https://media.tenor.com/uwdcBiJFkKkAAAAC/attack-on-titan-levi.gif"
GIF_TITAN_WIN    = "https://media.tenor.com/KRO_0CcW4PAAAAAC/attack-on-titan-colossal-titan.gif"
GIF_EXILE        = "https://media.tenor.com/K3_QWwTGEwoAAAAC/attack-on-titan-aot.gif"
GIF_TASK_DONE    = "https://media.tenor.com/W4iiMFuqS_EAAAAC/attack-on-titan-aot.gif"

# ─────────────────────────────────────────────────────────────────────────────
# Jigsaw-style tasks
# Each task is a multi-step puzzle: the player receives a SCRAMBLED word/phrase
# and must click the correct fragments in order to reconstruct the answer.
# Step counts: 3–4 steps per task (each step reveals a fragment to pick).
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class JigsawTask:
    title: str
    location: str
    setup_text: str          # flavour / context
    answer_word: str         # the final assembled answer shown on success
    steps: tuple             # tuple of JigsawStep objects
    success_gif: str = GIF_TASK_DONE
    emoji: str = "🧩"


@dataclass(frozen=True)
class JigsawStep:
    instruction: str         # what the player must do at this step
    correct_fragment: str    # the one correct piece to pick
    distractors: tuple       # wrong pieces shown alongside the correct one


JIGSAW_TASKS: list[JigsawTask] = [
    # ── TASK 1 ──────────────────────────────────────────────────────────────
    JigsawTask(
        title="Repair the ODM Blueprint",
        location="Survey Corps Workshop — Wall Rose",
        setup_text=(
            "A critical ODM gear schematic was shredded. You must reassemble the label "
            "on the main propulsion component **piece by piece** before the next expedition."
        ),
        answer_word="GAS CANISTER",
        steps=(
            JigsawStep(
                "**Fragment 1/3 — Pick the correct opening label:**",
                "⬡ GAS",
                ("⬡ BLADE", "⬡ WIRE", "⬡ BOLT")
            ),
            JigsawStep(
                "**Fragment 2/3 — Pick the middle connector:**",
                "◈ [—]",
                ("◈ [///]", "◈ [≈]", "◈ [✗]")
            ),
            JigsawStep(
                "**Fragment 3/3 — Complete the component name:**",
                "⬡ CANISTER",
                ("⬡ TANK", "⬡ PACK", "⬡ BARREL")
            ),
        ),
        emoji="🔧",
    ),
    # ── TASK 2 ──────────────────────────────────────────────────────────────
    JigsawTask(
        title="Decode the Recon Cipher",
        location="Survey Corps Forward Base — Forest of Giant Trees",
        setup_text=(
            "A coded recon message arrived. The cipher key was lost but the letters "
            "are still visible — just scrambled. "
            "Reconstruct **THE NAPE** in the correct slot order."
        ),
        answer_word="THE NAPE",
        steps=(
            JigsawStep(
                "**Slot 1/3 — Which tile goes FIRST?**",
                "[T]",
                ("[N]", "[E]", "[P]")
            ),
            JigsawStep(
                "**Slot 2/3 — Which tile follows?**",
                "[H]",
                ("[A]", "[E]", "[T]")
            ),
            JigsawStep(
                "**Slot 3/3 — Final tile?**",
                "[E]",
                ("[N]", "[P]", "[A]")
            ),
        ),
        emoji="🔐",
    ),
    # ── TASK 3 ──────────────────────────────────────────────────────────────
    JigsawTask(
        title="Seal the Breach Blueprint",
        location="Shiganshina District — Wall Maria Gate",
        setup_text=(
            "The gate engineers gave you a torn diagram of the sealing procedure. "
            "Slot the **four action tiles** into the correct sequence to seal the wall."
        ),
        answer_word="PLUG → BRACE → WELD → SEAL",
        steps=(
            JigsawStep(
                "**Step 1/4 — First action to secure the breach:**",
                "PLUG the gap",
                ("WELD the frame", "SEAL the gate", "BRACE the arch")
            ),
            JigsawStep(
                "**Step 2/4 — Next reinforcement action:**",
                "BRACE the arch",
                ("PLUG the gap", "WELD the frame", "SEAL the gate")
            ),
            JigsawStep(
                "**Step 3/4 — Bonding action:**",
                "WELD the frame",
                ("SEAL the gate", "PLUG the gap", "BRACE the arch")
            ),
            JigsawStep(
                "**Step 4/4 — Final closure:**",
                "SEAL the gate",
                ("BRACE the arch", "WELD the frame", "PLUG the gap")
            ),
        ),
        emoji="🧱",
    ),
    # ── TASK 4 ──────────────────────────────────────────────────────────────
    JigsawTask(
        title="Reconstruct the Flare Code",
        location="Survey Corps Signal Tower",
        setup_text=(
            "The flare codebook got wet and the ink ran. "
            "Match the **correct colour fragment** to each signal meaning:"
        ),
        answer_word="GREEN=REGROUP, RED=ATTACK, BLACK=RETREAT",
        steps=(
            JigsawStep(
                "**Signal 1/3 — 'REGROUP' corresponds to which colour?**",
                "🟢 GREEN",
                ("🔴 RED", "⚫ BLACK", "🔵 BLUE")
            ),
            JigsawStep(
                "**Signal 2/3 — 'ATTACK' corresponds to which colour?**",
                "🔴 RED",
                ("🟢 GREEN", "🔵 BLUE", "⚫ BLACK")
            ),
            JigsawStep(
                "**Signal 3/3 — 'RETREAT' corresponds to which colour?**",
                "⚫ BLACK",
                ("🔴 RED", "🟢 GREEN", "🔵 BLUE")
            ),
        ),
        emoji="🚨",
    ),
    # ── TASK 5 ──────────────────────────────────────────────────────────────
    JigsawTask(
        title="Reassemble the Garrison Map",
        location="Trost District Command Room",
        setup_text=(
            "The defensive map of Trost was torn into four quadrants. "
            "Arrange the **zone labels** in correct compass order: N → E → S → W."
        ),
        answer_word="NORTH → EAST → SOUTH → WEST",
        steps=(
            JigsawStep(
                "**Quadrant 1/4 — Which zone is NORTH?**",
                "🔼 Inner Wall Gate",
                ("🔼 Rooftop Market", "🔼 East Barracks", "🔼 Outer Ridge")
            ),
            JigsawStep(
                "**Quadrant 2/4 — Which zone is EAST?**",
                "▶ East Barracks",
                ("▶ Inner Wall Gate", "▶ West Garrison", "▶ Outer Ridge")
            ),
            JigsawStep(
                "**Quadrant 3/4 — Which zone is SOUTH?**",
                "🔽 Outer Ridge",
                ("🔽 Inner Wall Gate", "🔽 East Barracks", "🔽 Rooftop Market")
            ),
            JigsawStep(
                "**Quadrant 4/4 — Which zone is WEST?**",
                "◀ West Garrison",
                ("◀ Outer Ridge", "◀ Inner Wall Gate", "◀ East Barracks")
            ),
        ),
        emoji="🗺️",
    ),
    # ── TASK 6 ──────────────────────────────────────────────────────────────
    JigsawTask(
        title="Restore the Titan Sketch",
        location="Survey Corps Research Lab",
        setup_text=(
            "A scientist's sketch of the Survey Corps emblem was scrambled. "
            "Click the correct puzzle pieces **in order** to restore the Wings of Freedom."
        ),
        answer_word="WINGS OF FREEDOM",
        steps=(
            JigsawStep(
                "**Piece 1/3 — Left wing fragment:**",
                "◤ Left Wing",
                ("◤ Left Claw", "◤ Left Fin", "◤ Left Scale")
            ),
            JigsawStep(
                "**Piece 2/3 — Centre body fragment:**",
                "◆ Eagle Crest",
                ("◆ Sword Cross", "◆ Rose Seal", "◆ Crown Crest")
            ),
            JigsawStep(
                "**Piece 3/3 — Right wing fragment:**",
                "◥ Right Wing",
                ("◥ Right Claw", "◥ Right Fin", "◥ Right Scale")
            ),
        ),
        emoji="🦅",
    ),
    # ── TASK 7 ──────────────────────────────────────────────────────────────
    JigsawTask(
        title="Rebuild the Thunder Spear Casing",
        location="Armament Depot — Fort Salta",
        setup_text=(
            "A thunder spear casing fell and the component labels detached. "
            "Reassemble the weapon label in **assembly order**: tip → shaft → trigger."
        ),
        answer_word="TIP → SHAFT → TRIGGER",
        steps=(
            JigsawStep(
                "**Component 1/3 — Explosive tip:**",
                "💥 WARHEAD TIP",
                ("💥 GRIP HANDLE", "💥 LAUNCH TUBE", "💥 TRIGGER RING")
            ),
            JigsawStep(
                "**Component 2/3 — Main body:**",
                "📏 SHAFT TUBE",
                ("📏 WARHEAD TIP", "📏 TRIGGER RING", "📏 GAS VENT")
            ),
            JigsawStep(
                "**Component 3/3 — Activation piece:**",
                "🔘 TRIGGER RING",
                ("🔘 SHAFT TUBE", "🔘 WARHEAD TIP", "🔘 GAS VENT")
            ),
        ),
        emoji="💥",
    ),
    # ── TASK 8 ──────────────────────────────────────────────────────────────
    JigsawTask(
        title="Decipher the Ackerman File",
        location="Military Police Archive — Wall Sina",
        setup_text=(
            "The Ackerman bloodline file has been deliberately scrambled by royal agents. "
            "Restore the **three key facts** in the correct order."
        ),
        answer_word="PROTECT → AWAKEN → INSTINCT",
        steps=(
            JigsawStep(
                "**Record 1/3 — The Ackerman's primary drive is to:**",
                "PROTECT their host",
                ("OBEY the crown", "SENSE danger nearby", "UNLOCK past memories")
            ),
            JigsawStep(
                "**Record 2/3 — Their power activates when:**",
                "AWAKEN under extreme will",
                ("PROTECT their host", "OBEY the crown", "UNLOCK past memories")
            ),
            JigsawStep(
                "**Record 3/3 — The trait gives access to:**",
                "INSTINCT of past Ackermans",
                ("AWAKEN under extreme will", "SENSE danger nearby", "PROTECT their host")
            ),
        ),
        emoji="🩸",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Jigsaw View — multi-step interactive puzzle
# ─────────────────────────────────────────────────────────────────────────────
class JigsawStepButton(discord.ui.Button):
    def __init__(self, label: str, is_correct: bool, step_index: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.is_correct = is_correct
        self.step_index = step_index

    async def callback(self, interaction: discord.Interaction):
        assert isinstance(self.view, JigsawTaskView)
        await self.view.handle_pick(interaction, self.label, self.is_correct)


class JigsawTaskView(discord.ui.View):
    """Multi-step jigsaw puzzle. Each step presents fragment buttons."""

    def __init__(
        self,
        cog: "TitanGameCog",
        game_channel_id: int,
        player_id: int,
        task: JigsawTask,
    ):
        super().__init__(timeout=180)
        self.cog = cog
        self.game_channel_id = game_channel_id
        self.player_id = player_id
        self.task = task
        self.current_step: int = 0
        self.wrong_picks: int = 0
        self._load_step_buttons()

    def _load_step_buttons(self) -> None:
        self.clear_items()
        step = self.task.steps[self.current_step]
        choices = [step.correct_fragment] + list(step.distractors)
        random.shuffle(choices)
        for choice in choices:
            self.add_item(
                JigsawStepButton(
                    label=choice,
                    is_correct=(choice == step.correct_fragment),
                    step_index=self.current_step,
                )
            )

    def _progress_bar(self) -> str:
        total = len(self.task.steps)
        filled = self.current_step
        return "🟩" * filled + "⬜" * (total - filled) + f" {filled}/{total}"

    def build_embed(self, note: Optional[str] = None) -> discord.Embed:
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        step = self.task.steps[self.current_step]

        embed = discord.Embed(
            title=f"{self.task.emoji}  {self.task.title}",
            color=discord.Color.dark_orange(),
        )
        embed.add_field(name="📍 Location", value=self.task.location, inline=False)
        embed.add_field(name="📖 Mission", value=self.task.setup_text, inline=False)
        embed.add_field(name="🧩 Puzzle Progress", value=self._progress_bar(), inline=False)
        embed.add_field(name="👇 Your Turn", value=step.instruction, inline=False)

        if self.wrong_picks > 0:
            embed.add_field(
                name="⚠️ Wrong picks",
                value=f"❌ × {self.wrong_picks} — keep trying!",
                inline=False,
            )

        if game:
            p = game.players.get(self.player_id)
            done, req = game.get_task_progress()
            personal = p.tasks_completed if p else 0
            embed.add_field(
                name="📊 Progress",
                value=(
                    f"Your tasks: **{personal}/{game.TASKS_PER_PLAYER}**\n"
                    f"Squad: **{done}/{req or game.total_tasks_required}**"
                ),
                inline=False,
            )
        if note:
            embed.add_field(name="📢 Note", value=note, inline=False)
        embed.set_footer(text=f"Round {game.round_number if game else '—'} • Piece together the truth!")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                "🔒 This puzzle board is locked to the scout who opened it.", ephemeral=True
            )
            return False
        return True

    async def handle_pick(self, interaction: discord.Interaction, label: str, is_correct: bool):
        if not is_correct:
            self.wrong_picks += 1
            await interaction.response.edit_message(
                embed=self.build_embed("❌ Wrong piece! Try again."), view=self
            )
            return

        self.current_step += 1

        if self.current_step < len(self.task.steps):
            # Advance to next step
            self._load_step_buttons()
            await interaction.response.edit_message(
                embed=self.build_embed("✅ Correct piece! Keep going."), view=self
            )
            return

        # All steps complete — submit task
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game:
            await interaction.response.edit_message(
                content="This puzzle expired — the game ended.", embed=None, view=None
            )
            return

        self.stop()
        success, msg = game.do_task(self.player_id)
        done, req = game.get_task_progress()

        result = discord.Embed(
            title=f"✅ {self.task.title} — Complete!",
            description=(
                f"🧩 **{self.task.answer_word}** reconstructed successfully!\n\n"
                f"**{msg}**\n"
                f"Squad progress: **{done}/{req or game.total_tasks_required}**"
            ),
            color=discord.Color.green(),
        )
        result.set_image(url=self.task.success_gif)
        result.set_footer(text=f"Round {game.round_number} • Wrong guesses: {self.wrong_picks}")
        await interaction.response.edit_message(embed=result, view=None)

        if not success:
            return

        winner = game.check_win()
        if winner:
            ch = self.cog.get_active_channel(game)
            if ch:
                await self.cog.end_game(ch, game, winner)


# ─────────────────────────────────────────────────────────────────────────────
# Lobby View
# ─────────────────────────────────────────────────────────────────────────────
class TitanLobbyView(discord.ui.View):
    def __init__(self, cog: "TitanGameCog", channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="⚔️ Join Lobby", style=discord.ButtonStyle.primary)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_lobby_game(self.channel_id)
        if not game:
            await interaction.response.send_message("Lobby not found.", ephemeral=True)
            return
        success, msg = game.add_player(interaction.user.id)
        if not success:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        await interaction.message.edit(embed=self.cog.build_lobby_embed(game), view=self)
        await interaction.response.send_message(
            f"✅ You joined the squad. ({len(game.players)}/{game.MAX_PLAYERS})",
            ephemeral=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Eliminate select — BUG FIX: always fetches fresh game ref, re-shows after bad kill
# ─────────────────────────────────────────────────────────────────────────────
class EliminateSelectView(discord.ui.View):
    def __init__(self, cog: "TitanGameCog", game_channel_id: int, shifter_id: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.game_channel_id = game_channel_id
        self.shifter_id = shifter_id
        self._refresh_options()

    def _refresh_options(self) -> None:
        """Rebuild the select menu with currently alive Survey Corps."""
        self.clear_items()
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game:
            self.add_item(discord.ui.Button(label="No active game", disabled=True))
            return
        options = [
            discord.SelectOption(
                label=p.character_name,
                value=str(uid),
                description=f"User: {uid}",
            )
            for uid, p in game.players.items()
            if p.is_alive and p.role == Role.SURVEY_CORPS
        ]
        if not options:
            self.add_item(discord.ui.Button(label="No valid targets", disabled=True))
            return
        sel = discord.ui.Select(
            placeholder="Choose a Survey Corps target…",
            options=options[:25],
        )
        sel.callback = self.select_cb
        self.add_item(sel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.shifter_id:
            await interaction.response.send_message(
                "This panel belongs to another shifter.", ephemeral=True
            )
            return False
        return True

    async def select_cb(self, interaction: discord.Interaction):
        # Always fetch the LATEST game state — fixes the stale-ref kill bug
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game:
            await interaction.response.edit_message(content="Game no longer active.", view=None)
            return

        target_id = int(interaction.data["values"][0])
        success, msg = game.eliminate(self.shifter_id, target_id)
        if not success:
            await interaction.response.edit_message(content=msg, view=self)
            return

        # Kill succeeded — close menu and post kill notice
        await interaction.response.edit_message(
            content=f"💀 {msg}", view=None
        )
        active_channel = self.cog.get_active_channel(game)
        if active_channel:
            target_player = game.players[target_id]
            kill_embed = discord.Embed(
                title="☠️ Casualty Report",
                description=(
                    f"<@{target_id}> (**{target_player.character_name}**) "
                    "was devoured somewhere in the chaos."
                ),
                color=discord.Color.red(),
            )
            kill_embed.set_image(url=GIF_KILL)
            await active_channel.send(embed=kill_embed)
            winner = game.check_win()
            if winner:
                await self.cog.end_game(active_channel, game, winner)


# ─────────────────────────────────────────────────────────────────────────────
# Shifter DM control panel — sends a FRESH EliminateSelectView each press
# ─────────────────────────────────────────────────────────────────────────────
class ShifterControlView(discord.ui.View):
    def __init__(self, cog: "TitanGameCog", game_channel_id: int, user_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_channel_id = game_channel_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This panel belongs to another shifter.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="🗡️ Open Kill Menu", style=discord.ButtonStyle.danger)
    async def kill_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game:
            await interaction.response.send_message("Game is no longer active.", ephemeral=False)
            return
        p = game.players.get(self.user_id)
        if not p or p.role != Role.TITAN_SHIFTER or not p.is_alive:
            await interaction.response.send_message("You cannot use titan powers right now.", ephemeral=False)
            return
        cooldown = game.seconds_until_kill(self.user_id)
        if cooldown > 0:
            await interaction.response.send_message(
                f"⏳ Titan power recharging — **{cooldown}s** remaining.", ephemeral=False
            )
            return
        # ← BUG FIX: create a brand-new EliminateSelectView with fresh target list
        view = EliminateSelectView(self.cog, self.game_channel_id, self.user_id)
        await interaction.response.send_message(
            "🔴 Choose your target carefully…", view=view, ephemeral=False
        )

    @discord.ui.button(label="⏱️ Cooldown Status", style=discord.ButtonStyle.secondary)
    async def cooldown_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game:
            await interaction.response.send_message("Game is no longer active.", ephemeral=False)
            return
        cd = game.seconds_until_kill(self.user_id)
        if cd > 0:
            await interaction.response.send_message(f"⏳ Kill ready in **{cd}s**.", ephemeral=False)
        else:
            await interaction.response.send_message("✅ Kill is **ready now**!", ephemeral=False)


# ─────────────────────────────────────────────────────────────────────────────
# Main game channel view
# ─────────────────────────────────────────────────────────────────────────────
class TitanGameTempView(discord.ui.View):
    def __init__(self, cog: "TitanGameCog", game_channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_channel_id = game_channel_id

    def get_game(self) -> Optional[TitanGameEngine]:
        return self.cog.get_game_by_temp_channel(self.game_channel_id)

    @discord.ui.button(label="🧩 Do Task", style=discord.ButtonStyle.success)
    async def task_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _send_task(self.cog, self.game_channel_id, interaction.user, interaction=interaction)

    @discord.ui.button(label="📡 Squad Status", style=discord.ButtonStyle.secondary)
    async def status_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.get_game()
        if not game:
            await interaction.response.send_message("No active game.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=self.cog.build_status_embed(game, interaction.user.id), ephemeral=True
        )

    @discord.ui.button(label="🚨 Emergency Meeting", style=discord.ButtonStyle.primary)
    async def meeting_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.get_game()
        if not game:
            await interaction.response.send_message("No active game.", ephemeral=True)
            return
        success, err = game.call_meeting(interaction.user.id)
        if not success:
            await interaction.response.send_message(err or "You cannot call a meeting right now.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🚨 EMERGENCY MEETING!",
            description=(
                f"{interaction.user.mention} fired the emergency flare!\n\n"
                "All scouts must gather. You have **60 seconds** to discuss and vote."
            ),
            color=discord.Color.gold(),
        )
        embed.set_image(url=GIF_MEETING)
        await interaction.response.send_message(
            content="@everyone",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        await self.cog.begin_voting(interaction.channel, game)


# ─────────────────────────────────────────────────────────────────────────────
# Shared task dispatch helper (used by both button and /task command)
# ─────────────────────────────────────────────────────────────────────────────
async def _send_task(
    cog: "TitanGameCog",
    game_channel_id: int,
    user: discord.User | discord.Member,
    *,
    interaction: Optional[discord.Interaction] = None,
    ctx: Optional[commands.Context] = None,
) -> None:
    game = cog.get_game_by_temp_channel(game_channel_id)

    async def _reply(content: str) -> None:
        if interaction:
            if not interaction.response.is_done():
                await interaction.response.send_message(content, ephemeral=True)
            else:
                await interaction.followup.send(content, ephemeral=True)
        elif ctx:
            await ctx.send(content, ephemeral=True)

    async def _send_view(embed: discord.Embed, view: discord.ui.View) -> None:
        if interaction:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        elif ctx:
            await ctx.send(embed=embed, view=view)

    if not game:
        await _reply("No active game in this channel.")
        return
    p = game.players.get(user.id)
    if not p or not p.is_alive:
        await _reply("Only living players can do tasks.")
        return
    if p.role == Role.TITAN_SHIFTER:
        await _reply("🎭 Shifters only *pretend* to work. Your real panel is in your DMs.")
        return
    if p.tasks_completed >= game.TASKS_PER_PLAYER:
        await _reply("✅ You already completed all your tasks! Wait for the others.")
        return
    if game.state != GameState.EXPLORATION:
        await _reply("Tasks can only be done during the Exploration phase.")
        return

    idx = game.get_next_task_index(user.id)
    if idx is None or idx >= len(JIGSAW_TASKS):
        await _reply("You have no more tasks assigned right now.")
        return

    task = JIGSAW_TASKS[idx]
    view = JigsawTaskView(cog, game_channel_id, user.id, task)
    await _send_view(view.build_embed(), view)


# ─────────────────────────────────────────────────────────────────────────────
# Main Cog
# ─────────────────────────────────────────────────────────────────────────────
class TitanGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games: dict[int, TitanGameEngine] = {}
        self.vote_tasks: dict[int, asyncio.Task] = {}

    def cog_unload(self):
        for t in self.vote_tasks.values():
            if not t.done():
                t.cancel()

    # ── Lookup helpers ────────────────────────────────────────────────────
    def get_lobby_game(self, channel_id: int) -> Optional[TitanGameEngine]:
        return self.games.get(channel_id)

    def get_game_by_channel(self, channel_id: int) -> Optional[TitanGameEngine]:
        for g in self.games.values():
            if g.state == GameState.LOBBY and g.channel_id == channel_id:
                return g
            if g.game_channel_id == channel_id:
                return g
        return None

    def get_game_by_player(self, user_id: int) -> Optional[TitanGameEngine]:
        for g in self.games.values():
            if user_id in g.players:
                return g
        return None

    def get_game_by_temp_channel(self, ch_id: int) -> Optional[TitanGameEngine]:
        for g in self.games.values():
            if g.game_channel_id == ch_id:
                return g
        return None

    def get_active_channel(self, game: TitanGameEngine) -> Optional[discord.TextChannel]:
        ch = self.bot.get_channel(game.game_channel_id or game.channel_id)
        return ch if isinstance(ch, discord.TextChannel) else None

    # ── Embed builders ────────────────────────────────────────────────────
    def build_lobby_embed(self, game: TitanGameEngine) -> discord.Embed:
        players = "\n".join(f"<@{uid}>" for uid in game.players)
        embed = discord.Embed(
            title="⚔️ Titan Shifters — Lobby",
            description=(
                f"Host: <@{game.host_id}>\n"
                f"Players: **{len(game.players)}/{game.MAX_PLAYERS}** (min {game.MIN_PLAYERS})\n"
                "Use `/titan-game join` or the button below to enlist."
            ),
            color=discord.Color.dark_theme(),
        )
        embed.add_field(name="🪖 Current Squad", value=players or "No scouts yet.", inline=False)
        embed.set_footer(text="The Walls need defenders. Will you answer the call?")
        return embed

    def build_status_embed(self, game: TitanGameEngine, viewer_id: Optional[int] = None) -> discord.Embed:
        alive = len(game.alive_players())
        embed = discord.Embed(
            title=f"📊 Field Status — Round {game.round_number}",
            color=discord.Color.gold(),
        )
        embed.description = (
            f"Phase: **{game.state.name.title()}**\n"
            f"Round: **{game.round_number}**\n"
            f"Alive: **{alive}/{len(game.players)}**\n"
            f"Survey Corps: **{len(game.alive_survey_corps())}** alive\n"
            f"Shifters: **{len(game.alive_shifters())}** alive"
        )
        done, req = game.get_task_progress()
        embed.add_field(
            name="🎯 Mission Progress",
            value=f"Squad tasks: **{done}/{req or game.total_tasks_required}**",
            inline=False,
        )
        mc = game.seconds_until_meeting()
        embed.add_field(
            name="🚨 Meeting Cooldown",
            value="✅ Meeting ready!" if mc == 0 else f"⏳ **{mc}s** until next meeting allowed",
            inline=False,
        )
        if viewer_id and viewer_id in game.players:
            p = game.players[viewer_id]
            if p.role == Role.SURVEY_CORPS:
                embed.add_field(
                    name="📋 Your Assignment",
                    value=(
                        f"Tasks done: **{p.tasks_completed}/{game.TASKS_PER_PLAYER}**\n"
                        f"Remaining: **{game.TASKS_PER_PLAYER - p.tasks_completed}**"
                    ),
                    inline=False,
                )
            else:
                cd = game.seconds_until_kill(viewer_id)
                embed.add_field(
                    name="🔴 Titan Kill Window",
                    value="✅ Ready!" if cd == 0 else f"⏳ Cooldown: **{cd}s**",
                    inline=False,
                )
        if game.state == GameState.VOTING:
            embed.add_field(
                name="🗳️ Voting Clock",
                value=f"**{game.get_vote_time_remaining()}s** left",
                inline=False,
            )
        return embed

    # ── Lobby message refresh ─────────────────────────────────────────────
    async def refresh_lobby_message(self, game: TitanGameEngine):
        if not game.lobby_message_id:
            return
        ch = self.bot.get_channel(game.channel_id)
        if not isinstance(ch, discord.TextChannel):
            return
        try:
            msg = await ch.fetch_message(game.lobby_message_id)
            await msg.edit(embed=self.build_lobby_embed(game), view=TitanLobbyView(self, game.channel_id))
        except discord.HTTPException:
            pass

    # ── Vote task helpers ─────────────────────────────────────────────────
    def cancel_vote_task(self, game: TitanGameEngine):
        t = self.vote_tasks.pop(game.channel_id, None)
        cur = asyncio.current_task()
        if t and not t.done() and t is not cur:
            t.cancel()

    async def begin_voting(self, channel: discord.abc.Messageable, game: TitanGameEngine):
        if not game.start_voting():
            return
        embed = discord.Embed(
            title="🗳️ Voting Begins!",
            description=(
                "Use `Aot vote @user` or `/vote @user` to cast your vote within **60 seconds**.\n"
                "Skip with the command and no target."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_image(url=GIF_VOTE_START)
        await channel.send(embed=embed)
        self.cancel_vote_task(game)
        self.vote_tasks[game.channel_id] = self.bot.loop.create_task(
            self.vote_timeout_task(channel.id, game.channel_id)
        )

    async def vote_timeout_task(self, channel_id: int, game_key: int):
        try:
            await asyncio.sleep(TitanGameEngine.VOTE_DURATION_SECONDS)
            game = self.games.get(game_key)
            if not game or game.state != GameState.VOTING:
                return
            ch = self.bot.get_channel(channel_id)
            if isinstance(ch, discord.TextChannel):
                await ch.send("⏰ Voting time is up! Tallying results now…")
                await self.resolve_votes(ch, game)
        except asyncio.CancelledError:
            return

    async def lobby_timeout_task(self, channel_id: int, game: TitanGameEngine):
        await asyncio.sleep(240)
        if game.state == GameState.LOBBY and self.games.get(channel_id) == game:
            del self.games[channel_id]
            ch = self.bot.get_channel(channel_id)
            if isinstance(ch, discord.TextChannel):
                await ch.send("⏰ Lobby cancelled after 4 minutes of inactivity.")

    # ── Commands ──────────────────────────────────────────────────────────
    @commands.hybrid_group(
        name="titan-game",
        description="Titan Shifters social deduction game",
        invoke_without_command=True,
    )
    async def titan_game(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @titan_game.command(name="create", description="Create a new Titan Shifters lobby")
    async def tg_create(self, ctx: commands.Context):
        if self.get_lobby_game(ctx.channel.id) or self.get_game_by_channel(ctx.channel.id):
            await ctx.send("A game is already tied to this channel.", ephemeral=True)
            return
        game = TitanGameEngine(ctx.guild.id, ctx.channel.id, ctx.author.id)
        self.games[ctx.channel.id] = game
        view = TitanLobbyView(self, ctx.channel.id)
        msg = await ctx.send(embed=self.build_lobby_embed(game), view=view)
        game.lobby_message_id = msg.id
        self.bot.loop.create_task(self.lobby_timeout_task(ctx.channel.id, game))

    @titan_game.command(name="join", description="Join the lobby")
    async def tg_join(self, ctx: commands.Context):
        game = self.get_lobby_game(ctx.channel.id)
        if not game:
            await ctx.send("No lobby found.", ephemeral=True)
            return
        success, msg = game.add_player(ctx.author.id)
        if success:
            await self.refresh_lobby_message(game)
            await ctx.send(f"{ctx.author.mention} joined. ({len(game.players)}/{game.MAX_PLAYERS})")
        else:
            await ctx.send(msg, ephemeral=True)

    @titan_game.command(name="leave", description="Leave the lobby")
    async def tg_leave(self, ctx: commands.Context):
        game = self.get_lobby_game(ctx.channel.id)
        if not game or game.state != GameState.LOBBY:
            await ctx.send("You can only leave during the lobby phase.", ephemeral=True)
            return
        if not game.remove_player(ctx.author.id):
            await ctx.send("You are not in the lobby.", ephemeral=True)
            return
        if not game.players:
            del self.games[ctx.channel.id]
            await ctx.send("Everyone left. Lobby closed.")
            return
        await self.refresh_lobby_message(game)
        await ctx.send(f"{ctx.author.mention} left. Host: <@{game.host_id}>.")

    @titan_game.command(name="start", description="Start the game (host only)")
    async def tg_start(self, ctx: commands.Context):
        game = self.get_lobby_game(ctx.channel.id)
        if not game:
            await ctx.send("No lobby found.", ephemeral=True)
            return
        if ctx.author.id != game.host_id:
            await ctx.send("Only the host can start.", ephemeral=True)
            return
        success, msg = game.start_game()
        if not success:
            await ctx.send(msg, ephemeral=True)
            return

        guild = ctx.guild
        category = guild.get_channel(GAME_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            try:
                category = await guild.fetch_channel(GAME_CATEGORY_ID)
            except discord.HTTPException:
                category = None
        if not isinstance(category, discord.CategoryChannel):
            category = ctx.channel.category

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for uid in game.players:
            m = guild.get_member(uid)
            if m:
                overwrites[m] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

        game_channel = await guild.create_text_channel(
            name=f"shifters-r{game.round_number}-{random.randint(1000,9999)}",
            category=category,
            overwrites=overwrites,
        )
        game.game_channel_id = game_channel.id

        # Update lobby message
        if game.lobby_message_id:
            lch = self.bot.get_channel(game.channel_id)
            if isinstance(lch, discord.TextChannel):
                try:
                    lmsg = await lch.fetch_message(game.lobby_message_id)
                    await lmsg.edit(
                        embed=discord.Embed(
                            title="🚀 Squad Deployed!",
                            description=f"Game moved to {game_channel.mention}. Roles sent via DM.",
                            color=discord.Color.dark_blue(),
                        ),
                        view=None,
                    )
                except discord.HTTPException:
                    pass

        # Ping every player
        mentions = " ".join(f"<@{uid}>" for uid in game.players)
        await ctx.send(
            content=f"⚔️ **Titan Shifters — Round {game.round_number} begins!** {mentions}\nHead to {game_channel.mention} — roles incoming via DM!",
            allowed_mentions=discord.AllowedMentions(users=True),
        )

        # Send DMs
        for uid, p in game.players.items():
            user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
            embed = discord.Embed(
                title="🔴 Secret Transmission" if p.role == Role.TITAN_SHIFTER else "🟢 Operation Briefing"
            )
            file_obj = None
            if p.role == Role.TITAN_SHIFTER:
                embed.color = discord.Color.red()
                embed.description = (
                    f"You are the **{p.character_name}**.\n\n"
                    "**Role:** 🔴 Titan Shifter\n"
                    "Blend in, survive the vote, and devour the Survey Corps.\n"
                    "Your private kill panel is below."
                )
                embed.add_field(
                    name="⚠️ Shifter Tips",
                    value=(
                        "• Use the kill menu for each kill — it refreshes after every one.\n"
                        "• Kill cooldown: **45s** — plan ahead.\n"
                        "• Meeting cooldown is **30s** after any meeting ends."
                    ),
                    inline=False,
                )
            else:
                embed.color = discord.Color.green()
                embed.description = (
                    f"You are **{p.character_name}**.\n\n"
                    "**Role:** 🟢 Survey Corps Member\n"
                    "Complete your jigsaw tasks, catch the shifter, and survive."
                )
                embed.add_field(
                    name="📋 Crewmate Tips",
                    value=(
                        "• Use **🧩 Do Task** or `Aot task` to get a jigsaw puzzle.\n"
                        "• Assemble pieces in the right order — no boring quizzes!\n"
                        f"• You have **{game.TASKS_PER_PLAYER}** tasks to complete.\n"
                        "• Call 🚨 Emergency Meeting if you spot a shifter."
                    ),
                    inline=False,
                )
            embed.add_field(
                name="🏟️ Game Channel",
                value=f"Head to {game_channel.mention}!",
                inline=False,
            )
            if p.image_url:
                file_obj = attach_image(embed, p.image_url, as_thumbnail=True)
            elif p.role == Role.SURVEY_CORPS and SURVEY_CORPS_IMAGES:
                file_obj = attach_image(embed, random.choice(SURVEY_CORPS_IMAGES), as_thumbnail=True)
            try:
                if file_obj:
                    await user.send(embed=embed, file=file_obj)
                else:
                    await user.send(embed=embed)
                if p.role == Role.TITAN_SHIFTER:
                    await user.send(
                        "🔴 **Private Titan Control Panel** — only you can use this.",
                        view=ShifterControlView(self, game_channel.id, uid),
                    )
            except discord.Forbidden:
                await ctx.channel.send(
                    f"⚠️ <@{uid}> has DMs disabled — they will miss role info."
                )

        # Game channel intro
        missions = [
            "Seal the breach before titans flood the district",
            "Escort refugees through collapsing rooftops",
            "Scout a forest approach and mark titan nests",
            "Recover supply carts stranded beyond the inner gate",
            "Hunt for a hidden shifter moving inside the smoke",
            "Defend Trost District from the Pure Titan advance",
            "Investigate Wall Titan sightings near Wall Rose",
        ]
        embed = discord.Embed(
            title=f"⚔️ Round {game.round_number} — Expedition Begins!",
            description=(
                "Steel cables scream through the air as the squad enters hostile territory.\n\n"
                f"**📜 Mission:** {random.choice(missions)}\n"
                f"**🧩 Tasks:** {game.TASKS_PER_PLAYER} jigsaw tasks per crewmate\n"
                f"**⏱️ Kill Cooldown:** {game.KILL_COOLDOWN_SECONDS}s\n"
                f"**🚨 Meeting Cooldown:** {game.MEETING_COOLDOWN_SECONDS}s after each meeting\n"
                f"**👥 Players:** {len(game.players)} deployed"
            ),
            color=discord.Color.dark_blue(),
        )
        embed.add_field(
            name="📣 How to Play",
            value=(
                "🧩 **Crewmates** → Click **Do Task** or use `Aot task` for jigsaw puzzles.\n"
                "🚨 **Emergency Meeting** → Call a vote if you suspect a shifter.\n"
                "🔴 **Shifters** → Kill panel is in your **DMs** (works every kill!).\n"
                "🗳️ Vote ends after **60s** automatically."
            ),
            inline=False,
        )
        embed.add_field(
            name="🪖 Players",
            value=" ".join(f"<@{uid}>" for uid in game.players),
            inline=False,
        )
        embed.set_image(url=GIF_GAME_START)
        embed.set_footer(text="May the Walls protect you — or may the titans feast tonight.")

        view = TitanGameTempView(self, game_channel.id)
        await game_channel.send(embed=embed, view=view)

    @titan_game.command(name="status", description="Check game status")
    async def tg_status(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("No active game here.", ephemeral=True)
            return
        await ctx.send(embed=self.build_status_embed(game, ctx.author.id))

    @titan_game.command(name="stop", description="Force-end the game (host/admin)")
    async def tg_stop(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id) or self.get_game_by_player(ctx.author.id)
        if not game:
            await ctx.send("No active game found.", ephemeral=True)
            return
        if ctx.author.id != game.host_id and not ctx.author.guild_permissions.administrator:
            await ctx.send("Only the host or an admin can stop the game.", ephemeral=True)
            return
        self.cancel_vote_task(game)
        self.games.pop(game.channel_id, None)
        await ctx.send("🛑 Game forcefully stopped.")
        ch = self.get_active_channel(game)
        if ch and ch.id != ctx.channel.id:
            await ch.send("🛑 The expedition was aborted by command.")
        if game.game_channel_id:
            self.bot.loop.create_task(self.cleanup_temp_channel(game))

    @commands.hybrid_command(name="eliminate", description="Eliminate a player (Titan Shifter only)")
    async def eliminate(self, ctx: commands.Context, target: discord.User):
        game = self.get_game_by_player(ctx.author.id)
        if not game:
            await ctx.send("You are not in any game.", ephemeral=True)
            return
        if not isinstance(ctx.channel, discord.DMChannel) and not ctx.interaction:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            await ctx.author.send("⚠️ You used `Aot eliminate` in public. Be more careful!")
        success, msg = game.eliminate(ctx.author.id, target.id)
        if not success:
            await ctx.send(msg, ephemeral=True)
            return
        await ctx.send(msg, ephemeral=True)
        ch = self.get_active_channel(game)
        if ch:
            tp = game.players[target.id]
            embed = discord.Embed(
                title="☠️ Casualty Report",
                description=f"{target.mention} (**{tp.character_name}**) was devoured by a Titan.",
                color=discord.Color.red(),
            )
            embed.set_image(url=GIF_KILL)
            await ch.send(embed=embed)
            winner = game.check_win()
            if winner:
                await self.end_game(ch, game, winner)

    @commands.hybrid_command(name="meeting", description="Call an emergency meeting")
    async def meeting(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("No active game here.", ephemeral=True)
            return
        success, err = game.call_meeting(ctx.author.id)
        if not success:
            await ctx.send(err or "You cannot call a meeting now.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🚨 EMERGENCY MEETING!",
            description=(
                f"{ctx.author.mention} fired the emergency flare!\n\n"
                "Gather! You have **60 seconds** to discuss and vote."
            ),
            color=discord.Color.gold(),
        )
        embed.set_image(url=GIF_MEETING)
        await ctx.send(
            content="@everyone",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        await self.begin_voting(ctx.channel, game)

    @commands.hybrid_command(name="task", description="Start your next jigsaw task (Survey Corps only)")
    async def task_cmd(self, ctx: commands.Context):
        """Allows players to start a task without the button — `Aot task` or `/task`."""
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("No active game in this channel.", ephemeral=True)
            return
        await _send_task(self, game.game_channel_id or ctx.channel.id, ctx.author, ctx=ctx)

    @commands.hybrid_command(name="vote", description="Vote to exile a player")
    async def vote(self, ctx: commands.Context, target: discord.Member = None):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("No active game here.", ephemeral=True)
            return
        target_id = target.id if target else None
        success, msg = game.vote(ctx.author.id, target_id)
        if not success:
            await ctx.send(msg, ephemeral=True)
            return
        if target_id is None:
            await ctx.send(f"{ctx.author.mention} skipped their vote.")
        else:
            await ctx.send(f"🗳️ {ctx.author.mention} locked in a vote.")
        if all(p.has_voted for p in game.alive_players()):
            await self.resolve_votes(ctx.channel, game)

    # ── Vote resolution ───────────────────────────────────────────────────
    async def resolve_votes(self, channel: discord.TextChannel, game: TitanGameEngine):
        self.cancel_vote_task(game)
        exiled_id, is_tie = game.get_vote_results()

        embed = discord.Embed(title="⚖️ The Verdict", color=discord.Color.dark_theme())
        if is_tie or exiled_id is None:
            embed.description = "🤝 Tie — **no one was exiled.**"
        else:
            ep = game.players[exiled_id]
            embed.description = f"<@{exiled_id}> (**{ep.character_name}**) was exiled."
            if ep.role == Role.TITAN_SHIFTER:
                embed.color = discord.Color.green()
                embed.description += "\n\n✅ **They WERE a Titan Shifter!** Corps celebrates!"
            else:
                embed.color = discord.Color.red()
                embed.description += "\n\n❌ **They were NOT a Titan Shifter.** An innocent falls."
        embed.set_image(url=GIF_EXILE)
        await channel.send(embed=embed)

        winner = game.check_win()
        if winner:
            await self.end_game(channel, game, winner)
            return

        # Advance round + set meeting cooldown
        game.advance_round()
        game.end_meeting_set_cooldown()
        game.state = GameState.EXPLORATION
        await channel.send(
            f"💨 Meeting ends. Round **{game.round_number}** begins!\n"
            f"🚨 Next meeting available in **{game.MEETING_COOLDOWN_SECONDS}s**.\n"
            "Survey Corps — back to tasks. Shifters — stay hidden."
        )

    # ── End game ──────────────────────────────────────────────────────────
    async def end_game(self, channel: discord.TextChannel, game: TitanGameEngine, winner: Role):
        self.cancel_vote_task(game)
        game.state = GameState.GAME_OVER

        embed = discord.Embed(title="🏁 Game Over", color=discord.Color.gold())
        if winner == Role.SURVEY_CORPS:
            embed.description = (
                "🎉 **Survey Corps wins!**\n\n"
                "Every Titan Shifter was rooted out. Humanity holds the line!"
            )
            embed.set_image(url=GIF_SC_WIN)
        else:
            embed.description = (
                "💀 **Titans win!**\n\n"
                "The Titan Shifters overwhelmed the expedition. The district falls."
            )
            embed.set_image(url=GIF_TITAN_WIN)

        embed.add_field(
            name="🔴 Titan Shifters",
            value="\n".join(
                f"<@{p.user_id}> — **{p.character_name}**"
                for p in game.players.values() if p.role == Role.TITAN_SHIFTER
            ) or "None",
            inline=False,
        )
        embed.add_field(
            name="🟢 Survey Corps Results",
            value="\n".join(
                f"<@{p.user_id}> — {p.character_name} — {p.tasks_completed}/{game.TASKS_PER_PLAYER} tasks"
                for p in game.players.values() if p.role == Role.SURVEY_CORPS
            ) or "None",
            inline=False,
        )
        embed.set_footer(text=f"Game lasted {game.round_number} round(s).")
        await channel.send(embed=embed)

        lch = self.bot.get_channel(game.channel_id)
        if isinstance(lch, discord.TextChannel) and lch.id != channel.id:
            await lch.send(f"🏁 Titan Shifters ended in {channel.mention} after {game.round_number} round(s). GG!")

        self.games.pop(game.channel_id, None)
        if game.game_channel_id:
            self.bot.loop.create_task(self.cleanup_temp_channel(game))

    async def cleanup_temp_channel(self, game: TitanGameEngine):
        if not game.game_channel_id:
            return
        ch = self.bot.get_channel(game.game_channel_id)
        if not isinstance(ch, discord.TextChannel):
            return
        try:
            await asyncio.sleep(15)
            await ch.delete()
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(TitanGameCog(bot))
