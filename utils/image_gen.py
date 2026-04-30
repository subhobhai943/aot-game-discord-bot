"""Dynamic battle image generator using Pillow."""
from __future__ import annotations
import io
import random
from PIL import Image, ImageDraw, ImageFont

# ─── Colour palette ───────────────────────────────────────────────────────────
COLORS = {
    "bg_dark":      (15,  15,  25),
    "accent_red":   (180, 30,  30),
    "accent_gold":  (220, 170, 30),
    "accent_teal":  (30,  180, 160),
    "hp_green":     (50,  200, 80),
    "hp_yellow":    (220, 180, 30),
    "hp_red":       (220, 50,  50),
    "hp_bg":        (60,  20,  20),
    "white":        (240, 240, 240),
    "grey":         (140, 140, 160),
    "titan_purple": (120, 40,  180),
}

IMG_W, IMG_H = 900, 420


def _try_font(size: int) -> ImageFont.FreeTypeFont:
    """
    Try system fonts first. Fall back to Pillow 10+ load_default(size=).
    This guarantees anchor parameter support.
    """
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    # Pillow 10+ supports size= in load_default() which returns a FreeTypeFont
    # that supports anchor. Falls back to old bitmap if Pillow < 10.
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _txt(
    draw: ImageDraw.ImageDraw,
    xy: tuple,
    text: str,
    font,
    fill: tuple,
    anchor: str = None,
) -> None:
    """
    Safe text draw wrapper.
    Uses anchor if the font supports it (FreeTypeFont), else draws without it.
    """
    try:
        if anchor:
            draw.text(xy, text, font=font, fill=fill, anchor=anchor)
        else:
            draw.text(xy, text, font=font, fill=fill)
    except (TypeError, AttributeError):
        # Fallback for old bitmap fonts that don't support anchor
        draw.text(xy, text, font=font, fill=fill)


def _hp_color(pct: float) -> tuple:
    if pct > 0.55:
        return COLORS["hp_green"]
    if pct > 0.28:
        return COLORS["hp_yellow"]
    return COLORS["hp_red"]


def _draw_hp_bar(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    width: int, height: int,
    hp: int, max_hp: int,
    label: str, font_sm,
    reverse: bool = False,
) -> None:
    pct = max(0.0, hp / max(max_hp, 1))
    draw.rounded_rectangle([x, y, x + width, y + height],
                            radius=height // 2, fill=COLORS["hp_bg"])
    fill_w = int(width * pct)
    bar_x = x + width - fill_w if reverse else x
    if fill_w > 4:
        draw.rounded_rectangle([bar_x, y, bar_x + fill_w, y + height],
                                radius=height // 2, fill=_hp_color(pct))
    _txt(draw, (x, y - 22), f"{label}  {hp}/{max_hp}", font_sm, COLORS["white"])


def _draw_aura(
    draw: ImageDraw.ImageDraw,
    cx: int, cy: int,
    r: int, color: tuple,
    steps: int = 6,
) -> None:
    r3 = color[:3]
    for i in range(steps, 0, -1):
        alpha = int(50 * i / steps)
        rc = r + (steps - i) * 8
        draw.ellipse(
            [cx - rc, cy - rc, cx + rc, cy + rc],
            fill=(*r3, alpha),
        )


def _draw_silhouette_scout(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, color: tuple
) -> None:
    draw.ellipse([cx-14, cy-60, cx+14, cy-32], fill=color)       # head
    draw.line([(cx, cy-32), (cx, cy+20)], fill=color, width=5)   # torso
    draw.line([(cx, cy-20), (cx-30, cy-5)], fill=color, width=4) # left arm
    draw.line([(cx, cy-20), (cx+30, cy-5)], fill=color, width=4) # right arm
    draw.line([(cx, cy+20), (cx-18, cy+55)], fill=color, width=4)# left leg
    draw.line([(cx, cy+20), (cx+18, cy+55)], fill=color, width=4)# right leg
    draw.line([(cx-30, cy-5), (cx-60, cy+10)], fill=COLORS["accent_gold"], width=2)
    draw.line([(cx+30, cy-5), (cx+60, cy+10)], fill=COLORS["accent_gold"], width=2)


def _draw_silhouette_titan(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, color: tuple
) -> None:
    draw.ellipse([cx-30, cy-100, cx+30, cy-45], fill=color)         # head
    draw.ellipse([cx-18, cy-85,  cx-6,  cy-70], fill=(255, 80, 80)) # left eye
    draw.ellipse([cx+6,  cy-85,  cx+18, cy-70], fill=(255, 80, 80)) # right eye
    draw.rectangle([cx-38, cy-45, cx+38, cy+60], fill=color)        # body
    draw.line([(cx-38, cy-30), (cx-75, cy+20)], fill=color, width=16)
    draw.line([(cx+38, cy-30), (cx+75, cy+20)], fill=color, width=16)
    draw.line([(cx-20, cy+60), (cx-25, cy+120)], fill=color, width=18)
    draw.line([(cx+20, cy+60), (cx+25, cy+120)], fill=color, width=18)


def _draw_background(img: Image.Image, phase: str) -> None:
    # Use RGBA draw context so alpha fills work
    draw = ImageDraw.Draw(img, "RGBA")
    sky_map = {
        "start":   ((15,15,30),  (30,10,10)),
        "mid":     ((10,10,40),  (60,20,20)),
        "intense": ((5, 5, 20),  (100,10,10)),
        "victory": ((10,30,10),  (20,60,20)),
        "defeat":  ((30,10,10),  (80,10,10)),
    }
    top_c, bot_c = sky_map.get(phase, ((15,15,30), (30,10,10)))
    for y in range(IMG_H):
        t = y / IMG_H
        r = int(top_c[0] + (bot_c[0] - top_c[0]) * t)
        g = int(top_c[1] + (bot_c[1] - top_c[1]) * t)
        b = int(top_c[2] + (bot_c[2] - top_c[2]) * t)
        draw.line([(0, y), (IMG_W, y)], fill=(r, g, b))
    buildings = [
        (50,280,120,380), (130,260,200,380), (210,290,270,380),
        (580,250,640,380), (650,270,710,380), (720,240,790,380), (800,260,870,380),
    ]
    rng = random.Random(42)  # fixed seed so windows are consistent
    for bx1, by1, bx2, by2 in buildings:
        draw.rectangle([bx1,by1,bx2,by2], fill=(20,20,35))
        for wx in range(bx1+5, bx2-5, 12):
            for wy in range(by1+8, by2-8, 16):
                if rng.random() > 0.4:
                    draw.rectangle([wx,wy,wx+6,wy+8], fill=(200,180,80,120))
    draw.rectangle([0, 370, IMG_W, IMG_H], fill=(18,18,28))
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
    img = Image.new("RGBA", (IMG_W, IMG_H), (0, 0, 0, 255))
    _draw_background(img, phase)
    draw = ImageDraw.Draw(img, "RGBA")

    font_lg = _try_font(28)
    font_md = _try_font(20)
    font_sm = _try_font(15)
    font_xs = _try_font(12)

    # Scout silhouette (left)
    scout_cx, scout_cy = 175, 200
    _draw_aura(draw, scout_cx, scout_cy, 55, COLORS["accent_teal"])
    _draw_silhouette_scout(draw, scout_cx, scout_cy, COLORS["accent_teal"])

    # Titan silhouette (right)
    titan_cx, titan_cy = 700, 190
    _draw_aura(draw, titan_cx, titan_cy, 80, COLORS["titan_purple"])
    _draw_silhouette_titan(draw, titan_cx, titan_cy, COLORS["titan_purple"])

    # VS banner
    vs_x = IMG_W // 2
    _txt(draw, (vs_x, 160), "VS", font_lg, COLORS["accent_gold"], anchor="mm")
    draw.line([(vs_x-25,130),(vs_x+25,190)], fill=COLORS["accent_gold"], width=3)
    draw.line([(vs_x+25,130),(vs_x-25,190)], fill=COLORS["accent_gold"], width=3)

    # Name plates
    draw.rounded_rectangle([10,10,350,50], radius=8, fill=(0,0,0,160))
    _txt(draw, (20, 30), f"\U0001fa7a {scout_name}", font_md, COLORS["accent_teal"])

    draw.rounded_rectangle([550,10,890,50], radius=8, fill=(0,0,0,160))
    _txt(draw, (560, 30), f"{titan_name} \U0001f479", font_md, (200,100,255))

    # HP bars
    _draw_hp_bar(draw, 10,  70, 320, 18, scout_hp, scout_max_hp, "HP", font_sm, reverse=False)
    _draw_hp_bar(draw, 570, 70, 320, 18, titan_hp, titan_max_hp, "HP", font_sm, reverse=True)

    # Round badge
    draw.rounded_rectangle([390,8,510,52], radius=10, fill=COLORS["accent_red"])
    _txt(draw, (450, 30), f"RND {round_num}", font_md, COLORS["white"], anchor="mm")

    # Action log bar
    if last_action:
        draw.rounded_rectangle([10, 375, IMG_W-10, 412], radius=6, fill=(0,0,0,180))
        action_txt = (last_action[:90] + "...") if len(last_action) > 90 else last_action
        _txt(draw, (IMG_W//2, 393), action_txt, font_xs, COLORS["accent_gold"], anchor="mm")

    # Phase overlay
    if phase == "victory":
        draw.rounded_rectangle([250, IMG_H//2-30, 650, IMG_H//2+30],
                                radius=12, fill=(0,0,0,160))
        _txt(draw, (IMG_W//2, IMG_H//2), "\u2705  VICTORY!", font_lg, (80,255,80), anchor="mm")
    elif phase == "defeat":
        draw.rounded_rectangle([250, IMG_H//2-30, 650, IMG_H//2+30],
                                radius=12, fill=(0,0,0,160))
        _txt(draw, (IMG_W//2, IMG_H//2), "\u2620\ufe0f  FALLEN", font_lg, (255,60,60), anchor="mm")

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
    W, H = 700, 300
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    for y in range(H):
        t = y / H
        draw.line([(0,y),(W,y)], fill=(int(10+20*t), int(10+10*t), int(30+30*t)))

    draw.rounded_rectangle([2,2,W-2,H-2], radius=12,
                            outline=COLORS["accent_gold"], width=3)

    font_lg = _try_font(24)
    font_md = _try_font(17)
    font_sm = _try_font(13)

    # Title
    draw.rounded_rectangle([10,10,690,52], radius=8, fill=(0,0,0,140))
    _txt(draw, (350,31), f"\U0001fa7a  Scout Profile  —  {username}",
         font_md, COLORS["accent_gold"], anchor="mm")

    # Scout name
    _txt(draw, (30, 75), f"Character:  {scout_name}", font_lg, COLORS["accent_teal"])

    # Rank badge
    rank_colors = {
        "Cadet":   (100,100,100), "Scout":   (50,150,200),
        "Elite":   (200,150,50),  "Captain": (200,80,80),
        "Legend":  (180,50,200),
    }
    rc = rank_colors.get(rank, (100,100,100))
    draw.rounded_rectangle([500,65,690,108], radius=8, fill=(*rc, 220))
    _txt(draw, (595,86), rank, font_md, COLORS["white"], anchor="mm")

    # Stats (left column)
    for i, (label, value) in enumerate([
        ("Level",       str(level)),
        ("Wins",        str(wins)),
        ("Losses",      str(losses)),
        ("Titan Kills", str(kills)),
    ]):
        sy = 135 + i * 38
        _txt(draw, (30,  sy), f"{label}:", font_sm, COLORS["grey"])
        _txt(draw, (170, sy), value,        font_sm, COLORS["white"])

    # XP bar (right column)
    xp_pct = min(1.0, xp / max(xp_needed, 1))
    bx, by, bw, bh = 250, 138, 420, 16
    draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=8, fill=COLORS["hp_bg"])
    fw = int(bw * xp_pct)
    if fw > 4:
        draw.rounded_rectangle([bx, by, bx+fw, by+bh], radius=8, fill=COLORS["accent_gold"])
    _txt(draw, (bx, by-20), f"XP  {xp} / {xp_needed}", font_sm, COLORS["grey"])

    total = wins + losses
    wr = (wins / total * 100) if total > 0 else 0.0
    _txt(draw, (250, 175), f"Win Rate:      {wr:.1f}%",   font_sm, COLORS["accent_gold"])
    _txt(draw, (250, 213), f"Total Battles: {total}",       font_sm, COLORS["grey"])
    _txt(draw, (250, 251), f"Next Level:    {xp_needed - xp} XP", font_sm, COLORS["grey"])

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf
