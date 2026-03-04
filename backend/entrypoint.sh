#!/bin/bash
set -e

if [ -n "$TZ" ]; then
    echo "[系统] 设置时区为 $TZ"
fi

export PYTHONPATH="${PYTHONPATH}:/app/data/ai"

echo "[系统] 启动番剧管家服务..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --loop uvloop --http httptools