"""Fun minigames: AoT trivia, titan spawn simulator, ODM training."""
import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.game_state import GameState, TITANS, CHARACTERS, get_titan_image, SURVEY_CORPS_ICON
from utils.gifs import get_gif



# AoT Trivia Questions
TRIVIA_QUESTIONS = [
    {
        "question": "What is Eren's vow to the world?",
        "options": ["Tatakae!", "I'll kill them all!", "Freedom!", "Never give up!"],
        "answer": 0,
        "explanation": "Eren Yeager's iconic battle cry throughout the series!",
        "image": get_titan_image("Attack Titan"),
    },
    {
        "question": "Which character can use the Founding Titan's power?",
        "options": ["Eren Yeager", "Zeke Yeager", "Rod Reiss", "Both Eren and Zeke"],
        "answer": 3,
        "explanation": "The Founding Titan requires royal blood AND can be used by Eren through his connection to Zeke.",
        "image": get_titan_image("Founding Titan"),
    },
    {
        "question": "What is Levi Ackerman's rank?",
        "options": ["Captain", "Squad Leader", "Commander", "General"],
        "answer": 1,
        "explanation": "Levi leads the Special Operations Squad, an elite team answering directly to Commander Erwin.",
        "image": SURVEY_CORPS_ICON,
    },
    {
        "question": "How many times has Mikasa saved Eren?",
        "options": ["Once", "Twice", "Too many to count", "Never needed"],
        "answer": 2,
        "explanation": "According to the series, she's saved him countless times throughout their lives!",
        "image": SURVEY_CORPS_ICON,
    },
    {
        "question": "Which Titan is known as the 'Strongest Titan'?",
        "options": ["Colossal Titan", "Armored Titan", "Attack Titan", "Founding Titan"],
        "answer": 3,
        "explanation": "The Founding Titan holds absolute power over all Titans and the Subjects of Ymir.",
        "image": get_titan_image("Founding Titan"),
    },
    {
        "question": "What is the name of Eren's father?",
        "options": ["Grisha Yeager", "Kruger Yeager", "Zeke Yeager", "Keith Shadis"],
        "answer": 0,
        "explanation": "Grisha Yeager is the one who stole the Founding Titan from the Reiss family.",
        "image": get_titan_image("Attack Titan"),
    },
    {
        "question": "Which Titan did Annie Leonhart possess?",
        "options": ["Female Titan", "War Hammer Titan", "Cart Titan", "Jaw Titan"],
        "answer": 0,
        "explanation": "Annie was the inheritor of the Female Titan during the 57th Expedition.",
        "image": get_titan_image("Female Titan"),
    },
    {
        "question": "What does the phrase 'Sasageyo!' mean?",
        "options": ["Devote yourselves!", "Die for freedom!", "Attack!", "Never surrender!"],
        "answer": 0,
        "explanation": "The Survey Corps' battle cry, meaning 'Dedicate your hearts!' in Japanese.",
        "image": SURVEY_CORPS_ICON,
    },
    {
        "question": "Which character can transform into a Titan WITHOUT being injected?",
        "options": ["Hange Zoe", "Armin Arlert", "Historia Reiss", "Ymir Fritz"],
        "answer": 1,
        "explanation": "Armin inherited the Colossal Titan through serum but can transform due to his determination.",
        "image": get_titan_image("Colossal Titan"),
    },
    {
        "question": "What is the Colossal Titan's signature ability?",
        "options": ["Hardening", "Explosive Transformation", "Speed", "Flight"],
        "answer": 1,
        "explanation": "Bertolt Hoover's Colossal Titan creates massive explosions upon transformation!",
        "image": get_titan_image("Colossal Titan"),
    },
]

# Titan spawn rates
TITAN_SPAWN_DATA = {
    "Pure Titan":       {"rarity": "Common",    "weight": 50, "description": "A mindless Titan wandering the wasteland"},
    "Abnormal Titan":   {"rarity": "Uncommon",  "weight": 30, "description": "A Titan moving with unusual speed and purpose"},
    "Jaw Titan":        {"rarity": "Rare",      "weight": 12, "description": "A fast, agile Titan with crushing jaws"},
    "Cart Titan":       {"rarity": "Rare",      "weight": 10, "description": "A quadrupedal Titan built for endurance and cargo"},
    "Female Titan":     {"rarity": "Epic",      "weight": 5,  "description": "A highly intelligent Titan with hardening abilities"},
    "Armored Titan":    {"rarity": "Epic",      "weight": 4,  "description": "A heavily armored Titan with incredible defense"},
    "Beast Titan":      {"rarity": "Legendary", "weight": 2,  "description": "A Titan with beast-like features and projectile power"},
    "War Hammer Titan": {"rarity": "Legendary", "weight": 1,  "description": "A Titan capable of creating weapons from hardened crystal"},
}


class Games(commands.Cog):
    """Fun minigames and simulations for AoT fans!"""

    def __init__(self, bot):
        self.bot = bot
        self.active_trivia = {}  # message_id -> game state

    # ── Trivia Command ─────────────────────────────────────────────────────────

    @app_commands.command(name="trivia", description="Play an Attack on Titan trivia game!")
    async def trivia(self, interaction: discord.Interaction):
        q = random.choice(TRIVIA_QUESTIONS)
        options = q["options"]
        letters = ["🇦", "🇧", "🇨", "🇩"]

        embed = discord.Embed(
            title="📖 AoT Trivia Challenge",
            description=f"**{q['question']}**\n\n" + "\n".join(f"{letters[i]} {options[i]}" for i in range(4)),
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=q.get("image", SURVEY_CORPS_ICON))
        embed.set_footer(text="⏳ You have 30 seconds to answer! | React with the correct letter")

        msg = await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for letter in letters:
            await msg.add_reaction(letter)

        self.active_trivia[str(msg.id)] = {
            "question": q["question"],
            "answer": q["answer"],
            "explanation": q["explanation"],
            "options": options,
            "creator": interaction.user.id,
            "correct_users": set(),
        }

    # ── Titan Spawn Simulator ──────────────────────────────────────────────────

    @app_commands.command(name="spawn_titan", description="Simulate a Titan spawning in the wasteland!")
    async def spawn_titan(self, interaction: discord.Interaction):
        items = list(TITAN_SPAWN_DATA.items())
        names = [item[0] for item in items]
        weights = [item[1]["weight"] for item in items]

        result = random.choices(names, weights=weights, k=1)[0]
        data = TITAN_SPAWN_DATA[result]

        rarity_colors = {
            "Common":    discord.Color.light_grey(),
            "Uncommon":  discord.Color.green(),
            "Rare":      discord.Color.blue(),
            "Epic":      discord.Color.purple(),
            "Legendary": discord.Color.gold(),
        }
        rarity_emojis = {
            "Common": "⬜", "Uncommon": "🟢", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡",
        }

        embed = discord.Embed(
            title="👹 TITAN SPOTTED!",
            description="🚨 *A terrifying presence appears on the horizon...*",
            color=rarity_colors.get(data["rarity"], discord.Color.red())
        )
        embed.add_field(name="👾 Type",        value=f"**{result}**", inline=True)
        embed.add_field(name="⭐ Rarity",      value=f"{rarity_emojis.get(data['rarity'], '')} {data['rarity']}", inline=True)
        embed.add_field(name="\u200b",           value="\u200b", inline=True)
        embed.add_field(name="📜 Description", value=data["description"], inline=False)

        titan_img = get_titan_image(result)
        if titan_img:
            embed.set_image(url=titan_img)

        if data["rarity"] == "Legendary":
            embed.set_footer(text="💀 RUN! A LEGENDARY TITAN HAS APPEARED! 💀")
        elif data["rarity"] in ["Epic", "Rare"]:
            embed.set_footer(text="⚔️ Prepare for battle! Sound the horns!")
        else:
            embed.set_footer(text="📢 Sound the alarm! All soldiers to positions!")

        await interaction.response.send_message(embed=embed)

    # ── ODM Gear Training ─────────────────────────────────────────────────────

    @app_commands.command(name="odm_training", description="Test your ODM gear skills with a training simulation!")
    @app_commands.describe(difficulty="Training difficulty level")
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Beginner",     value="easy"),
        app_commands.Choice(name="Intermediate", value="medium"),
        app_commands.Choice(name="Elite",        value="hard"),
    ])
    async def odm_training(self, interaction: discord.Interaction, difficulty: str = "medium"):
        difficulties = {
            "easy":   {"obstacles": 5,  "success_rate": 0.90, "name": "Beginner"},
            "medium": {"obstacles": 8,  "success_rate": 0.75, "name": "Intermediate"},
            "hard":   {"obstacles": 12, "success_rate": 0.55, "name": "Elite"},
        }
        d = difficulties[difficulty]
        results = []
        score = 0
        obstacle_types = [
            "Tight urban passage", "Building grapple swing", "High-speed descent",
            "Nape strike practice", "Gas conservation run", "Blade durability test",
            "Emergency evasion", "Multi-target lock",
        ]
        for i in range(d["obstacles"]):
            obstacle = obstacle_types[i % len(obstacle_types)]
            success = random.random() < d["success_rate"]
            if success:
                score += 1
                results.append(f"✅ {obstacle} - Success!")
            else:
                results.append(f"❌ {obstacle} - Failed!")

        percentage = int((score / d["obstacles"]) * 100)

        if percentage >= 90:
            grade, grade_emoji, color = "S Rank! 🏆", "👑", discord.Color.gold()
            banner = get_titan_image("Colossal Titan")
        elif percentage >= 80:
            grade, grade_emoji, color = "A Rank!", "⚡", discord.Color.green()
            banner = get_titan_image("Armored Titan")
        elif percentage >= 60:
            grade, grade_emoji, color = "B Rank!", "✅", discord.Color.teal()
            banner = get_titan_image("Female Titan")
        elif percentage >= 40:
            grade, grade_emoji, color = "C Rank!", "📜", discord.Color.orange()
            banner = get_titan_image("Jaw Titan")
        else:
            grade, grade_emoji, color = "D Rank! 💀", "💀", discord.Color.red()
            banner = get_titan_image("Pure Titan")

        embed = discord.Embed(
            title=f"🪂 ODM Gear Training — {d['name']} Course",
            description=f"{grade_emoji} **Final Grade: {grade}** ({percentage}%)\n**Score:** {score}/{d['obstacles']} obstacles cleared",
            color=color
        )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        embed.set_image(url=banner)

        result_text = "\n".join(results[:10])
        if len(results) > 10:
            result_text += f"\n... and {len(results) - 10} more"
        embed.add_field(name="📋 Results", value=result_text, inline=False)

        xp_gained = score * (10 if difficulty == "easy" else 15 if difficulty == "medium" else 20)
        embed.add_field(name="💰 Rewards", value=f"+{xp_gained} XP", inline=True)

        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        player.add_xp(xp_gained)
        GameState.save_player(player)

        embed.add_field(name="🔖 New Level", value=f"Level {player.level} ({player.xp}/{player.xp_needed} XP)", inline=True)
        embed.set_footer(text="Remember: Speed is everything in ODM combat!")
        await interaction.response.send_message(embed=embed)

    # ── Daily Challenge ────────────────────────────────────────────────────────────

    @app_commands.command(name="daily_challenge", description="Get today's AoT daily challenge!")
    async def daily_challenge(self, interaction: discord.Interaction):
        challenges = [
            {"title": "Titan Slayer",  "desc": "Win a battle against any titan",              "reward": 50,  "image": get_titan_image("Pure Titan")},
            {"title": "Lore Master",   "desc": "Look up 3 different characters",               "reward": 30,  "image": SURVEY_CORPS_ICON},
            {"title": "ODM Expert",    "desc": "Complete an ODM training course",              "reward": 40,  "image": SURVEY_CORPS_ICON},
            {"title": "Team Player",   "desc": "React to another player's message with a gif", "reward": 20,  "image": SURVEY_CORPS_ICON},
            {"title": "Scout Elite",   "desc": "Reach a new rank level",                       "reward": 100, "image": get_titan_image("Beast Titan")},
        ]
        challenge = random.choice(challenges)

        embed = discord.Embed(
            title="📜 Daily Challenge",
            description=f"**{challenge['title']}**\n\n{challenge['desc']}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=challenge["image"])
        embed.add_field(name="🎁 Reward",     value=f"{challenge['reward']} XP", inline=True)
        embed.add_field(name="⏱️ Time Limit", value="24 hours",                inline=True)
        embed.set_footer(text="Complete challenges for bonus XP!")

        if random.random() < 0.3:
            q = random.choice(TRIVIA_QUESTIONS)
            embed.add_field(
                name="💡 Bonus Trivia",
                value=f"**{q['question']}**\n*(Answer: {q['options'][q['answer']]}) — {q['explanation']}*",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    # ── Random Fact ───────────────────────────────────────────────────────────────

    @app_commands.command(name="aot_fact", description="Get a random Attack on Titan fact!")
    async def aot_fact(self, interaction: discord.Interaction):
        facts = [
            {"text": "Eren's Titan form is 15 meters tall, the same height as the Attack Titan.",                                   "image": get_titan_image("Attack Titan")},
            {"text": "Mikasa's scarf is made from the same material as the Scout Regiment cloaks.",                                 "image": SURVEY_CORPS_ICON},
            {"text": "The Founding Titan can alter or erase the memories of Subjects of Ymir.",                                     "image": get_titan_image("Founding Titan")},
            {"text": "Levi's cleaning obsession is so strong he once threatened to break Eren's legs for dirtying the room.",        "image": SURVEY_CORPS_ICON},
            {"text": "The Colossal Titan can emit steam at will, using it as both offense and defense.",                            "image": get_titan_image("Colossal Titan")},
            {"text": "Armin's strategic mind was recognized even by Erwin Smith, who trusted him with crucial plans.",              "image": get_titan_image("Colossal Titan")},
            {"text": "Reiner's 'Warrior' persona was a coping mechanism for his years of living as a double agent.",               "image": get_titan_image("Armored Titan")},
            {"text": "The Beast Titan's ability to throw objects with precision is unmatched by any other Titan.",                  "image": get_titan_image("Beast Titan")},
            {"text": "Historia Reiss was willing to sacrifice herself to save Eren and humanity.",                                   "image": get_titan_image("Founding Titan")},
            {"text": "Hange Zoë's passion for Titan research led to numerous breakthroughs in Titan biology.",                      "image": SURVEY_CORPS_ICON},
            {"text": "The War Hammer Titan can create structures and weapons from hardened crystal.",                                "image": get_titan_image("War Hammer Titan")},
            {"text": "Ymir Fritz's connection to the Founding Titan spans over 2,000 years of history.",                           "image": get_titan_image("Founding Titan")},
            {"text": "The Attack Titan can see memories of future inheritors, creating visions of what's to come.",                "image": get_titan_image("Attack Titan")},
            {"text": "Annie Leonhart's crystal hardening ability can preserve her Titan form indefinitely.",                        "image": get_titan_image("Female Titan")},
            {"text": "The Cart Titan's endurance allowed its inheritor to maintain Titan form for months.",                        "image": get_titan_image("Cart Titan")},
            {"text": "The Jaw Titan is the fastest of all Nine Titans due to its small size and agile claws.",                     "image": get_titan_image("Jaw Titan")},
        ]
        fact = random.choice(facts)

        embed = discord.Embed(
            title="📚 Did You Know?",
            description=fact["text"],
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=fact["image"])
        embed.set_footer(text="🧩 The mystery of the Titans continues...")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Games(bot))
