# khasa-sandbox: контейнер-песочница для агента.
# Внутри: python, node, базовые утилиты. Запуск под непривилегированным
# юзером uid 10001 (sandbox). Без сети наружу (управляется docker network).

FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Базовые инструменты + python + node
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        wget \
        git \
        unzip \
        zip \
        jq \
        ripgrep \
        less \
        vim-tiny \
        python3 \
        python3-pip \
        python3-venv \
        nodejs \
        npm \
        build-essential \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Полезные python-пакеты в системном venv
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir \
        requests \
        httpx \
        beautifulsoup4 \
        lxml \
        pyyaml \
        pandas \
        numpy \
        matplotlib \
        pillow \
        rich

ENV PATH="/opt/venv/bin:${PATH}"

# Создаём непривилегированного юзера
RUN groupadd -g 10001 sandbox && \
    useradd -u 10001 -g 10001 -m -s /bin/bash sandbox

# Workspace
RUN mkdir -p /workspace && chown -R 10001:10001 /workspace
WORKDIR /workspace

USER 10001:10001
ENV HOME=/workspace

# tini как PID 1 — корректно обрабатывает сигналы (важно для docker stop)
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "tail -f /dev/null"]
