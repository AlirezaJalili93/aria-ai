FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /srv/aria

COPY packages/observability ./packages/observability
COPY apps/worker/pyproject.toml apps/worker/uv.lock ./apps/worker/

RUN python -m pip install --no-cache-dir uv==0.12.5 \
    && uv sync --project apps/worker --locked --no-dev

COPY apps/worker/app ./apps/worker/app

RUN useradd --create-home --uid 10001 aria \
    && chown -R aria:aria /srv/aria

USER aria

WORKDIR /srv/aria/apps/worker

CMD ["uv", "run", "--project", "/srv/aria/apps/worker", "--no-sync", "python", "-m", "app.main"]
