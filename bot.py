import os
import sys
import subprocess
import shutil
import urllib.request
import tarfile
import discord
from discord.ext import commands
from dotenv import load_dotenv
from cogs.settings import get_prefix

load_dotenv()


def install_dependencies():
    """Auto-install missing Python packages at startup."""
    packages = ["yt-dlp", "PyNaCl"]
    for pkg in packages:
        module = pkg.replace("-", "_").lower()
        try:
            __import__(module)
        except ImportError:
            print(f"[Setup] Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])
            print(f"[Setup] {pkg} installed!")


def install_ffmpeg():
    """Auto-download static ffmpeg binary using Python only (no wget/tar CLI needed)."""
    # Check if ffmpeg already exists in system PATH
    if shutil.which("ffmpeg"):
        print("[Setup] ffmpeg already available in PATH.")
        return

    ffmpeg_dir = os.path.join(os.path.expanduser("~"), "ffmpeg_bin")
    ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg")

    # Check if already downloaded before
    if os.path.isfile(ffmpeg_bin):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        print("[Setup] ffmpeg found in ~/ffmpeg_bin, added to PATH.")
        return

    print("[Setup] ffmpeg not found. Downloading static binary (this may take ~30s)...")
    os.makedirs(ffmpeg_dir, exist_ok=True)

    url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    archive_path = os.path.join(ffmpeg_dir, "ffmpeg.tar.xz")

    try:
        # Download using Python urllib (no wget needed)
        print("[Setup] Downloading ffmpeg...")
        urllib.request.urlretrieve(url, archive_path)
        print("[Setup] Download complete. Extracting...")

        # Extract using Python tarfile module (no tar CLI needed)
        with tarfile.open(archive_path, "r:xz") as tar:
            for member in tar.getmembers():
                # Only extract the ffmpeg binary file itself
                if member.name.endswith("/ffmpeg") and member.isfile():
                    member.name = "ffmpeg"  # flatten path
                    tar.extract(member, ffmpeg_dir)
                    break

        os.remove(archive_path)

        # Make it executable
        os.chmod(ffmpeg_bin, 0o755)

        # Add to PATH for this session
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        print("[Setup] ffmpeg installed successfully at ~/ffmpeg_bin/ffmpeg!")

    except Exception as e:
        print(f"[Setup] WARNING: Could not auto-install ffmpeg: {e}")
        print("[Setup] Music voice commands may not work.")


# Run auto-setup before loading the bot
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
