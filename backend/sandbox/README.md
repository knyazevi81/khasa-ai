# khasa-sandbox

Образ контейнера-песочницы для агентного режима. Внутри:
- Debian bookworm slim
- Python 3 + venv с requests/httpx/pandas/numpy/matplotlib/pillow/rich
- Node.js + npm
- git, jq, ripgrep, curl, wget, zip/unzip
- Запуск под uid/gid 10001 (sandbox), workspace в `/workspace`

## Сборка

```bash
docker build -t khasa-sandbox:latest backend/sandbox/
```

Автоматически собирается в `make sandbox-build`.

## Безопасность

- Непривилегированный юзер (uid 10001)
- `no-new-privileges` capability
- Ограничения CPU/memory/pids (задаются при `docker run` из бэкенда)
- Отдельная docker-network `khasa_sandbox_net` (изолирована от других сервисов)
- Bind-mount только `/workspace` хоста — никакого `docker.sock` внутрь

## Что НЕ делает образ

- Не настраивает firewall выхода в интернет — это можно сделать через
  `--network=none` или iptables rules на хосте, для MVP оставлено как есть
- Не пресетит конфиги — это задача `bash`-tool агента
