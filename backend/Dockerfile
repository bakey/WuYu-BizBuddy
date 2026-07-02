# BizBuddy RAG 服务镜像
# 说明：bge-m3 模型不打进镜像，运行时用 -v 挂载；torch 用 CPU 版以控制体积。
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 国内镜像加速 pip + 加大超时/重试
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com \
    && pip config set global.timeout 120 \
    && pip config set global.retries 10

# torch 运行时需要 libgomp1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/postgresql/lists/*

WORKDIR /app

# 先装 CPU 版 torch
RUN pip install --no-cache-dir torch \
    --index-url https://mirrors.aliyun.com/pytorch-wheels/cpu/ \
    --extra-index-url https://mirrors.aliyun.com/pypi/simple/

# 再装其余依赖（torch 已满足，不会重复拉取）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝源码与迁移脚本
COPY src ./src
COPY migrations ./migrations

ENV PYTHONPATH=/app/src
EXPOSE 8200

CMD ["python", "-m", "uvicorn", "bizbuddy_rag.main:app", "--host", "0.0.0.0", "--port", "8200"]
