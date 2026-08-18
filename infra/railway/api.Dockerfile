FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /srv/aria

COPY packages/observability ./packages/observability
COPY apps/api/pyproject.toml apps/api/uv.lock ./apps/api/

RUN python -m pip install --no-cache-dir uv==0.12.5 \
    && uv sync --project apps/api --locked --no-dev

COPY apps/api/app ./apps/api/app

RUN useradd --create-home --uid 10001 aria \
    && chown -R aria:aria /srv/aria

USER aria

EXPOSE 8080

CMD ["sh", "-c", "exec uv run --project apps/api --no-sync uvicorn app.main:create_app --factory --app-dir apps/api --host 0.0.0.0 --port ${PORT:-8080}"]
