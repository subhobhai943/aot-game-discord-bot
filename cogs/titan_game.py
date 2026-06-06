from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Optional

import discord
from discord.ext import commands

from data.titan_images import SURVEY_CORPS_IMAGES, TITAN_IMAGES
from games.titan_logic import GameState, Role, TitanGameEngine
from utils.game_state import attach_image


GAME_CATEGORY_ID = 1510159583040114788


@dataclass(frozen=True)
class TaskChallenge:
    title: str
    briefing: str
    prompt: str
    options: tuple[str, ...]
    correct_option: str
    success_text: str
    failure_text: str


def shuffled_options(*items: str) -> tuple[str, ...]:
    options = list(items)
    random.shuffle(options)
    return tuple(options)


def build_task_challenge() -> TaskChallenge:
    templates = [
        TaskChallenge(
            title="ODM Supply Dash",
            briefing="A forward squad is pinned on the rooftops and needs fresh gear immediately.",
            prompt="Which crate reaches them first?",
            options=shuffled_options("Thunder Spears", "Tea Rations", "Ceremonial Cloaks", "Broken Scabbards"),
            correct_option="Thunder Spears",
            success_text="You secure the thunder spears and the vanguard breaks through the titan line.",
            failure_text="Wrong crate. The quartermaster shouts for the live ordnance shipment.",
        ),
        TaskChallenge(
            title="Scout Flare Cipher",
            briefing="The signal book says green means regroup, red means attack, and black smoke means retreat.",
            prompt="Which flare do you fire to regroup the squad?",
            options=shuffled_options("Green Flare", "Red Flare", "Black Smoke", "Blue Flare"),
            correct_option="Green Flare",
            success_text="Your flare arcs overhead and the nearby scouts reform their line perfectly.",
            failure_text="That signal would send the wrong order. Check the flare book again.",
        ),
        TaskChallenge(
            title="Titan Weak Point Briefing",
            briefing="A trainee panics during the charge and asks where the strike must land.",
            prompt="Call out the true weak point.",
            options=shuffled_options("The Nape", "The Left Ankle", "The Chest Plate", "The Jaw Hinge"),
            correct_option="The Nape",
            success_text="Your call is sharp and clear. The squad slices the nape cleanly.",
            failure_text="That target wastes precious time. The weak point is smaller and deadlier than that.",
        ),
        TaskChallenge(
            title="Refugee Route Planning",
            briefing="Titans were spotted to the west, rooftops are collapsing to the south, and the east ridge is still clear.",
            prompt="Which route do you assign to the convoy?",
            options=shuffled_options("East Ridge", "West Alley", "South Market", "North Gate Rubble"),
            correct_option="East Ridge",
            success_text="The convoy slips through the east ridge and reaches safety before the next titan wave.",
            failure_text="That route is compromised. Recheck the field report and choose the clear path.",
        ),
    ]
    return random.choice(templates)


class TaskChoiceButton(discord.ui.Button):
    def __init__(self, option_text: str):
        super().__init__(label=option_text, style=discord.ButtonStyle.secondary)
        self.option_text = option_text

    async def callback(self, interaction: discord.Interaction):
        assert isinstance(self.view, TitanTaskChallengeView)
        await self.view.handle_choice(interaction, self.option_text)


class TitanLobbyView(discord.ui.View):
    def __init__(self, cog: "TitanGameCog", channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="Join Lobby", style=discord.ButtonStyle.primary)
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
            f"You joined the squad. ({len(game.players)}/{game.MAX_PLAYERS})",
            ephemeral=True,
        )


class TitanTaskChallengeView(discord.ui.View):
    def __init__(self, cog: "TitanGameCog", game_channel_id: int, player_id: int, challenge: TaskChallenge):
        super().__init__(timeout=90)
        self.cog = cog
        self.game_channel_id = game_channel_id
        self.player_id = player_id
        self.challenge = challenge

        for option in challenge.options:
            self.add_item(TaskChoiceButton(option))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("This task board is locked to the scout who opened it.", ephemeral=True)
            return False
        return True

    def build_embed(self, note: Optional[str] = None) -> discord.Embed:
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        embed = discord.Embed(title=self.challenge.title, color=discord.Color.blurple())
        embed.description = f"{self.challenge.briefing}\n\n{self.challenge.prompt}"
        if game:
            player = game.players.get(self.player_id)
            completed, required = game.get_task_progress()
            personal = player.tasks_completed if player else 0
            embed.add_field(
                name="Task Progress",
                value=(
                    f"Personal: {personal}/{game.TASKS_PER_PLAYER}\n"
                    f"Squad: {completed}/{required or game.total_tasks_required}"
                ),
                inline=False,
            )
        if note:
            embed.add_field(name="Intel", value=note, inline=False)
        return embed

    async def handle_choice(self, interaction: discord.Interaction, option_text: str):
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game:
            await interaction.response.edit_message(content="This task has expired because the game is no longer active.", embed=None, view=None)
            return

        if option_text != self.challenge.correct_option:
            await interaction.response.edit_message(embed=self.build_embed(self.challenge.failure_text), view=self)
            return

        success, msg = game.do_task(self.player_id)
        completed, required = game.get_task_progress()
        color = discord.Color.green() if success else discord.Color.red()
        result = discord.Embed(
            title=f"{self.challenge.title} Complete" if success else self.challenge.title,
            description=(
                f"{self.challenge.success_text}\n\n{msg}\n"
                f"Squad task progress: {completed}/{required or game.total_tasks_required}"
            ) if success else msg,
            color=color,
        )
        await interaction.response.edit_message(embed=result, view=None)

        if not success:
            return

        winner = game.check_win()
        if winner:
            active_channel = self.cog.get_active_channel(game)
            if active_channel:
                await self.cog.end_game(active_channel, game, winner)


class EliminateSelectView(discord.ui.View):
    def __init__(self, cog: "TitanGameCog", game: TitanGameEngine, shifter_id: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.game = game
        self.shifter_id = shifter_id

        options = [
            discord.SelectOption(label=player.character_name, value=str(user_id), description=f"Eliminate <@{user_id}>")
            for user_id, player in game.players.items()
            if player.is_alive and player.role == Role.SURVEY_CORPS
        ]

        if not options:
            self.add_item(discord.ui.Button(label="No valid targets", disabled=True))
            return

        select = discord.ui.Select(placeholder="Choose a Survey Corps target...", options=options[:25])
        select.callback = self.select_cb
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.shifter_id:
            await interaction.response.send_message("This control panel is bound to another Titan Shifter.", ephemeral=False)
            return False
        return True

    async def select_cb(self, interaction: discord.Interaction):
        target_id = int(interaction.data["values"][0])
        success, msg = self.game.eliminate(self.shifter_id, target_id)
        if not success:
            await interaction.response.edit_message(content=msg, view=None)
            return

        await interaction.response.edit_message(content=msg, view=None)

        active_channel = self.cog.get_active_channel(self.game)
        if active_channel:
            target_player = self.game.players[target_id]
            embed = discord.Embed(
                title="Casualty Report",
                description=f"<@{target_id}> ({target_player.character_name}) was devoured in the chaos.",
                color=discord.Color.red(),
            )
            await active_channel.send(embed=embed)

            winner = self.game.check_win()
            if winner:
                await self.cog.end_game(active_channel, self.game, winner)


class ShifterControlView(discord.ui.View):
    def __init__(self, cog: "TitanGameCog", game_channel_id: int, user_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_channel_id = game_channel_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This shifter panel belongs to another player.", ephemeral=False)
            return False
        return True

    @discord.ui.button(label="Open Kill Menu", style=discord.ButtonStyle.danger)
    async def kill_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game:
            await interaction.response.send_message("This control panel is no longer active.", ephemeral=False)
            return

        player = game.players.get(self.user_id)
        if not player or player.role != Role.TITAN_SHIFTER or not player.is_alive:
            await interaction.response.send_message("You cannot use titan powers right now.", ephemeral=False)
            return

        cooldown = game.seconds_until_kill(self.user_id)
        if cooldown > 0:
            await interaction.response.send_message(
                f"Your titan power is recharging. Wait {cooldown}s before the next strike.",
                ephemeral=False,
            )
            return

        view = EliminateSelectView(self.cog, game, self.user_id)
        await interaction.response.send_message("Choose a scout to devour.", view=view, ephemeral=False)

    @discord.ui.button(label="Check Cooldown", style=discord.ButtonStyle.secondary)
    async def cooldown_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game:
            await interaction.response.send_message("This control panel is no longer active.", ephemeral=False)
            return

        cooldown = game.seconds_until_kill(self.user_id)
        if cooldown > 0:
            await interaction.response.send_message(f"Next kill is ready in {cooldown}s.", ephemeral=False)
        else:
            await interaction.response.send_message("Your next kill is ready now.", ephemeral=False)


class TitanGameTempView(discord.ui.View):
    def __init__(self, cog: "TitanGameCog", game_channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_channel_id = game_channel_id

    def get_game(self) -> Optional[TitanGameEngine]:
        return self.cog.get_game_by_temp_channel(self.game_channel_id)

    @discord.ui.button(label="Do Task", style=discord.ButtonStyle.success)
    async def task_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.get_game()
        if not game:
            await interaction.response.send_message("No game is active in this channel anymore.", ephemeral=True)
            return

        player = game.players.get(interaction.user.id)
        if not player or not player.is_alive:
            await interaction.response.send_message("Only living players can operate field tasks.", ephemeral=True)
            return
        if player.role == Role.TITAN_SHIFTER:
            await interaction.response.send_message("Titan Shifters only pretend to work. Your real control panel is private.", ephemeral=True)
            return
        if player.tasks_completed >= game.TASKS_PER_PLAYER:
            await interaction.response.send_message("You already completed every assigned mission task.", ephemeral=True)
            return

        challenge = build_task_challenge()
        view = TitanTaskChallengeView(self.cog, self.game_channel_id, interaction.user.id, challenge)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)

    @discord.ui.button(label="Squad Status", style=discord.ButtonStyle.secondary)
    async def status_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.get_game()
        if not game:
            await interaction.response.send_message("No game is active in this channel anymore.", ephemeral=True)
            return

        await interaction.response.send_message(embed=self.cog.build_status_embed(game, interaction.user.id), ephemeral=True)

    @discord.ui.button(label="Emergency Meeting", style=discord.ButtonStyle.primary)
    async def meeting_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.get_game()
        if not game:
            await interaction.response.send_message("No game is active in this channel anymore.", ephemeral=True)
            return

        if not game.call_meeting(interaction.user.id):
            await interaction.response.send_message("You cannot call a meeting right now.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Emergency Meeting",
            description=f"{interaction.user.mention} fired a flare. The squad has one minute to decide.",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)
        await self.cog.begin_voting(interaction.channel, game)


class TitanGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games: dict[int, TitanGameEngine] = {}
        self.vote_tasks: dict[int, asyncio.Task] = {}

    def cog_unload(self):
        for task in self.vote_tasks.values():
            if not task.done():
                task.cancel()

    def get_lobby_game(self, channel_id: int) -> Optional[TitanGameEngine]:
        return self.games.get(channel_id)

    def get_game_by_channel(self, channel_id: int) -> Optional[TitanGameEngine]:
        for game in self.games.values():
            if game.state == GameState.LOBBY and game.channel_id == channel_id:
                return game
            if game.game_channel_id == channel_id:
                return game
        return None

    def get_game_by_player(self, user_id: int) -> Optional[TitanGameEngine]:
        for game in self.games.values():
            if user_id in game.players:
                return game
        return None

    def get_game_by_temp_channel(self, game_channel_id: int) -> Optional[TitanGameEngine]:
        for game in self.games.values():
            if game.game_channel_id == game_channel_id:
                return game
        return None

    def get_active_channel(self, game: TitanGameEngine) -> Optional[discord.TextChannel]:
        channel_id = game.game_channel_id or game.channel_id
        channel = self.bot.get_channel(channel_id)
        return channel if isinstance(channel, discord.TextChannel) else None

    def build_lobby_embed(self, game: TitanGameEngine) -> discord.Embed:
        players = "\n".join(f"<@{user_id}>" for user_id in game.players.keys())
        embed = discord.Embed(
            title="Titan Shifters Lobby",
            description=(
                f"Host: <@{game.host_id}>\n"
                f"Players: {len(game.players)}/{game.MAX_PLAYERS} (Minimum: {game.MIN_PLAYERS})\n"
                "Use `/titan-game join`, `Aot titan-game join`, or the button below to enlist."
            ),
            color=discord.Color.dark_theme(),
        )
        embed.add_field(name="Current Squad", value=players or "No scouts yet.", inline=False)
        return embed

    def build_status_embed(self, game: TitanGameEngine, viewer_id: Optional[int] = None) -> discord.Embed:
        alive = len(game.alive_players())
        alive_shifters = len(game.alive_shifters())
        alive_scouts = len(game.alive_survey_corps())
        completed, required = game.get_task_progress()

        embed = discord.Embed(title="Field Status", color=discord.Color.gold())
        embed.description = (
            f"Phase: **{game.state.name.title()}**\n"
            f"Alive: **{alive}/{len(game.players)}**\n"
            f"Survey Corps Alive: **{alive_scouts}**\n"
            f"Shifters Alive: **{alive_shifters}**"
        )
        embed.add_field(
            name="Mission Progress",
            value=f"Squad tasks completed: {completed}/{required or game.total_tasks_required}",
            inline=False,
        )

        if viewer_id and viewer_id in game.players:
            player = game.players[viewer_id]
            if player.role == Role.SURVEY_CORPS:
                embed.add_field(
                    name="Your Assignment",
                    value=f"Tasks completed: {player.tasks_completed}/{game.TASKS_PER_PLAYER}",
                    inline=False,
                )
            else:
                cooldown = game.seconds_until_kill(viewer_id)
                embed.add_field(
                    name="Your Titan Window",
                    value="Kill ready now." if cooldown == 0 else f"Kill cooldown: {cooldown}s",
                    inline=False,
                )

        if game.state == GameState.VOTING:
            embed.add_field(
                name="Voting Clock",
                value=f"{game.get_vote_time_remaining()}s remaining to vote.",
                inline=False,
            )

        return embed

    async def refresh_lobby_message(self, game: TitanGameEngine):
        if not game.lobby_message_id:
            return

        channel = self.bot.get_channel(game.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(game.lobby_message_id)
        except discord.HTTPException:
            return

        await message.edit(embed=self.build_lobby_embed(game), view=TitanLobbyView(self, game.channel_id))

    def cancel_vote_task(self, game: TitanGameEngine):
        task = self.vote_tasks.pop(game.channel_id, None)
        current = asyncio.current_task()
        if task and not task.done() and task is not current:
            task.cancel()

    async def begin_voting(self, channel: discord.abc.Messageable, game: TitanGameEngine):
        if not game.start_voting():
            return

        await channel.send(
            "Voting has started. Use `Aot vote @user` or `/vote @user` within 60 seconds. "
            "Use the command without a target to skip."
        )
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

            channel = self.bot.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                await channel.send("The voting flare burns out. The meeting is ending now.")
                await self.resolve_votes(channel, game)
        except asyncio.CancelledError:
            return

    async def lobby_timeout_task(self, channel_id: int, game: TitanGameEngine):
        await asyncio.sleep(240)
        if game.state == GameState.LOBBY and self.games.get(channel_id) == game:
            del self.games[channel_id]
            channel = self.bot.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                await channel.send("Lobby automatically cancelled after 4 minutes of inactivity.")

    @commands.hybrid_group(name="titan-game", description="Titan Shifters social deduction game", invoke_without_command=True)
    async def titan_game(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @titan_game.command(name="create", description="Create a new Titan Shifters lobby")
    async def tg_create(self, ctx: commands.Context):
        if self.get_lobby_game(ctx.channel.id) or self.get_game_by_channel(ctx.channel.id):
            await ctx.send("A Titan Shifters game is already tied to this channel.", ephemeral=True)
            return

        game = TitanGameEngine(ctx.guild.id, ctx.channel.id, ctx.author.id)
        self.games[ctx.channel.id] = game

        view = TitanLobbyView(self, ctx.channel.id)
        message = await ctx.send(embed=self.build_lobby_embed(game), view=view)
        game.lobby_message_id = message.id
        self.bot.loop.create_task(self.lobby_timeout_task(ctx.channel.id, game))

    @titan_game.command(name="join", description="Join the current Titan Shifters lobby")
    async def tg_join(self, ctx: commands.Context):
        game = self.get_lobby_game(ctx.channel.id)
        if not game:
            await ctx.send("No lobby found in this channel.", ephemeral=True)
            return

        success, msg = game.add_player(ctx.author.id)
        if success:
            await self.refresh_lobby_message(game)
            await ctx.send(f"{ctx.author.mention} joined the squad. ({len(game.players)}/{game.MAX_PLAYERS} players)")
        else:
            await ctx.send(msg, ephemeral=True)

    @titan_game.command(name="leave", description="Leave the current Titan Shifters lobby")
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
            await ctx.send("Everyone left. The lobby has been closed.")
            return

        await self.refresh_lobby_message(game)
        await ctx.send(f"{ctx.author.mention} left the squad. Host is now <@{game.host_id}>.")

    @titan_game.command(name="start", description="Start the game (host only)")
    async def tg_start(self, ctx: commands.Context):
        game = self.get_lobby_game(ctx.channel.id)
        if not game:
            await ctx.send("No lobby found.", ephemeral=True)
            return
        if ctx.author.id != game.host_id:
            await ctx.send("Only the host can start the game.", ephemeral=True)
            return

        success, msg = game.start_game()
        if not success:
            await ctx.send(msg, ephemeral=True)
            return

        guild = ctx.guild
        category = guild.get_channel(GAME_CATEGORY_ID)
        if category is None:
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
        for user_id in game.players.keys():
            member = guild.get_member(user_id)
            if member:
                overwrites[member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )

        game_channel = await guild.create_text_channel(
            name=f"shifters-game-{random.randint(1000, 9999)}",
            category=category,
            overwrites=overwrites,
        )
        game.game_channel_id = game_channel.id

        if game.lobby_message_id:
            channel = self.bot.get_channel(game.channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    message = await channel.fetch_message(game.lobby_message_id)
                    launch_embed = discord.Embed(
                        title="Squad Deployed",
                        description=f"The expedition has moved to {game_channel.mention}.",
                        color=discord.Color.dark_blue(),
                    )
                    await message.edit(embed=launch_embed, view=None)
                except discord.HTTPException:
                    pass

        await ctx.send(f"The mission is live in {game_channel.mention}. Roles are being sent now.")

        for user_id, player in game.players.items():
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            embed = discord.Embed(
                title="Secret Transmission" if player.role == Role.TITAN_SHIFTER else "Operation Briefing"
            )
            file = None

            if player.role == Role.TITAN_SHIFTER:
                embed.color = discord.Color.red()
                embed.description = (
                    f"You are the **{player.character_name}**.\n\n"
                    "**Role:** Titan Shifter\n"
                    "Blend in, survive the vote, and devour the Survey Corps. "
                    "Your private kill panel is attached below."
                )
            else:
                embed.color = discord.Color.green()
                embed.description = (
                    f"You are **{player.character_name}**.\n\n"
                    "**Role:** Survey Corps Member\n"
                    "Complete your field assignments, catch the shifter, and survive the expedition."
                )

            if player.image_url:
                file = attach_image(embed, player.image_url, as_thumbnail=True)
            elif player.role == Role.SURVEY_CORPS and SURVEY_CORPS_IMAGES:
                file = attach_image(embed, random.choice(SURVEY_CORPS_IMAGES), as_thumbnail=True)

            try:
                if file:
                    await user.send(embed=embed, file=file)
                else:
                    await user.send(embed=embed)

                if player.role == Role.TITAN_SHIFTER:
                    await user.send(
                        "Private Titan control panel. Only you can use these buttons.",
                        view=ShifterControlView(self, game_channel.id, user_id),
                    )
            except discord.Forbidden:
                await ctx.channel.send(
                    f"{user.mention} has DMs disabled. They will miss private role information and shifter controls."
                )

        missions = [
            "Seal the breach before titans flood the district",
            "Escort refugees through collapsing rooftops",
            "Scout a forest approach and mark titan nests",
            "Recover supply carts stranded beyond the inner gate",
            "Hunt for a hidden shifter moving inside the smoke",
        ]
        chosen_mission = random.choice(missions)

        embed = discord.Embed(
            title="Exploration Phase",
            description=(
                "Steel cables scream through the air as the squad enters hostile territory.\n\n"
                f"**Current Mission:** {chosen_mission}\n"
                f"**Crew Task Goal:** {game.TASKS_PER_PLAYER} tasks per living Survey Corps member\n"
                f"**Shifter Kill Cooldown:** {game.KILL_COOLDOWN_SECONDS} seconds"
            ),
            color=discord.Color.dark_blue(),
        )
        embed.add_field(
            name="Command Notes",
            value=(
                "Survey Corps should use the task button to clear mission objectives.\n"
                "Call a meeting if you spot suspicious behavior.\n"
                "Voting ends automatically after 60 seconds."
            ),
            inline=False,
        )

        view = TitanGameTempView(self, game_channel.id)
        if "Transformation" in TITAN_IMAGES:
            file = attach_image(embed, random.choice(TITAN_IMAGES["Transformation"]))
            if file:
                await game_channel.send(embed=embed, file=file, view=view)
            else:
                await game_channel.send(embed=embed, view=view)
        else:
            await game_channel.send(embed=embed, view=view)

    @titan_game.command(name="status", description="Check the status of the current game")
    async def tg_status(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("No active game in this channel.", ephemeral=True)
            return

        await ctx.send(embed=self.build_status_embed(game, ctx.author.id))

    @titan_game.command(name="stop", description="Forcefully end the game (host/admin only)")
    async def tg_stop(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id) or self.get_game_by_player(ctx.author.id)
        if not game:
            await ctx.send("No active game found for you here.", ephemeral=True)
            return

        if ctx.author.id != game.host_id and not ctx.author.guild_permissions.administrator:
            await ctx.send("Only the host or a server admin can stop the game.", ephemeral=True)
            return

        self.cancel_vote_task(game)
        self.games.pop(game.channel_id, None)
        await ctx.send("Titan Shifters has been forcefully stopped.")

        active_channel = self.get_active_channel(game)
        if active_channel and active_channel.id != ctx.channel.id:
            await active_channel.send("The expedition has been aborted by command.")
        if game.game_channel_id:
            self.bot.loop.create_task(self.cleanup_temp_channel(game))

    @commands.hybrid_command(name="eliminate", description="Eliminate a player (Titan Shifter only)")
    async def eliminate(self, ctx: commands.Context, target: discord.User):
        game = self.get_game_by_player(ctx.author.id)
        if not game:
            await ctx.send("You are not in any Titan Shifters game.", ephemeral=True)
            return

        if not isinstance(ctx.channel, discord.DMChannel) and not ctx.interaction:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            await ctx.author.send("You used `Aot eliminate` in public. Be careful not to expose yourself.")

        success, msg = game.eliminate(ctx.author.id, target.id)
        if not success:
            await ctx.send(msg, ephemeral=True)
            return

        await ctx.send(msg, ephemeral=True)

        active_channel = self.get_active_channel(game)
        if active_channel:
            target_player = game.players[target.id]
            embed = discord.Embed(
                title="Casualty Report",
                description=f"{target.mention} ({target_player.character_name}) has been found devoured by a Titan.",
                color=discord.Color.red(),
            )
            await active_channel.send(embed=embed)

            winner = game.check_win()
            if winner:
                await self.end_game(active_channel, game, winner)

    @commands.hybrid_command(name="meeting", description="Call an emergency meeting")
    async def meeting(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("No active game in this channel.", ephemeral=True)
            return

        if not game.call_meeting(ctx.author.id):
            await ctx.send("You cannot call a meeting right now.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Emergency Meeting",
            description=f"{ctx.author.mention} fired a flare. The squad has one minute to vote.",
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)
        await self.begin_voting(ctx.channel, game)

    @commands.hybrid_command(name="vote", description="Vote to exile a player")
    async def vote(self, ctx: commands.Context, target: discord.Member = None):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("No active game in this channel.", ephemeral=True)
            return

        target_id = target.id if target else None
        success, msg = game.vote(ctx.author.id, target_id)
        if not success:
            await ctx.send(msg, ephemeral=True)
            return

        if target_id is None:
            await ctx.send(f"{ctx.author.mention} skipped their vote.")
        else:
            await ctx.send(f"{ctx.author.mention} locked in a vote.")

        if all(player.has_voted for player in game.alive_players()):
            await self.resolve_votes(ctx.channel, game)

    async def resolve_votes(self, channel: discord.TextChannel, game: TitanGameEngine):
        self.cancel_vote_task(game)
        exiled_id, is_tie = game.get_vote_results()

        embed = discord.Embed(title="The Verdict", color=discord.Color.dark_theme())
        if is_tie or exiled_id is None:
            embed.description = "The squad could not reach a consensus. No one was exiled."
        else:
            exiled_player = game.players[exiled_id]
            embed.description = f"<@{exiled_id}> ({exiled_player.character_name}) was exiled by the squad."
            if exiled_player.role == Role.TITAN_SHIFTER:
                embed.color = discord.Color.green()
                embed.description += "\n\nThey were a Titan Shifter."
            else:
                embed.color = discord.Color.red()
                embed.description += "\n\nThey were not a Titan Shifter."

        await channel.send(embed=embed)

        winner = game.check_win()
        if winner:
            await self.end_game(channel, game, winner)
            return

        game.state = GameState.EXPLORATION
        await channel.send(
            "The meeting breaks. Smoke closes in again and the expedition resumes. "
            "Survey Corps, keep working. Shifters, stay hidden."
        )

    async def end_game(self, channel: discord.TextChannel, game: TitanGameEngine, winner: Role):
        self.cancel_vote_task(game)
        game.state = GameState.GAME_OVER

        embed = discord.Embed(title="Game Over", color=discord.Color.gold())
        file = None
        if winner == Role.SURVEY_CORPS:
            embed.description = (
                "The Survey Corps completed the mission and rooted out every Titan Shifter. Humanity holds the line."
            )
            if "Founding Titan" in TITAN_IMAGES:
                file = attach_image(embed, random.choice(TITAN_IMAGES["Founding Titan"]))
        else:
            embed.description = "The Titans overwhelmed the expedition. The district falls into ruin."
            if "Pure Titan" in TITAN_IMAGES:
                file = attach_image(embed, random.choice(TITAN_IMAGES["Pure Titan"]))

        shifter_mentions = [
            f"<@{player.user_id}> ({player.character_name})"
            for player in game.players.values()
            if player.role == Role.TITAN_SHIFTER
        ]
        embed.add_field(name="Titan Shifters", value="\n".join(shifter_mentions) or "None", inline=False)

        if file:
            await channel.send(embed=embed, file=file)
        else:
            await channel.send(embed=embed)

        lobby_channel = self.bot.get_channel(game.channel_id)
        if isinstance(lobby_channel, discord.TextChannel) and lobby_channel.id != channel.id:
            await lobby_channel.send(f"Titan Shifters ended in {channel.mention}.")

        self.games.pop(game.channel_id, None)
        if game.game_channel_id:
            self.bot.loop.create_task(self.cleanup_temp_channel(game))

    async def cleanup_temp_channel(self, game: TitanGameEngine):
        if not game.game_channel_id:
            return

        temp_channel = self.bot.get_channel(game.game_channel_id)
        if not isinstance(temp_channel, discord.TextChannel):
            return

        try:
            await asyncio.sleep(15)
            await temp_channel.delete()
        except discord.HTTPException:
            return


async def setup(bot):
    await bot.add_cog(TitanGameCog(bot))
