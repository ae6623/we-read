# -*- coding: utf-8 -*-
"""生成精美兜底封面：series 主题渐变 + 衬线书名 + 作者，428x616 (30:43)。
用法: python tools/gen_fallback.py <slug> "<书名>" "<作者>" [oracle|qingyou|tianya|default] [kicker] [--force]
"""
import sys, hashlib, math, os, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 428, 616
SERIF_B = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
SANS_R = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

# 每个系列一套配色：(渐变色1, 渐变色2, 强调色, 前景色)
THEMES = {
    'oracle':  ((26, 46, 40),  (10, 20, 17),  (200, 168, 106), (242, 236, 224)),
    'qingyou': ((58, 42, 32),  (26, 18, 14),  (214, 152, 96),  (246, 238, 226)),
    'tianya':  ((32, 40, 50),  (14, 18, 24),  (140, 170, 190), (236, 240, 244)),
    'default': ((34, 38, 44),  (14, 16, 20),  (176, 156, 120), (240, 238, 232)),
}


def pick_theme(series):
    return THEMES.get(series, THEMES['default'])


def grad(w, h, c1, c2):
    """45° 斜向渐变"""
    img = Image.new('RGB', (w, h), c1)
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.35 + y / h * 0.65)
            px[x, y] = (
                int(c1[0] + (c2[0] - c1[0]) * t),
                int(c1[1] + (c2[1] - c1[1]) * t),
                int(c1[2] + (c2[2] - c1[2]) * t),
            )
    return img


def vignette(img):
    """四角压暗，营造书封的柔和聚焦"""
    w, h = img.size
    mask = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-w * 0.25, -h * 0.2, w * 1.25, h * 1.2], fill=90)
    mask = mask.filter(ImageFilter.GaussianBlur(90))
    dark = Image.new('RGB', (w, h), (0, 0, 0))
    return Image.composite(img, dark, mask.point(lambda v: 255 - int((255 - v) * 0.75)))


def wrap(text, font, maxw, draw):
    """按像素宽度折行（中文按字切）"""
    lines, cur = [], ''
    for ch in text:
        if ch == '\n':
            lines.append(cur); cur = ''; continue
        t = cur + ch
        if draw.textlength(t, font=font) > maxw and cur:
            lines.append(cur); cur = ch
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def fit_font(text, maxw, maxh, start=62, minsize=26, lines_cap=6):
    """自适应字号：在给定宽高内尽量大"""
    dummy = Image.new('RGB', (10, 10))
    d = ImageDraw.Draw(dummy)
    size = start
    while size >= minsize:
        f = ImageFont.truetype(SERIF_B, size, index=0)
        lines = wrap(text, f, maxw, d)
        lh = size * 1.42
        if len(lines) <= lines_cap and len(lines) * lh <= maxh:
            return f, lines, lh
        size -= 2
    f = ImageFont.truetype(SERIF_B, minsize, index=0)
    lines = wrap(text, f, maxw, d)
    return f, lines, minsize * 1.42


def make(slug, title, author='', series='default', kicker='', force=False):
    out_path = ROOT / 'assets' / 'covers' / ('%s.jpg' % slug)
    if out_path.exists() and not force:
        print('已存在，跳过（要覆盖加 --force）：', out_path)
        return
    c1, c2, accent, fg = pick_theme(series)
    img = grad(W, H, c1, c2)
    img = vignette(img)

    # 细颗粒噪点，去掉数码渐变的塑料感
    noise = Image.new('L', (W, H))
    seed = int(hashlib.md5(slug.encode()).hexdigest()[:8], 16) % 99991
    random.seed(seed)
    npx = noise.load()
    for y in range(0, H, 1):
        for x in range(0, W, 1):
            npx[x, y] = random.randint(118, 138)
    img = Image.composite(Image.new('RGB', (W, H), (255, 255, 255)), img,
                          noise.point(lambda v: max(0, min(255, (v - 118) // 3))))

    # 书脊：左侧渐隐深色竖条 + 内侧 1px 高光，平涂封面有实体书的厚度感
    spine = Image.new('RGBA', (16, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spine)
    for x in range(16):
        sd.line([(x, 0), (x, H)], fill=(0, 0, 0, int(64 * (1 - x / 16.0) ** 1.4)))
    img = img.convert('RGBA')
    img.alpha_composite(spine, (0, 0))
    img = img.convert('RGB')
    d = ImageDraw.Draw(img)
    d.line([15, 0, 15, H], fill=(255, 255, 255, 20), width=1)

    # 顶部系列标签（小字 + 字距）
    if kicker:
        kf = ImageFont.truetype(SANS_R, 17, index=0)
        x = 46
        for ch in kicker:
            d.text((x, 52), ch, font=kf, fill=accent + (255,) if len(accent) == 3 else accent)
            x += d.textlength(ch, font=kf) + 3
        d.line([46, 86, 46 + 76, 86], fill=accent, width=2)

    # 书名主体：去掉书名号，长副标题单独降级
    clean = title.strip().lstrip('《').rstrip('》')
    main, sub = clean, ''
    for sep in ('：', ':', '——', '—'):
        if sep in clean:
            a, b = clean.split(sep, 1)
            if len(a) <= 18:
                main, sub = a, b
            break

    f, lines, lh = fit_font(main, W - 92, 300, start=68, minsize=30)
    total = len(lines) * lh
    y = 168 + (300 - total) / 2
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill=fg)
        y += lh

    # 书名下方的小装饰：菱形 + 细线
    dy = int(y + 16)
    cx = W // 2
    d.line([cx - 46, dy, cx - 10, dy], fill=accent, width=1)
    d.line([cx + 10, dy, cx + 46, dy], fill=accent, width=1)
    d.polygon([(cx, dy - 4), (cx + 4, dy), (cx, dy + 4), (cx - 4, dy)], fill=accent)

    if sub:
        sf = ImageFont.truetype(SANS_R, 19, index=0)
        slines = wrap(sub, sf, W - 110, d)[:3]
        sy = dy + 26
        for ln in slines:
            w = d.textlength(ln, font=sf)
            d.text(((W - w) / 2, sy), ln, font=sf, fill=(int(fg[0] * 0.86), int(fg[1] * 0.86), int(fg[2] * 0.86)))
            sy += 30

    # 底部作者 + 站点标识
    if author:
        af = ImageFont.truetype(SANS_R, 20, index=0)
        w = d.textlength(author, font=af)
        d.text(((W - w) / 2, H - 108), author, font=af, fill=(int(fg[0] * 0.72), int(fg[1] * 0.72), int(fg[2] * 0.72)))

    mf = ImageFont.truetype(SANS_R, 15, index=0)
    mark = 'W E   R E A D'
    w = d.textlength(mark, font=mf)
    d.text(((W - w) / 2, H - 62), mark, font=mf, fill=(int(fg[0] * 0.5), int(fg[1] * 0.5), int(fg[2] * 0.5)))

    out = str(ROOT / 'assets' / 'covers' / ('%s.jpg' % slug))
    img.save(out, 'JPEG', quality=88, optimize=True, progressive=True)
    print('已生成', out, img.size)


if __name__ == '__main__':
    slug = sys.argv[1]
    title = sys.argv[2]
    author = sys.argv[3] if len(sys.argv) > 3 else ''
    series = sys.argv[4] if len(sys.argv) > 4 else 'default'
    kicker = sys.argv[5] if len(sys.argv) > 5 else ''
    force = '--force' in sys.argv
    make(slug, title, author, series, kicker, force)
