"""產生程式圖示：assets/icon.png（1024）、packaging/icon.ico、assets/icon.ico。

資料助秘系列的深藍到青綠圓角方塊；中間是三張疊在一起的彩色專案卡片（最上面一張有標題列、
六個平台小圓點與勾選清單），右上角金幣寫「彙」。
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 1024


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shadow(img, shape_fn, blur=18, offset=(10, 20), alpha=100):
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shape_fn(ImageDraw.Draw(sh), offset, (0, 0, 0, alpha))
    return Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(blur)))


def font(size):
    try:
        f = ImageFont.truetype(os.path.join(HERE, "assets", "fonts", "NotoSansTC-VF.ttf"), size)
        try:
            f.set_variation_by_name("Black")
        except Exception:
            pass
        return f
    except Exception:
        return ImageFont.load_default()


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    c1, c2 = (15, 60, 110), (14, 150, 120)
    for y in range(S):
        gd.line([(0, y), (S, y)], fill=lerp(c1, c2, y / S) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([40, 40, S - 40, S - 40], radius=220, fill=255)
    img.paste(grad, (0, 0), mask)
    gloss = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(gloss).ellipse([-200, -520, S + 200, 420], fill=(255, 255, 255, 34))
    img = Image.alpha_composite(img, Image.composite(gloss, Image.new("RGBA", (S, S)), mask))

    # 三張疊起來的專案卡片（後面兩張稍微旋轉）
    cards = [((240, 180, 40), -12, (120, 40)), ((224, 82, 70), -6, (60, 20)), ((255, 255, 255), 0, (0, 0))]
    for color, angle, (dx, dy) in cards:
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        box = [200 + dx, 250 - dy, 720 + dx, 850 - dy]
        d.rounded_rectangle(box, radius=56, fill=color + (255,))
        layer = layer.rotate(angle, center=(460, 550), resample=Image.BICUBIC)
        sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        sh.paste((0, 0, 0, 90), (14, 24), layer.getchannel("A"))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(20)))
        img = Image.alpha_composite(img, layer)
    d = ImageDraw.Draw(img)
    # 最上面卡片：標題列
    d.rounded_rectangle([200, 250, 720, 380], radius=56, fill=(30, 77, 140, 255))
    d.rectangle([200, 320, 720, 380], fill=(30, 77, 140, 255))
    d.text((460, 312), "專案", font=font(84), fill=(255, 255, 255, 255), anchor="mm")
    # 六個平台小圓點
    dots = [(37, 99, 235), (71, 85, 105), (8, 145, 178), (124, 58, 237), (219, 39, 119), (22, 163, 74)]
    for i, c in enumerate(dots):
        x = 262 + i * 80
        d.ellipse([x - 26, 420, x + 26, 472], fill=c + (255,))
    # 勾選清單
    for i in range(3):
        y = 540 + i * 95
        d.rounded_rectangle([250, y - 30, 310, y + 30], radius=12, fill=(220, 252, 231, 255),
                            outline=(22, 163, 74, 255), width=6)
        if i < 2:
            d.line([(262, y), (277, y + 15), (300, y - 16)], fill=(22, 163, 74, 255), width=10, joint="curve")
        d.rounded_rectangle([340, y - 14, 660 - i * 70, y + 14], radius=14, fill=(203, 213, 225, 255))

    # 金幣「彙」
    cx, cy, r = 800, 230, 140
    img = shadow(img, lambda d, o, f: d.ellipse([cx - r + o[0], cy - r + o[1], cx + r + o[0], cy + r + o[1]], fill=f),
                 blur=16, offset=(10, 18), alpha=110)
    d = ImageDraw.Draw(img)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(240, 180, 40, 255), outline=(255, 226, 140, 255), width=14)
    d.ellipse([cx - r + 30, cy - r + 30, cx + r - 30, cy + r - 30], outline=(201, 138, 20, 255), width=6)
    d.text((cx, cy - 6), "彙", font=font(140), fill=(20, 50, 92, 255), anchor="mm")
    img.putalpha(Image.composite(img.getchannel("A"), Image.new("L", (S, S), 0), mask))
    out = os.path.join(HERE, "assets", "icon.png")
    img.save(out)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    for p in (os.path.join(HERE, "packaging", "icon.ico"), os.path.join(HERE, "assets", "icon.ico")):
        img.save(p, sizes=sizes)
    print("ok", out)


if __name__ == "__main__":
    main()
