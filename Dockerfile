FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --chown=10001:10001 requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=10001:10001 main.py data.json ./

USER 10001:10001

CMD ["python", "main.py"]
