"""Share thumbnails (Open Graph 1200x630) for prime-ads.ai/meta: GPT Image 2 team photo + exact typography (Archivo 900 condensed,
the site's display font). Outputs og/og_a.jpg (headline left) and og/og_b.jpg (headline on top)."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W, H = 1200, 630
def arch(size, wdth=70, wght=900):
    f = ImageFont.truetype("fonts/Archivo.ttf", size); f.set_variation_by_axes([wght, wdth]); return f
def inter(size, wght=600):
    f = ImageFont.truetype("fonts/Inter.ttf", size); f.set_variation_by_axes([min(32, max(14, size)), wght]); return f
WHITE, COBALT, LIVE = (255, 255, 255), (96, 128, 255), (52, 199, 89)
def base(src, crop_top):
    im = Image.open(src).convert("RGB"); w, h = im.size; ch = int(w * H / W)
    return im.crop((0, crop_top, w, crop_top + ch)).resize((W, H), Image.LANCZOS)
def shadowed(img, draw_fn):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0)); draw_fn(ImageDraw.Draw(sh), (0, 0, 0, 170))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    draw_fn(ImageDraw.Draw(img), None)
def pill(d, x, y, text, f):
    tw = d.textlength(text, font=f); d.rounded_rectangle([x, y, x + tw + 58, y + 46], radius=23, fill=(16, 18, 26, 230), outline=(60, 66, 90), width=2)
    d.ellipse([x + 18, y + 16, x + 32, y + 30], fill=LIVE); d.text((x + 42, y + 9), text, font=f, fill=WHITE)
# A: headline left, team right
im = base("gallery/og_team_a.png", 40).convert("RGBA")
grad = Image.new("L", (W, 1)); [grad.putpixel((x, 0), int(235 * max(0, 1 - x / 640) ** 1.4)) for x in range(W)]
im.alpha_composite(Image.merge("RGBA", [Image.new("L", (W, H), 6)] * 3 + [grad.resize((W, H))]))
def A(d, sh):
    c = lambda col: sh or col
    d.text((58, 92), "PRIME ADS", font=inter(26, 700), fill=c(COBALT))
    y = 132
    for line in ("META AGENCY", "AD ACCOUNT"):
        d.text((54, y), line, font=arch(96), fill=c(WHITE)); y += 92
    d.text((56, y + 14), "BUILT TO", font=arch(78), fill=c(COBALT)); d.text((56, y + 88), "STAY LIVE.", font=arch(78), fill=c(COBALT))
shadowed(im, A); d = ImageDraw.Draw(im)
pill(d, 58, 540, "prime-ads.ai", inter(24, 600))
im.convert("RGB").save("og/og_a.jpg", quality=90)
# B: headline on top, team below
im = base("gallery/og_team_b.png", 0).convert("RGBA")
top = Image.new("L", (1, H)); [top.putpixel((0, y), int(220 * max(0, 1 - y / 300) ** 1.3)) for y in range(H)]
im.alpha_composite(Image.merge("RGBA", [Image.new("L", (W, H), 6)] * 3 + [top.resize((W, H))]))
def B(d, sh):
    c = lambda col: sh or col
    t1, f1 = "META AGENCY AD ACCOUNT", arch(88)
    d.text(((W - d.textlength(t1, font=f1)) / 2, 30), t1, font=f1, fill=c(WHITE))
    t2, f2 = "BUILT TO STAY LIVE.", arch(70)
    d.text(((W - d.textlength(t2, font=f2)) / 2, 122), t2, font=f2, fill=c(COBALT))
shadowed(im, B)
im.convert("RGB").save("og/og_b.jpg", quality=90)
print("ok")
