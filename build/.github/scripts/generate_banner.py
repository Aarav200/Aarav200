#!/usr/bin/env python3
"""
Generate the animated theme-matched hero banner (dark.svg / light.svg).

Two independent pieces, both driven by profile.json + a photo:

  1. VISUAL.MAP  — your photo, converted to colored ASCII/block art,
                    with a scanning "reveal" animation.
  2. SYSTEM.INFO — a typed-out terminal readout of your info, built
                    from profile.json so you never hand-edit SVG.

Usage:
    python3 generate_banner.py profile.json photo.jpg out_dir/

Regenerate any time you change your photo or profile.json — no need
to touch dark.svg/light.svg by hand.
"""
import json, sys, os, html
from PIL import Image

THEMES = {
    "dark": {
        "BG": "#070B16", "PANEL_TOP": "#0A101F", "PANEL_BOT": "#0C1426",
        "BAR": "#0B1222", "BORDER": "rgba(255,255,255,0.10)",
        "CYAN": "#22D3EE", "VIOLET": "#A78BFA", "VIOLET2": "#7C3AED",
        "EMERALD": "#10B981", "TEXT": "#F8FAFC", "MUTED": "#94A3B8",
        "DIM": "#475569", "DOT": "rgba(148,163,184,0.35)",
        "BOXFILL": "#0A101F", "BOXSTROKE": "rgba(34,211,238,0.35)",
        "ASCII_RAMP": ["#2A2F45", "#3D3560", "#5B4A9E", "#7C3AED", "#A78BFA", "#C4B5FD", "#22D3EE"],
    },
    "light": {
        "BG": "#E2E8F0", "PANEL_TOP": "#FFFFFF", "PANEL_BOT": "#F8FAFC",
        "BAR": "#F1F5F9", "BORDER": "rgba(0,0,0,0.10)",
        "CYAN": "#0891B2", "VIOLET": "#7C3AED", "VIOLET2": "#6D28D9",
        "EMERALD": "#059669", "TEXT": "#0F172A", "MUTED": "#475569",
        "DIM": "#94A3B8", "DOT": "rgba(15,23,42,0.20)",
        "BOXFILL": "#FFFFFF", "BOXSTROKE": "rgba(8,145,178,0.35)",
        "ASCII_RAMP": ["#CBD5E1", "#94A3B8", "#7C3AED", "#6D28D9", "#0891B2", "#0E7490", "#0F172A"],
    },
}

W, H = 1180, 610
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

def esc(s): return html.escape(str(s), quote=True)

# ---------------- ASCII face ----------------
def image_to_ascii_rows(photo_path, cols=54, rows=64):
    """Sample the image on a coarse grid, return brightness 0..1 per cell."""
    img = Image.open(photo_path).convert("L")
    # center-crop to target aspect ratio before resizing
    target_ratio = cols / (rows * 1.9)  # chars are ~2x taller than wide
    w, h = img.size
    cur_ratio = w / h
    if cur_ratio > target_ratio:
        new_w = int(h * target_ratio)
        x0 = (w - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, h))
    else:
        new_h = int(w / target_ratio)
        y0 = (h - new_h) // 2
        img = img.crop((0, y0, w, y0 + new_h))
    img = img.resize((cols, rows), Image.LANCZOS)
    px = img.load()
    grid = []
    for y in range(rows):
        row = []
        for x in range(cols):
            row.append(px[x, y] / 255.0)
        grid.append(row)
    return grid

RAMP_CHARS = " .:-=+*#%@"

def ascii_face_svg(photo_path, theme, x, y, box_w, box_h, cols=54, rows=64):
    grid = image_to_ascii_rows(photo_path, cols, rows)
    cell_w = box_w / cols
    cell_h = box_h / rows
    font_size = cell_h * 1.05
    ramp = theme["ASCII_RAMP"]
    e = []
    a = e.append
    a(f'<g transform="translate({x},{y})" font-family="{FONT}" font-size="{font_size:.2f}">')
    for ri, row in enumerate(grid):
        # build one <text> per row using tspans for color runs (perf: group by color bucket)
        parts = []
        cur_color = None
        cur_chars = ""
        for ci, b in enumerate(row):
            # invert: darker pixel = denser character (face lines show up dark on light skin etc.)
            density = 1 - b
            char_idx = min(len(RAMP_CHARS) - 1, int(density * len(RAMP_CHARS)))
            ch = RAMP_CHARS[char_idx]
            color_idx = min(len(ramp) - 1, int(density * len(ramp)))
            color = ramp[color_idx]
            if ch == " ":
                if cur_chars:
                    parts.append((cur_color, cur_chars))
                    cur_chars = ""
                    cur_color = None
                parts.append((None, " "))
                continue
            if color != cur_color:
                if cur_chars:
                    parts.append((cur_color, cur_chars))
                cur_color = color
                cur_chars = ch
            else:
                cur_chars += ch
        if cur_chars:
            parts.append((cur_color, cur_chars))
        tspans = "".join(
            f'<tspan fill="{c}">{esc(chars)}</tspan>' if c else esc(chars)
            for c, chars in parts
        )
        begin = 0.15 + ri * 0.012
        a(f'<text x="0" y="{(ri+1)*cell_h:.2f}" xml:space="preserve" opacity="0">'
          f'<animate attributeName="opacity" from="0" to="1" dur="0.25s" begin="{begin:.3f}s" fill="freeze"/>'
          f'{tspans}</text>')
    a('</g>')
    # scanning highlight bar sweeping down, on loop, sci-fi reveal feel
    a(f'<rect x="{x}" y="{y}" width="{box_w}" height="3" fill="{theme["CYAN"]}" opacity="0.55">'
      f'<animate attributeName="y" values="{y};{y+box_h};{y}" dur="6s" repeatCount="indefinite"/>'
      f'</rect>')
    return "".join(e)

# ---------------- SYSTEM.INFO lines ----------------
def info_line(label, value, x, y, begin, theme, text_length=655, dots=64):
    dot_str = "." * dots
    return (f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" values="-8 0;0 0" dur="0.4s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<text x="{x}" y="{y}" font-size="14" textLength="{text_length}" lengthAdjust="spacingAndGlyphs" xml:space="preserve">'
            f'<tspan fill="{theme["CYAN"]}">{esc(label)} </tspan>'
            f'<tspan fill="{theme["DOT"]}">{dot_str}</tspan>'
            f'<tspan fill="{theme["TEXT"]}" font-weight="600"> {esc(value)}</tspan>'
            f'</text></g>')

def separator_line(label, x, y, begin, theme, text_length=655, dashes=90):
    dash_str = "-" * dashes
    return (f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<text x="{x}" y="{y}" font-size="14" textLength="{text_length}" lengthAdjust="spacingAndGlyphs" xml:space="preserve">'
            f'<tspan fill="{theme["MUTED"]}">- {esc(label)} </tspan>'
            f'<tspan fill="{theme["DOT"]}">{dash_str}</tspan>'
            f'</text></g>')

def build_svg(profile, photo_path, theme_name):
    theme = THEMES[theme_name]
    gid = f"accent_{theme_name}"
    e = []
    a = e.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
      f'font-family="{FONT}" role="img" aria-label="{esc(profile["name"])} — profile.sh --live">')
    a('<defs>')
    a(f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
      f'<stop offset="0" stop-color="{theme["VIOLET2"]}"><animate attributeName="stop-color" '
      f'values="{theme["VIOLET2"]};{theme["CYAN"]};{theme["EMERALD"]};{theme["VIOLET2"]}" dur="10s" repeatCount="indefinite"/></stop>'
      f'<stop offset="1" stop-color="{theme["EMERALD"]}"><animate attributeName="stop-color" '
      f'values="{theme["EMERALD"]};{theme["VIOLET2"]};{theme["CYAN"]};{theme["EMERALD"]}" dur="10s" repeatCount="indefinite"/></stop>'
      '</linearGradient>')
    a(f'<linearGradient id="panelGrad_{theme_name}" x1="0" y1="0" x2="0" y2="1">'
      f'<stop offset="0" stop-color="{theme["PANEL_TOP"]}"/><stop offset="1" stop-color="{theme["PANEL_BOT"]}"/></linearGradient>')
    a(f'<clipPath id="winClip_{theme_name}"><rect x="2" y="2" width="{W-4}" height="{H-4}" rx="18"/></clipPath>')
    a('</defs>')

    a(f'<rect x="2" y="2" width="{W-4}" height="{H-4}" rx="18" fill="{theme["BG"]}"/>')
    a(f'<g clip-path="url(#winClip_{theme_name})">')
    a(f'<rect x="2" y="2" width="{W-4}" height="{H-4}" fill="url(#panelGrad_{theme_name})"/>')
    a(f'<rect x="2" y="2" width="{W-4}" height="46" fill="{theme["BAR"]}"/>')
    a(f'<line x1="2" y1="48" x2="{W-2}" y2="48" stroke="{theme["BORDER"]}"/>')
    a(f'<circle cx="30" cy="25" r="5.5" fill="#ff5f56"/><circle cx="50" cy="25" r="5.5" fill="#ffbd2e"/><circle cx="70" cy="25" r="5.5" fill="#27c93f"/>')
    a(f'<text x="{W/2:.0f}" y="29" text-anchor="middle" font-size="12" fill="{theme["MUTED"]}">'
      f'{esc(profile["email"])} - % ./profile.sh --live</text>')

    # VISUAL.MAP box
    box_x, box_y, box_w, box_h = 36, 84, 400, 492
    a(f'<text x="38" y="74" font-size="10" letter-spacing="3" fill="{theme["DIM"]}">VISUAL.MAP</text>')
    a(f'<rect x="{box_x}" y="{box_y}" width="{box_w}" height="{box_h}" rx="10" fill="none" stroke="{theme["CYAN"]}" stroke-width="2" opacity="0.45"/>')
    a(f'<rect x="{box_x}" y="{box_y}" width="{box_w}" height="{box_h}" rx="10" fill="{theme["BOXFILL"]}" stroke="{theme["BOXSTROKE"]}"/>')
    a(f'<clipPath id="faceClip_{theme_name}"><rect x="{box_x}" y="{box_y}" width="{box_w}" height="{box_h}" rx="10"/></clipPath>')
    a(f'<g clip-path="url(#faceClip_{theme_name})">')
    a(ascii_face_svg(photo_path, theme, box_x+14, box_y+22, box_w-28, box_h-36))
    a('</g>')

    # SYSTEM.INFO box
    ix = 470
    a(f'<text x="{ix}" y="106" font-size="13" letter-spacing="2" fill="{theme["CYAN"]}">SYSTEM.INFO</text>')
    a(f'<text x="{W-55}" y="106" text-anchor="end" font-size="12" fill="#F87171" font-weight="700">'
      f'<tspan>&#9679;</tspan> LIVE<animate attributeName="opacity" values="1;0.25;1" dur="1.6s" repeatCount="indefinite"/></text>')
    a(f'<text x="{ix+9}" y="136" font-size="14" font-weight="700" fill="{theme["VIOLET"]}" opacity="0.9">{esc(profile["email"])}</text>')

    t = 0.90
    for i, (label, value) in enumerate(profile["info_lines"]):
        a(info_line(label, value, ix, 162 + i*23, t, theme))
        t += 0.12
    y_cursor = 162 + len(profile["info_lines"]) * 23 + 8

    a(separator_line("Contact", ix, y_cursor + 15, t, theme))
    t += 0.12
    y_cursor += 38
    for label, value in profile["contact_lines"]:
        a(info_line(label, value, ix, y_cursor, t, theme))
        t += 0.12
        y_cursor += 23

    a(f'<text x="{ix}" y="{y_cursor+30}" font-size="14" fill="{theme["MUTED"]}">'
      f'&#9656; More about me &amp; projects below in README &#8595; '
      f'<tspan fill="{theme["CYAN"]}">&#9608;<animate attributeName="fill-opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/></tspan></text>')

    a(f'<line x1="{box_x}" y1="{box_y+box_h+14}" x2="{W-36}" y2="{box_y+box_h+14}" stroke="url(#{gid})" stroke-width="1.5" opacity="0.5"/>')
    a('</g>')
    a('</svg>')
    return "".join(e)

if __name__ == "__main__":
    profile_path = sys.argv[1] if len(sys.argv) > 1 else "profile.json"
    photo_path = sys.argv[2] if len(sys.argv) > 2 else "photo.jpg"
    outdir = sys.argv[3] if len(sys.argv) > 3 else "."
    with open(profile_path) as f:
        profile = json.load(f)
    for theme_name, fname in (("dark", "dark.svg"), ("light", "light.svg")):
        svg = build_svg(profile, photo_path, theme_name)
        path = os.path.join(outdir, fname)
        with open(path, "w") as f:
            f.write(svg)
        print(f"wrote {path} ({len(svg)//1024}KB)")
