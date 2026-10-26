FROM python:3.12-slim

RUN pip install --no-cache-dir \
        mlflow==3.17.2 \
        "psycopg[binary]==3.3.6" \
        boto3==1.43.118 \
    && useradd --create-home --uid 10001 mlflow

USER mlflow
WORKDIR /home/mlflow

ENV MLFLOW_HOST=0.0.0.0 \
    MLFLOW_PORT=5000 \
    MLFLOW_SERVE_ARTIFACTS=true \
    PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=4)"

ENTRYPOINT ["mlflow", "server"]
