import os
import re
import json
import asyncio
import datetime
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from collections import deque
import time
from typing import Optional

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
POPULAR_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-pro-exp-02-05"
]

_request_times: deque = deque()
RPM_LIMIT = 14
RPD_LIMIT = 490
_daily_count = {"date": "", "count": 0}

SYSTEM_PROMPT = """You are Levi Ackerman, captain of the Survey Corps and this Discord server's AI assistant.
You help with:
- Making announcements (write a detailed, well-formatted announcement when asked)
- Moderating users on demand (warn/mute/kick/ban)
- Answering server questions
- Finding and playing music/playlists based on the user's mood, request, or environment (e.g. play some training music, find something relaxing, play aot theme, etc.)
- Any server management task

Respond in Levi's curt, no-nonsense tone.
If asked to make an announcement, write a DETAILED, well-formatted announcement (at least 4-6 lines). 
Include emojis, a title line starting with 📣, the body details, and a closing line. Make it look professional.
Do NOT write JSON for announcements — just write the announcement text directly.
If asked to warn/mute/kick/ban a user, respond ONLY with this JSON (no other text):
{"action": "warn|mute|kick|ban", "target": "<@userID or username>", "reason": "<reason>"}
If the user wants you to play or find music based on their mood, environment, request, or description, respond ONLY with this JSON (no other text):
{"action": "play_music", "query": "<YouTube search term, song name, or one of the built-in playlists: AOT, DEATHNOTE, NARUTO, DEMONSLAYER, BERSERK, VINLANDSAGA, TOKYOREVENGERS, JUJUTSUKAISEN>", "reply": "<Levi's curt, no-nonsense response explaining his choice and instructing them to listen>"}
Otherwise respond naturally."""

guild_config: dict[int, dict] = {}
warning_counts: dict[int, dict[int, int]] = {}


NVIDIA_API_URL = os.getenv("NVIDIA_API_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
DEFAULT_NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"
SETTINGS_FILE = "data/guild_settings.json"

POPULAR_MODELS = [
    "openai/gpt-oss-120b",
    "google/gemma-4-31b-it",
    "nvidia/gemma-4-31b-it-nvfp4",
    "moonshotai/kimi-k2.6",
    "z-ai/glm-5.1",
    "nvidia/glm-5.1-nvfp4",
    "deepseek-ai/deepseek-r1",
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "microsoft/phi-4",
    "microsoft/phi-4-mini-instruct",
    "microsoft/phi-4-mini-flash-reasoning",
    "mistralai/mistral-large-2-instruct",
    "mistralai/codestral-22b-instruct-v0.1",
    "nvidia/nemotron-mini-4b-instruct"
]


def _get_guild_setting(guild_id: Optional[int], key: str, default: str) -> str:
    if not guild_id:
        return default
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
                return data.get(str(guild_id), {}).get(key, default)
        except Exception:
            pass
    return default


def _get_system_prompt(guild_id: Optional[int]) -> str:
    mode = _get_guild_setting(guild_id, "ai_mode", "captain")
    common = (
        "You help with:\n"
        "- Making announcements (write a detailed, well-formatted announcement when asked)\n"
        "- Moderating users on demand (warn/mute/kick/ban)\n"
        "- Answering server questions\n"
        "- Finding and playing music/playlists based on the user's mood, request, or environment\n"
        "- Any server management task\n\n"
        "Rules:\n"
        "1. If asked to make an announcement, write a DETAILED, well-formatted announcement (at least 4-6 lines). "
        "Include emojis, a title line starting with 📣, the body details, and a closing line. Do NOT write JSON for announcements.\n"
        "2. If asked to warn/mute/kick/ban a user, respond ONLY with this JSON (no other text):\n"
        '{"action": "warn|mute|kick|ban", "target": "<@userID or username>", "reason": "<reason>"}\n'
        "3. If the user wants you to play or find music based on their mood/request, respond ONLY with this JSON (no other text):\n"
        '{"action": "play_music", "query": "<YouTube search term, song name, or one of the built-in playlists: AOT, DEATHNOTE, NARUTO, DEMONSLAYER, BERSERK, VINLANDSAGA, TOKYOREVENGERS, JUJUTSUKAISEN>", "reply": "<Your explanation of choice and instructing them to listen>"}\n'
        "4. LANGUAGE RULE: You MUST respond in the same language and script/style as the user's request. Do NOT refuse to answer in other languages. "
        "Translate your personality and tone naturally into their language. "
        "CRITICAL: If the user communicates in Hinglish (Hindi written using the English/Latin alphabet), you MUST respond in Hinglish using the Latin script. "
        "Do NOT reply in Devanagari script (Hindi characters) for Hinglish messages."
    )
    if mode == "friendly":
        personality = (
            "You are a friendly, warm, helpful, and polite AI assistant for this server.\n"
            "Respond in a very kind, supportive, and welcoming tone, showing a lot of care and eagerness to help. "
            "Avoid any rudeness, seriousness, or Levi Ackerman phrases. Keep it cheerful!"
        )
    elif mode == "funny":
        personality = (
            "You are a funny, sarcastic, witty, and humorous AI assistant for this server.\n"
            "Respond in a playful, lighthearted, and joke-filled tone. Use clever sarcasm, jokes, and funny analogies, "
            "but make sure you still answer their query or task helpful."
        )
    elif mode == "anime":
        personality = (
            "You are a high-energy, passionate, and hyper-enthusiastic anime protagonist AI assistant!\n"
            "Respond with fire, determination, and loud energy! Use classic anime protagonist phrases (like 'Yosh!', "
            "'Believe it!', 'Let's Tatakae!', 'I won't back down!'). Talk about the power of friendship, hard work, "
            "and overcoming walls. Keep the energy level at 100%!"
        )
    else:  # captain (default)
        personality = (
            "You are Levi Ackerman, captain of the Survey Corps and this Discord server's AI assistant.\n"
            "Respond in Levi's curt, no-nonsense, serious, and slightly rude tone (e.g. use phrases like 'Tch', 'clean it up', "
            "'recruit', etc.). Keep it serious, disciplined, and captain-like."
        )
    return f"{personality}\n\n{common}"


def _set_guild_setting(guild_id: Optional[int], key: str, value: str):
    if not guild_id:
        return
    data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
        except Exception:
            pass
    data.setdefault(str(guild_id), {})[key] = value
    os.makedirs("data", exist_ok=True)
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Error saving settings: {e}]")


def _get_gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")


def _get_nvidia_key() -> str:
    return os.getenv("NVIDIA_API_KEY", "")


def _get_nvidia_model() -> str:
    return os.getenv("NVIDIA_MODEL", DEFAULT_NVIDIA_MODEL)


def _get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)


def _can_call_api() -> tuple[bool, str]:
    now = time.time()
    while _request_times and _request_times[0] < now - 60:
        _request_times.popleft()
    if len(_request_times) >= RPM_LIMIT:
        return False, "rpm"
    today = datetime.date.today().isoformat()
    if _daily_count["date"] != today:
        _daily_count["date"] = today
        _daily_count["count"] = 0
    if _daily_count["count"] >= RPD_LIMIT:
        return False, "rpd"
    return True, "ok"


def _record_token_usage(guild_id: Optional[int], prompt_tokens: int, completion_tokens: int):
    if not guild_id:
        return
    data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
        except Exception:
            pass
            
    guild_data = data.setdefault(str(guild_id), {})
    stats = guild_data.setdefault("ai_usage_stats", {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_requests": 0
    })
    
    stats["input_tokens"] = stats.get("input_tokens", 0) + prompt_tokens
    stats["output_tokens"] = stats.get("output_tokens", 0) + completion_tokens
    stats["total_requests"] = stats.get("total_requests", 0) + 1
    
    os.makedirs("data", exist_ok=True)
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Error saving settings: {e}]")


async def call_gemini(prompt: str, system: Optional[str] = None, guild_id: Optional[int] = None) -> tuple[str, str]:
    if system is None:
        system = _get_system_prompt(guild_id)
    global_nv_key = _get_nvidia_key()
    default_provider = "nvidia" if global_nv_key else "gemini"
    provider = _get_guild_setting(guild_id, "ai_provider", default_provider)

    if provider == "nvidia" and global_nv_key:
        nv_model = _get_guild_setting(guild_id, "nvidia_model", _get_nvidia_model())
        payload = {
            "model": nv_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 768
        }
        headers = {
            "Authorization": f"Bearer {global_nv_key}",
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    NVIDIA_API_URL, 
                    json=payload, 
                    headers=headers, 
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        usage = data.get("usage", {})
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
                        if guild_id:
                            _record_token_usage(guild_id, prompt_tokens, completion_tokens)
                        return data["choices"][0]["message"]["content"].strip(), f"NVIDIA NIM ({nv_model})"
                    else:
                        text = await resp.text()
                        print(f"[NVIDIA NIM error {resp.status}: {text[:200]}. Falling back to Gemini...]")
        except Exception as e:
            print(f"[NVIDIA NIM exception: {e}. Falling back to Gemini...]")

    key = _get_gemini_key()
    if not key:
        return "⚠️ Both NVIDIA_API_KEY and GEMINI_API_KEY are missing in .env!", "None"
    allowed, reason = _can_call_api()
    if not allowed:
        msg = "⏳ Too many requests this minute. Wait a moment." if reason == "rpm" else "🚫 Daily API limit reached."
        return msg, "None"
    _request_times.append(time.time())
    _daily_count["count"] += 1
    
    gemini_model = _get_guild_setting(guild_id, "gemini_model", _get_gemini_model())
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={key}"
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 768}
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    usage = data.get("usageMetadata", {})
                    prompt_tokens = usage.get("promptTokenCount", 0)
                    completion_tokens = usage.get("candidatesTokenCount", 0)
                    if guild_id:
                        _record_token_usage(guild_id, prompt_tokens, completion_tokens)
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip(), f"Gemini ({gemini_model})"
                elif resp.status == 429:
                    return "⏳ Rate limit hit. Try again in a moment.", f"Gemini ({gemini_model})"
                else:
                    text = await resp.text()
                    return f"[Gemini error {resp.status}: {text[:200]}]", f"Gemini ({gemini_model})"
    except asyncio.TimeoutError:
        return "⏳ Gemini timed out. Try again.", f"Gemini ({gemini_model})"
    except Exception as e:
        return f"[Error: {e}]", f"Gemini ({gemini_model})"


def _extract_channel(message: discord.Message, clean_text: str) -> discord.TextChannel | None:
    """
    Try to find a target channel from:
    1. #channel mentions in the message
    2. Channel name mentioned in the text e.g. 'in #announcements' or 'to general'
    """
    # From actual Discord #channel mention objects
    if message.channel_mentions:
        return message.channel_mentions[0]
    # From text pattern like "in #announcements" or "to #general"
    name_match = re.search(r"(?:in|to|at|into|on)\s+#?([-\w]+)", clean_text, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).lower()
        found = discord.utils.find(
            lambda c: isinstance(c, discord.TextChannel) and c.name.lower() == name,
            message.guild.channels
        )
        if found:
            return found
    return None


def _is_announcement_request(text: str) -> bool:
    keywords = ["announce", "announcement", "post", "notify", "broadcast", "tell everyone", "inform"]
    return any(kw in text.lower() for kw in keywords)


async def _send_announcement(
    guild: discord.Guild,
    target_ch: discord.TextChannel,
    draft: str,
    posted_by: discord.Member,
    ping_everyone: bool = True,
    model_used: str = "Gemini"
):
    """Build a rich announcement embed and send it with @everyone to target_ch."""
    embed = discord.Embed(
        description=draft,
        color=discord.Color.from_rgb(200, 60, 40),  # AoT red
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_author(
        name=f"⚔️ {guild.name} — Official Announcement",
        icon_url=guild.icon.url if guild.icon else None
    )
    embed.set_footer(text=f"Posted by {posted_by.display_name} via Levi AI • {model_used}")
    # @everyone mention BEFORE the embed so it shows as a ping
    ping = "@everyone" if ping_everyone else ""
    await target_ch.send(content=ping if ping else None, embed=embed)


class AiModelSelect(discord.ui.Select):
    def __init__(self, provider: str, current_model: str, models_list: list[str]):
        options = []
        for i, m in enumerate(models_list):
            is_active = (m == current_model)
            label = f"{m}"
            if len(label) > 100:
                label = label[:97] + "..."
            options.append(discord.SelectOption(
                label=label,
                value=m,
                description=f"Select {provider.upper()} model #{i+1}",
                default=is_active
            ))
        placeholder = f"Select a {provider.upper()} model..."
        self.provider = provider
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        model_choice = self.values[0]
        setting_key = "nvidia_model" if self.provider == "nvidia" else "gemini_model"
        _set_guild_setting(interaction.guild_id, setting_key, model_choice)
        
        embed = discord.Embed(
            title="⚙️ Model Updated",
            description=f"Success! The active **{self.provider.upper()}** model has been set to:\n`{model_choice}`",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class AiModelSelectView(discord.ui.View):
    def __init__(self, provider: str, current_model: str, models_list: list[str]):
        super().__init__(timeout=60)
        self.add_item(AiModelSelect(provider, current_model, models_list))


# Model Metadata for /tokens command
MODEL_METADATA = {
    # Gemini Models
    "gemini-2.5-flash": {
        "provider": "Google Gemini",
        "context": "1,000,000 tokens",
        "input_price": "$0.075 / 1M tokens",
        "output_price": "$0.300 / 1M tokens",
        "description": "High-speed, lightweight model optimized for multimodal tasks and efficiency."
    },
    "gemini-2.5-pro": {
        "provider": "Google Gemini",
        "context": "2,000,000 tokens",
        "input_price": "$1.250 / 1M tokens",
        "output_price": "$5.000 / 1M tokens",
        "description": "Highly advanced reasoning model for complex tasks and coding."
    },
    "gemini-2.0-flash": {
        "provider": "Google Gemini",
        "context": "1,000,000 tokens",
        "input_price": "$0.075 / 1M tokens",
        "output_price": "$0.300 / 1M tokens",
        "description": "Next-gen flash model with improved speed and lower latency."
    },
    "gemini-2.0-pro-exp-02-05": {
        "provider": "Google Gemini",
        "context": "2,000,000 tokens",
        "input_price": "Free / Experimental",
        "output_price": "Free / Experimental",
        "description": "Experimental pro model with advanced coding and math logic."
    },
    # NVIDIA NIM / Popular models
    "meta/llama-3.3-70b-instruct": {
        "provider": "NVIDIA NIM",
        "context": "128,000 tokens",
        "input_price": "$0.700 / 1M tokens",
        "output_price": "$0.700 / 1M tokens",
        "description": "Highly capable instruction-following open weight model from Meta."
    },
    "google/gemma-4-31b-it": {
        "provider": "NVIDIA NIM",
        "context": "8,000 tokens",
        "input_price": "$0.150 / 1M tokens",
        "output_price": "$0.150 / 1M tokens",
        "description": "Next-gen Gemma model optimized for efficient text instruction."
    },
    "nvidia/gemma-4-31b-it-nvfp4": {
        "provider": "NVIDIA NIM",
        "context": "8,000 tokens",
        "input_price": "$0.150 / 1M tokens",
        "output_price": "$0.150 / 1M tokens",
        "description": "FP4 optimized Gemma model for lightning-fast inference."
    },
    "moonshotai/kimi-k2.6": {
        "provider": "NVIDIA NIM",
        "context": "128,000 tokens",
        "input_price": "$1.000 / 1M tokens",
        "output_price": "$1.000 / 1M tokens",
        "description": "Advanced Chinese-centric model from Moonshot AI."
    },
    "z-ai/glm-5.1": {
        "provider": "NVIDIA NIM",
        "context": "64,000 tokens",
        "input_price": "$0.100 / 1M tokens",
        "output_price": "$0.100 / 1M tokens",
        "description": "Highly efficient bilingual model from Zhipu AI."
    },
    "nvidia/glm-5.1-nvfp4": {
        "provider": "NVIDIA NIM",
        "context": "64,000 tokens",
        "input_price": "$0.100 / 1M tokens",
        "output_price": "$0.100 / 1M tokens",
        "description": "FP4 precision GLM model for low latency applications."
    },
    "deepseek-ai/deepseek-r1": {
        "provider": "NVIDIA NIM",
        "context": "64,000 tokens",
        "input_price": "$2.190 / 1M tokens",
        "output_price": "$2.190 / 1M tokens",
        "description": "State-of-the-art reasoning model with reinforcement learning."
    },
    "microsoft/phi-4": {
        "provider": "NVIDIA NIM",
        "context": "16,000 tokens",
        "input_price": "$0.100 / 1M tokens",
        "output_price": "$0.100 / 1M tokens",
        "description": "Highly capable small language model from Microsoft."
    }
}


class AiModelInfoSelect(discord.ui.Select):
    def __init__(self, current_model: str):
        options = []
        for m, data in MODEL_METADATA.items():
            is_active = (m == current_model)
            label = f"{m}"
            if len(label) > 100:
                label = label[:97] + "..."
            options.append(discord.SelectOption(
                label=label,
                value=m,
                description=f"{data['provider']} | Context: {data['context']}",
                default=is_active
            ))
        super().__init__(placeholder="Select a model to view details...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_model = self.values[0]
        meta = MODEL_METADATA.get(selected_model)
        if not meta:
            await interaction.response.send_message("❌ Model details not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🖥️ AI Model Details: {selected_model}",
            description=meta["description"],
            color=discord.Color.blurple()
        )
        embed.add_field(name="Provider", value=meta["provider"], inline=True)
        embed.add_field(name="Context Window", value=meta["context"], inline=True)
        embed.add_field(name="Input Token Price", value=meta["input_price"], inline=True)
        embed.add_field(name="Output Token Price", value=meta["output_price"], inline=True)

        # Show guild usage stats
        usage_data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE) as f:
                    data = json.load(f)
                    usage_data = data.get(str(interaction.guild_id), {}).get("ai_usage_stats", {})
            except Exception:
                pass
        
        in_t = usage_data.get("input_tokens", 0)
        out_t = usage_data.get("output_tokens", 0)
        reqs = usage_data.get("total_requests", 0)
        
        embed.add_field(
            name="📊 Server Usage (This Server)",
            value=(
                f"📥 **Input Tokens:** {in_t:,}\n"
                f"📤 **Output Tokens:** {out_t:,}\n"
                f"🔄 **Total API Requests:** {reqs:,}"
            ),
            inline=False
        )
        embed.set_footer(text="Compare other models by choosing from the dropdown below.")
        await interaction.response.edit_message(embed=embed, view=self.view)


class AiModelInfoView(discord.ui.View):
    def __init__(self, current_model: str):
        super().__init__(timeout=120)
        self.add_item(AiModelInfoSelect(current_model))


def _build_tokens_embed(guild_id: Optional[int], current_model: str) -> discord.Embed:
    meta = MODEL_METADATA.get(current_model, {
        "provider": "Unknown",
        "context": "Unknown",
        "input_price": "Unknown",
        "output_price": "Unknown",
        "description": "Custom or untracked model selected by administrator."
    })
    
    embed = discord.Embed(
        title=f"🖥️ AI Model Details: {current_model}",
        description=meta["description"],
        color=discord.Color.blurple()
    )
    embed.add_field(name="Provider", value=meta["provider"], inline=True)
    embed.add_field(name="Context Window", value=meta["context"], inline=True)
    embed.add_field(name="Input Token Price", value=meta["input_price"], inline=True)
    embed.add_field(name="Output Token Price", value=meta["output_price"], inline=True)

    # Show guild usage stats
    usage_data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
                usage_data = data.get(str(guild_id), {}).get("ai_usage_stats", {})
        except Exception:
            pass
    
    in_t = usage_data.get("input_tokens", 0)
    out_t = usage_data.get("output_tokens", 0)
    reqs = usage_data.get("total_requests", 0)
    
    embed.add_field(
        name="📊 Server Usage (This Server)",
        value=(
            f"📥 **Input Tokens:** {in_t:,}\n"
            f"📤 **Output Tokens:** {out_t:,}\n"
            f"🔄 **Total API Requests:** {reqs:,}"
        ),
        inline=False
    )
    embed.set_footer(text="Compare other models by choosing from the dropdown below.")
    return embed


class AutoMod(commands.Cog):
    """On-demand AI assistant using Google Gemini 2.5 Flash."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="automod")
    @commands.has_permissions(administrator=True)
    async def automod_status(self, ctx):
        today = datetime.date.today().isoformat()
        used = _daily_count["count"] if _daily_count["date"] == today else 0
        log_ch_id = guild_config.get(ctx.guild.id, {}).get("log_channel")
        log_ch = f"<#{log_ch_id}>" if log_ch_id else "Not set"
        embed = discord.Embed(title="🛡️ Levi AI — Status", color=discord.Color.dark_blue())
        embed.add_field(name="Mode", value="🎯 On-demand only (@mention / slash commands)", inline=False)
        
        nv_key = _get_nvidia_key()
        default_provider = "nvidia" if nv_key else "gemini"
        provider = _get_guild_setting(ctx.guild.id, "ai_provider", default_provider)
        
        if provider == "nvidia":
            active_model = f"NVIDIA NIM (`{_get_guild_setting(ctx.guild.id, 'nvidia_model', _get_nvidia_model())}`)"
            fallback_info = f"Yes (Gemini - `{_get_guild_setting(ctx.guild.id, 'gemini_model', _get_gemini_model())}`)" if nv_key else "None"
        else:
            gemini_model = _get_guild_setting(ctx.guild.id, "gemini_model", _get_gemini_model())
            active_model = f"Gemini (`{gemini_model}`)"
            fallback_info = "None (Explicitly using Gemini)"
            
        ai_mode = _get_guild_setting(ctx.guild.id, "ai_mode", "captain")
        embed.add_field(name="Model", value=active_model, inline=True)
        embed.add_field(name="Fallback Active", value=fallback_info, inline=True)
        embed.add_field(name="AI Mode", value=f"`{ai_mode.upper()}`", inline=True)
        embed.add_field(name="Log Channel", value=log_ch, inline=True)
        embed.add_field(name="📊 Gemini API Calls Today", value=f"{used} / {RPD_LIMIT}", inline=True)
        embed.add_field(
            name="💡 Usage Examples",
            value=(
                "`@ODM Striker announce maintenance at 9PM in #announcements`\n"
                "`@ODM Striker warn @user for spamming`\n"
                "`/announce` — Slash command with channel picker\n"
                "`/warn` `/mute` — Moderation actions"
            ),
            inline=False
        )
        embed.set_footer(text="Free tier: 15 RPM • 500 RPD")
        await ctx.send(embed=embed)

    @commands.command(name="setlogchannel", aliases=["setlog"])
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        ch = channel or ctx.channel
        guild_config.setdefault(ctx.guild.id, {"log_channel": None})["log_channel"] = ch.id
        await ctx.send(f"📋 Mod logs will be sent to {ch.mention}. *Levi approves.*")

    # ── @mention handler ──────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if self.bot.user not in message.mentions:
            return

        clean = (
            message.content
            .replace(f"<@{self.bot.user.id}>", "")
            .replace(f"<@!{self.bot.user.id}>", "")
            .strip()
        )

        if not clean:
            embed = discord.Embed(
                title="⚔️ Levi Ackerman — AI Assistant",
                description=(
                    "*Tch. You called?*\n\n"
                    "**Examples:**\n"
                    "• `@ODM Striker announce maintenance tonight at 9 PM in #announcements`\n"
                    "• `@ODM Striker warn @user for spamming`\n"
                    "• `@ODM Striker mute @user 10 minutes`\n"
                    "• Use `/announce` for the slash command version"
                ),
                color=discord.Color.dark_red()
            )
            nv_key = _get_nvidia_key()
            default_provider = "nvidia" if nv_key else "gemini"
            provider = _get_guild_setting(message.guild.id, "ai_provider", default_provider)
            active_model = _get_guild_setting(message.guild.id, "nvidia_model", _get_nvidia_model()) if provider == "nvidia" else _get_guild_setting(message.guild.id, "gemini_model", _get_gemini_model())
            embed.set_footer(text=f"Model: {active_model}")
            await message.reply(embed=embed, mention_author=False)
            return

        # ── Detect if this is an announcement request BEFORE calling AI ─────
        is_announce = _is_announcement_request(clean)
        target_ch = _extract_channel(message, clean) if is_announce else None

        async with message.channel.typing():
            roles = ', '.join(r.name for r in message.author.roles[1:]) or 'none'
            # Tell Gemini explicitly if it's an announcement
            if is_announce:
                prompt = (
                    f"Server: {message.guild.name}\n"
                    f"User: {message.author.display_name} (roles: {roles})\n"
                    f"Task: Write a detailed announcement for — {clean}\n"
                    f"Write ONLY the announcement body text (no JSON, no explanation)."
                )
            else:
                prompt = (
                    f"Server: {message.guild.name}\n"
                    f"Channel: #{message.channel.name}\n"
                    f"User: {message.author.display_name} (roles: {roles})\n"
                    f"Request: {clean}"
                )
            response, model_used = await call_gemini(prompt, guild_id=message.guild.id)

        # ── Handle announcement: post to detected channel or current channel ──
        if is_announce:
            post_ch = target_ch or message.channel
            # Check permissions
            perms = post_ch.permissions_for(message.guild.me)
            if not perms.send_messages:
                await message.reply(
                    f"❌ I don't have permission to send messages in {post_ch.mention}.",
                    mention_author=False
                )
                return
            # Check if requester has permission to ping @everyone
            can_ping = message.author.guild_permissions.mention_everyone
            await _send_announcement(message.guild, post_ch, response, message.author, ping_everyone=can_ping, model_used=model_used)
            # Confirm in the command channel if different
            if post_ch != message.channel:
                await message.reply(
                    f"✅ Announcement posted in {post_ch.mention}!",
                    mention_author=False
                )
            return

        # ── Check if response is a JSON action (mod action or play music) ───
        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                action = result.get("action", "").lower()
                
                if action == "play_music":
                    query = result.get("query", "")
                    reply_text = result.get("reply", "Tch. Fine, listen to this.")
                    if query:
                        ctx = await self.bot.get_context(message)
                        music_cog = self.bot.get_cog("Music")
                        if not music_cog:
                            await message.reply("❌ Music system is not loaded.", mention_author=False)
                            return
                        
                        # Check if author is in a VC
                        if not message.author.voice or not message.author.voice.channel:
                            await message.reply("❌ You need to be in a voice channel first, recruit.", mention_author=False)
                            return
                            
                        # Send Levi's reply first as a message reply
                        embed = discord.Embed(
                            title="🎵 AI Music Selection",
                            description=f"*{reply_text}*\n\n🔎 **Searching & playing:** `{query}`",
                            color=discord.Color.blurple()
                        )
                        embed.set_footer(text=f"Levi AI Mood Music Selection • Model: {model_used}")
                        await message.reply(embed=embed, mention_author=False)
                        
                        # Join and play!
                        try:
                            vc = await music_cog._join_channel(ctx)
                        except discord.errors.ClientException:
                            vc = message.guild.voice_client
                        if vc:
                            await music_cog._handle_play(message.guild, message.author, message.channel, query, vc)
                        return

                target_str = result.get("target", "")
                reason = result.get("reason", "No reason provided.")
                if action and action in ["warn", "mute", "kick", "ban"] and message.author.guild_permissions.manage_messages:
                    await self._execute_mod_action(message, action, target_str, reason)
                    return
        except (json.JSONDecodeError, ValueError):
            pass

        # ── General AI response ────────────────────────────────────────────
        await message.reply(f"{response}\n\n*(Model: {model_used})*", mention_author=False)

    # ── /announce slash command ──────────────────────────────────────────────
    @app_commands.command(name="announce", description="Draft and post an announcement with @everyone 📣")
    @app_commands.describe(
        topic="What to announce e.g. 'server maintenance tonight at 9 PM IST'",
        channel="Channel to post in (default: current channel)",
        ping_everyone="Ping @everyone? (default: yes)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def announce(self, interaction: discord.Interaction, topic: str,
                       channel: discord.TextChannel = None, ping_everyone: bool = True):
        await interaction.response.defer(thinking=True, ephemeral=True)
        target_ch = channel or interaction.channel

        perms = target_ch.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            await interaction.followup.send(f"❌ I don't have permission to post in {target_ch.mention}.", ephemeral=True)
            return

        prompt = (
            f"Write a detailed, well-formatted Discord announcement for: {topic}\n"
            f"Server: {interaction.guild.name}\n"
            f"Make it at least 5-8 lines. Use emojis. Include a title line starting with 📣, details, and a closing line.\n"
            f"Write ONLY the announcement text, no JSON, no extra explanation."
        )
        draft, model_used = await call_gemini(prompt, guild_id=interaction.guild_id)

        can_ping = ping_everyone and interaction.user.guild_permissions.mention_everyone
        await _send_announcement(interaction.guild, target_ch, draft, interaction.user, ping_everyone=can_ping, model_used=model_used)
        await interaction.followup.send(
            f"✅ Announcement posted in {target_ch.mention}{'with @everyone!' if can_ping else '.'}",
            ephemeral=True
        )

    # ── /mood-music slash command ────────────────────────────────────────────
    @app_commands.command(name="mood-music", description="Explain your mood or what you want to hear, and Levi AI will find and play music 🎵")
    @app_commands.describe(mood="Describe how you feel or what you are doing (e.g. 'feeling hyped for training', 'chill studying')")
    async def mood_music_slash(self, interaction: discord.Interaction, mood: str):
        await interaction.response.defer()
        
        # Check if user is in VC
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ You need to be in a voice channel first, recruit.", ephemeral=True)
            return

        music_cog = self.bot.get_cog("Music")
        if not music_cog:
            await interaction.followup.send("❌ Music system is not loaded.", ephemeral=True)
            return

        # Prepare prompt for LLM
        prompt = (
            f"User is feeling/requesting: {mood}\n"
            f"Identify a song, playlist, or music style to match this mood. "
            f"Respond ONLY in JSON format: "
            f'{{"action": "play_music", "query": "<song/playlist name>", "reply": "<Levi\'s comment>"}}'
        )
        
        response, model_used = await call_gemini(prompt, guild_id=interaction.guild_id)
        
        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                query = result.get("query", "")
                reply_text = result.get("reply", "Tch. Listen to this.")
                
                if query:
                    # Send response embed
                    embed = discord.Embed(
                        title="🎵 AI Music Selection",
                        description=f"*{reply_text}*\n\n🔎 **Searching & playing:** `{query}`",
                        color=discord.Color.blurple()
                    )
                    embed.set_footer(text=f"Levi AI Mood Music Selection • Model: {model_used}")
                    await interaction.followup.send(embed=embed)
                    
                    # Connect and play
                    try:
                        vc = await music_cog._join_channel(interaction)
                    except discord.errors.ClientException:
                        vc = interaction.guild.voice_client
                    if vc:
                        await music_cog._handle_play(interaction.guild, interaction.user, interaction.channel, query, vc)
                    return
        except Exception as e:
            print(f"[Mood Music Slash Error: {e}]")
            
        await interaction.followup.send(f"❌ Failed to find matching music for: `{mood}`. Levi is unimpressed.")

    # ── /ask slash command ───────────────────────────────────────────────────
    @app_commands.command(name="ask", description="Ask Levi AI to do any server task ⚔️")
    @app_commands.describe(task="What should Levi do?")
    async def ask_slash(self, interaction: discord.Interaction, task: str):
        await interaction.response.defer(thinking=True)
        roles = ', '.join(r.name for r in interaction.user.roles[1:]) or 'none'
        context = (
            f"Server: {interaction.guild.name}\n"
            f"Channel: #{interaction.channel.name}\n"
            f"User: {interaction.user.display_name} (roles: {roles})\n"
            f"Task: {task}"
        )
        response, model_used = await call_gemini(context, guild_id=interaction.guild_id)
        await interaction.followup.send(f"{response}\n\n*(Model: {model_used})*")

    # ── /warn slash command ───────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member 🗡️")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @app_commands.default_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Violating server rules"):
        import random
        warning_counts.setdefault(interaction.guild.id, {}).setdefault(member.id, 0)
        warning_counts[interaction.guild.id][member.id] += 1
        count = warning_counts[interaction.guild.id][member.id]
        aot_warns = [
            f"⚔️ {member.mention} — **Levi's watching you.** Warning: *{reason}*",
            f"🗡️ {member.mention} — *Tch.* Clean it up. Reason: *{reason}*",
            f"🏰 {member.mention} — The walls have rules. *{reason}*",
        ]
        await interaction.response.send_message(f"{random.choice(aot_warns)} *(Warning #{count})*")
        if count >= 3:
            await interaction.channel.send(f"🚨 {member.mention} has reached **3 warnings**. *Levi recommends escalation.*", delete_after=10)
        await self._log_action(interaction.guild, "WARN", member, interaction.user, reason)

    # ── /mute slash command ───────────────────────────────────────────────────
    @app_commands.command(name="mute", description="Timeout a member 🔇")
    @app_commands.describe(member="Member to mute", minutes="Duration in minutes", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "Violating server rules"):
        try:
            until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
            await member.timeout(until, reason=reason)
            await interaction.response.send_message(f"🔇 {member.mention} timed out **{minutes} min**. Reason: *{reason}*")
            await self._log_action(interaction.guild, f"MUTE ({minutes}m)", member, interaction.user, reason)
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

    # ── /warnings & /clearwarnings ──────────────────────────────────────────────
    @app_commands.command(name="warnings", description="Check warnings for a member")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        count = warning_counts.get(interaction.guild.id, {}).get(target.id, 0)
        embed = discord.Embed(
            title=f"📋 Warnings — {target.display_name}",
            description=f"**{count}** warning(s) on record.",
            color=discord.Color.orange() if count > 0 else discord.Color.green()
        )
        embed.set_footer(text="⚔️ Stay in line, soldier.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        warning_counts.setdefault(interaction.guild.id, {})[member.id] = 0
        await interaction.response.send_message(f"✅ Warnings cleared for {member.mention}.", ephemeral=True)

    # ── Internal helpers ─────────────────────────────────────────────────────────
    async def _execute_mod_action(self, message, action, target_str, reason):
        member = None
        id_match = re.search(r"\d{17,19}", target_str)
        if id_match:
            member = message.guild.get_member(int(id_match.group()))
        if not member:
            member = next((m for m in message.mentions if m != self.bot.user), None)
        if not member:
            await message.reply(f"⚔️ Action: **{action}** — Reason: *{reason}* \n*(Couldn't find the target member.)*", mention_author=False)
            return
        import random
        if action == "warn":
            warning_counts.setdefault(message.guild.id, {}).setdefault(member.id, 0)
            warning_counts[message.guild.id][member.id] += 1
            count = warning_counts[message.guild.id][member.id]
            await message.channel.send(f"⚔️ {member.mention} — Warning by Levi: *{reason}* *(#{count})*")
        elif action == "mute" and message.guild.me.guild_permissions.moderate_members:
            try:
                await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=10), reason=reason)
                await message.channel.send(f"🔇 {member.mention} timed out 10 min. Reason: *{reason}*")
            except (discord.Forbidden, discord.HTTPException):
                await message.channel.send("❌ No permission to timeout that member.")
        elif action == "kick" and message.guild.me.guild_permissions.kick_members:
            try:
                await member.kick(reason=reason)
                await message.channel.send(f"👢 {member.mention} kicked. Reason: *{reason}*")
            except (discord.Forbidden, discord.HTTPException):
                await message.channel.send("❌ No permission to kick that member.")
        elif action == "ban" and message.guild.me.guild_permissions.ban_members:
            try:
                await member.ban(reason=reason, delete_message_days=1)
                await message.channel.send(f"🔨 {member.mention} banned. Reason: *{reason}*")
            except (discord.Forbidden, discord.HTTPException):
                await message.channel.send("❌ No permission to ban that member.")
        await self._log_action(message.guild, action.upper(), member, message.author, reason)

    # ── AI Config Commands ───────────────────────────────────────────────────
    @app_commands.command(name="provider", description="Switch the active AI provider between Gemini and NVIDIA NIM (Admin only)")
    @app_commands.describe(choice="The provider to use")
    @app_commands.choices(choice=[
        app_commands.Choice(name="NVIDIA NIM 🟢", value="nvidia"),
        app_commands.Choice(name="Google Gemini 🔵", value="gemini")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def provider_slash(self, interaction: discord.Interaction, choice: str):
        _set_guild_setting(interaction.guild_id, "ai_provider", choice)
        provider_name = "NVIDIA NIM" if choice == "nvidia" else "Google Gemini"
        embed = discord.Embed(
            title="⚙️ AI Provider Updated",
            description=f"Success! The AI provider for this server has been set to **{provider_name}**.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @commands.command(name="provider", help="Switch the active AI provider. Usage: >provider <nvidia|gemini>")
    @commands.has_permissions(manage_guild=True)
    async def provider_prefix(self, ctx: commands.Context, choice: str):
        val = choice.strip().lower()
        if val not in ["nvidia", "gemini"]:
            await ctx.send("❌ Invalid provider choice. Please select `nvidia` or `gemini`.")
            return
        _set_guild_setting(ctx.guild.id, "ai_provider", val)
        provider_name = "NVIDIA NIM" if val == "nvidia" else "Google Gemini"
        await ctx.send(f"✅ AI provider updated to **{provider_name}** for this server.")

    @app_commands.command(name="models", description="Choose the active AI model for this server (Admin only)")
    @app_commands.describe(
        model_name="Select a model name or type a custom one. Leave empty to list and pick interactively."
    )
    @app_commands.default_permissions(manage_guild=True)
    async def models_slash(self, interaction: discord.Interaction, model_name: Optional[str] = None):
        nv_key = _get_nvidia_key()
        default_provider = "nvidia" if nv_key else "gemini"
        provider = _get_guild_setting(interaction.guild_id, "ai_provider", default_provider)

        if provider == "nvidia":
            current = _get_guild_setting(interaction.guild_id, "nvidia_model", _get_nvidia_model())
            models_list = POPULAR_MODELS
        else:
            current = _get_guild_setting(interaction.guild_id, "gemini_model", _get_gemini_model())
            models_list = POPULAR_GEMINI_MODELS

        if not model_name:
            embed = discord.Embed(
                title=f"🖥️ {provider.upper()} AI Models",
                description=(
                    f"Choose the active model for Levi AI (Active Provider: **{provider.upper()}**).\n\n"
                    f"**Current model:** `{current}`\n\n"
                    f"Use the dropdown below to select a popular model, or specify a custom name in the command."
                ),
                color=discord.Color.blurple()
            )
            view = AiModelSelectView(provider, current, models_list)
            await interaction.response.send_message(embed=embed, view=view)
            return

        choice = model_name.strip()
        setting_key = "nvidia_model" if provider == "nvidia" else "gemini_model"
        _set_guild_setting(interaction.guild_id, setting_key, choice)
        embed = discord.Embed(
            title="⚙️ Model Updated",
            description=f"Success! {provider.upper()} model set to:\n`{choice}`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @commands.command(name="models", help="List and select AI models. Usage: >models [number or model_name]")
    @commands.has_permissions(manage_guild=True)
    async def models_prefix(self, ctx: commands.Context, *, choice: Optional[str] = None):
        nv_key = _get_nvidia_key()
        default_provider = "nvidia" if nv_key else "gemini"
        provider = _get_guild_setting(ctx.guild.id, "ai_provider", default_provider)

        if provider == "nvidia":
            current = _get_guild_setting(ctx.guild.id, "nvidia_model", _get_nvidia_model())
            models_list = POPULAR_MODELS
        else:
            current = _get_guild_setting(ctx.guild.id, "gemini_model", _get_gemini_model())
            models_list = POPULAR_GEMINI_MODELS

        if not choice:
            embed = discord.Embed(
                title=f"🖥️ {provider.upper()} AI Models",
                description=f"Use `>models <number>` or select from the list below (Active Provider: **{provider.upper()}**):\n\n",
                color=discord.Color.blurple()
            )
            for i, m in enumerate(models_list):
                active_str = "👈 **(Active)**" if m == current else ""
                embed.description += f"**{i+1}.** `{m}` {active_str}\n"
            embed.set_footer(text=f"To set a custom model, use: >models <model_name>")
            view = AiModelSelectView(provider, current, models_list)
            await ctx.send(embed=embed, view=view)
            return

        choice_str = choice.strip()
        setting_key = "nvidia_model" if provider == "nvidia" else "gemini_model"
        if choice_str.isdigit():
            idx = int(choice_str) - 1
            if 0 <= idx < len(models_list):
                selected = models_list[idx]
                _set_guild_setting(ctx.guild.id, setting_key, selected)
                await ctx.send(f"✅ Success! {provider.upper()} model updated to:\n`{selected}`")
                return
            else:
                await ctx.send(f"❌ Invalid index. Please choose a number between 1 and {len(models_list)}.")
                return
        _set_guild_setting(ctx.guild.id, setting_key, choice_str)
        await ctx.send(f"✅ Success! {provider.upper()} model updated to custom model:\n`{choice_str}`")

    @app_commands.command(name="purge", description="Purge messages from this channel 🧹")
    @app_commands.describe(amount="Number of messages to delete (1-1000)", reason="Reason for purging")
    @app_commands.default_permissions(manage_messages=True)
    async def purge_slash(self, interaction: discord.Interaction, amount: int = 100, reason: str = "No reason provided"):
        if amount < 1 or amount > 1000:
            await interaction.response.send_message("❌ Amount must be between 1 and 1000.", ephemeral=True)
            return

        # Defer so we have time to delete and log
        await interaction.response.defer(ephemeral=True)
        
        try:
            deleted = await interaction.channel.purge(limit=amount)
            count = len(deleted)
            await interaction.followup.send(f"🧹 Purged **{count}** messages successfully.", ephemeral=True)
            
            # Log the action
            await self._log_action(
                guild=interaction.guild,
                action=f"PURGE ({count} msgs)",
                target=interaction.channel,
                moderator=interaction.user,
                reason=reason
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.followup.send(f"❌ Failed to purge messages: {e}", ephemeral=True)

    @commands.command(name="purge", help="Purge messages from this channel. Usage: >purge [amount] [reason]")
    @commands.has_permissions(manage_messages=True)
    async def purge_prefix(self, ctx: commands.Context, amount: Optional[int] = 100, *, reason: Optional[str] = "No reason provided"):
        if amount < 1 or amount > 1000:
            await ctx.send("❌ Amount must be between 1 and 1000.")
            return

        # First, delete the command message itself
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        try:
            deleted = await ctx.channel.purge(limit=amount)
            count = len(deleted)
            # Send confirmation and self-delete after 5 seconds
            confirm = await ctx.send(f"🧹 Purged **{count}** messages successfully.")
            await confirm.delete(delay=5)
            
            # Log the action
            await self._log_action(
                guild=ctx.guild,
                action=f"PURGE ({count} msgs)",
                target=ctx.channel,
                moderator=ctx.author,
                reason=reason
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            await ctx.send(f"❌ Failed to purge messages: {e}", delete_after=5)

    @app_commands.command(name="aimode", description="Change the AI assistant personality mode (Admin only)")
    @app_commands.describe(choice="The personality style to use")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Captain (Levi Ackerman) ⚔️", value="captain"),
        app_commands.Choice(name="Friendly 😊", value="friendly"),
        app_commands.Choice(name="Funny 🎭", value="funny"),
        app_commands.Choice(name="Anime Protagonist 🔥", value="anime")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def aimode_slash(self, interaction: discord.Interaction, choice: str):
        _set_guild_setting(interaction.guild_id, "ai_mode", choice)
        mode_names = {
            "captain": "Captain (Levi Ackerman) ⚔️",
            "friendly": "Friendly 😊",
            "funny": "Funny 🎭",
            "anime": "Anime Protagonist 🔥"
        }
        name = mode_names.get(choice, choice)
        embed = discord.Embed(
            title="⚙️ AI Personality Updated",
            description=f"Success! The AI assistant mode for this server has been set to **{name}**.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @commands.command(name="aimode", help="Switch the AI assistant personality mode. Usage: >aimode <captain|friendly|funny|anime>")
    @commands.has_permissions(manage_guild=True)
    async def aimode_prefix(self, ctx: commands.Context, choice: str):
        val = choice.strip().lower()
        if val not in ["captain", "friendly", "funny", "anime"]:
            await ctx.send("❌ Invalid mode choice. Please select `captain`, `friendly`, `funny`, or `anime`.")
            return
        _set_guild_setting(ctx.guild.id, "ai_mode", val)
        mode_names = {
            "captain": "Captain (Levi Ackerman) ⚔️",
            "friendly": "Friendly 😊",
            "funny": "Funny 🎭",
            "anime": "Anime Protagonist 🔥"
        }
        await ctx.send(f"✅ AI assistant personality mode updated to **{mode_names[val]}** for this server.")

    @app_commands.command(name="tokens", description="View AI model details (context size, pricing) and server token usage stats 📊")
    async def tokens_slash(self, interaction: discord.Interaction):
        nv_key = _get_nvidia_key()
        default_provider = "nvidia" if nv_key else "gemini"
        provider = _get_guild_setting(interaction.guild_id, "ai_provider", default_provider)
        if provider == "nvidia":
            current_model = _get_guild_setting(interaction.guild_id, "nvidia_model", _get_nvidia_model())
        else:
            current_model = _get_guild_setting(interaction.guild_id, "gemini_model", _get_gemini_model())

        embed = _build_tokens_embed(interaction.guild_id, current_model)
        view = AiModelInfoView(current_model)
        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name="tokens", help="View AI model details, pricing, and token usage. Usage: >tokens")
    async def tokens_prefix(self, ctx: commands.Context):
        nv_key = _get_nvidia_key()
        default_provider = "nvidia" if nv_key else "gemini"
        provider = _get_guild_setting(ctx.guild.id, "ai_provider", default_provider)
        if provider == "nvidia":
            current_model = _get_guild_setting(ctx.guild.id, "nvidia_model", _get_nvidia_model())
        else:
            current_model = _get_guild_setting(ctx.guild.id, "gemini_model", _get_gemini_model())

        embed = _build_tokens_embed(ctx.guild.id, current_model)
        view = AiModelInfoView(current_model)
        await ctx.send(embed=embed, view=view)

    async def _log_action(self, guild, action, target, moderator, reason):
        log_ch_id = guild_config.get(guild.id, {}).get("log_channel")
        if not log_ch_id:
            return
        log_ch = guild.get_channel(log_ch_id)
        if not log_ch:
            return
        embed = discord.Embed(
            title=f"📋 Mod Action — {action}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Target", value=f"{target.mention} (`{target.id}`)", inline=True)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        nv_key = _get_nvidia_key()
        default_provider = "nvidia" if nv_key else "gemini"
        provider = _get_guild_setting(guild.id, "ai_provider", default_provider)
        active_model = _get_guild_setting(guild.id, "nvidia_model", _get_nvidia_model()) if provider == "nvidia" else _get_guild_setting(guild.id, "gemini_model", _get_gemini_model())
        embed.set_footer(text=f"Levi AI • {active_model}")
        await log_ch.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
