"""Dynamic battle image generator using Pillow."""
from __future__ import annotations
import io
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Colour palette ───────────────────────────────────────────────────────────
COLORS = {
    "bg_dark":     (15, 15, 25),
    "bg_mid":      (25, 25, 40),
    "accent_red":  (180, 30,  30),
    "accent_gold": (220, 170,  30),
    "accent_teal": (30,  180, 160),
    "hp_green":    (50,  200,  80),
    "hp_yellow":   (220, 180,  30),
    "hp_red":      (220,  50,  50),
    "hp_bg":       (60,   20,  20),
    "white":       (240, 240, 240),
    "grey":        (140, 140, 160),
    "titan_purple":(120,  40, 180),
}

IMG_W, IMG_H = 900, 420


def _try_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a nice font, fallback to default."""
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _hp_color(pct: float) -> tuple:
    if pct > 0.55:
        return COLORS["hp_green"]
    if pct > 0.28:
        return COLORS["hp_yellow"]
    return COLORS["hp_red"]


def _draw_hp_bar(draw: ImageDraw.ImageDraw, x: int, y: int,
                 width: int, height: int, hp: int, max_hp: int,
                 label: str, font_sm, reverse: bool = False) -> None:
    pct = max(0.0, hp / max_hp)
    # Background track
    draw.rounded_rectangle([x, y, x + width, y + height],
                            radius=height // 2, fill=COLORS["hp_bg"])
    # Fill
    fill_w = int(width * pct)
    bar_x = x + width - fill_w if reverse else x
    if fill_w > 4:
        draw.rounded_rectangle([bar_x, y, bar_x + fill_w, y + height],
                                radius=height // 2, fill=_hp_color(pct))
    # Label
    txt = f"{label}  {hp}/{max_hp}"
    draw.text((x, y - 22), txt, font=font_sm, fill=COLORS["white"])


def _draw_aura(draw: ImageDraw.ImageDraw, cx: int, cy: int,
               r: int, color: tuple, steps: int = 6) -> None:
    """Draw a layered glow circle."""
    for i in range(steps, 0, -1):
        alpha = int(40 * i / steps)
        rc = r + (steps - i) * 8
        draw.ellipse([cx - rc, cy - rc, cx + rc, cy + rc],
                     fill=(*color[:3], alpha))


def _draw_silhouette_scout(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                            color: tuple, size: int = 1) -> None:
    """Draw a simplified scout stick figure."""
    sc = size
    # Body
    draw.ellipse([cx-14*sc, cy-60*sc, cx+14*sc, cy-32*sc], fill=color)  # head
    draw.line([(cx, cy-32*sc), (cx, cy+20*sc)], fill=color, width=5*sc)  # torso
    # Arms angled like ODM
    draw.line([(cx, cy-20*sc), (cx-30*sc, cy-5*sc)], fill=color, width=4*sc)
    draw.line([(cx, cy-20*sc), (cx+30*sc, cy-5*sc)], fill=color, width=4*sc)
    # Legs
    draw.line([(cx, cy+20*sc), (cx-18*sc, cy+55*sc)], fill=color, width=4*sc)
    draw.line([(cx, cy+20*sc), (cx+18*sc, cy+55*sc)], fill=color, width=4*sc)
    # ODM cable lines
    draw.line([(cx-30*sc, cy-5*sc), (cx-60*sc, cy+10*sc)],
               fill=COLORS["accent_gold"], width=2)
    draw.line([(cx+30*sc, cy-5*sc), (cx+60*sc, cy+10*sc)],
               fill=COLORS["accent_gold"], width=2)


def _draw_silhouette_titan(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                            color: tuple, size: int = 1) -> None:
    """Draw a huge simplified titan silhouette."""
    sc = size
    # Head
    draw.ellipse([cx-30*sc, cy-100*sc, cx+30*sc, cy-45*sc], fill=color)
    # Eyes
    draw.ellipse([cx-18*sc, cy-85*sc, cx-6*sc, cy-70*sc],
                  fill=(255, 80, 80))
    draw.ellipse([cx+6*sc, cy-85*sc, cx+18*sc, cy-70*sc],
                  fill=(255, 80, 80))
    # Body
    draw.rectangle([cx-38*sc, cy-45*sc, cx+38*sc, cy+60*sc], fill=color)
    # Arms
    draw.line([(cx-38*sc, cy-30*sc), (cx-75*sc, cy+20*sc)],
               fill=color, width=16*sc)
    draw.line([(cx+38*sc, cy-30*sc), (cx+75*sc, cy+20*sc)],
               fill=color, width=16*sc)
    # Legs
    draw.line([(cx-20*sc, cy+60*sc), (cx-25*sc, cy+120*sc)],
               fill=color, width=18*sc)
    draw.line([(cx+20*sc, cy+60*sc), (cx+25*sc, cy+120*sc)],
               fill=color, width=18*sc)


def _draw_background(img: Image.Image, phase: str) -> None:
    """Draw a cinematic gradient + building silhouettes background."""
    draw = ImageDraw.Draw(img)
    # Sky gradient
    sky_colors = {
        "start":   [(15,15,30),  (30,10,10)],
        "mid":     [(10,10,40),  (60,20,20)],
        "intense": [(5, 5, 20),  (100,10,10)],
        "victory": [(10,30,10),  (20,60,20)],
        "defeat":  [(30,10,10),  (80,10,10)],
    }.get(phase, [(15,15,30), (30,10,10)])
    top_c, bot_c = sky_colors
    for y in range(IMG_H):
        t = y / IMG_H
        r = int(top_c[0] + (bot_c[0] - top_c[0]) * t)
        g = int(top_c[1] + (bot_c[1] - top_c[1]) * t)
        b = int(top_c[2] + (bot_c[2] - top_c[2]) * t)
        draw.line([(0, y), (IMG_W, y)], fill=(r, g, b))
    # City silhouettes
    buildings = [(50,280,120,380), (130,260,200,380), (210,290,270,380),
                 (580,250,640,380), (650,270,710,380), (720,240,790,380),
                 (800,260,870,380)]
    for bx1,by1,bx2,by2 in buildings:
        draw.rectangle([bx1,by1,bx2,by2], fill=(20,20,35))
        # Windows
        for wx in range(bx1+5, bx2-5, 12):
            for wy in range(by1+8, by2-8, 16):
                if random.random() > 0.4:
                    draw.rectangle([wx,wy,wx+6,wy+8],
                                    fill=(200,180,80,100))
    # Ground
    draw.rectangle([0, 370, IMG_W, IMG_H], fill=(18,18,28))
    # Horizontal accent line
    draw.line([(0,370),(IMG_W,370)], fill=COLORS["accent_red"], width=2)


def generate_battle_image(
    scout_name: str,
    titan_name: str,
    scout_hp: int,
    scout_max_hp: int,
    titan_hp: int,
    titan_max_hp: int,
    phase: str = "mid",
    last_action: str = "",
    round_num: int = 1,
) -> io.BytesIO:
    """
    Generate a full battle scene image and return it as a BytesIO buffer.
    phase: 'start' | 'mid' | 'intense' | 'victory' | 'defeat'
    """
    img = Image.new("RGBA", (IMG_W, IMG_H), (0,0,0,255))
    _draw_background(img, phase)

    draw = ImageDraw.Draw(img, "RGBA")

    font_lg  = _try_font(28)
    font_md  = _try_font(20)
    font_sm  = _try_font(15)
    font_xs  = _try_font(12)

    # ── Scout (left side) ────────────────────────────────────────────────────
    scout_cx, scout_cy = 175, 200
    scout_color = COLORS["accent_teal"]
    _draw_aura(draw, scout_cx, scout_cy, 55, scout_color)
    _draw_silhouette_scout(draw, scout_cx, scout_cy, scout_color, size=1)

    # ── Titan (right side) ──────────────────────────────────────────────────
    titan_cx, titan_cy = 700, 190
    titan_color = COLORS["titan_purple"]
    _draw_aura(draw, titan_cx, titan_cy, 80, titan_color)
    _draw_silhouette_titan(draw, titan_cx, titan_cy, titan_color, size=1)

    # ── VS banner ────────────────────────────────────────────────────────────
    vs_x = IMG_W // 2
    draw.text((vs_x, 160), "VS", font=font_lg,
               fill=COLORS["accent_gold"], anchor="mm")
    # Crossed swords ✕
    draw.line([(vs_x-25,130),(vs_x+25,190)], fill=COLORS["accent_gold"], width=3)
    draw.line([(vs_x+25,130),(vs_x-25,190)], fill=COLORS["accent_gold"], width=3)

    # ── Name plates ─────────────────────────────────────────────────────────
    # Scout name plate
    draw.rounded_rectangle([10,10,340,50], radius=8, fill=(0,0,0,160))
    draw.text((20, 28), f"\U0001fa7a {scout_name}", font=font_md,
               fill=COLORS["accent_teal"], anchor="lm")

    # Titan name plate
    draw.rounded_rectangle([560,10,890,50], radius=8, fill=(0,0,0,160))
    draw.text((880, 28), f"{titan_name} \U0001f479", font=font_md,
               fill=(200,100,255), anchor="rm")

    # ── HP bars ─────────────────────────────────────────────────────────────
    _draw_hp_bar(draw, 10, 70, 320, 18,
                  scout_hp, scout_max_hp, "HP", font_sm, reverse=False)
    _draw_hp_bar(draw, 570, 70, 320, 18,
                  titan_hp, titan_max_hp, "HP", font_sm, reverse=True)

    # ── Round badge ─────────────────────────────────────────────────────────
    draw.rounded_rectangle([390,8,510,52], radius=10,
                            fill=COLORS["accent_red"])
    draw.text((450, 30), f"RND {round_num}", font=font_md,
               fill=COLORS["white"], anchor="mm")

    # ── Last action log ─────────────────────────────────────────────────────
    if last_action:
        draw.rounded_rectangle([10, 375, IMG_W-10, 410],
                                radius=6, fill=(0,0,0,180))
        # Truncate to fit
        action_txt = last_action[:95] + "..." if len(last_action) > 95 else last_action
        draw.text((IMG_W//2, 393), action_txt, font=font_xs,
                   fill=COLORS["accent_gold"], anchor="mm")

    # ── Phase overlay effects ────────────────────────────────────────────────
    if phase == "victory":
        draw.text((IMG_W//2, IMG_H//2), "\u2705 VICTORY", font=font_lg,
                   fill=(80,255,80), anchor="mm")
    elif phase == "defeat":
        draw.text((IMG_W//2, IMG_H//2), "\u2620\ufe0f FALLEN", font=font_lg,
                   fill=(255,60,60), anchor="mm")

    # Convert and return
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_profile_card(
    username: str,
    scout_name: str,
    level: int,
    xp: int,
    xp_needed: int,
    wins: int,
    losses: int,
    kills: int,
    rank: str,
) -> io.BytesIO:
    """Generate a profile card image."""
    W, H = 700, 300
    img = Image.new("RGBA", (W, H), (0,0,0,255))
    draw = ImageDraw.Draw(img, "RGBA")

    # Background gradient
    for y in range(H):
        t = y / H
        r = int(10 + 20*t)
        g = int(10 + 10*t)
        b = int(30 + 30*t)
        draw.line([(0,y),(W,y)], fill=(r,g,b))

    # Border
    draw.rounded_rectangle([2,2,W-2,H-2], radius=12,
                            outline=COLORS["accent_gold"], width=3)

    font_lg = _try_font(26)
    font_md = _try_font(18)
    font_sm = _try_font(14)

    # Title bar
    draw.rounded_rectangle([10,10,690,55], radius=8,
                            fill=(0,0,0,140))
    draw.text((350, 33), f"\U0001fa7a Scout Profile — {username}",
               font=font_md, fill=COLORS["accent_gold"], anchor="mm")

    # Scout name
    draw.text((30, 80), f"Character: {scout_name}",
               font=font_lg, fill=COLORS["accent_teal"])

    # Rank badge
    rank_colors = {
        "Cadet":   (100,100,100),
        "Scout":   (50,150,200),
        "Elite":   (200,150,50),
        "Captain": (200,80,80),
        "Legend":  (200,50,200),
    }
    rc = rank_colors.get(rank, (100,100,100))
    draw.rounded_rectangle([500,70,690,110], radius=8, fill=(*rc,200))
    draw.text((595, 90), rank, font=font_md,
               fill=COLORS["white"], anchor="mm")

    # Stats
    stats = [
        ("Level",   str(level),   30,  140),
        ("Wins",    str(wins),    30,  175),
        ("Losses",  str(losses),  30,  210),
        ("Titan Kills", str(kills), 30, 245),
    ]
    for label, value, sx, sy in stats:
        draw.text((sx, sy), f"{label}:", font=font_sm, fill=COLORS["grey"])
        draw.text((sx+150, sy), value, font=font_sm, fill=COLORS["white"])

    # XP bar
    xp_pct = min(1.0, xp / max(xp_needed, 1))
    bar_x, bar_y, bar_w, bar_h = 250, 140, 420, 16
    draw.rounded_rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h],
                            radius=8, fill=COLORS["hp_bg"])
    fill_w = int(bar_w * xp_pct)
    if fill_w > 4:
        draw.rounded_rectangle([bar_x, bar_y, bar_x+fill_w, bar_y+bar_h],
                                radius=8, fill=COLORS["accent_gold"])
    draw.text((bar_x, bar_y-18), f"XP  {xp}/{xp_needed}",
               font=font_sm, fill=COLORS["grey"])

    # Win rate
    total = wins + losses
    wr = (wins / total * 100) if total > 0 else 0
    draw.text((250, 175), f"Win Rate: {wr:.1f}%", font=font_sm,
               fill=COLORS["accent_gold"])
    draw.text((250, 210), f"Total Battles: {total}", font=font_sm,
               fill=COLORS["grey"])

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf
