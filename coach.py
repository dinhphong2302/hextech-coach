"""Gọi Claude để review trận, tìm meta và lập giáo án.

Hai chế độ, chọn bằng "engine" trong config.json:
  - "claude_cli": chạy Claude Code ở chế độ nền, dùng hạn mức gói Pro/Max (không tốn tiền API)
  - "api":        gọi Claude API, tính tiền theo lượt dùng
"""
import base64
import concurrent.futures
import assets
import crops
import json
import os
import re
import shutil
import subprocess
import threading
import tft_rules
import sys
from datetime import date
from pathlib import Path

from config import ROOT

GUIDE = (ROOT / "guide_vi.md").read_text(encoding="utf-8")


def handbook_text(cfg=None) -> str:
    """Cẩm nang đã tra từ tài liệu Dishsoap, nếu đã có."""
    for p in [(cfg or {}).get("data_path"), ROOT / "data"]:
        if not p:
            continue
        f = Path(p) / "handbook.md"
        if f.exists():
            return f.read_text(encoding="utf-8")
    return ""

SYSTEM = f"""Bạn là huấn luyện viên Teamfight Tactics đẳng cấp thế giới, tư duy như tuyển thủ Dishsoap: kinh tế chặt chẽ, xoay bài linh hoạt, mọi quyết định dựa trên toán học và xác suất chứ không cảm tính.

Nguyên tắc:
- Viết tiếng Việt, sắc bén, đi thẳng vào vấn đề.
- Luôn theo khung: Phân tích dữ kiện → Quyết định → Kế hoạch tiếp theo.
- Dùng bảng Markdown khi so sánh lõi, đồ, đội hình; gạch đầu dòng cho các bước.
- Dẫn số liệu cụ thể (vàng, máu, level, stage, tỉ lệ ra tướng) khi lập luận.
- Chỉ khẳng định điều bạn thấy trong ảnh hoặc dữ liệu. Chi tiết nào không đọc được thì nói rõ, không đoán bừa.
- Ưu tiên dữ liệu meta được cung cấp hơn kiến thức cũ của bạn, vì patch thay đổi liên tục.

{tft_rules.rules_md()}

Kiến thức nền dùng để đánh giá người chơi theo rank:

{GUIDE}"""

# Bản không kèm cẩm nang: dùng cho bước tìm meta và bước dựng lại chính cẩm nang. Nhét cẩm
# nang cũ vào lúc dựng cẩm nang mới thì lỗi cũ (tên tướng sai, ý lẫn set) bị chép tiếp.
SYSTEM_BASE = SYSTEM

_HB = handbook_text()
if _HB:
    SYSTEM += "\n\n---\n\nCẩm nang tổng hợp từ tài liệu của Dishsoap:\n\n" + _HB

REVIEW_FORMAT = """Dữ liệu đưa cho bạn là chuỗi JSON trạng thái trận theo mốc thời gian.
Hãy chấm trận này như một huấn luyện viên, dùng kiến thức nền của Dishsoap ở phần đầu prompt.

QUY TẮC BẮT BUỘC
- Mốc có "is_in_game": false đã bị loại sẵn, đừng nhắc tới chúng như diễn biến trận.
- Mua, bán, lên cấp KHÔNG nhìn thấy trực tiếp được. Chỉ suy ra bằng cách so sánh hai mốc
  liền nhau, và phải ghi rõ là suy ra, kèm khoảng thời gian.
- Trường null nghĩa là KHÔNG ĐỌC ĐƯỢC. Ghi đúng "không đọc được", cấm suy diễn giá trị.
- Tên lõi trong JSON ĐÃ được app đối chiếu với cơ sở dữ liệu lõi của set, nên mọi tên còn
  lại đều là lõi có thật — dùng thẳng, không sửa, không dịch. Trường null nghĩa là app
  đã bỏ vì không khớp lõi nào; ghi "không đọc được".
- "augment_choices" là BA lõi được MỜI chọn ở vòng đó, không phải lõi đã chọn.
  "augments" mới là lõi người chơi thật sự lấy. Đừng lẫn hai thứ.
- Vòng chọn lõi chỉ có ở stage """ + ", ".join(tft_rules.AUGMENT_ROUNDS) + """.
- Mọi con số phải lấy từ JSON, từ dữ liệu Riot API, hoặc từ bảng số liệu app cung cấp. Cấm bịa.
- KHÔNG lặp nội dung giữa các phần. Mỗi dữ kiện chỉ xuất hiện ở đúng một chỗ.
- Viết ngắn, đi thẳng vào số. Không mở bài, không kết luận sáo.

## Tóm tắt

Phần này người chơi đọc trước tiên và nhiều khi chỉ đọc mỗi nó. Viết đúng năm dòng dưới đây,
không thêm gì, không dùng bảng:

1. **Kết quả** — hạng mấy, bị loại ở stage nào, đánh bài gì. Một dòng.
2. **Vì sao ra hạng đó** — một câu duy nhất, nêu nguyên nhân lớn nhất, kèm con số.
3. **Ba lỗi nặng nhất** — ba gạch đầu dòng, mỗi dòng CHỈ gồm `Stage x-y` và con số thiệt hại,
   kèm hai tới ba từ đặt tên lỗi. Ví dụ: `3-2 — gãy mốc lãi — mất 14 vàng`.
   KHÔNG mô tả "lẽ ra làm gì" hay "thực tế đã làm gì" ở đây; đó là việc của mục 4.
4. **Việc cần sửa ngay ở trận sau** — đúng MỘT việc, việc có thiệt hại lớn nhất, kèm ngưỡng số.
5. **Độ tin của báo cáo này** — một dòng: `Cao / Trung bình / Thấp` kèm lý do ngắn
   (bao nhiêu mốc đọc được, trường quan trọng nào bị thiếu).

Các phần sau KHÔNG được nhắc lại câu chữ của phần Tóm tắt; chúng chỉ đào sâu bằng bảng và số.
Nếu dữ liệu quá mỏng để nêu được ba lỗi thì nêu ít hơn, và nói rõ ở dòng 5.

## 1. Dòng thời gian
Bảng: Mốc | Stage | Vàng | Máu | Level | Lõi | Hành động suy ra
Mỗi mốc một dòng, theo thứ tự thời gian. Cột hành động ghi: mua hoặc bán tướng nào,
lên cấp mấy, đang chuỗi thắng hay chuỗi thua, chạm mốc lãi nào (10, 20, 30, 40, 50 vàng).
Không có thay đổi thì ghi "không đổi".

## 2. Giữ máu
- Hết stage 2 còn bao nhiêu máu, mất bao nhiêu, mất nhiều nhất ở khoảng nào.
- Có cơ hội ghép đồ sớm để đỡ máu không: nêu mảnh đồ đang có ở từng mốc và món lẽ ra ghép được.
- Ước tính số máu mất oan, kèm một câu nói rõ ước tính dựa trên cái gì.

## 3. Kinh tế
Bảng: Mốc | Vàng thật | Mốc lãi chạm được | Lẽ ra | Thiệt hại
- Chạm mốc lãi đúng nhịp chưa, gãy mốc ở đâu và vì sao (mua tướng thừa hay roll lẻ tẻ).
- Roll sớm hay roll trễ so với level và số máu lúc đó.
- Thiệt hại quy ra vàng, và quy ra số lần roll bị mất.

## 4. Sai lầm theo thời điểm
Tối đa 5 dòng, xếp theo mức thiệt hại giảm dần. Mỗi dòng đúng mẫu:
**Stage x-y** — lẽ ra làm gì — thực tế đã làm gì — thiệt hại bằng số.
Ngay dưới mỗi dòng thêm dấu ảnh [[anh:mm:ss]] theo đúng mốc đã dựa vào.
Mốc không đủ dữ liệu để kết luận thì bỏ, đừng chấm bừa.

## 5. Vòng chọn lõi
Chỉ viết mục này nếu JSON có mốc nào `"is_augment_round": true` hoặc có `augment_choices`.
Không có thì ghi đúng một dòng: "Không đọc được vòng chọn lõi nào." rồi sang mục sau.

Bảng: Vòng | Ba lõi được mời | Lõi đã lấy | Nhận xét
Mỗi vòng """ + ", ".join(tft_rules.AUGMENT_ROUNDS) + """ một dòng. Cột nhận xét đúng một câu: lõi đã lấy có hợp với đồ và
tướng đang có lúc đó không, và nếu một lõi khác trong ba lõi hợp hơn thì nói rõ lõi nào
và vì sao. Lõi đã lấy để null thì ghi "không xác nhận được" — đừng đoán là lõi nào.

## 6. Hướng cải thiện
Ba bài tập đo được cho trận sau, mỗi bài gắn với đúng một lỗi ở mục 4, kèm ngưỡng số
để trận sau tự kiểm tra được là đã làm đúng hay chưa.

[[bieudo]]

## 7. Trận này khớp hay lệch với xu hướng của người chơi
**Nếu ở trên KHÔNG có khối "ĐIỂM MẠNH VÀ ĐIỂM YẾU ĐÃ TÍNH"** thì viết đúng một dòng:
"Chưa có hồ sơ các trận gần nhất, không đối chiếu được." rồi bỏ qua phần còn lại của mục này.
Tuyệt đối không tự nghĩ ra điểm mạnh điểm yếu từ một trận.

Nếu có khối đó: **không tính lại và không chép lại bảng đó.**

Chỉ viết tối đa 4 gạch đầu dòng, mỗi dòng trả lời một trong hai câu:
- Trận này có lặp lại đúng một điểm yếu đã biết không? Dẫn số của trận này cạnh số của hồ sơ.
- Trận này có đi ngược một điểm mạnh đã biết không?
Không có điểm nào khớp hay lệch rõ thì ghi đúng một dòng: "Trận này không đủ dữ liệu để
đối chiếu với xu hướng."

## 8. Độ tin cậy
Bảng ngắn: Hạng mục | Nguồn | Độ tin
Hạng mục: hạng cuối, đội hình cuối, vàng và máu theo thời gian, lõi đã chọn, mua bán tướng.
Nguồn ghi rõ "Riot API", "đọc từ ảnh" hay "suy ra từ chênh lệch mốc".
Dòng cuối ghi: bao nhiêu mốc bị loại vì ngoài game, bao nhiêu trường quan trọng bị null.

Chỉ xuất Markdown, không thêm lời dẫn."""


EXTRACT_FORMAT = """Bạn là hệ thống Computer Vision đọc giao diện trận Đấu Trường Chân Lý (TFT).
Nhiệm vụ: ĐỌC ảnh rồi xuất JSON nghiêm ngặt. KHÔNG nhận xét, KHÔNG khuyên, KHÔNG đoán.

QUY TẮC NHẬN DIỆN
1. Stage: đọc ở thanh trạng thái phía trên giữa màn hình (ví dụ 2-1, 3-2).
2. Kinh tế và level:
   - Vàng: số cạnh biểu tượng vàng, ở giữa phía dưới màn hình.
   - Máu: máu của CHÍNH người chơi, đọc ở bảng máu 8 nhà BÊN PHẢI màn hình, đúng dòng có tên người chơi.
   - Level và tiến trình EXP: góc trái phía dưới, ví dụ level 4 và exp "2/10".
3. Lõi công nghệ — đọc theo đúng cách vòng chọn lõi hoạt động:

   Vòng chọn lõi chỉ xảy ra ở **stage """ + ", ".join(tft_rules.AUGMENT_ROUNDS) + """**. Không có vòng nào khác.

   a) MÀN ĐANG MỜI CHỌN (có chữ "Choose One" hoặc "Chọn Một" ở giữa màn hình):
      - Ba thẻ lớn nằm giữa màn hình, mỗi thẻ có TÊN LÕI in đậm và phần mô tả bên dưới.
        Đọc đủ ba tên vào "augment_choices", đặt "is_augment_round": true.
      - Dưới mỗi thẻ có một nút xoay vòng ↻ để đổi lõi khác. Nút đó KHÔNG phải lựa chọn.
      - Lúc này người chơi CHƯA chọn gì: "augments" vẫn để null.

   b) HAI THỨ DỄ NHẦM LÀ "ĐÃ CHỌN XONG" — đều KHÔNG phải:
      - Nút màu xanh dương hình chồng thẻ ở giữa phía dưới: đó là nút TẮT TẠM bảng lõi
        để người chơi nhìn sảnh. Bảng lõi biến mất nhưng chưa chọn gì.
      - Ba thẻ biến mất kèm hiệu ứng: chỉ cho biết vừa có thao tác, chưa đủ để kết luận.

   c) CHỈ ĐƯỢC COI LÀ ĐÃ CHỌN khi lõi đó XUẤT HIỆN Ở CỘT BÊN TRÁI màn hình.
      Đó là nơi duy nhất xác nhận lõi đã thuộc về người chơi. Khi thấy, ghi vào "augments"
      theo đúng thứ tự từ trên xuống, tối đa 3 lõi.

   - Tên lõi CHỈ được ghi khi khớp DANH SÁCH LÕI HỢP LỆ ở cuối prompt này. Không khớp thì null.
     Cấm tự đặt tên, cấm dịch tên, cấm ghi tên lõi của set khác.
4. Sân đấu và hàng chờ:
   - LƯU Ý: tướng trên sân và trên hàng chờ KHÔNG có tên hiển thị, chỉ có hình. Chỉ ghi tên
     khi bạn thật sự nhận ra tướng đó, còn lại để null — thà thiếu còn hơn đoán sai.
     Riêng năm ô CỬA HÀNG thì CÓ tên in dưới mỗi ô, đọc thẳng được.
   - Đọc tên tướng và số sao (1, 2 hay 3 — nhìn sao trên đầu và màu viền).
   - Liệt kê ĐẦY ĐỦ mọi tướng nhìn thấy, kể cả tướng không cầm đồ. Thiếu một tướng là hỏng
     phần suy ra mua và bán ở bước sau.
   - Ghi trang bị đang mang trên từng tướng nếu đọc được.
5. Ảnh ngoài game hoặc bị che:
   - Ảnh đang ở trình duyệt, desktop, màn hình chờ, bảng điểm cuối trận hay bị cửa sổ khác che:
     đặt "is_in_game": false và để mọi trường còn lại null hoặc rỗng.
   - Không nhìn rõ thì trả null. TUYỆT ĐỐI không đoán mò.

Mỗi ảnh xuất ĐÚNG MỘT dòng JSON hợp lệ, không bọc trong dấu nháy ba, không thêm chữ nào khác:
{"t":"mm:ss","is_in_game":true,"stage":"2-2","gold":11,"hp":96,"level":4,"exp":"2/10",
 "streak":"thua 3","augments":["Tên lõi 1",null,null],"is_augment_round":false,
 "augment_choices":[],"board":[{"champion":"Ashe","star":2,"items":["Vô Cực Kiếm"]}],
 "bench":[{"champion":"Sivir","star":1,"items":[]}],"components":["Kiếm","Găng"],
 "shop_slots":["Kennen",null,"Ashe",null,null],"lobby_hp":[100,88,72],"note":null}

- MỘT MỐC THỜI GIAN CÓ NHIỀU ẢNH. App cắt mỗi khung hình thành vài tấm (cột trái, dải dưới,
  hoặc toàn cảnh và vùng giữa), nên bạn sẽ thấy hai ảnh trở lên có CÙNG nhãn thời gian.
  Đó là cùng một khoảnh khắc nhìn từ nhiều vùng màn hình. Cứ xuất một dòng JSON cho mỗi ảnh
  và điền đúng thứ tấm đó cho thấy; app sẽ tự gộp các dòng cùng nhãn lại. Đừng đoán bù cho
  phần không có trong tấm bạn đang xem — cứ để null, tấm kia sẽ điền.
- "t" lấy đúng theo nhãn thời gian của ảnh được đưa, không tự tính lại.
- Trường không đọc được: null với số và chuỗi, [] với danh sách.
- Xuất mỗi ảnh một dòng, đúng thứ tự ảnh đã cho.

SAI — đừng viết như bốn kiểu dưới đây:
  Ảnh 1: {"t":"01:00", ...}        <- thêm chữ dẫn trước JSON
  {"t":"01:00","is_in_game":"false"}  <- true/false phải là boolean, KHÔNG bọc nháy
  {"t":"01:00","gold":"11"}        <- số phải là số, KHÔNG bọc nháy
  {"t":"1:5", ...}                 <- nhãn thời gian phải đủ hai chữ số, ví dụ 01:05
"""


def parse_timeline(raw: str):
    """Gom đầu ra của bước đọc ảnh thành một dòng thời gian sạch.

    Trả về (danh sách mốc trong game, thống kê). Thống kê phải cộng lại bằng số mục đầu
    vào: mốc dùng được + mốc ngoài game + dòng hỏng. Nếu một mốc biến mất mà không vào
    nhóm nào thì phần "Độ tin cậy" của báo cáo sẽ khai số đẹp trong khi dữ liệu đã mất.
    """
    rows, bad, outside = [], 0, 0
    for khoi in _tach_json(raw or ""):
        try:
            row = json.loads(khoi)
        except json.JSONDecodeError:
            bad += 1
            continue
        if not isinstance(row, dict):
            bad += 1
            continue
        rows.append(row)

    rows.sort(key=_giay_cua_moc)
    # Mỗi khung hình cho ra vài tấm ảnh (cột trái, dải dưới...), nên AI trả vài dòng cùng
    # một nhãn thời gian. Phải GỘP chúng lại: vứt bớt là mất đúng những trường chỉ có ở
    # một tấm — máu, lõi, hàng chờ nằm ở tấm cột trái.
    theo_moc, out = {}, []
    for row in rows:
        key = row.get("t")
        if not (isinstance(key, str) and key):   # mốc không có nhãn thì để riêng, đừng gộp bừa
            out.append(row)
            continue
        if key in theo_moc:
            _gop_vao(theo_moc[key], row)
        else:
            theo_moc[key] = row
            out.append(row)
    # Lọc mốc ngoài game SAU khi gộp. Một tấm có thể bị chấm là ngoài game trong khi tấm
    # kia của cùng khung hình vẫn đọc được bàn cờ, nên phải gộp xong mới quyết.
    trong_game = []
    for row in out:
        if _ngoai_game(row.get("is_in_game")):
            outside += 1
            continue
        trong_game.append(row)
    out = trong_game
    filled = sum(1 for r in out if r.get("gold") is not None)
    return out, {"moc": len(out), "ngoai_game": outside, "dong_hong": bad, "doc_duoc_vang": filled}


_BS = chr(92)          # ký tự gạch chéo ngược, viết thế này cho khỏi rối khi đọc


def _tach_json(raw: str):
    """Tách từng khối JSON khỏi đầu ra của AI.

    Chịu được ba kiểu lệch đã gặp thật: chữ dẫn trước JSON ("Ảnh 1: {...}"), JSON xuống
    dòng cho đẹp, và khối bọc trong dấu nháy ba. Quét theo dấu ngoặc nhọn nên không phụ
    thuộc việc mỗi dòng có đúng một JSON hay không.
    """
    ra, sau, do_sau, trong_chuoi, thoat = [], 0, 0, False, False
    for i, ch in enumerate(raw):
        if trong_chuoi:
            if thoat:
                thoat = False
            elif ch == _BS:
                thoat = True
            elif ch == '"':
                trong_chuoi = False
            continue
        if ch == '"':
            trong_chuoi = True
        elif ch == "{":
            if do_sau == 0:
                sau = i
            do_sau += 1
        elif ch == "}":
            if do_sau:
                do_sau -= 1
                if do_sau == 0:
                    ra.append(raw[sau:i + 1])
    if do_sau:                       # ngoặc mở mà không đóng: một mốc bị cắt cụt
        ra.append(raw[sau:])
    return ra


NGOAI_GAME = {False, 0, "false", "False", "FALSE", "no", "No", "0"}


def _ngoai_game(val) -> bool:
    """AI có thể trả false, "false", 0 hay "no". Tất cả đều nghĩa là ảnh ngoài game."""
    if isinstance(val, bool):
        return val is False
    if val is None:
        return False                 # thiếu trường thì coi như đang trong game
    if not isinstance(val, (str, int, float)):
        return False                 # [] hay {} không tra được trong set, và cũng không nói "ngoài game"
    return val in NGOAI_GAME


def _co_du_lieu(v) -> bool:
    """Giá trị này có mang thông tin không. None và danh sách rỗng thì không."""
    if v is None:
        return False
    if isinstance(v, (list, dict, str)) and len(v) == 0:
        return False
    return True


def _gop_vao(dich: dict, them: dict) -> None:
    """Gộp một dòng JSON vào dòng cùng mốc đã có. Giá trị đọc được luôn thắng giá trị rỗng."""
    for k, v in them.items():
        if k == "t":
            continue
        if k == "is_in_game":
            # Tấm toàn cảnh có thể bị chấm là ngoài game trong khi tấm cột trái vẫn thấy
            # bàn cờ. Chỉ cần MỘT tấm khẳng định đang trong game là mốc đó tính là trong game.
            # Tấm không nói gì (null) thì không được xoá lời khẳng định "ngoài game" của tấm kia.
            if v is not None and not _ngoai_game(v):
                dich[k] = v
            continue
        if not _co_du_lieu(v):
            continue
        if not _co_du_lieu(dich.get(k)):
            dich[k] = v


def _giay_cua_moc(row) -> int:
    """Giây của một mốc theo nhãn "t". Nhãn sai định dạng bị đẩy xuống cuối."""
    m = re.match(r"^(\d{1,3}):(\d{1,2})$", str(row.get("t") or "").strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 10 ** 6


def ghim_ten_loi(rows, danh_sach) -> dict:
    """Ghim mọi tên lõi trong dòng thời gian về tên thật trong cơ sở dữ liệu lõi.

    AI đọc thẻ trên màn hình nên hay ra tên tiếng Anh hoặc lệch vài ký tự. Sau bước này,
    tên nào còn lại đều là lõi CÓ THẬT của set; tên không khớp được thì thành None để báo
    cáo ghi "không đọc được" thay vì để một cái tên bịa lọt vào.

    Sửa trực tiếp trong `rows`. Trả về {"khop": n, "bo": m} để ghi vào phần Độ tin cậy.
    """
    if not danh_sach:
        return {"khop": 0, "bo": 0}
    khop = bo = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        for truong in ("augments", "augment_choices"):
            ds = row.get(truong)
            if not isinstance(ds, list):
                continue
            moi = []
            for x in ds:
                if x is None:
                    moi.append(None)
                    continue
                that = assets.match_augment(x, danh_sach) if isinstance(x, str) else None
                moi.append(that)
                if that:
                    khop += 1
                else:
                    bo += 1
            row[truong] = moi
    return {"khop": khop, "bo": bo}


class CoachError(Exception):
    pass


def _kill_tree(proc):
    """Diệt cả tiến trình con, nếu không ống dữ liệu vẫn mở và luồng đọc bị treo."""
    try:
        import psutil
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            child.kill()
    except Exception:  # noqa: BLE001 - không có psutil hoặc tiến trình đã thoát
        pass
    try:
        proc.kill()
    except OSError:
        pass


def _print_line(text):
    _print(str(text) + "\n")


def _print(text):
    sys.stdout.write(text)
    sys.stdout.flush()


# ---------- phần văn bản dùng chung cho cả hai chế độ ----------
def frame_seconds(path) -> int | None:
    """Giây của khung hình lấy từ tên file.

    Chịu được cả tên gốc "00704.jpg" lẫn tên ảnh đã cắt "00021_1_cot.jpg".
    Trả None nếu tên không mang nhãn thời gian.
    """
    m = re.match(r"^(\d+)", Path(path).stem)
    return int(m.group(1)) if m else None


def build_sheets(frames, log=None):
    """Cắt vùng giao diện cho từng khung hình.

    Trả về một DANH SÁCH CÁC CỤM: mỗi khung hình là một cụm gồm vài ảnh. Nhờ vậy khi chia
    việc cho các luồng, `frames_per_worker` vẫn đếm theo khung hình chứ không theo ảnh,
    nên số lượt gọi AI không đổi so với trước.

    Ảnh ghép nằm ở <trận>/reads/, vẫn giữ nguyên tên theo giây nên nhãn thời gian không đổi.
    Khung hình nào dựng hỏng thì dùng lại ảnh gốc, không làm hỏng cả lượt review.
    """
    if not frames:
        return frames
    session = frames[0].parent.parent
    out_dir = session / "reads"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Recorder ghi lại giây nào chụp lúc màn hình tối (vòng chọn lõi). Trận ghi bằng bản
    # cũ không có file này, khi đó coi mọi khung hình là lúc đang đánh thường.
    try:
        dark = set(json.loads((session / "dark_frames.json").read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError):
        dark = set()
    cum, made, n_loi, n_anh = [], 0, 0, 0
    for f in frames:
        try:
            chon_loi = (frame_seconds(f) in dark)
            ra = crops.build_all(f, out_dir, dang_chon_loi=chon_loi)
            if ra:
                cum.append(ra)
                made += 1
                n_loi += 1 if chon_loi else 0
                n_anh += len(ra)
            else:
                cum.append([f])
                n_anh += 1
        except Exception:  # noqa: BLE001 - lỗi cắt ảnh không được chặn cả lượt review
            cum.append([f])
            n_anh += 1
    if log and made:
        log(f"Đã cắt vùng giao diện cho {made} khung hình ({n_loi} ở vòng chọn lõi) "
            f"→ {n_anh} ảnh gửi đi.")
    return cum


def _canh_bao_thieu_khung(tk: dict) -> str:
    """Câu cảnh báo khi số mốc nhận về ít hơn số khung hình đã gửi.

    Không có câu này thì AI không biết mình bỏ sót ảnh, và báo cáo vẫn tự chấm
    "Độ tin: Cao" trên dữ liệu thiếu.
    """
    gui, thieu = tk.get("khung_gui"), tk.get("thieu")
    if not gui:
        return ""
    if not thieu:
        return f"Đã đọc đủ {gui} khung hình, không mất khung nào."
    return (f"CẢNH BÁO: đã gửi {gui} khung hình nhưng chỉ dựng được {tk['moc']} mốc và loại "
            f"{tk['ngoai_game']} mốc ngoài game, tức {thieu} khung hình KHÔNG được đọc. "
            "Phải ghi rõ điều này ở phần Độ tin cậy và hạ mức tin xuống tương ứng.")


def _mo_ta_khoang_cach(giay_cac_moc) -> str:
    """Câu mô tả khoảng cách thật giữa hai mốc, tính từ dữ liệu chứ không ghi cứng.

    Trước đây prompt ghi cứng "cách nhau khoảng 80 giây", trong khi đo trên trận thật là
    1 tới 5 phút. AI tính sai số round giữa hai mốc nên phần suy ra mua bán lệch theo.
    """
    if not giay_cac_moc or len(giay_cac_moc) < 2:
        return ""
    cach = sorted(b - a for a, b in zip(giay_cac_moc, giay_cac_moc[1:]))
    giua = cach[len(cach) // 2]

    def mmss(g):
        return f"{g // 60}:{g % 60:02d}"

    return (f"Hai mốc liền nhau cách nhau từ {mmss(cach[0])} tới {mmss(cach[-1])}, "
            f"thường là {mmss(giua)} — tức khoảng {max(1, round(giua / 35))} "
            f"tới {max(1, round(cach[-1] / 35))} round. Mọi suy luận mua bán chỉ là kết quả "
            "RÒNG của cả khoảng đó, không suy ra được thứ tự thao tác bên trong.\n")


def review_intro(cfg, match_info, meta_md, stats, n_frames, manh_yeu=None,
                 giay_cac_moc=None) -> str:
    rank = (match_info or {}).get("rank") or cfg["rank"]
    parts = [f"REVIEW TRẬN TFT. Rank người chơi: {rank}."]
    if match_info:
        parts.append("Dữ liệu chính thức từ Riot API (tin cậy hơn ảnh):\n```json\n"
                     + json.dumps(match_info, ensure_ascii=False, indent=1) + "\n```")
    else:
        parts.append("Không có dữ liệu Riot API. Hãy đọc hạng, đồ, lõi và vàng trực tiếp từ ảnh.")
    if stats and stats.get("games"):
        parts.append("Phong độ gần đây:\n```json\n" + json.dumps(stats, ensure_ascii=False) + "\n```")
    if manh_yeu and (manh_yeu.get("manh") or manh_yeu.get("yeu")):
        parts.append("ĐIỂM MẠNH VÀ ĐIỂM YẾU ĐÃ TÍNH (app tự tính từ số thật, đừng tính lại):\n"
                     "```json\n" + json.dumps(manh_yeu, ensure_ascii=False) + "\n```")
    parts.append("META HIỆN TẠI:\n" + (meta_md or "(chưa có)"))
    who = f"{cfg.get('riot_game_name','')}#{cfg.get('riot_tag_line','')}".strip("#")
    parts.append(
        f"Có {n_frames} MỐC THỜI GIAN, mỗi mốc gồm vài tấm ảnh cắt từ cùng một khung hình "
        "(cột trái, dải dưới, hoặc toàn cảnh và vùng giữa). Nhãn là thời điểm tính từ lúc vào trận.\n"
        + _mo_ta_khoang_cach(giay_cac_moc) +
        f"Người chơi cần chấm là {who or '(không rõ tên)'} — tìm đúng dòng này trên bảng máu bên phải.\n"
        "Ở mỗi mốc đọc: stage-round ở góc trên, vàng, level và thanh exp, máu các nhà, sân, hàng chờ, "
        "đồ đang cầm và đồ chờ ghép, cửa hàng. Từ đó dựng lại dòng thời gian rồi mới chấm.")
    return "\n\n".join(parts)


def meta_prompt() -> str:
    today = date.today().isoformat()
    return f"""Hôm nay là {today}. Tìm trên web meta Teamfight Tactics của patch hiện hành để giúp tôi leo rank.

Nguồn:
- Tier list và cách đánh: tftacademy.com (ưu tiên).
- Số liệu thực tế (tỉ lệ chọn, hạng trung bình, tỉ lệ Top 4, tỉ lệ Top 1): metatft.com, tactics.tools hoặc lolchess.gg, lấy ở rank cao (Kim Cương trở lên) nếu có.
Nếu hai nguồn lệch nhau thì ghi cả hai, không tự bịa số. Số nào không tìm được thì để null.

Ngôn ngữ: dùng TÊN TIẾNG VIỆT chính thức trong game cho trang bị, tộc hệ và lõi nâng cấp
(ví dụ: Găng Bảo Thạch, Mũ Thích Nghi, Triệu Hồi, Bá Chủ). Tên tướng giữ nguyên bản (Ahri, Maokai).
Nếu không chắc tên tiếng Việt, ghi "Tên tiếng Việt (Tên tiếng Anh)".

Chọn 14–18 đội hình đáng chơi (không chỉ bài top, gồm cả bài hạng B để người chơi biết khi nào nên tránh), kèm bảng trang bị và lõi đang mạnh. Trả về đúng MỘT khối ```json theo cấu trúc:
{{
 "patch": "15.x", "set": "tên set", "fetched_at": "{today}",
 "comps": [{{
   "name": "tên bài", "tier": "S|A|B", "style": "reroll 1/2/3 vàng | fast 8 | fast 9 | ...",
   "core_units": ["..."], "carry_items": {{"Tướng": ["đồ 1","đồ 2","đồ 3"]}},
   "augments": ["lõi mạnh nhất cho bài"], "emblems_or_special": "ấn/tướng đột biến/hero augment nếu có",
   "conditions": "điều kiện để đánh: đồ mở bài, lõi, trạng thái máu, khi nào không nên đánh",
   "roll_plan": "roll ở level nào, stage nào",
   "difficulty": "Dễ|Trung bình|Khó",
   "stats": {{"avg_place": null, "top4": null, "win": null, "pick_rate": null, "sample_rank": "Kim Cương+"}},
   "sources": ["url"]
 }}],
 "items": [{{
   "name": "tên đồ ghép", "tier": "S|A|B", "recipe": "Mảnh 1 + Mảnh 2",
   "role": "AD|AP|Tank|Util", "best_on": "kiểu tướng/bài nên cầm", "notes": "vì sao mạnh ở patch này",
   "stats": {{"avg_place": null}}
 }}],
 "augments": [{{
   "name": "tên lõi", "tier": "S|A|B", "level": "Bạc|Vàng|Ngọc",
   "kind": "kinh tế|sức mạnh|linh hoạt|tộc hệ", "best_for": "bài/kiểu chơi hợp nhất",
   "notes": "điều kiện để lõi này mạnh",
   "stats": {{"avg_place": null, "pick_rate": null}}
 }}],
 "general_notes": ["thay đổi quan trọng của patch, đồ/lõi đang quá mạnh"]
}}

Lấy 12–16 đồ ghép mạnh nhất và 22–28 lõi mạnh nhất của patch (đủ cả ba bậc Bạc, Vàng, Ngọc),
ưu tiên những thứ quyết định thắng thua.

Quy ước xếp tier, áp dụng thống nhất cho cả đội hình, trang bị và lõi:
- **S**: mạnh nhất patch, đánh được cả khi điều kiện không hoàn hảo. Tương đương hạng trung bình 3.80 trở xuống.
- **A**: mạnh và ổn định nhưng cần một điều kiện (một lõi, một món đồ lõi, hoặc không bị tranh). Hạng TB 3.81–4.10.
- **B**: khá, chỉ nên đánh khi mở bài đẩy vào hoặc sảnh trống. Hạng TB 4.11–4.40.
- **C**: yếu ở patch này, chỉ đánh khi bị ép. Hạng TB trên 4.40.
Nếu nguồn không cho tier, tự suy ra theo hạng trung bình; nếu không có cả hạng trung bình thì để null."""


def rank_prompt(rank, stats, meta_md) -> str:
    return f"""Người chơi đang ở rank: {rank}.
Phong độ thực tế 20 trận gần nhất (Riot API): {json.dumps(stats, ensure_ascii=False) if stats else "không có"}

META HIỆN TẠI:
{meta_md or "(chưa có)"}

Lập giáo án leo rank cá nhân hóa:
## 1. Chẩn đoán
Điểm yếu lớn nhất dựa trên số liệu (hạng trung bình, tỉ lệ Top 4, bài hay chơi và hiệu quả của từng bài).
## 2. Điều kiện cần để lên rank kế tiếp
Bảng: Kỹ năng | Tiêu chuẩn đo được | Hiện tại của bạn
## 3. Bộ bài leo rank
2 bài chính + 1 bài dự phòng lấy từ meta ở trên, phù hợp trình độ. Mỗi bài ghi: mở bài bằng gì, đồ lõi, lõi ưu tiên, khi nào roll.
## 4. Checklist từng stage (2-1, 3-2, 4-1, 4-2, 5-1)
## 5. Mục tiêu 20 trận tới (con số cụ thể)

Chỉ xuất Markdown, không thêm lời dẫn."""


AGENTS = (ROOT / "prompts" / "multi_agent_coach.md")


def advise_prompt(situation: str, data_blocks: dict) -> str:
    """Prompt cho hệ 4 agent: luật chung + dữ liệu thật + tình huống người chơi."""
    rules = AGENTS.read_text(encoding="utf-8") if AGENTS.exists() else ""
    blocks = "\n\n".join(f"### {name}\n```json\n{content}\n```"
                         for name, content in data_blocks.items())
    return (f"{rules}\n\n---\n\n# DỮ LIỆU THẬT CỦA APP\n\n{blocks}\n\n---\n\n"
            f"# TÌNH HUỐNG NGƯỜI CHƠI ĐƯA VÀO\n\n{situation}\n\n"
            "Chạy lần lượt Meta Analyst → Lineup Tactician → Scout, in kết quả từng agent gọn gàng, "
            "rồi kết bằng phần Head Coach đúng 4 mục. Chỉ xuất Markdown.")


def augment_block(augments) -> str:
    """Danh sách tên lõi hợp lệ của set, để AI khớp tên thay vì tự đặt."""
    if not augments:
        return ""
    names = [a["name"] for a in augments if a.get("name")]
    return ("\n\nDANH SÁCH LÕI HỢP LỆ CỦA SET (chỉ được dùng tên trong danh sách này, "
            f"không khớp thì ghi null):\n{' · '.join(names)}")


HANDBOOK_LAYOUT = """Bố cục bắt buộc, dùng tiếng Việt:

# Cẩm nang Dishsoap

## A. Nguyên tắc dùng được ở MỌI set
Đây là phần quan trọng nhất. Chỉ đưa vào đây những ý còn đúng khi Riot đổi set:
kinh tế, nhịp lên cấp, cách quyết định roll, cách đọc sảnh, cách chọn lõi theo tình thế,
cách ghép đồ, xếp vị trí, quản lý máu, cách chốt mục tiêu Top 4 hay Top 1.
Chia theo các mục con:
### A1. Kinh tế và nhịp độ
### A2. Roll và rolldown
### A3. Chọn lõi
### A4. Trang bị
### A5. Xếp vị trí và vi điều khiển
### A6. Đọc sảnh, tranh bài và xoay bài
### A7. Quản lý máu và chốt mục tiêu
### A8. Sai lầm Dishsoap hay chỉ ra

## B. Riêng set và patch hiện tại
Những ý chỉ đúng cho Set 18 hoặc một patch cụ thể. Ghi rõ tên tướng, lõi, patch.

## C. Những câu đáng nhớ
Tối đa 6 câu ngắn của anh ấy, mỗi câu dưới 20 từ, trong ngoặc kép, kèm tên video.

## D. Nguồn đã dùng
Danh sách video đã đọc.

Quy tắc viết:
- Mỗi ý một gạch đầu dòng, kèm ngưỡng số khi nguồn có nói (vàng, máu, level, stage, số bản sao).
- Nguồn nói định tính thì ghi là định tính, KHÔNG tự thêm số.
- Cuối mỗi ý ghi nguồn trong ngoặc: (tên video rút gọn).
- Tuyệt đối không bịa. Không chắc thì bỏ ý đó.
- Tên tướng giữ nguyên bản; trang bị, tộc hệ, lõi dùng tên tiếng Việt trong game nếu biết.
- Transcript là phụ đề tự động nên tên tướng hay bị nghe sai (Civer=Sivir, Casio=Cassiopeia,
  Vagar=Veigar, Malight=Malphite, Kale=Kayle, Orn=Ornn, Ari=Ahri). Luôn ghi tên CHÍNH THỨC.
- Cơ chế chỉ có ở set hiện tại (portal, charm, artifact, lõi cụ thể) KHÔNG được vào phần A.
- Không ghi luật số của game (vòng chọn lõi, thưởng chuỗi, XP, tỉ lệ ra tướng): app đã có
  bảng luật riêng, cẩm nang ghi lại sẽ lệch khi đổi patch."""


def handbook_batch_prompt(transcripts: str, part: int, total: int) -> str:
    """Rút ý từ một đợt transcript. Chưa cần bố cục đẹp, chỉ cần đúng và đủ."""
    return (f"Đây là đợt {part}/{total} transcript video của Dishsoap — tuyển thủ TFT hai lần vô địch "
            "thế giới. Đọc hết và rút ra các nguyên tắc chiến thuật anh ấy nói hoặc thể hiện.\n\n"
            "Với MỖI ý, viết một gạch đầu dòng theo mẫu:\n"
            "- [CHUNG] hoặc [SET] — nội dung nguyên tắc, kèm số nếu nguồn nói ra số — (tên video)\n\n"
            "[CHUNG] là ý còn đúng ở set khác. [SET] là ý gắn với tướng, lõi hay patch cụ thể.\n"
            "Gom theo 8 nhóm: kinh tế, roll, lõi, trang bị, vị trí, đọc sảnh và xoay bài, "
            "quản lý máu và mục tiêu, sai lầm hay gặp.\n"
            "Viết càng nhiều ý có giá trị càng tốt, nhưng cấm bịa. Không suy diễn ngoài transcript.\n\n"
            f"--- TRANSCRIPT ---\n{transcripts}")


def handbook_merge_prompt(parts: str) -> str:
    """Gộp các bản rút gọn thành cẩm nang cuối."""
    return ("Dưới đây là các bản ghi ý rút ra từ nhiều đợt transcript của Dishsoap. "
            "Hãy gộp thành MỘT cẩm nang hoàn chỉnh.\n\n"
            "Yêu cầu khi gộp:\n"
            "- Bỏ ý trùng, gộp các ý gần giống thành một ý rõ hơn.\n"
            "- Ý [CHUNG] đưa vào phần A, ý [SET] đưa vào phần B.\n"
            "- Giữ nguyên các con số và tên nguồn. Không thêm ý mới ngoài danh sách.\n"
            "- Sắp thứ tự trong mỗi mục: ý quan trọng và có số liệu lên trước.\n\n"
            f"{HANDBOOK_LAYOUT}\n\n--- CÁC BẢN GHI Ý ---\n{parts}")


def handbook_prompt(transcripts: str = "") -> str:
    """Dùng khi không có transcript: tra thẳng trên web."""
    today = date.today().isoformat()
    if transcripts:
        return handbook_batch_prompt(transcripts, 1, 1) + "\n\n" + HANDBOOK_LAYOUT
    return (f"Hôm nay {today}. Tra trên web tài liệu của Dishsoap (TFTAcademy, YouTube, podcast "
            f"TFT Study Hall, X @Dishsoaptft) rồi tổng hợp thành cẩm nang.\n\n{HANDBOOK_LAYOUT}")


def parse_meta_json(text: str) -> dict:
    blocks = re.findall(r"```json\s*(.*?)```", text, re.S)
    raw = blocks[-1] if blocks else text[text.find("{"): text.rfind("}") + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise CoachError(f"Không đọc được JSON meta ({e}). Chạy lại lệnh meta.")


# ---------- Chế độ 1: Claude Code CLI (dùng hạn mức gói thuê bao) ----------
class CliCoach:
    name = "Claude Code (gói thuê bao)"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.exe = shutil.which(cfg["claude_cli_path"])
        if not self.exe:
            raise CoachError(
                "Chưa cài Claude Code CLI. Mở PowerShell và chạy:\n"
                "    irm https://claude.ai/install.ps1 | iex\n"
                "Sau đó mở cửa sổ mới, chạy `claude` một lần để đăng nhập bằng tài khoản Pro/Max.")

    def _run(self, prompt: str, tools: str, cwd: Path | None = None, on_text=_print) -> str:
        cmd = [self.exe, "-p", "--output-format", "text"]
        if tools:
            cmd += ["--allowed-tools", tools]
        if self.cfg.get("cli_model"):
            cmd += ["--model", self.cfg["cli_model"]]
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, cwd=str(cwd) if cwd else None,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as e:
            raise CoachError(f"Không chạy được Claude Code CLI: {e}")

        proc.stdin.write(prompt)
        proc.stdin.close()

        # canh giờ ở luồng riêng: nếu chỉ chờ dòng mới thì CLI im lặng sẽ treo mãi
        timed_out = threading.Event()

        def watchdog():
            if not done.wait(self.cfg["cli_timeout_sec"]):
                timed_out.set()
                _kill_tree(proc)

        done = threading.Event()
        threading.Thread(target=watchdog, daemon=True).start()
        out = []
        try:
            for line in proc.stdout:
                out.append(line)
                on_text(line)
        finally:
            done.set()
        if timed_out.is_set():
            raise CoachError("Claude Code chạy quá lâu, đã dừng. Giảm max_frames_for_review rồi thử lại.")
        code = proc.wait()
        err = proc.stderr.read().strip()
        text = "".join(out).strip()
        if code != 0 or not text:
            # CLI thường in lý do ra stdout chứ không phải stderr, nên phải kèm cả hai
            detail = (err or text or "").strip()[-400:] or "không có thông báo"
            hint = ("\nThường là do chạm hạn mức gói thuê bao. Đợi hạn mức làm mới rồi "
                    "chạy lại review cho trận đó.") if "limit" in detail.lower() or not err else ""
            raise CoachError(f"Claude Code báo lỗi (mã {code}): {detail}{hint}")
        return text

    @staticmethod
    def _listing(frames):
        ra = []
        for f in frames:
            sec = frame_seconds(f)
            nhan = f"{sec // 60:02d}:{sec % 60:02d}" if sec is not None else "không rõ"
            ra.append(f"- Ảnh tại {nhan} → {f.resolve()}")
        return "\n".join(ra)

    def _extract(self, group, aug_list="") -> str:
        """Giai đoạn 1: đọc một nhóm ảnh, trả về dữ kiện dạng JSON từng dòng."""
        prompt = ("Bạn đọc ảnh chụp màn hình Teamfight Tactics.\n\n"
                  "Dùng công cụ Read để xem từng ảnh dưới đây:\n" + self._listing(group) +
                  "\n\n" + EXTRACT_FORMAT + aug_list)
        return self._run(prompt, "Read", cwd=group[0].parent.parent, on_text=lambda t: None)

    def review(self, frames: list[Path], match_info, meta_md, stats, augments=None,
               manh_yeu=None) -> str:
        cfg = self.cfg
        aug_list = augment_block(augments)
        per = max(1, int(cfg.get("frames_per_worker", 3)))
        workers = max(1, int(cfg.get("review_parallel", 6)))
        # mỗi phần tử của `cum` là các ảnh của MỘT khung hình
        cum = (build_sheets(frames, log=_print_line) if cfg.get("use_ui_crops", True)
               else [[f] for f in frames])
        giay_moc = [g for g in (frame_seconds(k[0]) for k in cum if k) if g is not None]

        if workers > 1 and len(cum) > per:
            # Giai đoạn 1: chia ảnh thành nhiều nhóm, đọc song song. Đây là phần tốn thời
            # gian nhất vì mỗi ảnh là một lượt gọi công cụ Read.
            khoi = [cum[i:i + per] for i in range(0, len(cum), per)]
            groups = [[anh for khung in k for anh in khung] for k in khoi]
            facts = [None] * len(groups)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(self._extract, g, aug_list): i for i, g in enumerate(groups)}
                for fut in concurrent.futures.as_completed(futures):
                    i = futures[fut]
                    try:
                        facts[i] = fut.result()
                    except CoachError as e:
                        facts[i] = f"(nhóm ảnh {i + 1} đọc lỗi: {e})"
            data = "\n".join(f or "" for f in facts)
            # Giai đoạn 2: chấm từ dòng thời gian đã lọc, không phải mở lại ảnh
            rows, tk = parse_timeline(data)
            # Đối chiếu với số khung hình thật sự đã gửi. AI bỏ qua ảnh thì không có
            # gì báo động, và báo cáo vẫn tự chấm "Độ tin: Cao" trên dữ liệu thiếu.
            tk["khung_gui"] = len(cum)
            tk["thieu"] = max(0, len(cum) - tk["moc"] - tk["ngoai_game"])
            # Ghim mọi tên lõi về tên thật trong cơ sở dữ liệu lõi của set. Sau bước này
            # báo cáo không thể chứa một tên lõi không tồn tại.
            tk.update(ghim_ten_loi(rows, augments))
            if rows:
                body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
                data_block = (
                    "CHUỖI JSON TRẠNG THÁI TRẬN theo mốc thời gian "
                    "(đã sắp theo thời gian, đã loại mốc ngoài game, null là không đọc được):\n"
                    f"```json\n{body}\n```\n"
                    f"Chất lượng đọc ảnh: {tk['moc']} mốc dùng được, "
                    f"{tk['ngoai_game']} mốc ngoài game đã loại, {tk['dong_hong']} dòng đọc hỏng, "
                    f"{tk.get('khop', 0)} tên lõi khớp được cơ sở dữ liệu và "
                    f"{tk.get('bo', 0)} tên bị bỏ vì không khớp lõi nào có thật. "
                    + _canh_bao_thieu_khung(tk))
            else:
                # không dựng được JSON thì vẫn chấm, nhưng phải nói rõ độ tin thấp
                data_block = ("KHÔNG dựng được JSON trạng thái. Dữ kiện thô đọc từ ảnh:\n"
                              f"```\n{data}\n```")
            prompt = (f"{SYSTEM}\n\n{review_intro(cfg, match_info, meta_md, stats, len(cum), manh_yeu, giay_moc)}\n\n"
                      f"{data_block}\n\n{REVIEW_FORMAT}")
            # Không cấp công cụ nào ở bước chấm: dữ liệu đã nằm trọn trong prompt dưới dạng
            # JSON, không còn ảnh nào cần mở. Cấp Read ở đây từng là mắt xích khiến nội dung
            # lấy từ web (qua meta.json) có thể sai khiến AI đọc file cấu hình.
            return self._run(prompt, "", cwd=frames[0].parent.parent)

        prompt = (f"{SYSTEM}\n\n{review_intro(cfg, match_info, meta_md, stats, len(cum), manh_yeu, giay_moc)}\n\n"
                  f"Dùng công cụ Read để xem TỪNG ảnh dưới đây theo đúng thứ tự trước khi viết báo cáo:\n"
                  f"{self._listing([a for k in cum for a in k])}{aug_list}\n\n{REVIEW_FORMAT}")
        return self._run(prompt, "Read", cwd=frames[0].parent.parent)

    def fetch_meta(self) -> dict:
        return parse_meta_json(self._run(f"{SYSTEM_BASE}\n\n{meta_prompt()}", "WebSearch,WebFetch"))

    def fetch_handbook(self, batches=None, on_step=None, cache_dir=None) -> str:
        """Đọc từng đợt transcript song song rồi gộp thành cẩm nang.

        Mỗi đợt xong được ghi ngay vào cache_dir, nên chạy đứt giữa chừng thì lần sau
        chạy tiếp từ đợt còn thiếu chứ không phải đọc lại từ đầu.
        """
        if not batches:
            return self._run(f"{SYSTEM_BASE}\n\n{handbook_prompt()}", "WebSearch,WebFetch")
        notes = [None] * len(batches)
        if cache_dir:
            cache_dir = Path(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            for i in range(len(batches)):
                f = cache_dir / f"batch_{i + 1}.md"
                if f.exists():
                    notes[i] = f.read_text(encoding="utf-8")
            if on_step and any(notes):
                on_step(sum(1 for n in notes if n), len(batches))
        todo = [i for i, n in enumerate(notes) if n is None]
        if todo:
            workers = min(3, len(todo))     # 3 đợt một lúc, tránh dồn hạn mức
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(self._run,
                                       handbook_batch_prompt(batches[i], i + 1, len(batches)),
                                       "Read", None, lambda t: None): i
                           for i in todo}
                for fut in concurrent.futures.as_completed(futures):
                    i = futures[fut]
                    try:
                        notes[i] = fut.result()
                        if cache_dir:
                            (cache_dir / f"batch_{i + 1}.md").write_text(notes[i], encoding="utf-8")
                    except CoachError as e:
                        notes[i] = f"(đợt {i + 1} lỗi: {e})"
                    if on_step:
                        on_step(sum(1 for n in notes if n), len(batches))
        joined = "\n\n".join(f"### Đợt {i + 1}\n{n}" for i, n in enumerate(notes) if n)
        return self._run(f"{SYSTEM_BASE}\n\n{handbook_merge_prompt(joined)}", "Read")

    def rank_plan(self, rank, stats, meta_md) -> str:
        return self._run(f"{SYSTEM}\n\n{rank_prompt(rank, stats, meta_md)}", "Read")

    def advise(self, situation, data_blocks) -> str:
        """Hệ 4 agent tư vấn một tình huống người dùng tự mô tả."""
        return self._run(f"{SYSTEM}\n\n{advise_prompt(situation, data_blocks)}", "Read")


# ---------- Chế độ 2: Claude API (tính tiền theo lượt dùng) ----------
class ApiCoach:
    name = "Claude API"

    def __init__(self, cfg: dict):
        import anthropic  # nạp muộn để chế độ CLI không cần thư viện này
        self.anthropic = anthropic
        self.cfg = cfg
        key = cfg["anthropic_api_key"] or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key.strip():
            raise CoachError("Chưa có Claude API key. Điền anthropic_api_key trong config.json "
                             "hoặc đặt biến môi trường ANTHROPIC_API_KEY.")
        self.client = anthropic.Anthropic(api_key=key)

    def _run(self, content, tools=None, effort="high", on_text=_print) -> str:
        anthropic = self.anthropic
        messages = [{"role": "user", "content": content}]
        parts = []
        for _ in range(8):  # pause_turn: công cụ web chạy lâu, cần gửi tiếp
            kwargs = dict(
                model=self.cfg["model"],
                max_tokens=64000,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": effort},
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default"},
            )
            if tools:
                kwargs["tools"] = tools
            try:
                with self.client.beta.messages.stream(**kwargs) as stream:
                    for text in stream.text_stream:
                        on_text(text)
                    msg = stream.get_final_message()
            except anthropic.AuthenticationError:
                raise CoachError("Claude API key sai hoặc chưa đặt (config.json hoặc biến ANTHROPIC_API_KEY).")
            except anthropic.RateLimitError:
                raise CoachError("Claude API đang giới hạn tốc độ. Đợi một phút rồi chạy lại.")
            except anthropic.APIConnectionError:
                raise CoachError("Không kết nối được Claude API. Kiểm tra mạng.")
            except anthropic.APIStatusError as e:
                raise CoachError(f"Claude API lỗi {e.status_code}: {e.message}")
            except TypeError as e:  # SDK không tìm thấy thông tin xác thực
                raise CoachError(f"Claude API chưa xác thực được: {e}")

            parts += [b.text for b in msg.content if b.type == "text"]
            if msg.stop_reason == "refusal":
                raise CoachError("Claude từ chối yêu cầu này.")
            if msg.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": msg.content})
                continue
            return "".join(parts)
        return "".join(parts)

    def review(self, frames: list[Path], match_info, meta_md, stats, augments=None,
               manh_yeu=None) -> str:
        if self.cfg.get("use_ui_crops", True):
            # build_sheets trả về theo cụm (mỗi khung hình một cụm), trải phẳng để gửi ảnh
            frames = [anh for cum in build_sheets(frames) for anh in cum]
        content = [{"type": "text", "text": review_intro(self.cfg, match_info, meta_md, stats, len(frames), manh_yeu)
                    + augment_block(augments)}]
        for f in frames:
            sec = int(f.stem)
            content.append({"type": "text", "text": f"Ảnh tại {sec // 60:02d}:{sec % 60:02d}"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                        "data": base64.standard_b64encode(f.read_bytes()).decode()}})
        content.append({"type": "text", "text": REVIEW_FORMAT})
        return self._run(content, effort=self.cfg.get("review_effort", "medium"))

    WEB_TOOLS = [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": 20},
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 20},
    ]

    def fetch_meta(self) -> dict:
        return parse_meta_json(self._run(meta_prompt(), tools=self.WEB_TOOLS, effort="medium"))

    def fetch_handbook(self, batches=None, on_step=None, cache_dir=None) -> str:
        if not batches:
            return self._run(handbook_prompt(), tools=self.WEB_TOOLS, effort="high")
        cache_dir = Path(cache_dir) if cache_dir else None
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
        notes = []
        for i, b in enumerate(batches):
            f = cache_dir / f"batch_{i + 1}.md" if cache_dir else None
            if f and f.exists():
                notes.append(f.read_text(encoding="utf-8"))
            else:
                notes.append(self._run(handbook_batch_prompt(b, i + 1, len(batches)), effort="medium"))
                if f:
                    f.write_text(notes[-1], encoding="utf-8")
            if on_step:
                on_step(i + 1, len(batches))
        joined = "\n\n".join(f"### Đợt {i + 1}\n{n}" for i, n in enumerate(notes))
        return self._run(handbook_merge_prompt(joined), effort="high")

    def rank_plan(self, rank, stats, meta_md) -> str:
        return self._run(rank_prompt(rank, stats, meta_md), effort="high")

    def advise(self, situation, data_blocks) -> str:
        return self._run(advise_prompt(situation, data_blocks), effort="high")


def Coach(cfg: dict):
    """Trả về backend theo cấu hình engine."""
    engine = cfg.get("engine", "claude_cli")
    if engine == "claude_cli":
        return CliCoach(cfg)
    if engine == "api":
        return ApiCoach(cfg)
    raise CoachError(f'engine không hợp lệ: "{engine}". Dùng "claude_cli" hoặc "api".')
