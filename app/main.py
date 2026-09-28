"""Agent service — điểm ráp nối của cả lab (CP1, CP3, CP4).

Luồng một request tới /ask:

    client ──► verify_api_key ──► rate_limiter ──► cost_guard
                                                       │
                              store.get_history ◄──────┘
                                       │
                                    ask_llm
                                       │
                              store.append × 2 ──► cost_guard.record ──► log_event
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from utils.mock_llm import ask_llm

from .auth import verify_api_key
from .config import get_settings
from .cost_guard import CostGuard
from .lifecycle import lifecycle
from .logging_utils import log_event
from .rate_limiter import RateLimiter
from .store import ConversationStore, get_redis_client

SERVICE_NAME = "day12-agent"
SERVICE_VERSION = "1.0.0"


# ─────────────────────────────────────────────────────────────
# Providers — CHO SẴN
# Tách ra thành hàm để test có thể thay bằng Redis giả qua
# app.dependency_overrides, và để kết nối Redis chỉ tạo khi thật sự cần.
# ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_store() -> ConversationStore:
    return ConversationStore(get_redis_client())


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_redis_client(), get_settings().rate_limit_per_minute)


@lru_cache(maxsize=1)
def get_cost_guard() -> CostGuard:
    return CostGuard(get_redis_client(), get_settings().monthly_budget_usd)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """CHO SẴN — chạy lúc app khởi động và lúc tắt."""
    lifecycle.install()
    log_event("service_started", service=SERVICE_NAME, version=SERVICE_VERSION)
    yield
    log_event("service_stopped", service=SERVICE_NAME)


app = FastAPI(title="Day 12 Production Agent", version=SERVICE_VERSION, lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


# ─────────────────────────────────────────────────────────────
# Trang chủ
# ─────────────────────────────────────────────────────────────
@app.get("/")
def index():
    """Mở Public URL ra mà thấy 404 thì tưởng service chết.

    Không có route `/` thì FastAPI trả ``{"detail":"Not Found"}`` — trông
    y hệt một deploy hỏng, dù ``/health`` vẫn 200. Người mở link công
    khai lần đầu thường thử đúng đường dẫn gốc, nên ở đây chỉ trả về
    danh sách endpoint và trạng thái, không chạm vào Redis để liveness
    vẫn nhẹ.
    """
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "endpoints": {
            "GET /health": "liveness — không phụ thuộc dependency",
            "GET /ready": "readiness — có kiểm tra Redis",
            "POST /ask": "hỏi agent (cần header X-API-Key)",
            "GET /docs": "OpenAPI docs tương tác",
        },
    }


# ─────────────────────────────────────────────────────────────
# Health & readiness
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness probe — process này có cần restart không?

    Cố tình **không** nhận tham số dependency nào: không Redis, không DB, không
    API key. Nếu liveness phụ thuộc Redis, Redis chết một nhịp là cả cụm
    container bị orchestrator restart theo — biến sự cố nhỏ thành sự cố lớn.
    Endpoint kiểm tra dependency là ``/ready`` (CP4).

    Khi đang tắt dần (đã nhận SIGTERM) trả 503 để load balancer ngừng đẩy
    request mới vào instance này, còn request đang chạy vẫn kịp trả lời.
    """
    if lifecycle.shutting_down:
        return JSONResponse(status_code=503, content={"status": "shutting_down"})
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/ready")
def ready(store: ConversationStore = Depends(get_store)):
    """Readiness probe — đã sẵn sàng nhận traffic chưa?

    - Đang tắt dần → 503 ``{"status": "shutting_down"}``
    - ``store.ping()`` False → 503 ``{"status": "not ready", "redis": False}``
    - Ngược lại → ``{"status": "ready", "redis": True}``

    Khác /health ở chỗ: endpoint này ĐƯỢC PHÉP kiểm tra dependency. Load
    balancer dùng nó để quyết định có đẩy request vào instance này không.
    """
    # Cùng lý do như /health: đang tắt dần thì instance này sắp biến mất,
    # dù Redis còn sống thì cũng không nên nhận thêm request mới.
    if lifecycle.shutting_down:
        return JSONResponse(status_code=503, content={"status": "shutting_down"})

    # Phải dùng KẾT QUẢ của ping(). `if not store.ping()` — bỏ mất kết quả
    # thì /ready luôn trả 200 kể cả khi Redis đã chết, và load balancer vẫn
    # đẩy traffic vào một instance không phục vụ được.
    if not store.ping():
        return JSONResponse(
            status_code=503, content={"status": "not ready", "redis": False}
        )

    return {"status": "ready", "redis": True}


# ─────────────────────────────────────────────────────────────
# Endpoint chính
# ─────────────────────────────────────────────────────────────
@app.post("/ask")
def ask(
    payload: AskRequest,
    user_id: str = Depends(verify_api_key),
    store: ConversationStore = Depends(get_store),
    limiter: RateLimiter = Depends(get_rate_limiter),
    guard: CostGuard = Depends(get_cost_guard),
):
    """Hỏi agent một câu.

    Thực hiện ĐÚNG THỨ TỰ sau:
      1. ``limiter.check(user_id)``           → 429 nếu gọi quá nhanh
      2. ``guard.check(user_id)``             → 402 nếu hết ngân sách
      3. ``history = store.get_history(user_id)``
      4. ``result = ask_llm(payload.question, history)``
      5. ``store.append(user_id, "user", payload.question)`` và
         ``store.append(user_id, "assistant", result["answer"])``
      6. ``guard.record(user_id, result["cost_usd"])``
      7. ``log_event("ask_completed", user_id=user_id,
         tokens_in=result["tokens_in"], tokens_out=result["tokens_out"],
         cost_usd=result["cost_usd"])``
      8. trả về::

            {
                "answer": result["answer"],
                "user_id": user_id,
                "history_length": len(history),
                "cost_usd": result["cost_usd"],
                "tokens": {"in": result["tokens_in"], "out": result["tokens_out"]},
            }

    Vì sao check trước rồi mới gọi LLM? Vì tiền mất ở bước gọi LLM. Chặn sau
    khi đã gọi thì bạn vừa trả tiền vừa trả lỗi.

    ``user_id`` do ``verify_api_key`` trả về, nên request không có API key
    hợp lệ sẽ dừng ở 401 trước khi chạm vào bất cứ dòng nào ở đây.
    """
    # ── Chặn TRƯỚC khi tốn tiền ──────────────────────────────
    limiter.check(user_id)        # 429: gọi quá nhanh
    guard.check(user_id)          # 402: đã hết ngân sách tháng

    # ── Tốn tiền ──────────────────────────────────────────────
    history = store.get_history(user_id)
    result = ask_llm(payload.question, history)

    # ── Ghi lại state và số liệu ──────────────────────────────
    store.append(user_id, "user", payload.question)
    store.append(user_id, "assistant", result["answer"])
    guard.record(user_id, result["cost_usd"])

    log_event(
        "ask_completed",
        user_id=user_id,
        tokens_in=result["tokens_in"],
        tokens_out=result["tokens_out"],
        cost_usd=result["cost_usd"],
        history_length=len(history),
    )

    return {
        "answer": result["answer"],
        "user_id": user_id,
        # Đếm history TRƯỚC khi append: đây là số lượt mà câu hỏi vừa rồi
        # được dựa vào, nên lần đầu tiên luôn là 0 và lần sau tăng đều.
        "history_length": len(history),
        "cost_usd": result["cost_usd"],
        "tokens": {"in": result["tokens_in"], "out": result["tokens_out"]},
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
