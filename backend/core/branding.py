"""Company themes: default Jay's HR sage green, or colours taken from a client's logo."""

import colorsys

from PIL import Image

DEFAULT_BRAND = "#4f7462"   # sage green
DEFAULT_ACCENT = "#b9d0c2"  # pale sage
DEFAULT_STYLE = "bold"

# Calm, plain colour sets to choose from: (key, name, main colour, second colour)
PRESETS = [
    ("mauve", "Mauve", "#7d5f80", "#c9b3c9"),
    ("lavender", "Lavender", "#6b62a3", "#c7c2e6"),
    ("rose", "Dusty rose", "#9a5a6b", "#e2bcc4"),
    ("plum", "Plum", "#6e3f5c", "#d4a9c2"),
    ("terracotta", "Terracotta", "#a0573d", "#e7c0ad"),
    ("sand", "Sand", "#8a6d45", "#e0cfae"),
    ("olive", "Olive", "#66703f", "#cdd3a8"),
    ("sage", "Sage", "#4f7462", "#b9d0c2"),
    ("teal", "Teal", "#2f6f73", "#a9cfd0"),
    ("dusty_blue", "Dusty blue", "#4c6a8a", "#b8c9db"),
    ("navy", "Navy", "#2f4468", "#a9b6cc"),
    ("slate", "Slate", "#55606e", "#c4cad2"),
]

# Page designs: (key, name, description)
STYLES = [
    ("soft", "Soft", "White header with a thin colour strip, rounded cards"),
    ("bold", "Bold", "Header filled with the main colour"),
    ("minimal", "Minimal", "All white, square corners, no colour strip"),
    ("tinted", "Tinted", "Page washed with a pale shade of your colour"),
]


def _rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def luminance(hexcolor):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in _rgb(hexcolor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted([luminance(a), luminance(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a, b, t):
    """Blend colour a towards b by t (0–1)."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex([x + (y - x) * t for x, y in zip(ra, rb)])


def readable_on_white(hexcolor, target=4.5):
    """Darken a colour until text in it is readable on white."""
    c = hexcolor
    for _ in range(20):
        if contrast(c, "#ffffff") >= target:
            return c
        c = mix(c, "#000000", 0.12)
    return c


def theme(brand=None, accent=None, style=None):
    """CSS variables for a brand colour. Works for light or dark brand colours."""
    brand = brand or DEFAULT_BRAND
    accent = accent or DEFAULT_ACCENT
    strong = readable_on_white(brand)  # links, headings, button fill
    return {
        "brand": strong,
        "brand_ink": "#ffffff" if contrast(strong, "#ffffff") >= 4.5 else "#1f1a21",
        "brand_soft": mix(brand, "#ffffff", 0.88),   # chips, active nav
        "brand_line": mix(brand, "#ffffff", 0.70),
        "accent": accent,
        "accent_soft": mix(accent, "#ffffff", 0.75),
        "page_tint": mix(brand, "#ffffff", 0.94),
        "style": style if style in dict((k, n) for k, n, _ in STYLES) else DEFAULT_STYLE,
    }


def palette_from_logo(fileobj, count=5):
    """Pick the main non-white, non-grey colours from a logo image."""
    img = Image.open(fileobj).convert("RGBA")
    img.thumbnail((200, 200))
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(bg, img).convert("RGB")
    q = img.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    found = []
    for n, idx in sorted(q.getcolors(), reverse=True):
        r, g, b = pal[idx * 3: idx * 3 + 3]
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if l > 0.93 or l < 0.06:      # near white / near black background
            continue
        if s < 0.12 and found:        # keep greys only if nothing better
            continue
        hx = _hex((r, g, b))
        if all(contrast(hx, f) > 1.25 for f in found):
            found.append(hx)
        if len(found) >= count:
            break
    return found
