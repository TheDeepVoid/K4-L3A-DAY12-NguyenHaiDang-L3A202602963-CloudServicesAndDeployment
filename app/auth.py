"""CP3 — Xác thực bằng API key.

Public URL = ai cũng gọi được. Không có lớp này, hóa đơn LLM của bạn do
người lạ quyết định.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from .config import get_settings

ANONYMOUS_USER = "anonymous"


def verify_api_key(
    x_api_key: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    """Kiểm tra header ``X-API-Key``; trả về user_id nếu hợp lệ.

    1. Lấy khóa đúng từ ``get_settings().agent_api_key``.
    2. Nếu ``x_api_key`` là None hoặc không khớp → raise
       ``HTTPException(status_code=401, detail="invalid or missing API key")``.
    3. So sánh bằng ``secrets.compare_digest(a, b)``, **không dùng** ``==``.
       Toán tử ``==`` dừng ngay tại ký tự đầu khác nhau, nên thời gian trả
       lời rò rỉ thông tin về khóa (timing attack). ``compare_digest`` luôn
       chạy hết chuỗi.
    4. Hợp lệ → trả về ``x_user_id`` nếu client có gửi, ngược lại trả
       ``ANONYMOUS_USER``. user_id này là đơn vị để rate limit và tính chi phí.
    """
    expected = get_settings().agent_api_key

    # compare_digest chỉ nhận hai chuỗi cùng kiểu, nên ép str cho cả hai vế:
    # header HTTP luôn là str, nhưng nếu client gửi rỗng thì vẫn phải so sánh
    # được chứ không ném TypeError. Nhánh `x_api_key is None` tách riêng vì
    # thiếu header hoàn toàn là chuyện khác vì có header nhưng sai.
    if x_api_key is None or not secrets.compare_digest(str(x_api_key), str(expected)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
        )

    return x_user_id or ANONYMOUS_USER
