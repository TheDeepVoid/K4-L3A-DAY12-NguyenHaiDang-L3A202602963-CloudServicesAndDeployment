"""CP4 — Stateless: state sống ngoài process.

Nếu lịch sử hội thoại nằm trong một dict trong RAM, thì khi scale lên 3
instance, user hỏi câu 1 vào instance A và câu 2 vào instance B sẽ thấy agent
"mất trí nhớ". Container còn bị restart bất cứ lúc nào. Vì vậy state phải
nằm ở nơi mọi instance cùng nhìn thấy: Redis.
"""

from __future__ import annotations

import json

import redis

from .config import get_settings

HISTORY_MAX_MESSAGES = 20
HISTORY_TTL_SECONDS = 7 * 24 * 3600


def get_redis_client(url: str | None = None):
    """CHO SẴN — tạo client Redis từ URL.

    ``fake://`` trả về Redis giả chạy trong RAM, dùng khi máy bạn chưa có
    Docker. Tiện cho lúc học, nhưng KHÔNG dùng khi deploy: nó vẫn là state
    trong process, đúng cái mà CP4 đang tìm cách loại bỏ.
    """
    url = url or get_settings().redis_url
    if url.startswith("fake://"):
        import fakeredis

        return fakeredis.FakeRedis(decode_responses=True)
    return redis.from_url(url, decode_responses=True)


class ConversationStore:
    """Lưu lịch sử hội thoại của từng user trong Redis List."""

    def __init__(self, client) -> None:
        self.client = client

    @staticmethod
    def _key(user_id: str) -> str:
        """CHO SẴN."""
        return f"history:{user_id}"

    def ping(self) -> bool:
        """Redis có trả lời không? Dùng cho endpoint /ready.

        Gọi ``self.client.ping()`` trong try/except.
        Trả ``True`` nếu thành công, ``False`` nếu có bất kỳ Exception nào
        (mất mạng, sai mật khẩu, Redis chưa khởi động...).
        """
        # Nuot moi exception va tra False. Ly do: ham nay duoc goi tu
        # /ready, va mot exception tho ra se bien readiness probe thanh loi
        # 500 — luc do orchestrator/toan bo load balancer coi service dang
        # hong, trong khi thuoc tinh la chi co mot dependency chet.
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def append(self, user_id: str, role: str, content: str) -> None:
        """Ghi thêm một lượt vào lịch sử.

        1. ``self.client.rpush(key, json.dumps({"role": role, "content": content},
           ensure_ascii=False))``
        2. ``self.client.ltrim(key, -HISTORY_MAX_MESSAGES, -1)`` — chỉ giữ
           ``HISTORY_MAX_MESSAGES`` message gần nhất, nếu không prompt sẽ
           phình vô hạn và tiền token cũng vậy.
        3. ``self.client.expire(key, HISTORY_TTL_SECONDS)`` — hội thoại cũ
           tự hết hạn, khỏi phải dọn tay.
        """
        key = self._key(user_id)
        # ensure_ascii=False: nội dung tiếng Việt đọc lại từ Redis giữ nguyên
        # dấu, không thành chuỗi \uXXXX khó đọc khi debug bằng tay.
        self.client.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
        # ltrim với chỉ số ÂM giữ N phần tử CUỐI cùng (mới nhất). Dùng
        # `ltrim(key, 0, N-1)` sẽ giữ nhầm N tin cũ nhất và xoá mất câu
        # trả lời vừa rồi — chính là tin quan trọng nhất với context.
        self.client.ltrim(key, -HISTORY_MAX_MESSAGES, -1)
        # TTL: hội thoại không ai hỏi nữa sẽ tự biến mất. Không đặt TTL thì
        # Redis đầy dần theo thời gian và đến một lúc sập.
        self.client.expire(key, HISTORY_TTL_SECONDS)

    def get_history(self, user_id: str) -> list[dict]:
        """Đọc lịch sử hội thoại, cũ nhất trước.

        ``self.client.lrange(key, 0, -1)`` rồi ``json.loads``
        từng phần tử. Chưa có gì → trả về list rỗng.
        """
        raw = self.client.lrange(self._key(user_id), 0, -1)
        return [json.loads(item) for item in raw]

    def clear(self, user_id: str) -> None:
        """CHO SẴN — xóa lịch sử của một user."""
        self.client.delete(self._key(user_id))
