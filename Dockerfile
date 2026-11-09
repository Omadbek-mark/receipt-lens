FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/scanner \
    SCANNER_DB_PATH=/app/data/expenses.sqlite3 \
    OMP_NUM_THREADS=2

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 scanner \
    && useradd --uid 10001 --gid scanner --create-home scanner
WORKDIR /app
COPY deploy/requirements-linux.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt && python -m pip check
COPY --chown=scanner:scanner app.py pyproject.toml ./
COPY --chown=scanner:scanner scanner/ ./scanner/
COPY --chown=scanner:scanner samples/ ./samples/
COPY --chown=scanner:scanner .streamlit/config.toml ./.streamlit/config.toml
COPY --chown=scanner:scanner deploy/offsite-backup.sh ./deploy/offsite-backup.sh
RUN mkdir -p /app/data && chown -R scanner:scanner /app/data /home/scanner
USER scanner
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
