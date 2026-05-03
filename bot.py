import os
import sys
import subprocess
import discord
from discord.ext import commands
from dotenv import load_dotenv
from cogs.settings import get_prefix

load_dotenv()


def install_dependencies():
    """Auto-install Python packages and ffmpeg-python at startup."""
    packages = ["yt-dlp", "PyNaCl"]
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_").lower())
        except ImportError:
            print(f"[Setup] Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])
            print(f"[Setup] {pkg} installed!")


def install_ffmpeg():
    """Download and install static ffmpeg binary if not found."""
    import shutil
    if shutil.which("ffmpeg"):
        print("[Setup] ffmpeg already available.")
        return

    ffmpeg_dir = os.path.join(os.path.expanduser("~"), "ffmpeg")
    ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg")

    if os.path.isfile(ffmpeg_bin):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        print("[Setup] ffmpeg found in ~/ffmpeg, added to PATH.")
        return

    print("[Setup] ffmpeg not found. Downloading static binary...")
    os.makedirs(ffmpeg_dir, exist_ok=True)
    try:
        url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        archive = os.path.join(ffmpeg_dir, "ffmpeg.tar.xz")
        subprocess.check_call(["wget", "-q", "-O", archive, url])
        subprocess.check_call(["tar", "-xf", archive, "-C", ffmpeg_dir, "--strip-components=1", "--wildcards", "*/ffmpeg"])
        os.remove(archive)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        print("[Setup] ffmpeg installed successfully!")
    except Exception as e:
        print(f"[Setup] WARNING: Could not install ffmpeg automatically: {e}")
        print("[Setup] Music commands may not work. Install ffmpeg manually.")


# Run auto-setup before anything else
install_dependencies()
install_ffmpeg()


def get_prefix_for_bot(bot, message):
    """Dynamic prefix per server."""
    if message.guild:
        p = get_prefix(message.guild.id)
        return [p + " ", p]
    return ["! ", "!"]


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=get_prefix_for_bot, intents=intents)

COGS = [
    "cogs.settings",
    "cogs.help",
    "cogs.battle",
    "cogs.lore",
    "cogs.odm",
    "cogs.profile",
    "cogs.arena",
    "cogs.gifs",
    "cogs.mikasa",
    "cogs.games",
    "cogs.abilities",
    "cogs.afk",
    "cogs.automod",
    "cogs.music",     # Music player — YouTube, Spotify search, ping
]


@bot.event
async def on_ready():
    print(f"\u2705 Logged in as {bot.user}")
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"  \u2714 Loaded {cog}")
        except Exception as e:
            print(f"  \u274c Failed to load {cog}: {e}")
    await bot.tree.sync()
    print("\u2705 All slash commands synced!")


bot.run(os.getenv("DISCORD_TOKEN"))
