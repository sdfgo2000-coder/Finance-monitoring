#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
삼성 계열사 신문스크랩 메일의 카테고리별 고정 일러스트(배너) 생성기.

- 런타임이 아니라 '한 번' 실행해 assets/news/*.png 를 만들어 repo에 커밋한다.
- 메일에는 이 PNG들을 CID 인라인 첨부로 넣어 항상 표시(외부 호스팅/차단 없음).
- 이미지에는 한글 텍스트를 넣지 않는다(카테고리명은 메일 HTML이 담당) → 폰트 의존 없음.
- 더 멋진 자체 일러스트가 있으면 같은 파일명으로 교체만 하면 된다.

재생성:  python scripts/gen_news_images.py
"""
import os
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "news")
S = 4                      # supersampling 배율(안티에일리어싱)
W, H = 600, 168            # 최종 배너 크기

# (파일명, 상단색, 하단색(그라데이션), 아이콘종류)
SPECS = [
    ("samsung_electronics.png", (20, 40, 160),  (12, 24, 110), "chip"),
    ("electronics_group.png",   (11, 114, 133), (8, 78, 92),   "battery"),
    ("bio_cnt.png",             (33, 138, 68),  (22, 100, 48), "bio"),
    ("finance.png",             (193, 65, 12),  (140, 46, 8),  "won"),
    ("others.png",              (74, 58, 140),  (52, 40, 104), "building"),
]


def _grad(w, h, top, bot):
    img = Image.new("RGB", (w, h), top)
    for y in range(h):
        t = y / max(h - 1, 1)
        img.paste(tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)),
                  (0, y, w, y + 1))
    return img


def _rrect(d, box, r, **kw):
    d.rounded_rectangle(box, radius=r, **kw)


def draw_chip(d, cx, cy, s, col):
    w = int(s * 1.0)
    half = w // 2
    _rrect(d, (cx - half, cy - half, cx + half, cy + half), s // 8,
           outline=col, width=max(2, s // 12))
    inner = int(half * 0.5)
    _rrect(d, (cx - inner, cy - inner, cx + inner, cy + inner), s // 14,
           outline=col, width=max(2, s // 14))
    pin = max(2, s // 12)
    leg = int(s * 0.18)
    for frac in (-0.5, 0.0, 0.5):
        off = int(half * frac)
        d.line((cx + off, cy - half, cx + off, cy - half - leg), fill=col, width=pin)
        d.line((cx + off, cy + half, cx + off, cy + half + leg), fill=col, width=pin)
        d.line((cx - half, cy + off, cx - half - leg, cy + off), fill=col, width=pin)
        d.line((cx + half, cy + off, cx + half + leg, cy + off), fill=col, width=pin)


def draw_battery(d, cx, cy, s, col):
    w, h = int(s * 1.15), int(s * 0.72)
    x0, y0 = cx - w // 2, cy - h // 2
    _rrect(d, (x0, y0, x0 + w, y0 + h), s // 10, outline=col, width=max(2, s // 12))
    cap = max(3, s // 9)
    d.rounded_rectangle((x0 + w, cy - h // 6, x0 + w + cap, cy + h // 6),
                        radius=cap // 2, fill=col)
    # 번개
    bx, by = cx, cy
    bolt = [(bx + s // 12, by - h // 3), (bx - s // 8, by + s // 20),
            (bx - s // 60, by + s // 20), (bx - s // 12, by + h // 3),
            (bx + s // 7, by - s // 30), (bx + s // 80, by - s // 30)]
    d.polygon(bolt, fill=col)


def draw_bio(d, cx, cy, s, col):
    w = max(3, s // 11)
    # 캡슐(알약)
    cw, ch = int(s * 0.95), int(s * 0.42)
    img = Image.new("RGBA", (cw + 8, ch + 8), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    dd.rounded_rectangle((4, 4, cw + 4, ch + 4), radius=ch // 2,
                         outline=col, width=w)
    dd.line((cw // 2 + 4, 4, cw // 2 + 4, ch + 4), fill=col, width=w)
    img = img.rotate(35, expand=True, resample=Image.BICUBIC)
    d._image.paste(img, (cx - img.width // 2, cy - img.height // 2), img)
    # 분자 점들
    r = max(3, s // 16)
    pts = [(cx + int(s * 0.42), cy - int(s * 0.34)),
           (cx + int(s * 0.6), cy - int(s * 0.12)),
           (cx + int(s * 0.34), cy - int(s * 0.08))]
    for a in range(len(pts)):
        for b in range(a + 1, len(pts)):
            d.line((pts[a], pts[b]), fill=col, width=max(2, s // 22))
    for p in pts:
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=col)


def draw_won(d, cx, cy, s, col):
    w = max(3, s // 12)
    rad = int(s * 0.5)
    d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=col, width=w)
    # ₩ : W 획(4개 사선) + 가로줄 2개
    hw = int(rad * 0.52)
    gh = int(rad * 0.74)
    top, bot = cy - gh // 2, cy + gh // 2
    xs = [cx - hw, cx - hw // 2, cx, cx + hw // 2, cx + hw]
    ys = [top, bot, top, bot, top]
    d.line(list(zip(xs, ys)), fill=col, width=w, joint="curve")
    bar = int(hw * 1.18)
    for yy in (top + int(gh * 0.30), top + int(gh * 0.55)):
        d.line((cx - bar, yy, cx + bar, yy), fill=col, width=max(2, int(w * 0.7)))


def draw_building(d, cx, cy, s, col):
    w = max(2, s // 14)
    base = cy + int(s * 0.45)
    cols = [(-0.55, 0.5), (-0.05, 0.85), (0.45, 0.65)]  # (x중심비율, 높이비율)
    bw = int(s * 0.3)
    for fx, fh in cols:
        h = int(s * fh)
        x0 = cx + int(s * fx) - bw // 2
        d.rectangle((x0, base - h, x0 + bw, base), outline=col, width=w)
        for ry in range(base - h + bw // 3, base - bw // 3, bw // 3):
            for rx in range(x0 + bw // 4, x0 + bw, bw // 3):
                d.rectangle((rx, ry, rx + max(2, bw // 8), ry + max(2, bw // 8)), fill=col)
    d.line((cx - int(s * 0.7), base, cx + int(s * 0.7), base), fill=col, width=w)


DRAW = {"chip": draw_chip, "battery": draw_battery, "bio": draw_bio,
        "won": draw_won, "building": draw_building}


def main():
    os.makedirs(OUT, exist_ok=True)
    for fname, top, bot, kind in SPECS:
        img = _grad(W * S, H * S, top, bot)
        d = ImageDraw.Draw(img)
        d._image = img
        col = (255, 255, 255)
        DRAW[kind](d, W * S // 2, H * S // 2, int(H * S * 0.5), col)
        img = img.resize((W, H), Image.LANCZOS)
        img.save(os.path.join(OUT, fname), "PNG")
        print("wrote", fname)


if __name__ == "__main__":
    main()
