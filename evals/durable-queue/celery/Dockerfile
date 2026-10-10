FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /experiment

COPY pyproject.toml uv.lock ./

RUN python -m pip install --no-cache-dir uv==0.12.5 \
    && uv sync --locked --no-dev

COPY queue_eval ./queue_eval

RUN useradd --create-home --uid 10001 queueeval \
    && chown -R queueeval:queueeval /experiment

USER queueeval

ENV PATH="/experiment/.venv/bin:${PATH}"

CMD ["python", "-m", "queue_eval.cli", "--help"]
