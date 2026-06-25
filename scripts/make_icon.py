"""Generate HydroBalance brand icons.

Outputs:
  brand/icon.png      256x256, transparent
  brand/icon@2x.png   512x512, transparent
  brand/logo.png      ~700x256, transparent
  brand/logo@2x.png   ~1400x512

A blue water droplet with a green leaf overlapping on the right — same
clean flat aesthetic as the reference.
"""
from __future__ import annotations

import math
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "..", "brand")
os.makedirs(OUT, exist_ok=True)

# Palette — vivid, friendly, HA-brands style
BLUE = (38, 153, 220, 255)       # main droplet
GREEN = (95, 178, 70, 255)        # main leaf
GREEN_DK = (60, 130, 50, 255)     # leaf vein
TEXT = (38, 50, 56, 255)


def droplet_points(cx: float, cy: float, R: float, H: float, samples: int = 200):
    """Smooth teardrop with pointed top and circular body.

    Apex at (cx, cy-H), body is a circle of radius R around (cx, cy).
    Two straight tangents from the apex down to the circle, joined by the
    arc going around the bottom — C1 smooth at the contact points.
    """
    # Tangent contact points (math: y above center is positive, but we work in
    # image coords where y grows down — so tangent y in image is cy minus offset).
    yt = R * R / H
    xt = R * math.sqrt(H * H - R * R) / H
    apex = (cx, cy - H)
    right_t = (cx + xt, cy - yt)
    left_t = (cx - xt, cy - yt)

    pts = [apex, right_t]
    # Arc from right tangent → bottom → left tangent.
    # Compute parametric angles. atan2(y_local, x_local) where y_local is
    # image-y minus center, so positive means below center. Right tangent has
    # y_local = -yt (above center) → angle in (-π/2, 0). To sweep through the
    # bottom (angle +π/2), we increase the angle past 0 then keep going.
    a_start = math.atan2(-yt, xt)           # ≈ -32°
    a_end = math.atan2(-yt, -xt)            # ≈ -148°
    # We want to go from a_start increasing through +π/2 (bottom) and continue
    # past π up to where a_end + 2π lies.
    if a_end < a_start:
        a_end += 2 * math.pi  # → ≈ 212° → sweep of ≈ 245°, through +π/2 ✓
    for i in range(1, samples + 1):
        t = a_start + (a_end - a_start) * i / samples
        pts.append((cx + R * math.cos(t), cy + R * math.sin(t)))
    pts.append(left_t)
    return pts


def leaf_points(cx: float, cy: float, length: float, width: float,
                angle_deg: float, samples: int = 120):
    """Pointed-tip leaf shape (almond), rotated.

    Uses y = ±(W/2) × sin(t)^1.5 for sharper tips than a plain ellipse.
    """
    a = math.radians(angle_deg)
    cos_a, sin_a = math.cos(a), math.sin(a)
    pts = []
    # Upper edge: t from 0 (left tip) to π (right tip)
    for i in range(samples + 1):
        t = math.pi * i / samples
        x_local = -length / 2 * math.cos(t)
        y_local = -(width / 2) * (math.sin(t) ** 1.5)  # negative = up in image
        xr = x_local * cos_a - y_local * sin_a
        yr = x_local * sin_a + y_local * cos_a
        pts.append((cx + xr, cy + yr))
    # Lower edge: t from π back to 0
    for i in range(samples, -1, -1):
        t = math.pi * i / samples
        x_local = -length / 2 * math.cos(t)
        y_local = (width / 2) * (math.sin(t) ** 1.5)
        xr = x_local * cos_a - y_local * sin_a
        yr = x_local * sin_a + y_local * cos_a
        pts.append((cx + xr, cy + yr))
    return pts


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 256.0

    # Droplet — point at top, body in lower half. Pulled slightly left so the
    # leaf can sit naturally on the right.
    cx = 118 * s
    cy = 148 * s
    R = 72 * s
    H = 132 * s
    droplet = droplet_points(cx, cy, R, H)
    draw.polygon(droplet, fill=BLUE)

    # Leaf — angled NE/SW, overlapping the droplet's right side
    lx, ly = 168 * s, 158 * s
    leaf = leaf_points(lx, ly, length=140 * s, width=58 * s, angle_deg=-58)
    draw.polygon(leaf, fill=GREEN)

    # Leaf midrib — slim darker stroke along the leaf's long axis
    rib_a = math.radians(-58)
    rib_len = 56 * s
    rib_dx, rib_dy = rib_len * math.cos(rib_a), rib_len * math.sin(rib_a)
    draw.line(
        [(lx - rib_dx, ly - rib_dy), (lx + rib_dx, ly + rib_dy)],
        fill=GREEN_DK,
        width=max(1, int(3 * s)),
    )

    return img


def draw_logo(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    icon = draw_icon(height)
    img.paste(icon, (0, 0), icon)

    draw = ImageDraw.Draw(img)
    text = "HydroBalance"
    font = None
    for cand in [
        "C:/Windows/Fonts/SegoeUI.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",  # bold
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if os.path.exists(cand):
            try:
                font = ImageFont.truetype(cand, int(height * 0.48))
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_h = bbox[3] - bbox[1]
    x = height + int(height * 0.08)
    y = (height - text_h) // 2 - bbox[1]
    draw.text((x, y), text, fill=TEXT, font=font)
    return img


def main():
    draw_icon(256).save(os.path.join(OUT, "icon.png"))
    draw_icon(512).save(os.path.join(OUT, "icon@2x.png"))
    draw_logo(700, 256).save(os.path.join(OUT, "logo.png"))
    draw_logo(1400, 512).save(os.path.join(OUT, "logo@2x.png"))
    print("Wrote brand/ assets.")


if __name__ == "__main__":
    main()
