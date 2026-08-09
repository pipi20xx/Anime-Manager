# --- Stage 1: Frontend Build ---
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
# 删除 lock 文件以避免 npm 可选依赖跨架构 bug (npm/cli#4828)
# 锁文件在 x64 上生成时不含 arm64 的 @rolldown/binding 原生包
RUN rm -f package-lock.json && \
    npm config set registry https://repo.huaweicloud.com/repository/npm/ && \
    npm install --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

# Extract version from package.json
RUN sed -n 's/.*"version"\s*:\s*"\([^"]*\)".*/\1/p' package.json > /app/VERSION

# --- Stage 2: Backend & Final Image ---
FROM python:3.11-slim
WORKDIR /app

# 使用阿里云镜像源（更快）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY backend/ .

COPY skills/ ./skills/

RUN chmod +x entrypoint.sh

COPY --from=frontend-builder /app/frontend/dist ./dist

# Copy version file from Stage 1
COPY --from=frontend-builder /app/VERSION ./VERSION

RUN mkdir -p data

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
