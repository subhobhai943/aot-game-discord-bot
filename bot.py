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


def install_all_requirements():
    """Install everything from requirements.txt at startup."""
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    if not os.path.isfile(req_file):
        print("[Setup] requirements.txt not found, skipping.")
        return
    print("[Setup] Installing all packages from requirements.txt...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"],
        )
        print("[Setup] All requirements installed!")
    except Exception as e:
        print(f"[Setup] Warning: some packages failed to install: {e}")


def install_system_deps():
    """Install libsodium + ffmpeg via apt if available."""
    if shutil.which("apt-get"):
        try:
            print("[Setup] Installing libsodium + ffmpeg via apt...")
            subprocess.check_call(
                ["apt-get", "install", "-y", "-q", "libsodium-dev", "ffmpeg"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            print("[Setup] libsodium + ffmpeg installed via apt!")
            return True
        except Exception as e:
            print(f"[Setup] apt install failed: {e}")
    return False


def install_ffmpeg_fallback():
    """Download static ffmpeg binary using Python only if apt did not provide it."""
    if shutil.which("ffmpeg"):
        print("[Setup] ffmpeg already available in PATH.")
        return

    ffmpeg_dir = os.path.join(os.path.expanduser("~"), "ffmpeg_bin")
    ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg")

    if os.path.isfile(ffmpeg_bin):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        print("[Setup] ffmpeg found in ~/ffmpeg_bin, added to PATH.")
        return

    print("[Setup] Downloading static ffmpeg binary...")
    os.makedirs(ffmpeg_dir, exist_ok=True)
    url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    archive_path = os.path.join(ffmpeg_dir, "ffmpeg.tar.xz")
    try:
        urllib.request.urlretrieve(url, archive_path)
        with tarfile.open(archive_path, "r:xz") as tar:
            for member in tar.getmembers():
                if member.name.endswith("/ffmpeg") and member.isfile():
                    member.name = "ffmpeg"
                    tar.extract(member, ffmpeg_dir)
                    break
        os.remove(archive_path)
        os.chmod(ffmpeg_bin, 0o755)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        print("[Setup] ffmpeg installed at ~/ffmpeg_bin/ffmpeg!")
    except Exception as e:
        print(f"[Setup] WARNING: ffmpeg fallback download failed: {e}")


# --- Run all setup steps before loading the bot ---
apt_success = install_system_deps()
install_all_requirements()   # installs aot-toolkit, Pillow, PyNaCl, yt-dlp, etc.
if not apt_success:
    install_ffmpeg_fallback()


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
    "cogs.music",
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
