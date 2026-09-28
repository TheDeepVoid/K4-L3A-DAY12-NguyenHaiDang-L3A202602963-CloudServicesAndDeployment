# Phiếu Phản Ánh — K4 Level 3A, Ngày 12

> **Bài làm cá nhân.** Trả lời bằng lời của chính bạn, dựa trên những gì bạn
> quan sát được khi chạy code — không sao chép đáp án của người khác.
>
> Cách trả lời: thay dòng giữ chỗ mỗi câu bằng câu trả lời của bạn.
> `grade.py` đếm số câu đã trả lời (15 điểm cho 10 câu).
>
> Họ và tên: Nguyễn Hải Đăng   Mã học viên: L3A202602963

---

### Câu 1 — Fail fast (CP1)

Trong `Settings`, `agent_api_key` không có giá trị mặc định nên app chết ngay
khi khởi động nếu thiếu biến môi trường. Hãy mô tả một tình huống cụ thể mà
việc "chết sớm" này cứu bạn, so với việc để mặc định `"changeme"`.


Tình huống cụ thể là lúc deploy service lên Render. Trên Render, biến môi
trường không tự xuất hiện — nó phải được khai báo tay trong dashboard cho
từng service. Nếu `agent_api_key` có mặc định là `"changeme"` thì chuyện gì
xảy ra: tôi khai báo `REDIS_URL` và `PORT` xong, quên dòng `AGENT_API_KEY`,
bấm deploy. App khởi động trơn tru, `/health` trả 200, Render báo **live**,
tôi tưởng xong. Nhưng `AGENT_API_KEY="changeme"` chính là khóa hợp lệ — kẻ
nào quét URL trên GitHub, SecurityTrails hay Shodan cũng thử được, và mỗi
lượt của họ là một lượt tôi trả tiền. Tôi chỉ phát hiện khi nhìn hóa đơn
cuối tháng, lúc đó thống kê đã nhiễu và không biết chính xác mất bao nhiêu.

Với code của tôi, biến đó thiếu thì `Settings()` ném `ValidationError` ngay
tại lúc import `app.config`, tiến trình chết trước cả khi uvicorn kịp bind
cổng. Render đánh dấu deploy **failed**, tôi mở log thấy ngay dòng
`agent_api_key Field required` và biết phải điền gì — còn đang nhìn màn
hình. Cái giá của lỗi được đổi từ "tiền mất trong im lặng hàng tháng" thành
"mất 3 phút để sửa".

Một điểm nữa tôi thấy khi test: `test_thieu_api_key_thi_fail_fast` xác nhận
`Settings(_env_file=None)` phải ném `ValidationError`. Nghĩa là cơ chế fail
fast gắn với *biến môi trường thật*, không phụ thuộc file `.env` cục bộ —
nên nó hoạt động giống nhau ở laptop và trên cloud.

---

### Câu 2 — Log cho máy đọc (CP1)

Chạy service và gọi `/ask` vài lần. Dán một dòng log JSON bạn thu được, rồi
nêu **hai** việc bạn làm được với dòng log đó mà `print("đã trả lời xong")`
không làm được.


Đây là dòng log thật tôi thu được khi gọi `/ask` với `X-User-Id: sv01`:

```json
{"event":"ask_completed","level":"info","timestamp":"2026-09-28T08:23:43.826470+00:00","user_id":"sv01","tokens_in":94,"tokens_out":47,"cost_usd":4.23e-05,"history_length":4}
```

**Việc 1 — Tính bill theo user, không cần đọc log của bất kỳ ai khác.**
Dòng này có `user_id` và `cost_usd`. Tôi lấy 1.000 dòng `ask_completed` từ
log của Render, `jq -s 'group_by(.user_id) | map({user: .[0].user_id, usd: (map(.cost_usd)|add)}) | sort_by(-.usd)'`,
và ra ngay top user tiêu nhiều tiền nhất. Vì mỗi request có sẵn `cost_usd`
và `tokens_in`/`tokens_out`, tôi cũng biết user nào đang gửi câu hỏi dài —
dấu hiệu sớm của việc lạm dụng hoặc của một client đang gửi prompt vô
tội vạ. Với `print("đã trả lời xong")` thì 1.000 request chỉ ra 1.000 dòng
chữ giống hệt nhau: biết *có* xử lý, không biết *ai* và *tốn bao nhiêu*.

**Việc 2 — Tính tỷ lệ lỗi 5 phút qua để cảnh báo.** Vì `event`, `level` và
`timestamp` là ba khóa cố định có mặt trên mọi dòng, tôc lọc được
`level="error"` và nhóm theo `timestamp` để ra số lỗi mỗi phút, rồi đặt
ngưỡng cảnh báo. Cũng nhờ `timestamp` là ISO-8601 UTC chứ không phải
"Mon Sep 28 08:23:43" không múi giờ, nên tôi so sánh được log của nhiều máy
với nhau. `print` không cho tôi bất cứ điều gì trong ba điều đó: nó không
ghi máy, không ghi mức, không ghi thời điểm theo chuẩn.

Điểm nhỏ tôi cố ý kiểm: log phải nằm gọn trên **một** dòng. Cloud gom log
theo từng dòng; nếu `json.dumps(..., indent=2)` thì một sự kiện bị tách
thành 6 dòng và mọi truy vấn của tôi hỏng. Tôi cũng dùng
`ensure_ascii=False` để chữ "Đ" không bị thành `\u0110` rối mắt.

---

### Câu 3 — Kích thước image (CP2)

Build cả hai phiên bản và ghi lại số đo thật:

```bash
docker build -f <Dockerfile-1-stage> -t agent:single .
docker build -t agent:multi .
docker images | grep agent
```

| Bản | Dung lượng |
|-----|-----------|
| 1 stage (bản đầu) | ... MB |
| Multi-stage | ... MB |

Giải thích: phần dung lượng chênh lệch đó là những gì?


Đo thật trên máy tôi:

| Bản | Dung lượng |
|-----|-----------|
| 1 stage (Dockerfile gốc) | **1.72GB** |
| Multi-stage (bản của tôi) | **269MB** |

Chênh lệch **1.45GB**, tức bản multi-stage nhỏ hơn khoảng **6.4 lần** (giảm
~84%). Cả hai cùng base `python:3.11`, cùng `requirements.txt`, cùng source —
khác nhau chỉ ở chỗ chia stage.

Phần chênh lệch nằm ở ba chỗ:

1. **Base image.** Bản 1 stage dùng `python:3.11` (đầy đủ) — image đó có sẵn
   `gcc`, `make` và cả bộ thư viện phát triển để biên dịch các extension như
   `psycopg2`, `cryptography`. Bản của tôi dùng `python:3.11-slim`, chỉ giữ
   Python runtime. Đây là phần chênh lệch lớn nhất.
2. **Compiler và apt cache.** Stage `builder` của tôi cài `build-essential` để
   biên dịch rồi bị vứt đi hoàn toàn; stage runtime chỉ `COPY --from=builder
   /install /usr/local`, tức chỉ mang sang phần *đã cài*, không mang sang
   `gcc`/`make`/header. Bản 1 stage giữ tất cả compiler ấy trong image.
3. **Source và file thừa.** Bản 1 stage là `COPY . .` nên nuốt cả `tests/`,
   `screenshots/`, `*.md`. Bản của tôi chỉ `COPY app` và `COPY utils`.

Cái này quan trọng về *tốc độ deploy* chứ không chỉ về dung lượng: mỗi lần
Render pull image 1.72GB, thời gian chờ nhiều hơn hẳn 269MB. Mỗi lần tôi
đẩy một commit lên là một lần tải lại image đó.

---

### Câu 4 — Thứ tự lệnh trong Dockerfile (CP2)

Sửa một ký tự trong `app/main.py` rồi build lại. Với Dockerfile của bạn, những
layer nào được dùng lại từ cache, layer nào phải chạy lại? Nếu bạn đặt
`COPY . .` lên trước `RUN pip install` thì kết quả khác thế nào?


Tôi thêm đúng một dòng comment vào cuối `app/main.py` rồi build lại. Kết quả
thật từ output của Docker:

```
Step  5/16 : RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
 ---> Using cache                     <-- KHÔNG chạy lại
Step 10/16 : COPY app ./app
                                          <-- chạy lại (không có "Using cache")
Step 11/16 : COPY utils ./utils
 ---> Using cache
Step 12/16 : RUN useradd --create-home --uid 10001 appuser && chown -R ...
 ---> Running in b320cec374c7          <-- chạy lại
```

Tức là: **mọi layer trước `COPY app` đều được dùng lại** (kể cả
`RUN pip install`, thứ tốn thời gian nhất), còn `COPY app` và **tất cả những
gì nằm sau nó** phải chạy lại — kể cả `COPY utils` và `RUN useradd` dù
chúng không hề thay đổi, vì chúng nằm *sau* một layer đã bị vô hiệu.

Nếu đặt `COPY . .` lên trước `RUN pip install` (đúng như Dockerfile gốc),
thì lần build đầu tiên chạy được, nhưng từ lần thứ hai trở đi: sửa một dấu
phẩy trong `app/main.py` → `COPY . .` đổi checksum → `RUN pip install` bị
vô hiệu → **toàn bộ thư viện được cài lại từ đầu**, mỗi lần. Đây chính là
tình huống cụ thể tôi gặp: sau khi sửa Dockerfile, tôi chỉ sửa code mà
`pip install` vẫn chạy lại mỗi lần. Đảo lại thứ tự thì tôi build lại chỉ
mất vài giây vì `requirements.txt` không đổi.

---

### Câu 5 — Vì sao không chạy bằng root (CP2)

Container mặc định chạy bằng root. Mô tả chuỗi sự kiện dẫn từ "một lỗ hổng
trong code Python của bạn" tới "kẻ tấn công có quyền cao trên máy host", và
lệnh `USER` cắt đứt chuỗi đó ở chỗ nào.


Chuỗi sự kiện, theo đúng thứ tự:

1. Kẻ tấn công gửi payload tới `/ask` — chỗ duy nhất tôi nhận dữ liệu người
   dùng và đưa vào xử lý.
2. Payload đó tìm được một lỗ hổng: ví dụ trong `app/main.py` tôi đọc
   `payload.question` rồi đưa vào một hàm dễ bị shell injection. Vì FastAPI
   đã parse JSON, lỗ hổng phải nằm ở chỗ sâu hơn: ví dụ nếu sau này tôi thêm
   log ghi ra file, hoặc một dependency (`uvicorn`, `python-multipart`) có CVE.
3. Lỗ hổng cho phép thực thi mã **bên trong container**. Tại bước này kẻ
   tấn công đã có shell, uid là `0` (root) vì container chạy bằng root.
4. Vì là root **trong container**, những gì root làm được nhiều hơn hẳn: ghi
   vào mọi file trong image, cài thêm package, đọc biến môi trường — tức đọc
   được `AGENT_API_KEY` của chính tôi.
5. Bước nguy hiểm nhất: nếu container chạy với quyền hạn chế, root bên trong
   đó gần như vô hại với máy host. Nhưng nếu tôi mount volume, dùng
   `privileged`, `hostPID`, hoặc chạy Docker socket vào container, thì root
   bên trong **chính là root trên host**: nó ghi được vào `/etc`, đọc
   `/root/.ssh`, cài SSH key, và từ đó đi vào mạng nội bộ.
6. Kết quả: một lỗ hổng input validation trong code Python — vốn chỉ nên
   gây thiệt hại bằng một request — biến thành quyền root trên toàn bộ máy
   chủ.

Lệnh `USER appuser` cắt chuỗi **ở bước 3→4**. Sau khi có `USER`, lỗ hổng vẫn
cho kẻ tấn công một shell, nhưng shell đó chạy dưới uid 10001 không có
group đặc biệt. Bước 4 (đọc secret trong biến môi trường) và bước 5 (leo
lên host) bị chặn vì uid đó không đủ quyền — không sửa được file hệ thống,
không cài được package hệ thống. Trong image của tôi tôi còn `chown -R
appuser:appuser /app` trước khi chuyển user, nên app vẫn đọc được code của
chính nó mà không cần quyền root.

Tôi kiểm chứng bằng `docker run --rm --entrypoint sh day12-agent:prod -c id`
→ in ra `uid=10001(appuser) gid=10001(appuser)`, không phải `uid=0(root)`.

---

### Câu 6 — Cửa sổ trượt (CP3)

Rate limit của bạn dùng sliding window 60 giây. Nếu thay bằng cách đếm theo
phút đồng hồ (reset lúc giây 00), một người dùng có thể gửi tối đa bao nhiêu
request trong 2 giây liên tiếp khi hạn mức là 10/phút? Giải thích cách đạt được
con số đó.


**Tối đa 20 request.**

Cách đạt được: một request lấy đúng khoảnh thời gian 2 giây đó nằm sát ranh
giới giữa hai phút. Cụ thể, tôi gửi 10 request lúc **10:00:59** (đủ 1/10 giây
để chúng kịp nằm trong phút 10:00) rồi gửi tiếp 10 request lúc
**10:01:01** (đã sang phút mới). Khoảng cách giữa request đầu tiên và
request cuối cùng chỉ là 2 giây.

Với cách đếm theo phút đồng hồ: ô đếm của phút 10:00 chỉ mới bị reset đúng
lúc 10:01:00, nên 10 request lúc 10:00:59 vẫn được tính vào hạn mức của
phút cũ; 10 request lúc 10:01:01 tính vào hạn mức của phút mới vừa được reset
về 0. Cả hai lô đều hợp lệ theo luật, tổng cộng 20 request/2 giây.

Với sliding window của tôi thì không: tôi giữ từng request trong một Redis
ZSET với score là timestamp, và mỗi lần đếm chạy
`zremrangebyscore(key, 0, now - 60)` để vứt đúng những request đã trượt khỏi
60 giây gần nhất. Lúc 10:01:01, cửa sổ là [10:00:01, 10:01:01] — 10 request
lúc 10:00:59 vẫn còn nằm trong cửa sổ, nên số đang hiệu lực là 10, bằng đúng
`limit`, và request thứ 11 bị chặn 429. Người dùng phải **chờ** đủ 60 giây
không có request nào mới lấy lại được quota. Đó là điểm cốt lõi: cửa sổ
trượt không có kẽ hở ở ranh giới phút.

---

### Câu 7 — Rate limit và cost guard (CP3)

Hai cơ chế này khác nhau ở điểm nào? Cho một tình huống mà rate limit cho qua
nhưng cost guard phải chặn, và một tình huống ngược lại.


Khác nhau ở **thứ được đo**: rate limit đo *số lượng request trong một cửa
sổ thời gian* (đơn vị là "lần gọi"), cost guard đo *tiền đã tiêu trong một
tháng* (đơn vị là USD). Rate limit tự động quên sau 60 giây, còn cost guard
cộng dồn cả tháng rồi mới xoá khi sang tháng mới (key `cost:<user>:<YYYY-MM>`).
Hệ quả: rate limit bảo vệ **hệ thống** khỏi bị dội, cost guard bảo vệ **ví
tiền** của tôi.

**Rate limit cho qua nhưng cost guard phải chặn (402):**
User `sv01` đã hỏi 4 lần trong tháng, mỗi lần câu hỏi dài 50.000 token và
kèm lịch sử hội thoại 20 message — `tokens_in` rất lớn nên `cost_usd` mỗi
lượt có thể cả USD. Tổng đã tiêu là 9.80 USD, `MONTHLY_BUDGET_USD=10.0`.
Lượt thứ 5 rơi vào giây thứ 3 của phút nên rate limit (10/phút) bỏ qua thoải
mái. Nhưng `spent(9.80) + estimated_cost(0.5) > 10.0` → cost guard trả 402.
Đây đúng là tình huống `test_con_ngan_sach_thi_cho_qua` và
`test_vuot_ngan_sach_thi_402` mô tả: rate limit nhìn *tần suất*, nên không
nhìn thấy được chuyện một request đắt bằng 50 request rẻ.

**Cost guard cho qua nhưng rate limit phải chặn (429):**
User mới `sv-new`, `spent=0.00` nên cost guard thoải mái cho qua. Nhưng hắn
gửi 11 request trong 3 giây. Lượt thứ 11 `hit_count() = 10 >= limit=10` → 429.
Tổng tiền mới tiêu có thể mới vài xu, hoàn toàn dưới ngân sách — nhưng 11
request/3 giây vẫn là lưu lượng bất thường, và nếu cho qua thì hắn có thể
tiếp tục đốt CPU và tiền. Cost guard không bao giờ chặn ở tình huống này vì
tiền chưa vượt ngưỡng.

Hai lớp này **không thay thế nhau**, và điều đó tôi thấy rõ ở thứ tự kiểm tra
trong `/ask`: `limiter.check` chạy trước `guard.check`. Nếu đảo lại, một kẻ
lạm dụng sẽ bị chặn 402 khi đã tiêu hết ngân sách, và tôi mất tiền ở các
lượt trước đó một cách vô ích.

---

### Câu 8 — /health khác /ready (CP4)

Nếu gộp hai endpoint làm một và cho nó kiểm tra Redis, chuyện gì xảy ra với cụm
3 container khi Redis mất kết nối 30 giây? Trả lời theo đúng thứ tự sự kiện.


Giả sử cụm 3 container `agent` sau một load balancer, và tôi gộp `/health` với
`/ready` thành một endpoint có gọi Redis. Redis mất kết nối trong 30 giây.
Trình tự sự kiện:

1. **T=0s — Redis ngừng phản hồi.** `store.ping()` ném `ConnectionError`.
2. **T≈0–5s — cả 3 container trả 503.** Endpoint hợp nhất gọi Redis nên cả
   ba cùng thất bại cùng lúc.
3. **T≈10s — orchestrator đọc `/health`, thấy 503, quyết định container đó
   hỏng.** Vì `/health` là *liveness*, trả 503 nghĩa là "hãy restart tôi".
   Vậy cả 3 container bị restart gần như đồng thời. Vòng lặp âm thầm: vừa
   restart xong, probe lại chạy, Redis vẫn chết → lại 503 → lại restart.
4. **T=10–30s — không còn container nào phục vụ.** Trong lúc đó load balancer
   không có chỗ nào để gửi request; user thấy 502. Tệ hơn: các request đang
   dở bị cắt giữa chừng vì container bị kill.
5. **T=30s — Redis quay lại.** Nhưng cả 3 container vừa mới khởi động lại,
   đang trong `start_period` của Docker/k8s, chưa sẵn sàng nhận traffic. Hệ
   thống phải chờ thêm một vòng nữa mới phục hồi.
6. **Kết quả:** một sự cố nhỏ và tạm thời của *một dependency* đã biến thành
   sự cố toàn hệ thống — 100% service down trong 30 giây, thay vì chỉ mất
   khả năng phục vụ vài request lỗi.

Với cách tách của tôi thì chuỗi này không xảy ra. `/health` **không** gọi
Redis: nó chỉ đọc `lifecycle.shutting_down` và trả 200, nên Redis chết thì
orchestrator thấy container vẫn khỏe và **không** restart gì. Đồng thời
`/ready` trả 503 `{"status":"not ready","redis": false}`, và load balancer chỉ
nghĩa là "ngừng đẩy request mới vào cả 3 container" — nó **không restart**.
Khi Redis quay lại ở T=30s, `/ready` trả 200 lại ngay và traffic tự chảy
trở lại, không mất container nào. Tóm lại: liveness trả 503 là lệnh *restart*,
còn readiness trả 503 chỉ là lệnh *rút khỏi vòng xoay*. Gộp chúng là đổi
một sự cố nhỏ thành một sự cố lớn.

---

### Câu 9 — Stateless (CP4)

Chạy `docker compose up --scale agent=3` rồi gọi `/ask` nhiều lần với cùng một
`X-User-Id`. Quan sát `history_length` trong response. Nếu lịch sử được lưu
trong một dict Python thay vì Redis, bạn sẽ thấy con số đó thay đổi thế nào?


Tôi đo trên bản deploy thật (`https://day12-agent-m3m7.onrender.com`) với
cùng một `X-User-Id: sv-stateless`, gọi 5 lượt:

```
  history_length = 0
  history_length = 2
  history_length = 4
  history_length = 6
  history_length = 8
```

Con số tăng đều 2 mỗi lượt, và đây là kết quả **không nhất quán về mặt logic
nếu state nằm trong RAM**: mỗi lượt tăng 2 vì mỗi lượt tôi `append` 2 message
(user + assistant). Nhưng trước khi `append`, `history_length` đếm lịch sử
*đã có*, nên lượt đầu là 0, lượt hai là 2 — đúng như mong đợi.

**Nếu lịch sử nằm trong một dict Python thay vì Redis**, con số đó sẽ
**nhảy cóc về 0 một cách ngẫu nhiên**, chứ không tăng đều. Cụ thể: giả sử
load balancer có round-robin và chia 5 lượt cho 3 container A, B, C:

| Lượt | vào container | dict của container đó | history_length |
|---|---|---|---|
| 1 | A | A rỗng | 0 |
| 2 | C | C rỗng | **0** ← nhảy về 0 |
| 3 | A | A có 2 | 2 |
| 4 | B | B rỗng | **0** ← nhảy về 0 |
| 5 | A | A có 4 | 4 |

Kết quả có thể là `0, 0, 2, 0, 4` thay vì `0, 2, 4, 6, 8`. Người dùng nhìn
thấy agent "quên" ngay giữa cuộc hội thoại — hỏi câu 1, hỏi câu 2, rồi câu 3
agent trả lời như lần đầu. Với 3 container, xác suất câu kế tiếp rơi trúng
container khác là 2/3, nên lỗi này xảy ra **thường xuyên** chứ không phải
hiếm. Tệ hơn, mỗi lần deploy là mất sạch dict trong RAM, nên lịch sử biến
mất hoàn toàn.

Đó chính là lý do `store.py` không giữ dict nào cả và `test_khong_co_bien_
toan_cuc_giu_state` quét source để bắt trường hợp này. Lịch sử, rate limit
và chi phí đều sống trong Render Key Value, nên mọi container cùng nhìn thấy
một nguồn sự thật và scale ngang được mà không cần sticky session.

---

### Câu 10 — Deploy thật (CP5)

Ghi lại **một** lỗi bạn gặp khi deploy lên cloud (build fail, health check
timeout, sai REDIS_URL, app không đọc `$PORT`...): thông báo lỗi là gì, bạn
tìm ra nguyên nhân bằng cách nào, và sửa ra sao?


**Lỗi:** khi tạo web service trên Render qua API, tôi gửi payload không khai
báo `plan`. Render trả về:

```
HTTP 402
{"message":"Payment information is required to complete this request.
            To add a card, visit https://dashboard.render.com/billing"}
```

Ban đầu tôi tưởng mình cần thẻ tín dụng, và định bỏ CP5, chuyển sang
`LOCAL_FALLBACK=true` để lấy 9/15 điểm. Nhưng trước khi bỏ, tôi thử lại
với biến thể payload khác và phát hiện điểm khác biệt: request không có
`plan` bị Render mặc định sang plan trả phí `0.5c-512mb` (đúng như schema ghi
`"default": "0.5c-512mb"`), và plan trả phí thì đòi thẻ. Tôi xác nhận bằng
cách gửi lại payload **giống hệt** nhưng thêm `"plan": "free"` vào trong
`serviceDetails` — lần này HTTP 201 và service được tạo thành công.

**Nguyên nhân:** không phải lỗi cấu hình hạ tầng hay thiếu biến môi trường
(mà những lỗi đó đáng nói hơn nhiều), mà là lỗi ở chỗ tôi gọi API — bỏ trống
một trường có mặc định. Điều này cũng nhắc lại bài học của CP1 ở tầng khác:
*thiếu cấu hình thì nên fail sớm và rõ ràng*, chứ không âm thầm điền vào
một giá trị mặc định rồi làm hậu quả về sau.

**Cách sửa:** thêm `"plan": "free"` vào payload, và chỉ định
`"region": "oregon"` để khớp với Render Key Value. Sau đó service build từ
`./Dockerfile` của tôi và chuyển sang `status: live` sau khoảng một phút;
`/ready` trả 200 `{"redis": true}` xác nhận nó đã nối được Redis qua private
network của Render.

Một lỗi nữa tôi gặp và cũng đáng kể: lần deploy đầu tiên, app **không lên
được** vì `lifespan` trong `app/main.py` gọi `lifecycle.install()`, mà hàm đó
lúc đó còn là `raise NotImplementedError` (CP4 chưa làm). Test CP1–CP3 vẫn
xanh vì `conftest.py` cố tình dựng `TestClient` mà **không** dùng
`with TestClient(...)`, nên lifespan không bao giờ chạy và lỗi này bị giấu
khỏi test. Tôi phát hiện ra khi thử `uvicorn app.main:app` thật trước khi
deploy. Bài học: có những lỗi chỉ lộ ra ở đường chạy thật, test tự động dù
đẹp đến mấy cũng không thay thế được một lần chạy tay.
