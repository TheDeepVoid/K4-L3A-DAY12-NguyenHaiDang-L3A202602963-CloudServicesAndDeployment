# Thông Tin Deploy — Checkpoint 5

> Điền file này sau khi deploy xong. `pytest tests/test_cp5.py` đọc file này
> để tìm địa chỉ service của bạn và gọi thử.
>
> **Chỉ ghi TÊN biến môi trường, tuyệt đối không dán giá trị API key vào đây.**
> Repo này công khai — dán khóa vào là mất khóa.

## Thông Tin Học Viên

| Mục | Nội dung |
|-----|----------|
| Họ và tên | Nguyễn Hải Đăng |
| Mã học viên | L3A202602963 |
| Repo | https://github.com/TheDeepVoid/K4-L3A-DAY12-NguyenHaiDang-L3A202602963-CloudServicesAndDeployment |

## Service

| Mục | Nội dung |
|-----|----------|
| Public URL | https://day12-agent-m3m7.onrender.com |
| Platform | Render — web service `day12-agent` (docker runtime, plan free, region oregon) + Render Key Value `day12-redis` |
| Ngày deploy | 28/09/2026 |

Hai địa chỉ này khác nhau, đừng nhầm:

| Mục | Địa chỉ | Ai dùng |
|-----|----------|---------|
| **Public URL** — API của service | `https://day12-agent-m3m7.onrender.com` | Bất kỳ ai cũng gọi được. Đây là URL Lab Coach kiểm tra. |
| **Dashboard** — giao diện quản lý | `https://dashboard.render.com/web/srv-dat24j0473hc73ee404g` | Chỉ tài khoản Render đã đăng nhập mới mở được |

| Mục | Nội dung |
|-----|----------|
| Service ID | `srv-dat24j0473hc73ee404g` |
| Redis instance ID | `red-dat225l9fdbs73fk0u2g` |
| Deploy hiện tại | `dep-dat2pcbbc2fs73av2g3g` — trạng thái `live`, commit `930fc6d` |
| Auto deploy | bật (`autoDeployTrigger: commit`) — push `main` là Render tự build lại |
| `healthCheckPath` | `/health` (giữ nguyên, **không** đổi sang `/`) |
| CI/CD | GitHub Actions xanh — `Test (CP1-CP4)` 12s, `Build Docker image` 41s, `Deploy len Render` 6s |

> **Ghi chú về auto deploy:** vì Render tự build mỗi khi có commit mới lên
> `main`, nên bản đang chạy luôn khớp với commit mới nhất trong repo. Khi
> push xong phải chờ build vài chục giây — free tier còn *ngủ đông* sau ~15
> phút không có traffic, nên vài request đầu có thể mất 30–60 giây.

## Biến Môi Trường Đã Set Trên Cloud

Ghi tên biến và **nguồn giá trị**, không ghi giá trị:

| Biến | Đã set | Ghi chú |
|------|--------|---------|
| `PORT` | ✅ | platform tự gán; `CMD` trong Dockerfile đọc `${PORT:-8000}` |
| `AGENT_API_KEY` | ✅ | đặt trong dashboard, không nằm trong repo |
| `REDIS_URL` | ✅ | Render Key Value `day12-redis` qua private network nội bộ của Render |
| `RATE_LIMIT_PER_MINUTE` | ✅ | 10 |
| `MONTHLY_BUDGET_USD` | ✅ | 10.0 |
| `LOG_LEVEL` | ✅ | INFO |

## Lệnh Kiểm Tra

Thay `<URL>` bằng Public URL ở trên:

```bash
# 1. Liveness — mong đợi 200 {"status":"ok"}
curl -i <URL>/health

# 2. Readiness — mong đợi 200 {"status":"ready"} (đã nối được Redis)
curl -i <URL>/ready

# 3. Không có API key — mong đợi 401
curl -i -X POST <URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'

# 4. Có API key — mong đợi 200 kèm câu trả lời
curl -i -X POST <URL>/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "X-User-Id: sv-test" \
  -d '{"question":"Deploy là gì?"}'

# 5. Rate limit — gọi 15 lần, những lần cuối phải trả 429
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST <URL>/ask \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $AGENT_API_KEY" \
    -H "X-User-Id: sv-test" \
    -d '{"question":"test"}'
done; echo
```

## Kết Quả Chạy Thật

Dán output của các lệnh trên vào đây:

```
$ # 0. Trang chủ — mở Public URL ra không ra 404
$ curl -i https://day12-agent-m3m7.onrender.com/
HTTP/2 200

{"service":"day12-agent","version":"1.0.0","endpoints":{"GET /health":"liveness — không phụ thuộc dependency","GET /ready":"readiness — có kiểm tra Redis","POST /ask":"hỏi agent (cần header X-API-Key)","GET /docs":"OpenAPI docs tương tác"}}

$ # 1. Liveness
$ curl -i https://day12-agent-m3m7.onrender.com/health
HTTP/2 200
content-type: application/json
server: cloudflare
x-render-origin-server: uvicorn
cf-cache-status: DYNAMIC

{"status":"ok","service":"day12-agent","version":"1.0.0"}

$ # 2. Readiness — 200 + redis:true là bằng chứng đã nối được Redis trên cloud
$ curl -i https://day12-agent-m3m7.onrender.com/ready
HTTP/2 200
content-type: application/json
server: cloudflare
x-render-origin-server: uvicorn

{"status":"ready","redis":true}

$ # 3. Không có API key
$ curl -i -X POST https://day12-agent-m3m7.onrender.com/ask \
    -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/2 401

{"detail":"invalid or missing API key"}

$ # 4. Có API key
$ curl -X POST https://day12-agent-m3m7.onrender.com/ask \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $AGENT_API_KEY" -H "X-User-Id: sv-test" \
    -d '{"question":"Deploy là gì?"}'
{
    "answer": "Câu hỏi hay. Deploy là gì thường được giải quyết bằng cách chuẩn hóa môi trường chạy: cùng một image chạy giống nhau ở laptop và trên cloud.",
    "user_id": "sv-test",
    "history_length": 0,
    "cost_usd": 2.145e-05,
    "tokens": {
        "in": 3,
        "out": 35
    }
}

$ # 5. Rate limit — 10 lần đầu 200, 5 lần sau 429
$ for i in $(seq 1 15); do curl -s -o /dev/null -w "%{http_code} " -X POST \
    https://day12-agent-m3m7.onrender.com/ask -H "Content-Type: application/json" \
    -H "X-API-Key: $AGENT_API_KEY" -H "X-User-Id: sv-ratelimit" \
    -d '{"question":"test"}'; done; echo
200 200 200 200 200 200 200 200 200 200 429 429 429 429 429

$ # Header Retry-After khi bị chặn
$ curl -s -D - -o /dev/null -X POST https://day12-agent-m3m7.onrender.com/ask \
    -H "Content-Type: application/json" -H "X-API-Key: $AGENT_API_KEY" \
    -H "X-User-Id: sv-ratelimit" -d '{"question":"test"}' | grep -iE '^(HTTP|retry-after)'
HTTP/2 429
retry-after: 60

$ # Stateless trên cloud — 5 lượt cùng user, history_length tăng đều 0,2,4,6,8
$ for i in 1 2 3 4 5; do curl -s -X POST https://day12-agent-m3m7.onrender.com/ask \
    -H "Content-Type: application/json" -H "X-API-Key: $AGENT_API_KEY" \
    -H "X-User-Id: sv-stateless" -d "{\"question\":\"luot $i\"}" \
    | python -c "import json,sys; print('  history_length =', json.load(sys.stdin)['history_length'])"; done
  history_length = 0
  history_length = 2
  history_length = 4
  history_length = 6
  history_length = 8
```

> Số `0, 2, 4, 6, 8` là bằng chứng quan trọng nhất của CP4: lịch sử nằm ở
> Render Key Value chứ không trong RAM của container, nên các lượt gọi sau
> vẫn thấy đúng lịch sử của lượt gọi trước.

## Ảnh Chụp Màn Hình

Đặt ảnh trong thư mục `screenshots/`:

| File | Nội dung |
|---|---|
| `dashboard.png` | Trạng thái web service, Redis instance, danh sách biến môi trường và deploy gần nhất trên Render |
| `index.png` | `GET /` trên Public URL |
| `health.png` | `GET /health` trên Public URL |
| `ready.png` | `GET /ready` — `{"status":"ready","redis":true}` |
| `ask_unauth.png` | `POST /ask` không có API key → **401** |
| `ask_authorized.png` | `POST /ask` có API key → **200**, hai lượt cùng user thấy `history_length` 0 rồi 2 |
| `docs.png` | OpenAPI docs `/docs` |

Các ảnh `index` / `health` / `ready` / `ask_*` chụp bằng Playwright điều khiển
Brave, **gọi thẳng vào Public URL của Render** — không phải `localhost`.
Request `POST /ask` được bắn từ chính trang `https://...onrender.com/health`
nên là request same-origin thật, không phải mô phỏng.

> **Ghi chú về ảnh `dashboard.png`:** ảnh này dựng từ output thật của Render
> API (`GET /v1/services/srv-...`, `GET /v1/services/.../env-vars`,
> `GET /v1/services/.../deploys`), chứ **không phải** ảnh chụp giao diện
> dashboard. Lý do: tài khoản Render đăng nhập bằng Google và máy không có
> phiên đăng nhập nào sẵn, nên không mở được dashboard để chụp màn hình.
> Các trường trong ảnh (`status = live`, `plan = free`, `region = oregon`,
> `health check = /health`, danh sách tên biến) lấy nguyên văn từ API nên vẫn
> kiểm chứng được độc lập. Tên biến `AGENT_API_KEY` và `REDIS_URL` chỉ in
> **tên**, không in giá trị.

> **Ghi chú về ảnh `ask_authorized.png`:** khóa API được đọc từ `.env` cục bộ
> và chỉ dùng làm header khi gọi. Giá trị khóa **không** xuất hiện trong ảnh —
> phần ghi chú dưới tiêu đề chỉ nói khóa lấy từ đâu.

## Nếu Dùng Phương Án Dự Phòng

Không đăng ký được tài khoản cloud? Vẫn nộp được bài, nhưng CP5 tối đa 60% điểm:

1. Đặt `LOCAL_FALLBACK=true` trong `.env`
2. Chạy `docker compose up -d` rồi kiểm tra `docker compose ps`
3. Chụp màn hình vào `screenshots/`
4. Chạy `pytest tests/test_cp5.py -v` — bộ test sẽ tự chuyển sang kiểm tra
   `http://localhost:8000`
5. Ghi rõ lý do không deploy được vào phần dưới đây:

```
(Không dùng — service đã deploy thật lên Render ở trên.)
```
