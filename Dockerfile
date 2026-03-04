# --- Stage 1: Frontend Build ---
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
# 设置 npm 国内镜像源并允许忽略 peer 依赖冲突
RUN npm config set registry https://registry.npmmirror.com && \
    npm install --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Backend & Final Image ---
FROM python:3.11-slim
WORKDIR /app

# 替换 APT 源为清华大学镜像源并安装必要库
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies (使用清华源加速)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy backend code
COPY backend/ .

# 给启动脚本执行权限
RUN chmod +x entrypoint.sh

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./dist

# Create data directory
RUN mkdir -p data

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
