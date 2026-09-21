"""assets/prizm_coin.png v5: монета 85% кадра, ободок и свечение целиком в кадре.
Запуск: python make_coin5.py"""
from PIL import Image, ImageDraw, ImageFilter

SRC = "assets/prizm_coin_src.png"
OUT = "assets/prizm_coin.png"
KEY = (255, 0, 255)
RING_COLOR = (194, 107, 255)        # #c26bff — цвет линии курса
RING_W = 16

src = Image.open(SRC).convert("RGBA")
ImageDraw.floodfill(src, (0, 0), KEY + (255,), thresh=60)
px = src.load()
w, h = src.size
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if (r, g, b) == KEY:
            px[x, y] = (0, 0, 0, 0)
src = src.crop(src.getbbox())
cw, ch = src.size

S = int(max(cw, ch) * 1.30)         # кадр с запасом под ободок и свечение
canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
c = int(S * 0.85)                   # монета крупнее (было 72)
coin = src.resize((c, c), Image.LANCZOS)
canvas.paste(coin, ((S - c) // 2, (S - c) // 2), coin)
cx = cy = S / 2
rad = c / 2
ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(ring).ellipse([cx - rad - RING_W, cy - rad - RING_W,
                              cx + rad + RING_W, cy + rad + RING_W],
                             outline=RING_COLOR + (255,), width=RING_W)
glow = ring.filter(ImageFilter.GaussianBlur(6))
out = Image.alpha_composite(glow, canvas)
out = Image.alpha_composite(out, ring)
out.save(OUT)
print("✅", OUT, "v5: монета 85%, ободок в кадре")