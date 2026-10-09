"""Tạo bộ icon JC Coaching từ assets/source.png.

Chạy: python make_icons.py
Sinh jc.ico (shortcut, thanh tác vụ, cửa sổ) và tray.png (khay hệ thống khi chạy nền).
"""
import io, struct
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "assets"
SRC = OUT / "source.png"      # ảnh gốc; thay file này rồi chạy lại để đổi logo
OUT.mkdir(parents=True, exist_ok=True)
GOLD = (216, 169, 79, 255)

full = Image.open(SRC).convert("RGBA")
full.resize((512, 512), Image.LANCZOS).save(OUT / "logo.png")

# cắt lấy phần đầu + mũ: đọc được cả khi thu về 16px
head = full.crop((330, 20, 1590, 1280)).resize((512, 512), Image.LANCZOS)


def badge(src: Image.Image, size: int, ring: int) -> Image.Image:
    """Huy hiệu tròn, viền vàng — dùng cho khay hệ thống và icon cỡ nhỏ."""
    s = 1024
    img = src.resize((s, s), Image.LANCZOS)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, s - 1, s - 1), fill=255)
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    d = ImageDraw.Draw(out)
    w = int(s * ring / 100)
    d.ellipse((w // 2, w // 2, s - 1 - w // 2, s - 1 - w // 2), outline=GOLD, width=w)
    return out.resize((size, size), Image.LANCZOS)


badge(head, 256, 5).save(OUT / "tray.png")


def png_bytes(im: Image.Image) -> bytes:
    b = io.BytesIO()
    im.save(b, format="PNG")
    return b.getvalue()


def write_ico(path: Path, images: dict):
    """ICO nhiều kích thước, mỗi kích thước một ảnh riêng."""
    sizes = sorted(images)
    blobs = [png_bytes(images[s]) for s in sizes]
    head_b = struct.pack("<HHH", 0, 1, len(sizes))
    off = 6 + 16 * len(sizes)
    entries = b""
    for s, blob in zip(sizes, blobs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(blob), off)
        off += len(blob)
    path.write_bytes(head_b + entries + b"".join(blobs))


# cỡ nhỏ dùng huy hiệu đầu cho rõ nét, cỡ lớn dùng trọn ảnh kèm chữ JC COACHING
imgs = {}
for s in (16, 20, 24, 32, 48):
    imgs[s] = badge(head, s, 6)
for s in (64, 128, 256):
    imgs[s] = full.resize((s, s), Image.LANCZOS)
write_ico(OUT / "jc.ico", imgs)

print("xong:", *(p.name + " " + str(p.stat().st_size) for p in sorted(OUT.iterdir())), sep="\n  ")
