# Cẩm nang leo rank TFT

Luật số (thu nhập, lãi, thưởng chuỗi, XP, tỉ lệ ra tướng, vòng chọn lõi) nằm ở khối
"LUẬT GAME SET" phía trên, lấy từ `tft_rules.py`. File này KHÔNG ghi lại các con số đó để
khỏi lệch nhau.

| Chỉ số | Luật |
|---|---|
| Nhịp lên cấp chuẩn | Lv4 ở 2-1 · Lv5 ở 2-5 · Lv6 ở 3-2 · Lv7 ở 4-1 · Lv8 ở 4-2 hoặc 5-1 · Lv9 khi bài đã ổn định |
| Thời điểm roll | 3-2 (reroll hoặc cứu máu) · 4-1 (Lv7) · 4-2 (Lv8, bài 4 vàng) · 5-1 (Lv8/9) |

---

## Sắt → Đồng → Bạc: kỷ luật kinh tế

**Điều kiện cần**
- Luôn đặt đủ số tướng bằng level. Thiếu một tướng trên sân là tự bỏ phí sức mạnh.
- Không roll trước stage 3, trừ khi máu dưới 40.
- Thuộc cách ghép khoảng 10 món đồ phổ biến: 5 đồ tank, 5 đồ carry.

**Macro**
- Giữ 50 vàng là mặc định. Mỗi round không có lãi là mất 5 vàng, cả trận mất khoảng 60–80 vàng.
- Mua mọi bản sao của tướng đã có để ghép 2★ sớm. Tướng 2★ mạnh gần gấp đôi tướng 1★.
- Chọn một bài meta dễ đánh và chơi đi chơi lại cho đến khi thuộc.

**Micro**
- Tank đứng hàng trước, carry ở góc hàng sau.
- Đồ ghép lên tướng sẽ giữ lâu dài, không rải đồ lên tướng tạm.

**Lỗi hay gặp:** roll hết tiền ở stage 2, giữ 8 tướng lạ trên hàng chờ, lên cấp khi chỉ có 4 vàng.

---

## Vàng → Bạch Kim: chọn bài theo đồ

**Điều kiện cần**
- Mảnh đồ và tướng 2★ quyết định bài, không ép một đội hình yêu thích.
- Thuộc 3–4 bài meta: carry là ai, đồ chuẩn ra sao, tướng 2★ nào cần có.

**Macro**
- Chuỗi thắng và chuỗi thua đều có lợi. Thắng một thua một là kết quả tệ nhất.
- Stage 2: ghép ngay 2 món đồ mạnh (tank hoặc đồ tăng sát thương đòn đánh) để giữ máu.
- Chỉ roll ở 3-2 khi máu dưới 60 và bài yếu hẳn các nhà khác.

**Micro**
- Xem lại trận để biết mình thua vì đâu: tuyến đầu chết quá sớm, hay carry chưa kịp đánh.
- Đổi vị trí carry sang góc đối diện khi gặp bài có sát thủ.

**Lỗi hay gặp:** giữ mảnh đồ quá lâu, cố theo đuổi một bài khi sảnh có 3 người tranh cùng.

---

## Lục Bảo → Kim Cương: thời điểm roll

**Điều kiện cần**
- Có kế hoạch cho từng stage: roll ở mốc nào (3-2, 4-1, 4-2 hay 5-1) và lý do.
- Hiểu tỉ lệ ra tướng theo level (bảng ở khối luật). Tướng 4 vàng từ Lv7 lên Lv8 tăng gấp ba, nên bài 4 vàng gần như luôn lên 8 rồi mới roll.

**Macro**
- Máu là tài nguyên. Trước khi roll, tính xem còn chịu được bao nhiêu trận thua.
- Reroll tướng 1–3 vàng: roll ở level có tỉ lệ ra bậc giá đó cao nhất, giữ lãi, roll từng chút mỗi round.
- Bài dựa trên tướng 4 vàng: lên 8 với khoảng 50 vàng ở 4-2, roll đến khi có carry 2★.
- Lõi kinh tế chỉ đáng chọn khi sân của bạn đủ khỏe để giữ máu.

**Micro**
- Xem sảnh mỗi stage để biết ai đang tranh cùng tướng với mình.
- Đặt một tướng làm mồi để hút kỹ năng quan trọng của đối thủ.

**Lỗi hay gặp:** roll lưng chừng ở 4-1 rồi không lên nổi 8. Hãy all-in hẳn hoặc eco hẳn.

---

## Kim Cương → Cao Thủ: đọc sảnh và xoay bài

**Điều kiện cần**
- Đếm được số bản sao còn trong pool của tướng mình cần.
- Giữ 2 hướng đi đến 3-2, chốt hướng khi đã thấy lõi và đồ.
- Nhận ra lúc chỉ nên nhắm Top 4.

**Macro**
- Hai người tranh cùng bài: scout kỹ, thường một người sẽ yếu đi, đừng phản ứng thái quá. Ba người tranh cùng bài là án tử trừ khi bạn hơn hẳn về kinh tế — xoay trước 4-1.
- Tính EV theo vị trí xếp hạng: Top 4 ổn định cho LP đều, còn cố ép Top 1 làm tăng khả năng rơi xuống Top 5–8.
- Bài xoay dự phòng phải dùng lại được phần lớn đồ đã ghép.

**Micro**
- Xếp vị trí theo bài của đối thủ mạnh nhất mà bạn sắp gặp.
- Dời tướng cầm đồ tank để hứng sát thương từ hướng carry địch.

**Lỗi hay gặp:** tham Top 1 khi máu thấp, chọn lõi theo cảm tính thay vì theo đồ đang có.

---

## Cao Thủ → Đại Cao Thủ → Thách Đấu: tối ưu EV từng round

**Điều kiện cần**
- Gần như không còn lỗi kinh tế hay nhịp độ, sai lệch chỉ ở mức vài vàng.
- Biết cả các bài ngách ít người chơi.
- Có quy trình cố định mỗi round: xem sảnh → cửa hàng → exp → vị trí.

**Macro**
- Chấp nhận mất 3–5 máu để đổi lấy vàng hoặc đồ nếu nó tăng xác suất Top 4 ở late game.
- Chọn thời điểm roll khi các đối thủ đang yếu nhất trong sảnh.
- Chọn lõi theo phân bố hạng: sảnh mạnh thì ưu tiên lõi an toàn.

**Micro**
- Đoán trước đối thủ ở round sau để xếp vị trí đúng.
- Giữ tướng trên hàng chờ để chặn pool của đối thủ khi cần.

**Lỗi hay gặp:** tự tin quá mức vào bài quen, không thích nghi khi patch thay đổi.


---

# Khung soi trận theo từng mốc (dùng để chấm review)

Mỗi mốc dưới đây là một điểm kiểm tra bắt buộc. Khi review, phải soi đủ các mốc này theo đúng thứ tự.

## Stage 2 (2-1 → 2-7): Định hướng và quản lý chuỗi

**2-1 — Lõi 1 và chọn hướng đi**
- Đánh giá mảnh đồ khởi đầu và các cặp tướng đôi đang có.
- Quyết định ngay: đủ đồ và tướng khỏe thì đánh chuỗi thắng (lên cấp 4, ghép đồ ép thế trận); form yếu thì đánh chuỗi thua (ôm tiền, ưu tiên nhặt mảnh đồ chuẩn ở vòng đi chợ 2-4).
- Lỗi cần bắt: chọn lõi không ăn nhập với đồ và tướng đang có; không chốt hướng chuỗi.

**2-2 → 2-6 — Tối ưu kinh tế**
- Giữ chuỗi tuyệt đối. Thắng-thua xen kẽ là kịch bản phá tiền, phải bắt lỗi nặng.
- Đánh chuỗi thắng thì ghép sớm món vẫn dùng được ở mọi hướng đi đang cân nhắc (đồ tank cho tuyến đầu, đồ sát thương chung cho carry). Áo Choàng Lửa chỉ đáng khi đội đang thiếu giảm hồi máu.
- Bán tướng thừa trên hàng chờ để chạm mốc lãi 10 và 20 vàng sớm nhất có thể.

## Stage 3 (3-1 → 3-7): Ổn định bàn cờ và tích lũy

**3-2 — Lõi 2 và ngưỡng sức mạnh**
- Bắt buộc lên cấp 6.
- Kiểm tra máu: dưới 60 máu hoặc form quá yếu thì roll nhẹ 10–20 vàng nâng 2 sao giữ máu, không để tụt máu mất kiểm soát.

**3-5 → 3-7 — Phân nhánh chiến thuật**
- Scout cả sảnh để biết mức độ cạnh tranh bài.
- Bài reroll 1–2–3 tiền: chốt điểm dừng vàng để roll.
- Bài công thủ Fast 8: hạn chế tối đa roll lẻ tẻ, eco về mốc 50 vàng chuẩn bị xả.

## Stage 4 (4-1 → 4-7): Xoay bài quyết định

**4-1 hoặc 4-2 — Lõi 3 và rolldown cấp 8**
- Bước ngoặt của ván. Lên cấp 8 và xả tiền tìm bộ khung: 1 carry chính 4 vàng 2 sao và 1 tuyến đầu chắc (main tank 2 sao).
- Soi cả thao tác tay: mua bán nhanh, không để mất lượt roll.

**4-5 → 4-7 — Tối ưu trang bị và cân bằng chỉ số**
- Kiểm tra đồ nhặt từ quái ở vòng cuối.
- Bổ sung hiệu ứng bắt buộc cho late game: giảm giáp (Cung Xanh / Nỏ Sét), giảm hồi máu (Quỷ Thư / Vết Thương Sâu).
- Xếp vị trí chống sốc sát thương.

## Stage 5 → cuối trận: Tối đa trần sức mạnh và vi điều khiển

**Stage 5 — Xác định điều kiện thắng**
- Chốt mục tiêu: vào Top 4 an toàn hay tranh Top 1.
- Tranh Top 1: giữ tiền lên cấp 9 kẹp tướng 5 vàng đa dụng.
- Dưới 20 máu (ngưỡng một round chết): xả cạn tiền tìm nâng cấp 4 vàng 3 sao hoặc hoàn thiện dàn 2 sao.

**Stage 6+ — Đối đầu 1v1**
- Check bài đối thủ từng round.
- Đảo góc carry ở 3 giây cuối để né sát thủ hoặc kỹ năng diện rộng.
- Đặt tướng khống chế thẳng mặt carry đối phương.
- Check shop mua giấu bài (hắt tướng) chặn đối thủ lên 3 sao.


---

# Hiệu chỉnh khung mốc: bỏ cách nói tuyệt đối

Khi chấm, dùng bản hiệu chỉnh này thay cho cách diễn đạt tuyệt đối:

| Quy tắc gốc | Bản hiệu chỉnh khi chấm |
|---|---|
| Giữ chuỗi tuyệt đối | Giữ chuỗi trừ hai trường hợp: máu xuống dưới ngưỡng sống sót của stage đó, hoặc bàn đã tự khoẻ nên phá chuỗi không tốn gì |
| Bắt buộc lên 6 ở 3-2 | Bài fast 8 và bài công thủ: lên 6 ở 3-2. Bài reroll 1–2 tiền: đứng 5–6 và roll theo điểm dừng vàng đã chốt |
| Bán tướng để chạm mốc lãi | Chỉ bán tướng chắc chắn không nằm trong hai hướng đi đang cân nhắc. Không bao giờ bán bản sao của carry hoặc của tuyến đầu chính |
| Dưới 60 máu thì roll nhẹ | Roll khi máu thấp **và** nhìn thấy nâng cấp 2★ cụ thể đang cần. Máu thấp mà roll mù không sửa được gì thì là lỗi nặng hơn |
| 4-1 hoặc 4-2 gộp lõi 3 với rolldown | Tách hai việc: nhận lõi 3 ở vòng augment của set; rolldown khi đủ vàng, đúng ngưỡng máu và đúng level |

---

# Chín phần bổ sung

## 1. Máu là đơn vị tiền tệ — bảng thiệt hại theo stage
Một trận thua gây sát thương theo số tướng sống của đối thủ và stage. Ước lượng để tính "còn sống được mấy round":

| Stage | Mất mỗi trận thua |
|---|---|
| 2 | 2–6 máu |
| 3 | 5–10 máu |
| 4 | 8–15 máu |
| 5 | 12–20 máu |
| 6+ | 15–25 máu |

Cách dùng: trước khi quyết định eco hay roll, tính **số round còn chịu được = máu hiện tại ÷ thiệt hại trung bình của stage**. Dưới 3 round thì mọi lý lẽ về lãi suất đều vô nghĩa.

## 2. Đếm pool và mức độ tranh bài
- Mỗi tướng có số bản sao cố định trong pool chung của cả sảnh.
- Trước khi cam kết một carry, đếm: bản sao mình có + bản sao thấy trên sân người khác.
- Hai người cùng tranh một carry thì xác suất gom đủ giảm mạnh — scout xem ai yếu hơn. Ba người thì xoay bài trước 4-1, đừng đợi thua rồi mới xoay.
- Ghi rõ khi chấm: người chơi có scout trước khi cam kết không.

## 3. Khung chọn lõi (augment)
Chấm một lựa chọn lõi theo bốn câu hỏi, theo thứ tự:
1. Lõi này có dùng được **đồ đang có** không?
2. Có hợp **hướng bài** đang đi, hay bắt phải đổi hướng?
3. Đổi lại **sức mạnh ngay** hay **giá trị về sau**? Máu thấp thì luôn chọn sức mạnh ngay.
4. Lõi mạnh có đáng để **đổi cả hướng bài** không? Lõi cực mạnh thì bài phải theo lõi, không phải ngược lại.

Lỗi hay gặp cần bắt: chọn lõi kinh tế khi bàn đang yếu và máu đang tụt.

## 4. Chính sách ghép đồ
- Ghép ngay khi: máu dưới 60, hoặc đang cần chặn chuỗi thua, hoặc món đồ đó vẫn dùng được ở mọi hướng đi đang cân nhắc.
- Giữ mảnh khi: máu còn dày, đang giữ chuỗi, và còn thiếu đúng một mảnh cho đồ lõi của carry.
- Không bao giờ giữ quá 3 mảnh lẻ qua 3-5 — giá trị tích luỹ của đồ ghép sớm lớn hơn cái lợi của việc chờ.

## 5. Kinh tế lên cấp 8 và 9
- Lên 9 tốn 68 XP tính từ đầu cấp 8 (xem khối luật), tức khoảng 60 vàng sau khi trừ XP miễn phí — chỉ đáng khi bàn đã đủ khoẻ để không mất máu trong lúc gom.
- Quy tắc chấm: lên 9 khi **đã có carry 2★ và tuyến đầu ổn**; lên 9 khi bàn còn yếu là lỗi nặng.

## 6. Kỷ luật rolldown
- Trước khi roll, nói rõ **đang tìm gì**: tên tướng và số bản sao cần.
- Chốt **điểm dừng**: dừng ở 20–30 vàng nếu bàn đã ổn; roll cạn chỉ khi dưới ngưỡng một round chết.
- Roll từng 10 vàng rồi đánh giá lại, không nhấn liên tục đến hết tiền.
- Lỗi nặng: roll lưng chừng ở 4-1 rồi không còn tiền lên 8 ở 4-2.

## 7. Xếp vị trí: bốn việc phải làm mỗi round late game
1. Carry đứng góc xa nhất so với hướng sát thủ hoặc tướng lao vào.
2. Tách tướng khi đối thủ có kỹ năng diện rộng; dồn cụm khi cần bảo vệ carry bằng tuyến đầu.
3. Đặt tướng khống chế thẳng trục di chuyển của carry đối phương.
4. Đổi góc ở những giây cuối vòng chuẩn bị để đối thủ không kịp xếp ngược lại.

## 8. EV theo mục tiêu: Top 4 hay Top 1
- Hạng 4 và hạng 5 là ranh giới ăn hay mất LP. Chênh lệch giữa hai hạng này lớn hơn chênh lệch giữa hạng 1 và hạng 2.
- Khi đang chắc Top 4 mà bàn không đủ mạnh để tranh Top 1: giữ nguyên, không tiêu tài nguyên vào canh bạc.
- Chỉ ép Top 1 khi có ít nhất một trong ba: carry 3★, lõi cực mạnh, hoặc đối thủ còn lại đều yếu hơn rõ rệt.

## 9. Quy trình cố định mỗi round
Thứ tự bốn việc, làm đúng thứ tự này mỗi round:
1. **Scout** một vòng sảnh, ưu tiên đối thủ sắp gặp.
2. **Shop**: mua bản sao cần, cân nhắc hắt tướng chặn đối thủ lên 3★.
3. **Exp**: quyết định mua hay giữ theo kế hoạch level đã chốt.
4. **Vị trí**: chỉnh theo bài sắp gặp, chỉnh sau cùng ở những giây cuối.

---

# Tiêu chí KHÔNG chấm được bằng ảnh chụp

Khi review bằng ảnh chụp rời (khoảng cách thật giữa các mốc được ghi ở phần mở đầu review), những thứ sau **không có bằng chứng** — phải ghi "không có dữ liệu", không được suy đoán:
- Thao tác tay nhanh hay chậm, có mất lượt mua bán không.
- Có đảo góc carry ở ba giây cuối không (ảnh chỉ bắt được một thời điểm).
- Có scout sảnh không, trừ khi bắt được đúng khoảnh khắc đang xem bàn người khác.
- Có hắt tướng chặn đối thủ không.

Những mục này chỉ chấm được khi xem lại video đầy đủ trong `game.mp4`.
