FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY templates ./templates
COPY static ./static
COPY uploads/.gitkeep ./uploads/.gitkeep

ENV PYTHONUNBUFFERED=1
ENV UPLOAD_DIR=/data/uploads
ENV PORT=8000

RUN mkdir -p /data/uploads

EXPOSE 8000

CMD gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 90
