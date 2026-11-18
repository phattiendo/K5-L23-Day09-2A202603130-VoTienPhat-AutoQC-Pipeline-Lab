# Báo cáo Day 09 — Võ Tiến Phát, 2A202603130

## 1. Kết luận trước

Pipeline ra quyết định **HOLD** (mã thoát `10`).

Có 224 ảnh thô trong `data/raw/`. Bước intake loại 21 ảnh vi phạm quy tắc cứng (ảnh hỏng, kích thước nhỏ, trùng lặp hoặc rò rỉ từ tập test/val), giữ lại 203 ảnh cho bản xuất nháp ở `submission/export/clean_v1/`. Bản xuất này có 749 box thuộc 4 lớp: 101 `car`, 575 `person`, 41 `truck`, 32 `bus`.

Lỗi bắt buộc (`ERROR`) đã xử lý hết, còn 0. Lý do vẫn Hold là ngân sách duyệt thủ công chỉ đủ cho 80 trong 125 ảnh của hàng đợi. Sau vòng duyệt, còn 38/203 ảnh (18.72%) mang cảnh báo chưa được kiểm tra, cao hơn ngưỡng `warn_ratio_hold = 10%`.

## 2. Lỗi và phân việc

Tổng cộng có 206 dòng phát hiện trên dữ liệu thô: 21 lỗi ảnh ở cửa vào và 185 lỗi/cảnh báo trên 203 ảnh được nhận vào (xem `02_error_list_v1.txt`).

| Mã lỗi | Số lượng | Ai sửa | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy (`intake` / `autofix`) | So MD5 từng byte, loại được mà không cần người xem. |
| `LEAK_TEST` | 5 ảnh | Máy (`intake` / `autofix`) | Trùng MD5 hoặc pHash với `test/` và `gold_val/`. Phải chặn để không rò rỉ dữ liệu đánh giá. |
| `BAD_SIZE` | 3 ảnh | Máy (`intake` / `autofix`) | Cạnh ngắn `< 250px` (180px, 226px), kiểm tra bằng code. |
| `DUP_IMAGE_NEAR` | 3 ảnh | Máy (`intake` / `autofix`) | `phash_dist <= 8` (`img_0076`, `img_0143`, `img_0223`). |
| `CORRUPT_IMAGE` | 2 ảnh | Máy (`intake` / `autofix`) | File không mở được (`img_0010`, `img_0136`). |
| `BOX_OUT_OF_IMAGE` | 8 dòng | Máy (`autofix`, `clip_box`) | Cắt tọa độ tràn biên về `[0, 1]`, lớp và tâm vật thể vẫn giữ nguyên. |
| `DUP_BOX` | 7 dòng | Máy (`autofix`, `drop_line`) | Hai box cùng lớp có `IoU > 0.9` trên một ảnh, xóa dòng thừa là an toàn. |
| `BAD_CLASS_ID` | 6 dòng | Máy (`autofix`, `drop_line`) | ID lớp ngoài `0..3` (93, -1, 7, 4). Không đoán được nhãn đúng nên xóa dòng. |
| `BOX_ZERO` | 4 dòng | Máy (`autofix`, `drop_line`) | Rộng hoặc cao bằng `0.000000`, box không có diện tích. |
| `BAD_FORMAT` | 3 dòng | Máy (`autofix`, `drop_line`) | Dòng có `nan` hoặc thiếu cột (4 thay vì 5), không khôi phục được tọa độ. |
| `BAD_CLASS_NAME` | 2 dòng (`data.yaml`) | Máy (`autofix`, `rename_classes`) | Đổi tên viết hoa (`Person`, `Bus`) về đúng `['car', 'person', 'truck', 'bus']`. |
| `MISSING_LABEL_FILE` | 6 ảnh | Người (`needs_label`) | Thiếu file `.txt` khác với ảnh nền rỗng, máy không tự bịa nhãn. Các ca này được đẩy lên đầu hàng đợi. |
| `POSSIBLE_MISSING` | 53 cảnh báo | Người (hàng đợi duyệt) | `yolo26l` thấy vật thể (`conf >= 0.6`) nhưng nhãn không có. Cần người xác nhận, vì có thể là vật ngoài phạm vi. |
| `POSSIBLE_LOOSE_BOX` | 28 cảnh báo | Người (hàng đợi duyệt) | Box lệch hoặc phình (`IoU < 0.5` so với model), cần chỉnh lại cho khít. |
| `POSSIBLE_FALSE_POS` | 25 cảnh báo | Người (hàng đợi duyệt) | Box không khớp dự đoán nào của model (`IoU < 0.3`). Có thể là nhãn thừa, cũng có thể model bỏ sót. |
| `POSSIBLE_WRONG_CLASS` | 18 cảnh báo | Người (hàng đợi duyệt) | Cùng vị trí (`IoU >= 0.5`) nhưng khác lớp (vd. `car` và `truck`, `person` và `car`). Cần người quyết định. |
| `EMPTY_LABEL` | 12 ảnh | Người (hàng đợi duyệt) | File `.txt` rỗng. Cần người phân biệt ảnh nền thật với ảnh bị xóa hết nhãn. |
| `BOX_TINY` / `BOX_HUGE` / `CLASS_RARE` | 6 / 3 / 4 dòng | Người (hàng đợi duyệt) | Cảnh báo thống kê và kích thước (`< 12px` hoặc `> 95%` diện tích ảnh), cần xem ngữ cảnh. |

### Thứ tự trong `05_review_queue.csv`

Điểm ưu tiên của mỗi ảnh bằng tổng trọng số các cảnh báo, cộng thêm độ tin cậy (`conf`) của model. Trọng số quan trọng nhất là `NEEDS_LABEL = 10` và `FIXED_DROP_LINE = 2`. Kết quả là 7 vị trí đầu gồm `img_0020` (11.524), vừa có lỗi cú pháp vừa bị nghi sai lớp hoặc thiếu nhãn, và cả 6 ảnh thiếu file nhãn (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`, mỗi ảnh 10.0).

Phía sau là các ảnh có nhiều lỗi ngữ nghĩa. `POSSIBLE_WRONG_CLASS` có trọng số 3, còn `POSSIBLE_MISSING` và `POSSIBLE_FALSE_POS` có trọng số 2.

Với ngân sách 80/125 ảnh, người duyệt xử lý được cả 6 ca thiếu nhãn và 67/124 cảnh báo `second_opinion`. Số dòng cảnh báo của `second_opinion` giảm từ 124 ở vòng 1 xuống 57 ở vòng 3.

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 8 | `DUP_IMAGE_NEAR`: 1.00 / 0.50 (F1 = 0.67) → 1.00 / 0.67 (F1 = 0.80). `DUP_IMAGE_EXACT` giữ 1.00 / 1.00. | Tăng lên 8 bắt thêm được ảnh trùng bị biến đổi (thu nhỏ, đổi sáng) mà Precision vẫn 1.00, nghĩa là không xóa nhầm ảnh nào. 8 nằm giữa dải ổn định 4..14, nên ít rủi ro hơn khi chạy trên lô thật. |
| `second_opinion.conf` | 0.25 | 0.6 | `WRONG_CLASS`: 0.56 / 0.83 (F1 = 0.67) → 0.62 / 0.83 (F1 = 0.71). `MISSING`: 0.50 / 1.00 (F1 = 0.67) → 0.57 / 1.00 (F1 = 0.73). | Nâng lên 0.6 làm giảm báo động giả (FP của `MISSING` từ 8 xuống 6, của `WRONG_CLASS` từ 4 xuống 3), còn Recall không đổi (1.00 và 0.83). Ít báo động giả hơn thì đỡ tốn ngân sách duyệt 80 ảnh. |

### Chỗ calibration dễ chọn nhầm

Trên tập `data/calib/` (39 ảnh), ở `phash_dist = 16` thì `DUP_IMAGE_NEAR` đạt F1 = 0.91 (Recall = 0.83). Nếu chỉ nhìn F1 thì dễ chọn 16.

Nhưng sang `phash_dist = 20`, Recall của `DUP_IMAGE_EXACT` rơi từ 1.00 xuống 0.33. Ngưỡng quá lỏng làm gộp nhầm cả ảnh gốc, và chuỗi đối chiếu `seen` bị lệch theo.

Trên lô thật `raw/` (224 ảnh), `phash_dist = 8` chỉ loại 3 ảnh `DUP_IMAGE_NEAR`:
- `img_0076` trùng `img_0042` (phash = 0)
- `img_0143` trùng `img_0037` (phash = 0)
- `img_0223` trùng `img_0077` (phash = 6)

Cả ba đều hợp lý, và không có ảnh đường phố nào chỉ giống nhau về bố cục bị loại oan.

## 4. Cửa chặn và những gì pipeline không bắt được

### (a) Thử cửa chặn với `--budget 0`

Lệnh chạy: `python3 -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`

Không có người duyệt nên 6 ảnh `MISSING_LABEL_FILE` không được xử lý, và sau 3 vòng QC vẫn còn 6 lỗi `ERROR`. `gate.py` ra quyết định `REWORK` với lý do "Còn 6 lỗi bắt buộc (severity ERROR) chưa được xử lý", mã thoát `EXIT_CODE=20`, và không xuất dataset. `ls -la work/exp_nb` báo `No such file or directory`.

Vậy trong lần chạy này, gate chặn đúng: dữ liệu còn lỗi bắt buộc thì không được xuất ra để huấn luyện.

### (b) Những gì pipeline bỏ sót

Thứ nhất là box hơi lỏng hoặc vật thể mà cả model lớn cũng bỏ sót. Khi soi ảnh gốc bằng `viz_labels.py` (như `img_0001.jpg`, `img_0030.jpg`), các ca lệch nặng được bắt tốt, nhưng những box nhãn chỉ phình nhẹ mà vẫn giữ mức trùng khớp `IoU` khoảng 0.50 đến 0.65 (cao hơn ngưỡng `iou_loose = 0.5`) thì `second_opinion` không báo gì. Tương tự, người đi bộ ở xa hoặc bị che khuất khiến `yolo26l` dự đoán dưới ngưỡng `conf = 0.6` cũng sẽ lọt qua.

Thứ hai là ảnh trùng bị biến đổi hình học mạnh (xoay, cắt sâu hơn 50%, lật ngang). `imagehash.phash` nhạy với thay đổi bố cục lớn; trong tập `calib` (với `phash_dist = 8`), 2/6 ảnh `DUP_IMAGE_NEAR` bị biến đổi mạnh vẫn lọt qua (Recall = 0.67). Trên `raw/`, ảnh bị crop mạnh từ một ảnh gốc cũng sẽ không bị `duplicates.py` bắt.

Thứ ba là nhầm lớp giữa các loại xe có hình dáng gần nhau (`car` và `truck` ở góc hẹp). Nếu cả nhãn gốc lẫn `yolo26l` cùng nhận sai một chiếc xe bán tải hoặc xe van, hai bên sẽ trùng nhau và `second_opinion` không sinh cảnh báo `POSSIBLE_WRONG_CLASS`.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

Thực nghiệm huấn luyện mô hình `yolo26n` trong `20 epoch` với `2 seed` trên Google Colab (T4 GPU):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 203 | 2 | 0.699 ± 0.025 | 0.486 ± 0.013 | 0.796 ± 0.050 | 0.596 ± 0.049 |

Chênh mAP50 (clean − raw) = **-0.027**.

**Nhận xét và phân tích kết quả:**
- **Đánh giá trung thực theo độ lệch chuẩn:** Độ chênh `mAP50` giữa `clean` và `raw` là `-0.027`, gần như ngang bằng với độ lệch chuẩn giữa các seed của biến thể `clean` (`± 0.025`, tức `|ΔmAP50| ≈ 1.08 × SD`). Với chỉ 2 seed và 20 epoch, mức chênh này nằm sát ngưỡng nhiễu ngẫu nhiên nên chưa thể kết luận bản `clean` kém hơn về năng lực tổng quát hóa; đáng chú ý là **Precision của `clean` tăng từ `0.764` lên `0.796` (+0.032)** nhờ loại bỏ được các box nhiễu và gán nhầm lớp.
- **Ba giả thuyết giải thích hiện tượng `raw` có mAP50 cao hơn và cách kiểm chứng:**
  1. **Rò rỉ dữ liệu test trong `raw` (`LEAK_TEST`):** Tập `raw` (224 ảnh) chứa **5 ảnh trùng trực tiếp với tập `test/`** (`img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`), làm mô hình ghi nhớ mẫu kiểm tra và kéo `mAP50` tăng giả tạo. *Cách kiểm:* Đánh giá lại cả hai checkpoint trên tập `test` đã loại bỏ 5 ảnh trùng này để đo năng lực thực chất.
  2. **Bản xuất `clean_v1` đang ở trạng thái `HOLD` (còn sót nhãn thiếu):** Do ngân sách duyệt chỉ đạt 80/125 ảnh, trong `clean_v1` vẫn còn 38 ảnh mang cảnh báo chưa xử lý (gồm 13 ca `POSSIBLE_MISSING` chưa được bổ sung box), khiến mô hình học thiếu đối tượng và làm `Recall` giảm từ `0.649` xuống `0.596`. *Cách kiểm:* Duyệt nốt 38 ảnh tồn đọng để đạt trạng thái `Release` rồi huấn luyện lại.
  3. **Quy mô tập train giảm (`203` vs `224` ảnh) và tập `test` nhỏ (`100` ảnh):** Số lượng mẫu train ít hơn 9.4% trong thời gian ngắn (20 epoch) cùng kích thước tập test nhỏ (100 ảnh) khiến dao động vài box dự đoán đã làm lệch mAP50 vài phần trăm. *Cách kiểm:* Tăng số seed lên 3–5 và kéo dài lên 50 epoch để giảm phương sai đánh giá.

## 6. Quyết định và ghi chú AI

### (a) Quyết định cuối và điều kiện để chuyển sang Release

Quyết định hiện tại là **HOLD**. Bản xuất nháp ở `submission/export/clean_v1/` chỉ dùng thử nội bộ, không phát hành chính thức.

Muốn chuyển sang Release, cần thêm ngân sách duyệt cho 38 ảnh còn cảnh báo trong `07_error_list_v3.txt`, để tỉ lệ ảnh chưa duyệt giảm từ 18.72% xuống dưới 10% (tối đa 20/203 ảnh). Nên duyệt trước 3 ca `POSSIBLE_WRONG_CLASS` còn lại (`img_0078`, `img_0083`, `img_0220`) rồi đến 13 ca `POSSIBLE_MISSING`.

### (b) Ghi chú sử dụng AI

- Prompt chính: Nhờ AI gợi ý cấu trúc xử lý 4 module `label_format.py`, `gate.py`, `autofix.py`, `second_opinion.py` theo docstring và các ca biên mô tả trong `GUIDE.md` và `pipeline/common.py`.
- Cách kiểm tra code AI: Chạy `python -m pytest -q` (79/79 passed), đối chiếu từng dòng trong `03_fixes.csv`, và mở xem ảnh gốc qua `scripts/viz_labels.py` (`img_0001.jpg`, `img_0030.jpg`).
- Một lần AI viết sai: Ban đầu logic `autofix.py` chưa ưu tiên `drop_line` trước `clip_box` khi một dòng vừa tràn biên vừa trùng lặp, làm ghi thừa log chỉnh sửa; tôi chạy `pytest tests/test_autofix.py -q`, phát hiện lỗi ở ca biên này và sửa lại thứ tự lọc trước khi chạy lại test.
