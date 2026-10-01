# --- Stage 1: Frontend Build ---
# 基础镜像缓存（内网 registry:2 pull-through 代理）；内网外构建时用 --build-arg 覆盖：
#   --build-arg BASE_PREFIX=    （置空即走官方 Docker Hub）
ARG BASE_PREFIX=192.168.50.12:5000/library/
FROM ${BASE_PREFIX}node:22-alpine AS frontend-builder
# npm 包缓存（内网 Verdaccio 只读代理）；内网外构建时用 --build-arg 覆盖
ARG NPM_REGISTRY=http://192.168.50.12:4873
WORKDIR /app/frontend
COPY frontend/package*.json ./
# 删除 lock 文件以避免 npm 可选依赖跨架构 bug (npm/cli#4828)
# 锁文件在 x64 上生成时不含 arm64 的 @rolldown/binding 原生包
RUN rm -f package-lock.json && \
    npm config set registry ${NPM_REGISTRY} && \
    npm install --legacy-peer-deps \
        --fetch-retries=5 \
        --fetch-retry-mintimeout=20000 \
        --fetch-retry-maxtimeout=120000 \
        --fetch-timeout=300000
COPY frontend/ ./
RUN npm run build

# Extract version from package.json
RUN sed -n 's/.*"version"\s*:\s*"\([^"]*\)".*/\1/p' package.json > /app/VERSION

# --- Stage 2: Backend & Final Image ---
FROM ${BASE_PREFIX}python:3.11-slim
# pip 包缓存（内网 devpi 只读代理，http 地址必须配 trusted-host）；
# 内网外构建时用 --build-arg 覆盖
ARG PIP_INDEX_URL=http://192.168.50.12:3141/root/pypi/+simple
ARG PIP_TRUSTED_HOST=192.168.50.12
WORKDIR /app

# 使用阿里云镜像源（更快）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i ${PIP_INDEX_URL} --trusted-host ${PIP_TRUSTED_HOST}

COPY backend/ .

COPY skills/ ./skills/

RUN chmod +x entrypoint.sh

COPY --from=frontend-builder /app/frontend/dist ./dist

# Copy version file from Stage 1
COPY --from=frontend-builder /app/VERSION ./VERSION

RUN mkdir -p data

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
