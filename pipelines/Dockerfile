FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    MLFLOW_DISABLE_AGENT_HINT=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY configs ./configs
COPY data ./data
COPY training ./training
COPY registry ./registry

RUN groupadd --system app && useradd --system --gid app --create-home app
USER app

ENTRYPOINT ["python", "-m"]
CMD ["training.train", "--data", "s3://datasets/raw/creditcard.parquet"]
