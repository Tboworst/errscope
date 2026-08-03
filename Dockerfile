# Stage 1: build the React dashboard
FROM node:20-alpine AS web-builder

WORKDIR /web

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# Stage 2: Python ingest server
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Overlay the freshly built dashboard (overrides any stale local web/dist)
COPY --from=web-builder /web/dist ./web/dist

EXPOSE 7000

CMD ["python3", "start_server.py"]
