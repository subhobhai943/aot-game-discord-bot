# 🪽 AoT Game Discord Bot — Advanced Edition

A full-featured Attack on Titan Discord game bot powered by [aot-toolkit](https://github.com/subhobhai943/aot-toolkit).

## ✨ Features

- ⚔️ **Turn-Based Battle System** with interactive buttons
- 🎨 **Dynamic Battle Images** generated with Pillow (HP bars, scout vs titan silhouettes, phase effects)
- 📊 **Player Profiles** with level, XP, rank, win/loss stats — rendered as image cards
- 🧙 **Scout Selection** — choose from 9 AoT characters
- 👹 **9 Titan Opponents** with unique HP scaling
- 📖 **Lore Lookup** — characters, titans, quotes
- 🪂 **ODM Gear Mini-Game**

## 📦 Installation

```bash
git clone https://github.com/subhobhai943/aot-game-discord-bot.git
cd aot-game-discord-bot
pip install -r requirements.txt
```

## ⚙️ Setup

1. Copy `.env.example` to `.env`
2. Add your Discord bot token
3. Run: `python bot.py`

## 🤖 Slash Commands

| Command | Description |
|---|---|
| `/fight <titan>` | Start a turn-based battle with image rendering |
| `/flee` | Flee from active battle (counts as loss) |
| `/profile` | View your profile card as an image |
| `/choose_scout <character>` | Select your scout character |
| `/character <name>` | Look up character lore |
| `/titan <name>` | Look up titan info |
| `/quote [tag]` | Random AoT quote |
| `/simulate <char> <titan>` | Cinematic narrative simulation |
| `/odm_grapple <distance>` | ODM gear grapple sim |
| `/odm_strike [armor_level]` | Nape strike simulation |

## 🎨 Battle Image System

Each `/fight` turn generates a fresh battle image showing:
- Scout vs Titan silhouettes with glow auras
- Dynamic HP bars (green → yellow → red)
- Round counter
- Last action log
- Phase-based sky background (normal → intense → victory/defeat)

## 📄 License

MIT License
