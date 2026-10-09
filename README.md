# Hextech Coach (JC Coaching): Player Analytics & Match Review for TFT

**English summary.** A Windows desktop app that turns a Teamfight Tactics player's match history into analytics and post-game reviews.

- **Data pipeline:** pulls ranked match history from the Riot API, caches match records locally, and logs LP as a time series (the Riot API exposes no LP history).
- **Segmentation and benchmarking:** groups a player's games by main carry and trait, then compares each segment's average placement against population stats scraped from community sites (`research.py`, `stats_sites.py`). The result is a list of strategies to drop, keep or try.
- **Statistical guardrails:** no conclusion below 5 personal or 40 population games, because 2–3 games can swing average placement by ±1.3, which is more than the 0.7 decision threshold.
- **Diagnostics:** compares Top-4 rate against the 50% baseline and also reports placement standard deviation, early-elimination rate, and end-game level. Level is measured on Top-4 games only, so that a cause is not confused with a result. Every insight carries the number behind it.
- **Match review:** records the game window, crops and upscales the UI regions, reads each frame into strict JSON (null when unreadable), and cleans that into a timeline (`parse_timeline()` in `coach.py`). An LLM then grades the timeline into a 7-part report with SVG charts.
- **Tests:** `pytest tests/`

The app analyzes only after a match ends. It never reads game memory or gives in-game advice. Personal data, recordings and API keys stay local and are excluded from this repo. The detailed guide below is in Vietnamese.

---

# JC Coaching cho TFT

App chạy nền trên Windows: tự ghi hình từng trận TFT, khi trận kết thúc thì lấy số liệu từ Riot API, gửi các khung hình chính cho Claude phân tích rồi mở báo cáo review trên trình duyệt. Meta được tìm trên web (TFTAcademy kèm metatft/tactics.tools) và làm mới mỗi ngày.

App **không** đưa gợi ý trong lúc đang đấu, để tránh vi phạm chính sách công cụ bên thứ ba của Riot.

## Hai chế độ AI

Đặt `"engine"` trong `config.json`:

| engine | Chi phí | Cần gì |
|---|---|---|
| `"claude_cli"` (mặc định) | Nằm trong gói Claude Pro/Max, không tốn tiền API | Cài Claude Code CLI và đăng nhập một lần |
| `"api"` | Trả tiền theo lượt dùng — xem mục [Tiết kiệm hạn mức / chi phí](#tiết-kiệm-hạn-mức--chi-phí) để biết số token thật mỗi lượt review | Claude API key từ console.anthropic.com |

Cài Claude Code CLI (chỉ cần cho chế độ `claude_cli`), mở PowerShell và chạy:

```
irm https://claude.ai/install.ps1 | iex
```

Sau đó mở cửa sổ mới, gõ `claude` một lần để đăng nhập bằng tài khoản Pro/Max. Chế độ này dùng chung hạn mức với Claude Code, tính theo mỗi 5 giờ: review liên tục nhiều trận có thể chạm trần, khi đó app báo lỗi và bạn chạy lại lệnh `review` sau.

## Cài đặt (một lần)

1. Cài Python 3.11 trở lên, rồi chạy trong thư mục app:
   ```
   pip install -r requirements.txt
   ```
2. **AI:** cài Claude Code CLI như trên, hoặc đổi `"engine": "api"` rồi điền `anthropic_api_key`.
3. **Riot API key:** đăng nhập developer.riotgames.com và lấy *Development API Key*. Key này **hết hạn sau 24 giờ**, mỗi ngày phải lấy lại. Muốn dùng lâu dài thì đăng ký *Personal API Key* trên cùng trang.
4. Chạy `start.bat` lần đầu: app tạo `config.json` và mở Notepad để bạn điền:
   - `anthropic_api_key`, `riot_api_key`
   - `riot_game_name` và `riot_tag_line`: Riot ID của bạn, ví dụ `TenIngame` và `VN2`
   - Server khác VN: sửa `platform` (kr, na1, euw1...) và `match_region` (asia, americas, europe, sea)
5. Trong game, chọn chế độ hiển thị **Borderless (Không viền)**. Chế độ Fullscreen có thể khiến ảnh ghi bị đen.

## Cửa sổ JC Coaching

Bấm đúp shortcut **JC Coaching** trên Desktop: app mở trong một cửa sổ ứng dụng riêng (dùng WebView2 có sẵn của Windows), không có thanh địa chỉ và không còn cửa sổ đen. Cửa sổ không dùng thanh tiêu đề của Windows; thanh tiêu đề tối ở trên cùng là do app tự vẽ, kéo vào đó để di chuyển cửa sổ, kéo cạnh để đổi kích thước. Bấm dấu **✕** là thu xuống khay hệ thống, app vẫn ghi hình; muốn thoát hẳn thì chuột phải biểu tượng khay rồi chọn **Thoát hẳn**.

Bộ nhận diện nằm trong `assets/`: `jc.ico` dùng cho shortcut, thanh tác vụ và cửa sổ; `tray.png` là huy hiệu tròn nhỏ dùng cho khay hệ thống khi app chạy nền. Muốn đổi ảnh thì thay file gốc rồi tạo lại bộ này.

Giao diện có 4 tab:

| Tab | Nội dung |
|---|---|
| **Đội hình** | Tier list như TFTAcademy: hạng TB, Top 4, Top 1, tỉ lệ chọn. Bấm vào một bài để xem tướng lõi, đồ carry, lõi ưu tiên, điều kiện đánh và kế hoạch roll |
| **Trang bị** | Bảng đồ ghép đang mạnh: công thức, vai trò, hợp với kiểu tướng nào |
| **Lõi** | Bảng lõi nâng cấp: bậc Bạc/Vàng/Ngọc, loại, hợp với bài nào, điều kiện để mạnh |
| **Trận đấu** | Nhật ký app, danh sách trận đã ghi, hạng đạt được, nút mở báo cáo hoặc chạy review |

### Cách chấm trận

Review chạy hai bước, tách hẳn việc *đọc ảnh* khỏi việc *nhận xét*:

**Bước 0 — cắt và phóng to vùng giao diện** (`crops.py`). Đưa thẳng ảnh 1280×720 cho AI thì
biểu tượng lõi chỉ còn khoảng 20 px, không đọc nổi. Vị trí các bảng trong TFT cố định theo tỉ lệ
màn hình, nên app cắt sẵn từng vùng rồi phóng 1,6–3 lần và ghép tất cả vào **một** tấm ảnh:

| Vùng | Dùng để đọc |
|---|---|
| Cột trái | Lõi đã chọn, mảnh đồ, tộc hệ và số lượng |
| Bảng 8 nhà | Tên và máu từng nhà |
| Thanh trên | Stage-round |
| Thanh dưới | Cấp, thanh exp, vàng |
| Hàng chờ | Tướng và đồ đang cầm |
| Cửa hàng | 5 ô tướng đang bán |
| Giữa màn hình | Ba thẻ lõi khi đang ở vòng chọn lõi |

Ảnh ghép nằm ở `<trận>/reads/`, giữ nguyên tên theo giây nên nhãn thời gian không đổi, và vẫn chỉ
tốn **đúng một lượt đọc ảnh** cho mỗi khung hình. Tắt bằng `use_ui_crops: false`.

Hai việc đi kèm ở phần ghi hình: keyframe được lưu ở **độ phân giải gốc** của cửa sổ game (video
vẫn 720p), và khi màn hình tối đi — dấu hiệu của vòng chọn lõi — app hạ nhịp chụp từ 12 giây
xuống `keyframe_interval_dark_sec` (mặc định 2 giây). Màn chọn lõi chỉ hiện vài giây, nhịp 12 giây
gần như luôn chụp trượt, đó là lý do thật khiến phần lõi trước đây luôn trống.

**Bước 1 — đọc ảnh (Computer Vision).** Mỗi ảnh được đọc thành đúng một dòng JSON nghiêm ngặt:
stage, vàng, máu, level, exp, lõi, sân, hàng chờ, mảnh đồ, cửa hàng, máu các nhà. Trường nào
không nhìn rõ thì trả `null`, cấm đoán. Ảnh đang ở trình duyệt hay desktop bị gắn
`is_in_game: false`. Tên lõi chỉ được lấy từ danh sách lõi thật của set, không khớp thì `null`.

**Bước 2 — chấm.** `parse_timeline()` trong `coach.py` gom các dòng JSON lại, **loại thẳng các mốc
ngoài game**, sắp theo thời gian, bỏ mốc trùng, rồi mới đưa cho AI. Nhờ vậy AI chấm trên một
dòng thời gian sạch chứ không phải văn bản thô. Báo cáo có 7 phần:

| Phần | Nội dung |
|---|---|
| 1. Dòng thời gian | Bảng từng mốc kèm hành động **suy ra** từ chênh lệch hai mốc liền nhau (mua, bán, lên cấp, chạm mốc lãi) |
| 2. Giữ máu | Hết stage 2 mất bao nhiêu máu, mất ở đâu, cơ hội ghép đồ sớm bị bỏ lỡ |
| 3. Kinh tế | Bảng mốc lãi 10/20/30/40/50, gãy mốc ở đâu, thiệt hại quy ra vàng |
| 4. Sai lầm theo thời điểm | Tối đa 5 dòng: stage nào, lẽ ra làm gì, thực tế làm gì, thiệt hại bằng số, kèm ảnh trong game |
| 5. Hướng cải thiện | Ba bài tập đo được cho trận sau |
| 6. Điểm mạnh và điểm yếu | Dựa trên cả trận này lẫn hồ sơ các trận gần nhất, bắt buộc có số làm bằng chứng |
| 7. Độ tin cậy | Nguồn của từng hạng mục, số mốc bị loại, số trường `null` |

Giữa phần 5 và phần 6, app tự chèn hai biểu đồ dựng bằng SVG từ dữ liệu thật:
**cột phân bố hạng 1–8** của các trận gần nhất, và **đường LP theo thời gian**. Riot API không
trả lịch sử LP nên app tự ghi lại một mốc vào `data/lp_history.json` mỗi lần cập nhật hồ sơ —
đường LP cần ít nhất hai mốc mới vẽ được. Hai biểu đồ này cũng hiện ở tab **Cá nhân**.


Thanh trên cùng hiện trạng thái: *Đang chờ trận* hoặc *Đang ghi trận*, kèm nút **Cập nhật meta**. Dữ liệu tự làm mới mỗi 2,5 giây, không cần tải lại trang.

Giao diện chỉ chạy trên máy bạn (127.0.0.1), không mở ra internet. Đổi cổng bằng `ui_port`.

Shortcut chạy qua `launch.vbs` (vì Python bản Microsoft Store không khởi động được trực tiếp từ shortcut). Khi không có console, toàn bộ nhật ký được ghi vào `data/app.log`.

**Khi cần dò lỗi:** chạy `start.bat` để có cửa sổ đen kèm nhật ký, hoặc `python main.py watch --no-window` để chạy trong terminal. App cũng ghi toàn bộ nhật ký vào `data/app.log`, kể cả khi mở bằng shortcut.

## Quyền riêng tư

Đọc mục này trước khi cài cho người khác.

**App ghi gì**
- Quay **cửa sổ game** trong suốt trận, lưu `game.mp4` (720p) và ảnh chụp ở độ phân giải gốc.
- App bỏ qua khung hình khi cửa sổ game **không ở trước** (bạn alt-tab sang việc khác), nên
  nội dung ngoài game không bị chụp. Đặt `record_only_game_window: false` là tắt lớp bảo vệ này.

**App gửi gì ra ngoài**
| Gửi tới | Dữ liệu | Khi nào |
|---|---|---|
| Anthropic (Claude) | Ảnh chụp trận đã cắt vùng giao diện, và các số liệu trong báo cáo | Sau mỗi trận, lúc review |
| Riot Games API | Riot ID của bạn, để lấy kết quả trận và rank | Sau mỗi trận, và khi cập nhật hồ sơ |
| Data Dragon / Community Dragon | Không gửi gì, chỉ tải tên và ảnh tướng về | Lần đầu chạy |

Không có đích gửi nào khác.

**Dữ liệu lưu ở đâu, xoá thế nào**
- Tất cả nằm trong `data/`, chỉ trên máy bạn. Không có máy chủ nào của app.
- `data/sessions/<ngày-giờ>/` — video, ảnh, báo cáo của từng trận. Xoá thư mục trận là xoá sạch.
- `data/matches/` — cache trận lấy từ Riot API, **có chứa Riot ID của những người chơi khác**
  trong cùng trận. Xoá được bất cứ lúc nào, app tự tải lại khi cần.
- `data/profile.json`, `data/lp_history.json` — hồ sơ và lịch sử LP của bạn.
- **App không tự dọn dữ liệu cũ.** Mỗi trận chiếm khoảng 200–300 MB, nên nhớ xoá thủ công.

**Miễn trừ**

JC Coaching không phải sản phẩm của Riot Games và không được Riot Games bảo trợ hay xác nhận.
Teamfight Tactics và Riot Games là thương hiệu của Riot Games, Inc.

App chỉ phân tích **sau khi trận kết thúc**, không đọc bộ nhớ game, không chèn vào tiến trình
game, và không đưa gợi ý trong lúc bạn đang đấu.

## Sử dụng

| Lệnh | Tác dụng |
|---|---|
| Shortcut **JC Coaching** trên Desktop | Mở app trong cửa sổ riêng, tự ghi và review mọi trận |
| `start.bat` | Như trên nhưng kèm cửa sổ đen hiện nhật ký, dùng khi cần dò lỗi |
| `python main.py meta` | Cập nhật meta ngay và mở bảng đội hình |
| `python main.py stats` | Thống kê 20 trận gần nhất: hạng TB, Top 4, bài hay chơi, lõi hay chọn |
| `python main.py guide` | Giáo án leo rank cá nhân theo số liệu thật của bạn |
| `python main.py review data/sessions/<thư mục>` | Review lại một trận đã ghi |

Cẩm nang rank đầy đủ nằm ở `guide_vi.md`. Claude cũng dùng file này làm chuẩn khi chấm lỗi.

## Tiết kiệm hạn mức / chi phí

App đã bật sẵn các mức tiết kiệm sau, chỉnh trong `config.json`:

| Tham số | Mặc định | Tác dụng |
|---|---|---|
| `max_frames_with_match_data` | 18 | Khi đã có dữ liệu Riot, chỉ gửi 14 ảnh vì kết quả và đồ cuối trận đã có sẵn dạng chữ |
| `max_frames_for_review` | 20 | Số ảnh khi không có dữ liệu Riot |
| `keyframe_min_diff` | 4.0 | Bỏ qua ảnh gần trùng ảnh trước (màn hình chờ, lúc đứng yên) |
| `skip_review_if_top` | 0 | Đặt 2 để không review trận Top 1–2, chỉ review trận đánh hỏng |
| `meta_max_age_hours` | 72 | Chỉ tra meta 3 ngày một lần thay vì mỗi ngày |
| `review_effort` | medium | Chỉ áp dụng cho engine `api`: suy luận vừa phải, rẻ hơn mức cao |

Cách rẻ nhất vẫn là `engine: "claude_cli"`: không tốn tiền API, chỉ dùng hạn mức gói thuê bao. Trận nào bị bỏ qua vẫn còn nguyên ảnh, muốn review lúc nào cũng được bằng lệnh `review`.

## Dữ liệu và chi phí

- Mỗi trận nằm trong `data/sessions/<ngày-giờ>/`: `game.mp4` (720p, 8 fps, khoảng 150–250 MB mỗi trận), thư mục `keyframes/` (ảnh ở độ phân giải gốc, mỗi 12 giây và mỗi 2 giây khi đang chọn lõi, khoảng 40–60 MB mỗi trận), `reads/` (ảnh ghép đã phóng to vùng giao diện, xoá được bất cứ lúc nào vì app tự dựng lại), `review.html`.
- Tắt lưu video (chỉ giữ ảnh) để tiết kiệm ổ cứng: đặt `"keep_video": false`.
- Với `engine: "claude_cli"` app không gọi Claude API nên không phát sinh hoá đơn API; nó dùng **hạn mức gói Claude Pro/Max của chính bạn**, tính theo mỗi 5 giờ. App tự chạy `claude -p` sau mỗi trận, tức là dùng theo kiểu tự động — bạn nên tự đối chiếu điều khoản gói thuê bao của mình trước khi để nó chạy liên tục.
- Một lượt review gửi tối đa **20 khung hình**, mỗi khung hình thành **2 ảnh đã cắt vùng giao diện**, tức tối đa 40 ảnh. Chia thành **7 lượt gọi AI** (6 lượt đọc ảnh chạy song song + 1 lượt chấm). Đo trên một trận thật: khoảng **68.000 token đầu vào** và 5.000 token đầu ra, trong đó phần văn bản nền (`SYSTEM`) là 20.400 token và chỉ gửi **một lần**.
- Với `engine: "api"` thì nhân số token trên với bảng giá hiện hành của Anthropic. README này cố ý **không ghi con số USD cứng** vì bảng giá thay đổi theo thời gian.
- Giảm `max_frames_for_review` để rẻ hơn, đổi lại dòng thời gian thưa hơn.

## Xử lý sự cố

- **Không tự bắt đầu ghi:** kiểm tra tên tiến trình game trong Task Manager, sửa `game_process` nếu khác `League of Legends.exe`.
- **Báo "Chưa cài Claude Code CLI":** chạy lệnh cài ở trên, mở cửa sổ terminal mới rồi thử lại; nếu đã cài mà vẫn báo, điền đường dẫn đầy đủ vào `claude_cli_path`.
- **Báo lỗi 401/403 từ Riot:** key dev đã hết hạn, lấy key mới rồi dán vào `config.json`.
- **Review không có số liệu Riot:** API của Riot thường trễ 1–3 phút sau trận, app đợi tối đa 3 phút. Chạy lại lệnh `review` sau.
- App cũng ghi hình khi bạn chơi Liên Minh Huyền Thoại. Nếu đã cấu hình Riot API mà không tìm thấy trận TFT khớp, app sẽ bỏ qua review để không tốn tiền; bạn có thể xóa thư mục trận đó.
