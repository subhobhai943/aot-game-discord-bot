# 🪽 AoT Game Discord Bot

A feature-rich Discord bot for Attack on Titan fans, powered by [aot-toolkit](https://github.com/subhobhai943/aot-toolkit).

## ✨ Features

- ⚔️ **Battle Simulation** — Simulate encounters between scouts and titans
- 🪂 **ODM Gear Mini-Game** — Grapple and nape strike simulations
- 📖 **Lore Lookup** — Characters, titans, and quotes from offline database
- 🎮 **Slash Commands** — Modern Discord slash command interface

## 📦 Installation

```bash
git clone https://github.com/subhobhai943/aot-game-discord-bot.git
cd aot-game-discord-bot
pip install -r requirements.txt
```

## ⚙️ Setup

1. Copy `.env.example` to `.env`
2. Add your Discord bot token:
   ```
   DISCORD_TOKEN=your_bot_token_here
   ```
3. Run the bot:
   ```bash
   python bot.py
   ```

## 🤖 Slash Commands

| Command | Description |
|---|---|
| `/character <name>` | Look up a character (e.g. Levi, Mikasa) |
| `/titan <name>` | Look up a titan (e.g. Beast, Armored) |
| `/quote [tag]` | Random quote, optional tag: motivational, dark, wisdom |
| `/battle <character> <titan>` | Full combat narrative simulation |
| `/odm_grapple <distance> [speed] [gas]` | ODM grapple mini-game |
| `/odm_strike [armor_level] [abilities]` | Nape strike simulation |

## 🧱 Project Structure

```
aot-game-discord-bot/
├── bot.py              # Main entry point
├── cogs/
│   ├── battle.py       # Combat simulation commands
│   ├── lore.py         # Character/titan/quote commands
│   └── odm.py          # ODM gear mini-game commands
├── requirements.txt
├── .env.example
└── .gitignore
```

## 📄 License

MIT License
