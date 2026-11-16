FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Cài thư viện trước (tận dụng cache khi chỉ sửa code)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# /data/enrich-raw: bản gốc làm giàu dữ liệu MST khi không dùng R2 (volume enrichraw trong docker-compose)
RUN useradd --system --uid 10001 app \
    && mkdir -p /data/enrich-raw && chown app /data/enrich-raw
USER app

EXPOSE 8000
# Mặc định chạy API; worker/beat/migrate ghi đè lệnh trong docker-compose.yml
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
