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

- `screenshots/dashboard.png` — trạng thái service, Redis instance, danh sách
  biến môi trường và deploy gần nhất trên Render.
- `screenshots/health.png` — kết quả gọi `/health` và `/ready` (kèm header
  HTTP thật) từ trình duyệt hoặc curl.

> **Ghi chú về ảnh `dashboard.png`:** ảnh này được chụp lại từ output thật
> của Render API (`GET /v1/services/srv-...`, `GET /v1/services/.../env-vars`,
> `GET /v1/services/.../deploys`) chứ không phải ảnh chụp giao diện dashboard.
> Lý do: tài khoản Render đăng nhập bằng Google, không có phiên trình duyệt
> nào sẵn có trên máy nên không thể mở dashboard để chụp ảnh màn hình. Các
> trường trong ảnh (`status = live`, `plan = free`, `region = oregon`,
> `health check = /health`, danh sách tên biến) lấy nguyên văn từ API, nên
> vẫn kiểm chứng được độc lập. Tên biến `AGENT_API_KEY` và `REDIS_URL` chỉ in
> tên, không in giá trị.

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
