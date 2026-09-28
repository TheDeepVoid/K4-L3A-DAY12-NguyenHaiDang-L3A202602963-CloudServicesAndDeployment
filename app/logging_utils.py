"""CP1 — Structured logging.

`print("user abc hỏi gì đó")` là log cho người đọc. Cloud (Railway, Render,
Cloud Run, Datadog...) đọc log bằng máy: một dòng = một JSON object thì mới
lọc/đếm/cảnh báo được. Đây là khác biệt lớn giữa localhost và production.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """CHO SẴN — thời điểm hiện tại theo ISO-8601, múi giờ UTC."""
    return datetime.now(timezone.utc).isoformat()


def log_event(event: str, level: str = "info", **fields) -> str:
    """Ghi một dòng log JSON ra stdout và trả về chính dòng đó.

    Ba khóa luôn có mặt: ``event``, ``level`` (viết thường) và ``timestamp``
    (ISO-8601 UTC). Mọi cặp key/value trong ``**fields`` được gộp thêm vào cùng
    một object, nên có thể ghi kèm bất kỳ ngữ cảnh nào cần truy vấn sau này
    (``user_id``, ``cost_usd``, ``tokens_in``...).

    Không dùng ``indent``: cloud (Railway, Render, Cloud Run, Datadog) gom log
    theo từng dòng, một JSON xuống dòng sẽ bị tách thành nhiều mảnh vô nghĩa.
    ``ensure_ascii=False`` để tiếng Việt giữ nguyên dấu thay vì thành ``ạ``.

    Ví dụ:
        >>> log_event("ask_completed", user_id="sv01", cost_usd=0.0001)
        '{"event": "ask_completed", "level": "info", "timestamp": "...", ...}'
    """
    record = {
        "event": event,
        "level": level.lower(),
        "timestamp": utc_now_iso(),
        **fields,
    }
    # separators bỏ khoảng trắng thừa: dòng log càng ngắn càng rẻ khi bị lưu lại
    # hàng triệu lần, và `default=str` để một field lạ (vd datetime) không làm
    # sập cả request đang phục vụ.
    line = json.dumps(record, ensure_ascii=False, default=str, separators=(",", ":"))
    print(line, flush=True)  # flush=True: container bị kill thì log vẫn còn
    return line
