# ═══════════════════════════════════════════════════════════════════
# CP2 — Containerization
#
# Bản production-ready: multi-stage, non-root, có healthcheck, đọc $PORT.
#
# Kiểm tra:  pytest tests/test_cp2.py -v
# Build thử: docker build -t day12-agent:prod .
#            docker images day12-agent:prod     # xem dung lượng
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: builder ────────────────────────────────────────────
# Stage này được phép nặng: cài build-essential để biên dịch các
# package cần, rồi bị vứt đi hoàn toàn ở stage sau.
FROM python:3.11-slim AS builder

# Không cài vào hệ thống file thật, mà vào /install để copy sang
# stage runtime. Nhờ vậy stage runtime không phải mang theo compiler.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# COPY requirements.txt TRƯỚC, pip install SAU. Docker cache theo từng
# layer và huỷ cache từ layer đầu tiên thay đổi đi, nên sửa một dấu
# phẩy trong app/ sẽ không làm Docker cài lại toàn bộ thư viện.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ───────────────────────────────────────────
# Chỉ stage này trở thành image cuối cùng. Base slim, không compiler,
# không apt cache, không thư mục build.
FROM python:3.11-slim AS runtime

# Không dùng apt ở đây → không cần giữ cache gói. Biến môi trường
# PYTHONDONTWRITEBYTECODE/UNBUFFERED để stdout của uvicorn tới thẳng
# log collector của cloud thay vì bị đệm trong container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:${PATH}"

# COPY --from=builder: chỉ lấy phần đã cài, không lấy build-essential.
COPY --from=builder /install /usr/local

WORKDIR /app

# Source copy sau pip install (xem giải thích ở stage builder).
COPY app ./app
COPY utils ./utils

# User thường: container chạy root nghĩa là ai thoát được khỏi app
# cũng thành root trên host. UID cố định 10001 cho dễ nhận biết khi
# xem `docker compose top` hay log của orchestrator.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness probe ngay trong image. Dùng python sẵn có trong image thay
# vì curl (để image nhỏ hơn), và truy cập 127.0.0.1 vì probe chạy
# BÊN TRONG container.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT:-8000}/health').read()" || exit 1

# 0.0.0.0 chứ không phải 127.0.0.1: bind vào localhost thì bên ngoài
# container không gọi vào được. ${PORT:-8000} vì Railway/Render/Cloud Run
# tự gán PORT — cố định 8000 thì health check trên cloud timeout.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
