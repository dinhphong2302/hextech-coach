"""Cắt các vùng giao diện TFT rồi ghép thành một ảnh dễ đọc cho bước đọc ảnh.

Lý do: khung hình 1280x720 làm biểu tượng lõi chỉ còn khoảng 20 px, không model nào đọc nổi.
Vị trí các bảng trong TFT là cố định theo tỉ lệ màn hình, nên cắt đúng ô rồi phóng to là đọc được.
Mỗi khung hình vẫn chỉ tốn ĐÚNG MỘT lượt đọc ảnh: các vùng được ghép vào cùng một tấm.
"""
from pathlib import Path

import cv2
import numpy as np

# (x0, y0, x1, y1) theo tỉ lệ chiều rộng/chiều cao, kèm nhãn và mức phóng to
REGIONS = [
    # Đo lại trên khung hình thật 1936x1119 (tỉ lệ 1,730). Bộ toạ độ trước hiệu chỉnh trên
    # 1280x720 (tỉ lệ 1,778) nên vùng hàng chờ cắt trượt vào mép bàn cờ.
    ("traits", (0.000, 0.080, 0.135, 0.620), 2.6,
     "COT TRAI: loi da chon (neu hien), manh do tren hang cho, toc he va so luong"),
    ("scoreboard", (0.880, 0.150, 1.000, 0.780), 2.6,
     "BANG PHAI: mau 8 nha, HOAC bang sat thuong neu nguoi choi dang mo bang do"),
    ("topbar", (0.350, 0.010, 0.650, 0.060), 3.0, "THANH TREN: stage-round"),
    ("bottom", (0.085, 0.795, 0.560, 0.850), 2.6, "THANH DUOI: cap, thanh exp, vang"),
    ("bench", (0.150, 0.645, 0.840, 0.795), 2.2, "HANG CHO: tuong dang cho (KHONG co ten)"),
    ("shop", (0.170, 0.830, 0.820, 0.995), 2.2, "CUA HANG: 5 o tuong dang ban, CO ten duoi moi o"),
    ("center", (0.120, 0.150, 0.880, 0.880), 1.6,
     "GIUA: ba the loi dang moi chon, co ten va mo ta bang chu"),
]

LABEL_H = 26
PAD = 8
BG = (18, 28, 34)          # nền tối, cùng tông với app
FG = (216, 234, 232)


def _cut(img, box, zoom):
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    a, b = max(0, int(x0 * w)), max(0, int(y0 * h))
    c, d = min(w, int(x1 * w)), min(h, int(y1 * h))
    if c - a < 8 or d - b < 8:
        return None
    part = img[b:d, a:c]
    # phóng to bằng nội suy lập phương: nét hơn nội suy tuyến tính ở chữ và biểu tượng nhỏ
    return cv2.resize(part, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_CUBIC)


def _label(width, text):
    strip = np.full((LABEL_H, width, 3), BG, dtype=np.uint8)
    cv2.putText(strip, text, (6, LABEL_H - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, FG, 1, cv2.LINE_AA)
    return strip


def _row(parts, width):
    """Ghép vài mảnh nằm ngang, căn trái, nền tối cho phần thừa."""
    height = max(p.shape[0] for p in parts)
    row = np.full((height, width, 3), BG, dtype=np.uint8)
    x = 0
    for p in parts:
        ph, pw = p.shape[:2]
        if x + pw > width:
            pw = width - x
            p = p[:, :pw]
        if pw <= 0:
            break
        row[0:ph, x:x + pw] = p
        x += pw + PAD
    return row


# Ảnh gửi cho mô hình bị thu về cạnh dài tối đa MAX_EDGE px. Một tấm ghép cao 4000 px
# sẽ bị thu 0,36 lần, xoá sạch công phóng to — nên phải chia thành nhiều tấm thấp.
MAX_EDGE = 1568


def _vua_khung(part, max_edge=MAX_EDGE):
    """Thu nhỏ một mảnh nếu nó vượt quá cạnh cho phép."""
    h, w = part.shape[:2]
    k = min(1.0, max_edge / max(w, h))
    if k >= 1.0:
        return part
    return cv2.resize(part, (max(1, int(w * k)), max(1, int(h * k))), interpolation=cv2.INTER_AREA)


# Gộp các vùng thành ít tấm nhất mà vẫn giữ mọi cạnh dưới MAX_EDGE.
# "doc" xếp ngang (hai cột cao), "ngang" xếp chồng (các dải rộng và thấp).
GROUPS = [
    ("toancanh", "anh_goc", []),
    ("cot", "doc", ["traits", "scoreboard"]),
    ("dai", "ngang", ["topbar", "bottom", "bench", "shop"]),
    ("giua", "ngang", ["center"]),
]


def build_all(frame_path, out_dir, max_edge=MAX_EDGE, dang_chon_loi=False) -> list:
    """Cắt vùng giao diện thành vài tấm, mỗi tấm nằm dưới ngưỡng bị thu nhỏ.

    Gộp theo GROUPS để số ảnh gửi đi ít nhất có thể mà không tấm nào bị thu nhỏ.
    Trả về danh sách đường dẫn đã ghi; rỗng nghĩa là không đọc được ảnh gốc.
    """
    img = cv2.imread(str(frame_path))
    if img is None:
        return []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(frame_path).stem
    cut = {}
    for name, box, zoom, note in REGIONS:
        part = _cut(img, box, zoom)
        if part is not None:
            cut[name] = (part, note)

    # Không khung hình nào cần cả 4 tấm: lúc đang đánh thì thẻ lõi không có trên màn hình,
    # lúc đang chọn lõi thì hàng chờ và cửa hàng bị che.
    # `dang_chon_loi` do RECORDER xác định lúc ghi hình chứ không đoán lại từ ảnh: độ sáng
    # của một khung hình đơn lẻ không phân biệt được hai loại (đo thật: tỉ lệ giữa/rìa là
    # 1,81 lúc chọn lõi và 2,07 lúc đánh thường).
    chon = ("toancanh", "giua") if dang_chon_loi else ("cot", "dai")

    ra = []
    for i, (ten, kieu, vung) in enumerate(GROUPS):
        if ten not in chon:
            continue
        if kieu == "anh_goc":
            tam = _vua_khung(img, max_edge)
        else:
            co = [n for n in vung if n in cut]
            if not co:
                continue
            manh = [np.vstack([_label(cut[n][0].shape[1], _ascii(cut[n][1])), cut[n][0]]) for n in co]
            tam = _ghep_ngang(manh) if kieu == "doc" else _ghep_doc(manh)
            tam = _vua_khung(tam, max_edge)
        f = out_dir / f"{stem}_{i}_{ten}.jpg"
        if cv2.imwrite(str(f), tam, [cv2.IMWRITE_JPEG_QUALITY, 90]):
            ra.append(f)
    return ra


def _ghep_doc(manh):
    """Xếp chồng, căn trái, nền tối cho phần thừa."""
    w = max(m.shape[1] for m in manh)
    ra = []
    for m in manh:
        if m.shape[1] < w:
            dem = np.full((m.shape[0], w - m.shape[1], 3), BG, dtype=np.uint8)
            m = np.hstack([m, dem])
        ra.append(m)
    return np.vstack(ra)


def _ghep_ngang(manh):
    """Xếp cạnh nhau, căn trên."""
    h = max(m.shape[0] for m in manh)
    ra = []
    for m in manh:
        if m.shape[0] < h:
            dem = np.full((h - m.shape[0], m.shape[1], 3), BG, dtype=np.uint8)
            m = np.vstack([m, dem])
        ra.append(m)
        ra.append(np.full((h, PAD, 3), BG, dtype=np.uint8))
    return np.hstack(ra[:-1])


def build(frame_path, out_path, max_width=1600, full_width=1200) -> bool:
    """Ghép ảnh gốc + các vùng đã phóng to thành một tấm. False nếu không đọc được ảnh."""
    img = cv2.imread(str(frame_path))
    if img is None:
        return False
    h, w = img.shape[:2]

    blocks = [(_label(max_width, "ANH GOC (toan man hinh)"), None),
              (_row([cv2.resize(img, (full_width, int(h * full_width / w)),
                              interpolation=cv2.INTER_AREA)], max_width), None)]

    cut = {}
    for name, box, zoom, note in REGIONS:
        part = _cut(img, box, zoom)
        if part is not None:
            cut[name] = (part, note)

    def add(names):
        parts = []
        for n in names:
            if n not in cut:
                continue
            part = cut[n][0]
            if part.shape[1] > max_width:        # vùng rộng hơn khung thì thu lại cho vừa
                k = max_width / part.shape[1]
                part = cv2.resize(part, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            parts.append(part)
        if not parts:
            return
        note = " | ".join(cut[n][1] for n in names if n in cut)
        blocks.append((_label(max_width, _ascii(note)), None))
        blocks.append((_row(parts, max_width), None))

    add(["traits", "scoreboard"])      # hai cột dọc, xếp cạnh nhau cho đỡ cao
    add(["topbar"])
    add(["bottom"])
    add(["bench"])
    add(["shop"])
    add(["center"])

    sheet = np.vstack([b for b, _ in blocks])
    return bool(cv2.imwrite(str(out_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90]))


def _ascii(text: str) -> str:
    """OpenCV không vẽ được dấu tiếng Việt, nên nhãn trên ảnh dùng chữ không dấu."""
    import unicodedata
    out = unicodedata.normalize("NFD", text)
    return "".join(c for c in out if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
