import discord
from discord.ext import commands
from discord import app_commands
from games.among_titans_logic import AmongTitansGame, GameState, Role

class AmongTitans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Maps channel_id -> AmongTitansGame
        self.games: dict[int, AmongTitansGame] = {}

    game_group = app_commands.Group(name="among-titans", description="AoT themed social deduction game")

    def get_game(self, interaction: discord.Interaction) -> AmongTitansGame | None:
        return self.games.get(interaction.channel_id)

    @game_group.command(name="create", description="Create an Among Titans lobby in this channel")
    async def create(self, interaction: discord.Interaction):
        if self.get_game(interaction):
            await interaction.response.send_message("❌ A game is already active in this channel. End it first.", ephemeral=True)
            return

        game = AmongTitansGame(interaction.guild_id, interaction.channel_id, interaction.user.id)
        self.games[interaction.channel_id] = game

        embed = discord.Embed(
            title="⚔️ Among Titans Lobby Created",
            description=f"Host: {interaction.user.mention}\nUse `/among-titans join` to enter the fray!\nPlayers: 1/{game.MIN_PLAYERS} minimum",
            color=discord.Color.dark_theme()
        )
        await interaction.response.send_message(embed=embed)

    @game_group.command(name="join", description="Join the current Among Titans lobby")
    async def join(self, interaction: discord.Interaction):
        game = self.get_game(interaction)
        if not game:
            await interaction.response.send_message("❌ No lobby found in this channel.", ephemeral=True)
            return
        
        if game.state != GameState.LOBBY:
            await interaction.response.send_message("❌ The game has already started!", ephemeral=True)
            return
            
        if game.add_player(interaction.user.id):
            await interaction.response.send_message(f"✅ {interaction.user.mention} joined the squad! ({len(game.players)} players)")
        else:
            await interaction.response.send_message("❌ You are already in the lobby.", ephemeral=True)

    @game_group.command(name="leave", description="Leave the current Among Titans lobby")
    async def leave(self, interaction: discord.Interaction):
        game = self.get_game(interaction)
        if not game or game.state != GameState.LOBBY:
            await interaction.response.send_message("❌ You can only leave during the lobby phase.", ephemeral=True)
            return
            
        if game.remove_player(interaction.user.id):
            if not game.players:
                del self.games[interaction.channel_id]
                await interaction.response.send_message("🚪 Everyone left. Lobby destroyed.")
            else:
                await interaction.response.send_message(f"🚪 {interaction.user.mention} left the squad. Host is now <@{game.host_id}>.")
        else:
            await interaction.response.send_message("❌ You are not in the lobby.", ephemeral=True)

    @game_group.command(name="start", description="Start the game (Host only)")
    async def start(self, interaction: discord.Interaction):
        game = self.get_game(interaction)
        if not game:
            await interaction.response.send_message("❌ No lobby found.", ephemeral=True)
            return
            
        if interaction.user.id != game.host_id:
            await interaction.response.send_message("❌ Only the host can start the game.", ephemeral=True)
            return
            
        if not game.start_game():
            await interaction.response.send_message(f"❌ Need at least {game.MIN_PLAYERS} players to start.", ephemeral=True)
            return

        await interaction.response.defer()

        # Distribute DMs
        for uid, player in game.players.items():
            user = self.bot.get_user(uid)
            if not user:
                continue
                
            embed = discord.Embed(title="📜 Secret Transmission" if player.role == Role.TITAN_SHIFTER else "📜 Operation Briefing")
            if player.role == Role.TITAN_SHIFTER:
                embed.color = discord.Color.red()
                embed.description = f"You are the **{player.character_name}**.\n\n**Role: Titan Shifter**\nMission: Eliminate Survey Corps members without being exposed. Use `/among-titans eliminate` in the channel."
            else:
                embed.color = discord.Color.green()
                embed.description = f"You are **{player.character_name}**.\n\n**Role: Survey Corps Member**\nMission: Find the hidden Titan Shifter(s) before the squad falls. Report fallen comrades to call a meeting."
            
            if player.image_url:
                embed.set_thumbnail(url=player.image_url)

            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                await interaction.channel.send(f"⚠️ {user.mention} has DMs disabled! They might not know their role.")

        embed = discord.Embed(
            title="🌙 The Expedition Begins...",
            description="The sun sets. The Titans are lurking. Shifters, make your move.",
            color=discord.Color.dark_blue()
        )
        await interaction.followup.send(embed=embed)

    @game_group.command(name="status", description="Check the status of the game")
    async def status(self, interaction: discord.Interaction):
        game = self.get_game(interaction)
        if not game:
            await interaction.response.send_message("❌ No active game.", ephemeral=True)
            return
            
        alive = sum(1 for p in game.players.values() if p.is_alive)
        embed = discord.Embed(
            title="📊 Game Status",
            description=f"Phase: **{game.state.name}**\nAlive: {alive}/{len(game.players)}",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)

    @game_group.command(name="eliminate", description="Eliminate a player (Titan Shifter only, Night phase)")
    @app_commands.describe(target="The Survey Corps member to eliminate")
    async def eliminate(self, interaction: discord.Interaction, target: discord.Member):
        game = self.get_game(interaction)
        if not game or game.state != GameState.NIGHT:
            await interaction.response.send_message("❌ Now is not the time to attack.", ephemeral=True)
            return

        if game.eliminate(interaction.user.id, target.id):
            await interaction.response.send_message("🩸 Target eliminated silently.", ephemeral=True)
            # Check win
            winner = game.check_win()
            if winner:
                await self.end_game(interaction, game, winner)
        else:
            await interaction.response.send_message("❌ Invalid action. You might not be a shifter, you're dead, or target is invalid.", ephemeral=True)

    @game_group.command(name="report", description="Report a fallen comrade to call an emergency meeting")
    async def report(self, interaction: discord.Interaction):
        game = self.get_game(interaction)
        if not game or game.state != GameState.NIGHT:
            await interaction.response.send_message("❌ You can only report during the Night/Action phase.", ephemeral=True)
            return

        if game.report(interaction.user.id):
            embed = discord.Embed(
                title="🚨 EMERGENCY MEETING 🚨",
                description=f"{interaction.user.mention} has found something! Gather immediately to discuss.",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed)
            game.start_voting()
            await interaction.channel.send("🗣️ **Discussion & Voting Phase started!** Use `/among-titans vote @user` to cast your vote, or `/among-titans vote` with no target to skip.")
        else:
            await interaction.response.send_message("❌ You cannot report right now.", ephemeral=True)

    @game_group.command(name="vote", description="Vote to exile a player, or skip by leaving target empty")
    @app_commands.describe(target="The player to vote for (leave empty to skip)")
    async def vote(self, interaction: discord.Interaction, target: discord.Member = None):
        game = self.get_game(interaction)
        if not game or game.state != GameState.VOTING:
            await interaction.response.send_message("❌ It's not voting time.", ephemeral=True)
            return

        target_id = target.id if target else None
        
        if target_id and target_id not in game.players:
            await interaction.response.send_message("❌ Target is not in the game.", ephemeral=True)
            return

        if game.vote(interaction.user.id, target_id):
            await interaction.response.send_message(f"🗳️ {interaction.user.mention} has cast their vote.")
            
            # Check if all alive have voted
            alive_players = [p for p in game.players.values() if p.is_alive]
            if all(p.has_voted for p in alive_players):
                await self.resolve_votes(interaction, game)
        else:
            await interaction.response.send_message("❌ You cannot vote (already voted, dead, or not in game).", ephemeral=True)

    async def resolve_votes(self, interaction: discord.Interaction, game: AmongTitansGame):
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
                
        await interaction.channel.send(embed=embed)
        
        winner = game.check_win()
        if winner:
            await self.end_game(interaction, game, winner)
        else:
            game.state = GameState.NIGHT
            await interaction.channel.send("🌙 The sun sets again. Shifters, make your move.")

    @game_group.command(name="end", description="Forcefully end the game (Host/Admin only)")
    async def end(self, interaction: discord.Interaction):
        game = self.get_game(interaction)
        if not game:
            await interaction.response.send_message("❌ No active game.", ephemeral=True)
            return
            
        if interaction.user.id == game.host_id or interaction.user.guild_permissions.administrator:
            del self.games[interaction.channel_id]
            await interaction.response.send_message("🛑 Game forcefully ended.")
        else:
            await interaction.response.send_message("❌ Only the host or an admin can force end the game.", ephemeral=True)

    async def end_game(self, interaction: discord.Interaction, game: AmongTitansGame, winner: Role):
        embed = discord.Embed(title="🏁 GAME OVER", color=discord.Color.gold())
        if winner == Role.SURVEY_CORPS:
            embed.description = "🏆 **The Survey Corps has eliminated all Titans! Humanity is safe.**"
        else:
            embed.description = "💀 **The Titans have overrun the Survey Corps! Humanity falls.**"
            
        shifter_mentions = [f"<@{p.user_id}> ({p.character_name})" for p in game.players.values() if p.role == Role.TITAN_SHIFTER]
        embed.add_field(name="Titan Shifters", value="\n".join(shifter_mentions) or "None", inline=False)
        
        await interaction.channel.send(embed=embed)
        if game.channel_id in self.games:
            del self.games[game.channel_id]

async def setup(bot):
    await bot.add_cog(AmongTitans(bot))
