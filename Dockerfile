# --- Stage 1: Frontend Build ---
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm config set registry https://registry.npmmirror.com && \
    npm install --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

# Extract version from version.ts
RUN sed -n "s/.*APP_VERSION\s*=\s*['\"]\([^'\"]*\).*/\1/p" src/version.ts > /app/VERSION

# --- Stage 2: Backend & Final Image ---
FROM python:3.11-slim
WORKDIR /app

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY backend/ .

RUN chmod +x entrypoint.sh

COPY --from=frontend-builder /app/frontend/dist ./dist

# Copy version file from Stage 1
COPY --from=frontend-builder /app/VERSION ./VERSION

RUN mkdir -p data

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
