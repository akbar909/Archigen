FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend
COPY blender/metadata/ ./blender/metadata/
COPY blender/asset-audit.json ./blender/asset-audit.json

ENV PYTHONUNBUFFERED=1
ENV PORT=7860

WORKDIR /app/backend

CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]
