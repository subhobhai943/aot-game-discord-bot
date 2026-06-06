import discord
from discord.ext import commands
import random
from games.titan_logic import TitanGameEngine, GameState, Role
from data.titan_images import SURVEY_CORPS_IMAGES, TITAN_IMAGES
from utils.game_state import attach_image


class TitanLobbyView(discord.ui.View):
    def __init__(self, cog, channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="✋ Join Lobby", style=discord.ButtonStyle.primary)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game_by_channel(self.channel_id)
        if not game:
            await interaction.response.send_message("❌ Lobby not found.", ephemeral=True)
            return
        success, msg = game.add_player(interaction.user.id)
        if success:
            await interaction.response.send_message(f"✅ Joined! ({len(game.players)}/{game.MAX_PLAYERS})", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

class EliminateSelectView(discord.ui.View):
    def __init__(self, cog, game):
        super().__init__(timeout=60)
        self.cog = cog
        self.game = game
        options = []
        for uid, p in game.players.items():
            if p.is_alive and p.role == Role.SURVEY_CORPS:
                options.append(discord.SelectOption(label=p.character_name, value=str(uid)))
        if not options:
            options.append(discord.SelectOption(label="No valid targets", value="0"))
            
        select = discord.ui.Select(placeholder="Select target...", options=options[:25])
        select.callback = self.select_cb
        self.add_item(select)

    async def select_cb(self, interaction: discord.Interaction):
        if interaction.data["values"][0] == "0":
            await interaction.response.send_message("No valid targets.", ephemeral=True)
            return
        target_id = int(interaction.data["values"][0])
        success, msg = self.game.eliminate(interaction.user.id, target_id)
        if success:
            await interaction.response.edit_message(content=f"🩸 {msg}", view=None)
            target_p = self.game.players[target_id]
            await interaction.channel.send(embed=discord.Embed(title="💀 Casualty Report", description=f"<@{target_id}> ({target_p.character_name}) was devoured by a Titan.", color=discord.Color.red()))
            winner = self.game.check_win()
            if winner:
                await self.cog.end_game(interaction.channel, self.game, winner)
        else:
            await interaction.response.edit_message(content=f"❌ {msg}", view=None)

class TitanGameTempView(discord.ui.View):
    def __init__(self, cog, game_channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_channel_id = game_channel_id

    @discord.ui.button(label="📋 Do Task", style=discord.ButtonStyle.success)
    async def task_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game: return
        success, msg = game.do_task(interaction.user.id)
        await interaction.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)
        winner = game.check_win()
        if winner:
            await self.cog.end_game(interaction.channel, game, winner)

    @discord.ui.button(label="🔪 Kill Menu", style=discord.ButtonStyle.danger)
    async def kill_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game: return
        player = game.players.get(interaction.user.id)
        if not player or player.role != Role.TITAN_SHIFTER or not player.is_alive:
            await interaction.response.send_message("❌ You cannot do that.", ephemeral=True)
            return
        view = EliminateSelectView(self.cog, game)
        await interaction.response.send_message("Select a target to eliminate:", view=view, ephemeral=True)

    @discord.ui.button(label="🚨 Emergency Meeting", style=discord.ButtonStyle.primary)
    async def meeting_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game_by_temp_channel(self.game_channel_id)
        if not game: return
        if game.call_meeting(interaction.user.id):
            await interaction.response.send_message("Meeting called!")
            embed = discord.Embed(title="🚨 EMERGENCY MEETING 🚨", description=f"{interaction.user.mention} fired a flare!", color=discord.Color.gold())
            await interaction.channel.send(embed=embed)
            game.start_voting()
            await interaction.channel.send("🗣️ **Discussion Phase started!** Use `Aot vote @user`.")
        else:
            await interaction.response.send_message("❌ Cannot call meeting now.", ephemeral=True)

class TitanGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games: dict[int, TitanGameEngine] = {}

    def get_game_by_channel(self, channel_id: int) -> TitanGameEngine | None:
        return self.games.get(channel_id)

    def get_game_by_player(self, user_id: int) -> TitanGameEngine | None:
        for game in self.games.values():
            if user_id in game.players:
                return game
        return None


    def get_game_by_temp_channel(self, game_channel_id: int) -> TitanGameEngine | None:
        for game in self.games.values():
            if game.game_channel_id == game_channel_id:
                return game
        return None

    async def lobby_timeout_task(self, channel_id: int, game: TitanGameEngine):
        import asyncio
        await asyncio.sleep(240)
        if game.state == GameState.LOBBY and self.games.get(channel_id) == game:
            del self.games[channel_id]
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send("⏳ Lobby automatically cancelled due to inactivity (4 mins).")

    @commands.hybrid_group(name="titan-game", description="Titan Shifters Social Deduction Game", invoke_without_command=True)
    async def titan_game(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @titan_game.command(name="create", description="Create a new Titan Shifters lobby")
    async def tg_create(self, ctx: commands.Context):
        if self.get_game_by_channel(ctx.channel.id):
            await ctx.send("❌ A game is already active in this channel. Stop it first.", ephemeral=True)
            return

        game = TitanGameEngine(ctx.guild.id, ctx.channel.id, ctx.author.id)
        self.games[ctx.channel.id] = game

        embed = discord.Embed(
            title="⚔️ Titan Shifters Lobby Created",
            description=f"Host: {ctx.author.mention}\nUse `/titan-game join`, `Aot titan-game join`, or click the button to enter!\nPlayers: 1/{game.MAX_PLAYERS} (Min: {game.MIN_PLAYERS})",
            color=discord.Color.dark_theme()
        )
        view = TitanLobbyView(self, ctx.channel.id)
        await ctx.send(embed=embed, view=view)
        self.bot.loop.create_task(self.lobby_timeout_task(ctx.channel.id, game))

    @titan_game.command(name="join", description="Join the current Titan Shifters lobby")
    async def tg_join(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("❌ No lobby found in this channel.", ephemeral=True)
            return
            
        success, msg = game.add_player(ctx.author.id)
        if success:
            await ctx.send(f"✅ {ctx.author.mention} joined the squad! ({len(game.players)}/{game.MAX_PLAYERS} players)")
        else:
            await ctx.send(f"❌ {msg}", ephemeral=True)

    @titan_game.command(name="leave", description="Leave the current Titan Shifters lobby")
    async def tg_leave(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game or game.state != GameState.LOBBY:
            await ctx.send("❌ You can only leave during the lobby phase.", ephemeral=True)
            return
            
        if game.remove_player(ctx.author.id):
            if not game.players:
                del self.games[ctx.channel.id]
                await ctx.send("🚪 Everyone left. Lobby destroyed.")
            else:
                await ctx.send(f"🚪 {ctx.author.mention} left the squad. Host is now <@{game.host_id}>.")
        else:
            await ctx.send("❌ You are not in the lobby.", ephemeral=True)

    @titan_game.command(name="start", description="Start the game (Host only)")
    async def tg_start(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("❌ No lobby found.", ephemeral=True)
            return
            
        if ctx.author.id != game.host_id:
            await ctx.send("❌ Only the host can start the game.", ephemeral=True)
            return
            
        success, msg = game.start_game()
        if not success:
            await ctx.send(f"❌ {msg}", ephemeral=True)
            return

        guild = ctx.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        for uid in game.players.keys():
            member = guild.get_member(uid)
            if member:
                overwrites[member] = discord.PermissionOverwrite(read_messages=True)
                
        game_channel = await guild.create_text_channel(
            name=f"shifters-game-{random.randint(1000, 9999)}",
            category=ctx.channel.category,
            overwrites=overwrites
        )
        game.game_channel_id = game_channel.id

        await ctx.send(f"Starting game... Move to {game_channel.mention} and check your DMs for roles!")

        for uid, player in game.players.items():
            user = self.bot.get_user(uid)
            if not user:
                continue
                
            embed = discord.Embed(title="📜 Secret Transmission" if player.role == Role.TITAN_SHIFTER else "📜 Operation Briefing")
            if player.role == Role.TITAN_SHIFTER:
                embed.color = discord.Color.red()
                embed.description = f"You are the **{player.character_name}**.\n\n**Role: Titan Shifter (Imposter)**\nMission: Eliminate Survey Corps members without being exposed. Use the dropdown below."
            else:
                embed.color = discord.Color.green()
                embed.description = f"You are **{player.character_name}**.\n\n**Role: Survey Corps Member (Crewmate)**\nMission: Find the hidden Titan Shifter(s). Report fallen comrades using `Aot meeting`."
            file = None
            if player.image_url:
                file = attach_image(embed, player.image_url, as_thumbnail=True)
            elif player.role == Role.SURVEY_CORPS and SURVEY_CORPS_IMAGES:
                file = attach_image(embed, random.choice(SURVEY_CORPS_IMAGES), as_thumbnail=True)

            try:
                if file:
                    await user.send(embed=embed, file=file)
                else:
                    await user.send(embed=embed)
            except discord.Forbidden:
                await ctx.channel.send(f"⚠️ {user.mention} has DMs disabled! They cannot play properly.")

        missions = [
            "Resupply ODM gear",
            "Reinforce Wall Maria sector",
            "Map Titan movement patterns",
            "Escort civilian refugees",
            "Scout ahead into the forest"
        ]
        chosen_mission = random.choice(missions)
        
        embed = discord.Embed(
            title="🗺️ Exploration Phase",
            description=f"The squad sets out.\n\n**Current Mission:** {chosen_mission}\n\n*Survey Corps, stay alert. Shifters, make your move.*",
            color=discord.Color.dark_blue()
        )
        view = TitanGameTempView(self, game_channel.id)
        if "Transformation" in TITAN_IMAGES:
            file = attach_image(embed, random.choice(TITAN_IMAGES["Transformation"]))
            await game_channel.send(f"<@&{guild.default_role.id}>", embed=embed, file=file, view=view)
        else:
            await game_channel.send(f"<@&{guild.default_role.id}>", embed=embed, view=view)

    @titan_game.command(name="status", description="Check the status of the game")
    async def tg_status(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("❌ No active game.", ephemeral=True)
            return
            
        alive = sum(1 for p in game.players.values() if p.is_alive)
        embed = discord.Embed(
            title="📊 Game Status",
            description=f"Phase: **{game.state.name}**\nAlive: {alive}/{len(game.players)}",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @titan_game.command(name="stop", description="Forcefully end the game (Host/Admin only)")
    async def tg_stop(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("❌ No active game.", ephemeral=True)
            return
            
        if ctx.author.id == game.host_id or ctx.author.guild_permissions.administrator:
            del self.games[ctx.channel.id]
            await ctx.send("🛑 Game forcefully stopped.")
        else:
            await ctx.send("❌ Only the host or an admin can force stop the game.", ephemeral=True)

    @commands.hybrid_command(name="eliminate", description="Eliminate a player (Titan Shifter only)")
    async def eliminate(self, ctx: commands.Context, target: discord.User):
        game = self.get_game_by_player(ctx.author.id)
        if not game:
            await ctx.send("❌ You are not in any game.", ephemeral=True)
            return
            
        if not isinstance(ctx.channel, discord.DMChannel) and not ctx.interaction:
            # If not in DM and not a slash command, it's a public prefix command. Warn them.
            try:
                await ctx.message.delete()
            except:
                pass
            await ctx.author.send("⚠️ You just used Aot eliminate in public! Be careful, you might have exposed yourself.")

        success, msg = game.eliminate(ctx.author.id, target.id)
        if success:
            await ctx.send(f"🩸 {msg}", ephemeral=True)
            
            # Announce in game channel
            channel = self.bot.get_channel(game.channel_id)
            if channel:
                target_p = game.players[target.id]
                embed = discord.Embed(
                    title="💀 Casualty Report",
                    description=f"{target.mention} ({target_p.character_name}) has been found devoured by a Titan.",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed)
                
            winner = game.check_win()
            if winner and channel:
                await self.end_game(channel, game, winner)
        else:
            await ctx.send(f"❌ {msg}", ephemeral=True)

    @commands.hybrid_command(name="meeting", description="Call an emergency meeting or report a body")
    async def meeting(self, ctx: commands.Context):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("❌ No active game in this channel.", ephemeral=True)
            return

        if game.call_meeting(ctx.author.id):
            embed = discord.Embed(
                title="🚨 EMERGENCY MEETING 🚨",
                description=f"{ctx.author.mention} has fired a flare! Gather immediately to discuss.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            game.start_voting()
            await ctx.channel.send("🗣️ **Discussion & Voting Phase started!** Use `Aot vote @user` or `/vote @user` to cast your vote. To skip voting, use `Aot vote` without a mention.")
        else:
            await ctx.send("❌ You cannot call a meeting right now.", ephemeral=True)

    @commands.hybrid_command(name="vote", description="Vote to exile a player")
    async def vote(self, ctx: commands.Context, target: discord.Member = None):
        game = self.get_game_by_channel(ctx.channel.id)
        if not game:
            await ctx.send("❌ No active game in this channel.", ephemeral=True)
            return

        target_id = target.id if target else None
        success, msg = game.vote(ctx.author.id, target_id)
        
        if success:
            await ctx.send(f"🗳️ {ctx.author.mention} has cast their vote.")
            
            alive_players = [p for p in game.players.values() if p.is_alive]
            if all(p.has_voted for p in alive_players):
                await self.resolve_votes(ctx.channel, game)
        else:
            await ctx.send(f"❌ {msg}", ephemeral=True)

    async def resolve_votes(self, channel: discord.TextChannel, game: TitanGameEngine):
        exiled_id, is_tie = game.get_vote_results()
        
        embed = discord.Embed(title="⚖️ The Verdict", color=discord.Color.dark_theme())
        if is_tie or not exiled_id:
            embed.description = "The squad could not reach a consensus. No one was exiled."
        else:
            ep = game.players[exiled_id]
            embed.description = f"<@{exiled_id}> ({ep.character_name}) has been exiled by the squad."
            if ep.role == Role.TITAN_SHIFTER:
                embed.color = discord.Color.green()
                embed.description += "\n\n🎉 **They were a Titan Shifter!**"
            else:
                embed.color = discord.Color.red()
                embed.description += "\n\n🩸 **They were NOT a Titan Shifter...**"
                
        await channel.send(embed=embed)
        
        winner = game.check_win()
        if winner:
            await self.end_game(channel, game, winner)
        else:
            game.state = GameState.EXPLORATION
            await channel.send("🗺️ The sun rises. The squad continues their exploration mission. Shifters, remain hidden.")

    async def end_game(self, channel: discord.TextChannel, game: TitanGameEngine, winner: Role):
        embed = discord.Embed(title="🏁 GAME OVER", color=discord.Color.gold())
        file = None
        if winner == Role.SURVEY_CORPS:
            embed.description = "🏆 **The Survey Corps has eliminated all Titans! Humanity is safe.**"
            if "Founding Titan" in TITAN_IMAGES:
                 file = attach_image(embed, random.choice(TITAN_IMAGES["Founding Titan"]))
        else:
            embed.description = "💀 **The Titans have overrun the Survey Corps! Humanity falls.**"
            if "Pure Titan" in TITAN_IMAGES:
                 file = attach_image(embed, random.choice(TITAN_IMAGES["Pure Titan"]))
            
        shifter_mentions = [f"<@{p.user_id}> ({p.character_name})" for p in game.players.values() if p.role == Role.TITAN_SHIFTER]
        embed.add_field(name="Titan Shifters", value="\n".join(shifter_mentions) or "None", inline=False)
        
        if file:
            await channel.send(embed=embed, file=file)
        else:
            await channel.send(embed=embed)
            
        if game.game_channel_id:
            temp_ch = self.bot.get_channel(game.game_channel_id)
            if temp_ch:
                await temp_ch.send(embed=embed)
                try:
                    import asyncio
                    await asyncio.sleep(15)
                    await temp_ch.delete()
                except: pass
                
        if game.channel_id in self.games:
            del self.games[game.channel_id]

async def setup(bot):
    await bot.add_cog(TitanGameCog(bot))
