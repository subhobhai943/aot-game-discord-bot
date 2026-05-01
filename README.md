<div align="center">

# 🪽 AoT Game Discord Bot

**A full-featured Attack on Titan Discord game bot**  
Powered by [aot-toolkit](https://github.com/subhobhai943/aot-toolkit) • Built with Python & discord.py

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.3%2B-5865F2?style=for-the-badge&logo=discord)](https://discordpy.readthedocs.io/)
[![aot-toolkit](https://img.shields.io/badge/aot--toolkit-latest-green?style=for-the-badge)](https://github.com/subhobhai943/aot-toolkit)
[![License](https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge)](LICENSE)

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| ⚔️ **Turn-Based Combat** | Interactive button-driven battles against 9 titan opponents |
| 🎨 **Enhanced Battle Images** | Live scenes with detailed scout/titan silhouettes & ODM gear effects |
| 📊 **Player Profiles** | XP, levels, rank, win/loss stats rendered as image cards |
| 🧙 **Scout Selection** | Choose from 9 iconic AoT characters |
| 👹 **Titan Roster** | 9 titans with unique HP scaling and difficulty |
| 📖 **Lore Lookup** | Offline character, titan & quote database via aot-toolkit |
| 🪂 **ODM Gear Mini-Game** | Grapple and nape strike simulations |
| 🏆 **Rank System** | Cadet → Scout → Elite → Captain → Legend |
| 🎮 **Fun Games** | Trivia, Titan Spawn Simulator, ODM Training, Daily Challenges |
| ⚡ **Character Abilities** | Scout special powers & Titan Transformation Simulator |
| 🛠️ **Gear Upgrades** | Upgrade ODM blades, gas tanks, handles, and thrusters |
| 🧩 **Mikasa Mode** | Red scarf, protection, devotion, and Ackerman bond features |

---

## 🎨 Battle Image System

Every `/fight` turn dynamically generates a **fresh battle image** using Pillow:

- 🪽 **Scout silhouette** with ODM cable grapple lines
- 👹 **Titan silhouette** with glowing red eyes and glow aura
- 🟩 **Live HP bars** that shift color: `Green → Yellow → Red`
- 🏙️ **City skyline background** with lit windows
- 🌌 **Dynamic sky gradient** changes with battle phase
- 🔢 **Round counter badge**, last action log, and name plates
- ✅ / ☠️ **Victory / Defeat overlay** effects at battle end

---

## 🤖 Slash Commands

### ⚔️ Battle Commands
| Command | Description |
|---|---|
| `/fight <titan>` | Start a turn-based battle with live image rendering |
| `/flee` | Flee from your active battle (counts as a loss) |
| `/simulate <character> <titan>` | Cinematic narrative-style battle simulation |

### 🧙 Player Commands
| Command | Description |
|---|---|
| `/profile` | View your profile card as a rendered image |
| `/choose_scout <character>` | Select your scout character for battles |

### 🧩 Mikasa Commands
| Command | Description |
|---|---|
| `/mikasa <action> [user]` | Mikasa actions: red_scarf, protect, devotion, etc. |
| `/ackerman_bond <user>` | Check your Ackerman-style bond with another user |
| `/mikasa_stats` | View Mikasa's combat statistics and profile |

### 🎮 Game Commands
| Command | Description |
|---|---|
| `/trivia` | Play an AoT trivia challenge with reactions |
| `/spawn_titan` | Simulate a random Titan spawn (Common to Legendary) |
| `/odm_training [difficulty]` | Test ODM skills with obstacle course |
| `/daily_challenge` | Get today's daily challenge for bonus XP |
| `/aot_fact` | Get a random Attack on Titan fact |

### ⚡ Ability Commands
| Command | Description |
|---|---|
| `/ability` | Use your scout's signature special ability |
| `/transform <titan>` | Transform into a Titan (simulation) |
| `/gear_upgrade` | View/upgrade ODM gear components |
| `/scout_ranking` | View top 10 Scouts on leaderboard |

### 📖 Lore Commands
| Command | Description |
|---|---|
| `/character <name>` | Look up an AoT character (fuzzy search supported) |
| `/titan <name>` | Look up a titan's stats and abilities |
| `/quote [tag]` | Get a random AoT quote (optional tag: motivational, dark, wisdom) |

### 🪂 ODM Commands
| Command | Description |
|---|---|
| `/odm_grapple <distance> [speed] [gas]` | Simulate an ODM gear grapple |
| `/odm_strike [armor_level] [abilities]` | Simulate a nape strike on a titan |

---

## 📊 Battle Moves

| Move | Damage | Miss Chance |
|---|---|---|
| ⚔️ Slash | 40–70 | 10% |
| 🪂 ODM Dash | 25–55 | 5% |
| 💥 Thunder Spear | 60–100 | 20% |
| 🌀 Spiral Cut | 35–65 | 12% |
| 🧱 Titan Smash | 55–90 | 18% |
| 🛡️ Defend | Heals 20 HP | — |

The **Titan AI** counters with random moves each round: stomp, swipe, boulder throw, roar, and crystal hardening.

---

## 👹 Titan Roster

| Titan | HP | Difficulty |
|---|---|---|
| Founding Titan | 500 | 🔴 Legendary |
| Colossal Titan | 450 | 🔴 Legendary |
| War Hammer Titan | 400 | 🟠 Hard |
| Beast Titan | 380 | 🟠 Hard |
| Armored Titan | 360 | 🟠 Hard |
| Attack Titan | 320 | 🟡 Medium |
| Female Titan | 300 | 🟡 Medium |
| Jaw Titan | 260 | 🟢 Easy |
| Cart Titan | 240 | 🟢 Easy |

---

## 🧙 Scout Roster

Levi Ackerman • Mikasa Ackerman • Eren Yeager • Armin Arlert  
Hange Zoe • Erwin Smith • Reiner Braun • Annie Leonhart • Bertholdt Hoover

---

## 📆 Rank System

| Rank | Level Requirement |
|---|---|
| Cadet | Level 1–4 |
| Scout | Level 5–9 |
| Elite | Level 10–14 |
| Captain | Level 15–19 |
| Legend | Level 20+ |

Earn **+80 XP** on victory and **+20 XP** on defeat. Each level requires `level × 120 XP`.

---

## 📦 Installation

```bash
git clone https://github.com/subhobhai943/aot-game-discord-bot.git
cd aot-game-discord-bot
pip install -r requirements.txt
```

### Requirements

```
discord.py>=2.3.0
aot-toolkit
python-dotenv
Pillow>=10.0.0
aiohttp>=3.8.0
```

---

## ⚙️ Setup

1. **Create a Discord bot** at [discord.com/developers](https://discord.com/developers/applications)
2. Enable **Message Content Intent** and **Server Members Intent**
3. Copy `.env.example` → `.env` and add your token:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

---

## 🧱 Project Structure

```
aot-game-discord-bot/
├── bot.py                  # Main entry point
├── cogs/
│   ├── arena.py            # Turn-based battle system + button UI
│   ├── profile.py          # Player profile card generation
│   ├── battle.py           # Narrative battle simulation
│   ├── lore.py             # Character / titan / quote lookup
│   └── odm.py              # ODM gear mini-game
├── utils/
│   ├── image_gen.py        # Pillow battle & profile image generator
│   └── game_state.py       # Player data, battle sessions, move logic
├── data/
│   └── player_data.json    # Auto-generated player save file
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## 📝 License

This project is **proprietary and closed-source**.  
All rights reserved © 2026 [Subhadip Sarkar](https://github.com/subhobhai943).  
See [LICENSE](LICENSE) for full terms. Unauthorized copying, distribution, or modification is strictly prohibited.
