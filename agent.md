# agent.md — Ghi chú làm bài (KHÔNG commit file này)

File này là ghi chú nội bộ cho AI agent, **không thuộc bài nộp**. Nếu
`git status` có hiện `agent.md` ở trạng thái untracked thì đúng — cứ để
vậy, đừng `git add` file này. Bài nộp chỉ cần những gì `SUBMISSION.md` liệt
kê.

---

## 1. Tình trạng hiện tại

| Hạng mục | Trạng thái |
|---|---|
| CP1 — Config, Health, Logging | ✅ 13/13 test |
| CP2 — Docker | ✅ 16/16 test (14 cấu trúc + 2 build thật) |
| CP3 — API Security | ✅ 22/22 test |
| CP4 — Scaling & Reliability | ✅ 19/19 test |
| CP5 — Cloud Deployment | ✅ 9/9 test (deploy thật, **không** dùng LOCAL_FALLBACK) |
| `exercises.md` | ✅ 10/10 câu |
| BONUS — CI/CD | ⚠️ 12/13 test — xem mục 5 |

Tổng: `pytest tests/ -m "not docker"` → **89 passed, 1 failed, 4 skipped**.

Service đang chạy thật: **https://day12-agent-m3m7.onrender.com**

---

## 2. Lịch sử commit

Mỗi commit ứng với đúng một checkpoint, có ghi lý do trong message.

| Commit | Nội dung |
|---|---|
| `10ce7c8` | CP0 — mốc bắt đầu, xác nhận môi trường chạy được |
| `33e4654` | CP1 — 12-Factor config, log JSON, `/health` |
| `baf9f4b` | CP2 — Dockerfile multi-stage non-root, `.dockerignore`, compose |
| `9d011fa` | CP3 — API key, sliding window, cost guard, `/ask` |
| `9f5b48e` | CP4 — Redis store, `/ready`, graceful shutdown |
| `c113c57` | CP5 — deploy thật lên Render + `DEPLOYMENT.md` + screenshots |
| `7c74931` | 10 câu `exercises.md` (đã push) |
| `273af3b` | BONUS — workflow CI/CD (**chưa push**, xem mục 5) |

### Về commit đầu tiên

Repo ban đầu đã có 3 commit template từ giảng viên, cộng thêm một commit
`591e87e` ("CP1: ...") do một phiên agent trước tạo, nhưng nội dung commit đó
đã bị revert trong working tree (3 file về đúng trạng thái TODO). `origin/main`
vẫn là template sạch.

Đã hỏi và được xác nhận: `git reset --mixed` về `306b897` rồi tạo lịch sử
mới. Không mất gì — commit cũ chưa từng push và nội dung nó đã không còn trong
working tree.

---

## 3. Những gì đã sửa, theo từng file

Chỉ điền phần TODO và chỗ còn thiếu, giữ nguyên văn phong và cấu trúc
template.

| File | Thay đổi |
|---|---|
| `app/config.py` | 6 trường `Settings`; `agent_api_key` không mặc định (fail fast) |
| `app/logging_utils.py` | `log_event()` in 1 dòng JSON, `ensure_ascii=False`, `flush=True` |
| `app/auth.py` | `verify_api_key` so sánh bằng `secrets.compare_digest` |
| `app/rate_limiter.py` | `hit_count` + `check` — sliding window ZSET, check trước ghi sau |
| `app/cost_guard.py` | `spent` / `check` (402) / `record` (`incrbyfloat`) |
| `app/store.py` | `ping` nuốt exception, `append` có `ltrim`+`expire`, `get_history` |
| `app/lifecycle.py` | `install` nhớ handler cũ, `request_shutdown` nhường lại handler cũ |
| `app/main.py` | `/health`, `/ready`, `/ask` đúng thứ tự chặn-trước-khi-tốn-tiền |
| `Dockerfile` | Multi-stage, slim, non-root uid 10001, HEALTHCHECK, đọc `$PORT` |
| `.dockerignore` | `.env`, `__pycache__`, `.git`, `.venv`, `tests/`… nhưng **giữ** `app`/`utils`/`requirements.txt` |
| `docker-compose.yml` | Thêm service `agent` (build, healthcheck, `${AGENT_API_KEY}`) |
| `DEPLOYMENT.md` | Điền URL thật, output thật, ảnh thật |
| `exercises.md` | 10/10 câu, có số đo thật |
| `README.md` | Thêm badge CI ở đầu file |
| `.github/workflows/ci.yml` | File mới (bonus) |

### Hai chỗ phải sửa ngoài phần TODO

1. **`exercises.md` dòng 6** — câu hướng dẫn ở đầu file chứa đúng chuỗi
   `> *Câu trả lời của bạn*`, mà `grade.py` đếm chuỗi này để tính điểm. Để
   nguyên thì `grade.py` cho 0/10 dù đã trả lời đủ. Đã đổi thành "thay dòng
   giữ chỗ mỗi câu bằng câu trả lời của bạn".
2. **Xóa 10 dòng placeholder** trong các block trả lời — đúng như hướng dẫn
   yêu cầu là *thay dòng*, không phải viết thêm bên dưới.

---

## 4. Deploy trên Render — chi tiết kỹ thuật

| | |
|---|---|
| Web service | `day12-agent` — `srv-dat24j0473hc73ee404g` |
| Public URL | `https://day12-agent-m3m7.onrender.com` |
| Runtime | docker, đọc `./Dockerfile`, plan `free`, region `oregon` |
| Redis | Render Key Value `day12-redis` — `red-dat225l9fdbs73fk0u2g` |
| `REDIS_URL` | `redis://red-dat225l9fdbs73fk0u2g:6379` (internal connection string, qua private network) |
| Deploy | `dep-dat24pbmmadc73eqdlj0` — `live` |

### Hai lỗi thật đã gặp khi deploy

**Lỗi 1 — HTTP 402 khi tạo service qua API.**

```
{"message":"Payment information is required to complete this request."}
```

Nguyên nhân **không phải** thiếu thẻ tín dụng. Tôi bỏ trống trường `plan` và
Render mặc định sang plan trả phí `0.5c-512mb` (đúng như schema ghi
`"default": "0.5c-512mb"`), plan trả phí thì đòi thẻ. Thêm
`"plan": "free"` vào `serviceDetails` → HTTP 201, service tạo thành công.

**Lỗi 2 — app không khởi động được ở lần deploy đầu.**

```
File "app/main.py", line 60, in lifespan
    lifecycle.install()
NotImplementedError: TODO (CP4): cài đặt install
```

`lifespan` gọi `lifecycle.install()`, mà hàm đó thuộc CP4. CP1–CP3 vẫn xanh
suốt vì `conftest.py` dựng `TestClient` **không** dùng `with TestClient(...)`
→ lifespan không bao giờ chạy → lỗi bị giấu khỏi test. Chỉ lộ ra khi chạy
`uvicorn app.main:app` thật.

Cả hai lỗi đều đã ghi vào câu 10 của `exercises.md`.

### Endpoint đọc connection string của Redis

`GET /v1/redis/{id}` **không** trả connection string. Phải dùng:

```
GET /v1/key-value/{redisId}/connection-info
```

Trả về `internalConnectionString` (không cần auth, chỉ trong private network
cùng workspace) và `externalConnectionString` (cần auth + TLS, cần mở
`ipAllowList`).

Đã đặt `ipAllowList: []` nên không instance nào từ bên ngoài nối được vào
Redis — chỉ service cùng workspace mới vào được qua private network.

### Lệnh thường dùng

```bash
set -a && . ./.env && set +a   # nạp RENDER_API_KEY

# Trạng thái service
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  https://api.render.com/v1/services/srv-dat24j0473hc73ee404g

# Deploy lại (không xoá cache)
curl -s -X POST \
  -H "Authorization: Bearer $RENDER_API_KEY" -H "Content-Type: application/json" \
  -d '{"clearCache":"do_not_clear"}' \
  https://api.render.com/v1/services/srv-dat24j0473hc73ee404g/deploys
```

---

## 5. Phần bonus CI/CD — CHƯA HOÀN TẤT

Commit `273af3b` **đã commit local nhưng chưa push được**. GitHub từ chối vì
token `gh` hiện tại thiếu scope `workflow`:

```
refusing to allow an OAuth App to create or update workflow
`.github/workflows/ci.yml` without `workflow` scope
```

SSH key trên máy chưa đăng ký với GitHub (`Permission denied (publickey)`).
`gh auth refresh -s workflow` cần đăng nhập tương tác qua trình duyệt, agent
không tự làm được.

**Việc cần làm để mở khóa:**

```bash
gh auth refresh -h github.com -s workflow
```

Rồi mở `https://github.com/login/device`, dán mã hiện trên màn hình, bấm
Authorize. Sau đó:

```bash
git push origin main
```

Mã một-time code được sinh mới ở mỗi lần chạy — phải dùng mã mới nhất in ra,
không dùng lại mã của lần trước.

### Test nào đang đỏ và vì sao

`test_bonus_cicd.py::TestBadge::test_badge_bao_passing` — badge trả **404**
vì workflow chưa từng được push nên GitHub chưa có lần chạo nào. Đây là hệ
quả trực tiếp của vấn đề token ở trên, **không** phải lỗi logic trong
workflow.

**Chưa được kiểm chứng:** workflow chưa từng chạy thật. 12/13 test chỉ kiểm
tra *cấu trúc* YAML (có `on:` không, có `needs:` không, có ghim phiên bản
action không). Job `build` và job `deploy` có chạy đúng trên runner GitHub
Actions hay không thì **chưa ai biết**. Cần push xong, mở tab Actions xem
log từng job rồi mới kết luận được phần bonus có đạt hay không.

### GitHub Secrets / Variables đã set

| Loại | Tên | Ghi chú |
|---|---|---|
| secret | `RENDER_API_KEY` | token Render — **không** có trong repo |
| variable | `RENDER_SERVICE_ID` | `srv-dat24j0473hc73ee404g` |
| variable | `RENDER_DEPLOY_ID` | `dep-dat24pbmmadc73eqdlj0` |
| variable | `PUBLIC_URL` | `https://day12-agent-m3m7.onrender.com` |

---

## 6. Bảo mật — đã kiểm tra

- `.env` **không** được track (`git ls-files | grep '\.env$'` → rỗng)
- Đã quét toàn bộ file staged bằng `git grep -F` với giá trị thật của
  `AGENT_API_KEY`, `RENDER_API_KEY`, `DEPLOY_API_KEY` → không rò rỉ
- `DEPLOYMENT.md` chỉ ghi **tên** biến, không ghi giá trị
- Token Render trong `.env` là `RENDER_API_KEY`, tách riêng khỏi
  `DEPLOY_API_KEY` (biến này theo định nghĩa của lab là khóa API của chính
  service, không phải token của platform)
- Ảnh `screenshots/dashboard.png` chỉ in tên biến, không in giá trị

### Về ảnh chụp màn hình

Không có trình duyệt nào kết nối và tài khoản Render đăng nhập bằng Google
nên **không** chụp được ảnh dashboard thật. Thay vào đó ảnh được dựng từ
output thật của Render API (`GET /v1/services/...`, `/env-vars`, `/deploys`)
bằng ImageMagick. Điều này đã được ghi rõ trong `DEPLOYMENT.md` và trong
chính tiêu đề ảnh — không giả vờ là ảnh giao diện dashboard. Nếu Lab Coach
đòi ảnh dashboard thật thì phải tự chụp tay.

---

## 7. Số đo thật đã thu thập

Dùng lại được cho các câu hỏi hoặc khi Lab Coach hỏi:

| Phép đo | Kết quả |
|---|---|
| Image 1 stage | **1.72GB** |
| Image multi-stage | **269MB** (nhỏ hơn ~6.4×, giảm ~84%) |
| User trong container | `uid=10001(appuser)` |
| Nội dung `/app` trong image | chỉ `app` + `utils`, không có `.env` |
| Docker layer cache | sửa `app/main.py` → `pip install` vẫn `Using cache`, `COPY app` trở đi chạy lại |
| Lịch sử trên cloud | `history_length` = 0, 2, 4, 6, 8 |
| Rate limit | 10×200 rồi 5×429, header `retry-after: 60` |
| Một dòng log thật | `{"event":"ask_completed",...,"cost_usd":4.23e-05,"history_length":4}` |

---

## 8. Việc còn lại

1. **Chạy `gh auth refresh -h github.com -s workflow`**, authorize, rồi
   `git push origin main` — mở khóa phần bonus.
2. Mở tab **Actions** trên GitHub, đọc log từng job. Xác nhận `test` và
   `build` xanh thì phần bonus mới thật sự đạt.
3. Chạy lại `python grade.py` để chốt điểm.
4. Tự chụp ảnh dashboard Render thật nếu muốn thay ảnh hiện tại.
5. Deploy lại lần cuối nếu muốn badge và `DEPLOYMENT.md` khớp commit mới nhất
   (hiện deploy là `9f5b48e` = CP4; các commit sau đó chỉ đổi
   `exercises.md` / `README.md` / workflow nên app không đổi gì).

---

## 9. Ghi chú cho agent kế tiếp

- Đọc `RULES.md` trước: nộp code không giải thích được thì mất điểm phần đó.
  Mỗi quyết định thiết kế đều có lý do trong comment và commit message.
- `app/` không còn `NotImplementedError` nào. `grep -rn NotImplementedError app/`
  → rỗng.
- Cứ sửa một checkpoint thì commit ngay, đúng như `CHECKPOINTS.md` yêu cầu.
- `conftest.py` cố tình **không** chạy lifespan, nên test xanh **không** bảo
  đảm app chạy được. Luôn chạy `uvicorn` thật trước khi deploy.
- Free tier Render ngủ đông sau ~15 phút không có traffic. Request đầu tiên
  có thể mất 30–60 giây — bộ test CP5 đã có `FIRST_CALL_TIMEOUT = 60`.
