mkdir -p fastapi-ping-service
cat > fastapi-ping-service/main.py <<'PY'
from fastapi import FastAPI

app = FastAPI(title="Ping Service")


@app.get("/ping")
def ping():
    return {"message": "pong"}
PY
cat > fastapi-ping-service/requirements.txt <<'REQ'
fastapi==0.115.6
uvicorn[standard]==0.34.0
REQ
cat > fastapi-ping-service/README.md <<'MD'
# FastAPI Ping Service

Минимальный сервис на FastAPI с одной ручкой `GET /ping`.

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Проверка

```bash
curl http://localhost:8000/ping
```

Ответ:

```json
{"message":"pong"}
```
MD
zip -r fastapi-ping-service.zip fastapi-ping-service >/dev/null
ls -la fastapi-ping-service.zip
[exit 0]
--- stdout ---
-rw-r--r-- 1 sandbox sandbox 1189 May 15 04:14 fastapi-ping-service.zip

⌗
present_files
· Архив с минимальным FastAPI-сервисом и ручкой GET /ping
▾
// input
{
  "paths": [
    "fastapi-ping-service.zip"
  ],
  "caption": "Архив с минимальным FastAPI-сервисом и ручкой GET /ping"
}
// output
ERROR: ни один файл не найден в /workspace. Проверил пути: fastapi-ping-service.zip. Подсказка: пути должны быть относительно /workspace без ведущего /. Используй list_directory чтобы посмотреть актуальные имена.

⌗
list_directory
· .
▾
// input
{
  "path": "."
}
// output
total 16
drwxr-xr-x 3 sandbox sandbox  120 May 15 04:14 .
drwxr-xr-x 1 root    root    4096 May 15 04:00 ..
drwxr-xr-x 2 sandbox sandbox  100 May 15 04:14 fastapi-ping-service
-rw-r--r-- 1 sandbox sandbox 1189 May 15 04:14 fastapi-ping-service.zip
-rw-r--r-- 1 sandbox sandbox 1189 May 15 04:01 ping-service.zip
-rw-r--r-- 1 sandbox sandbox 1464 May 15 04:02 ping.zip

⌗
bash
· set -e cp -f fastapi-ping-service.zip ping-service-fastapi.z…
▾
// input
{
  "command": "set -e\ncp -f fastapi-ping-service.zip ping-service-fastapi.zip\npython3 - <<'PY'\nfrom pathlib import Path\nfor p in ['fastapi-ping-service.zip','ping-service-fastapi.zip']:\n    print(p, Path(p).exists(), Path(p).stat().st_size if Path(p).exists() else None)\nPY",
  "timeout_seconds": 60
}
// output
$ set -e
cp -f fastapi-ping-service.zip ping-service-fastapi.zip
python3 - <<'PY'
from pathlib import Path
for p in ['fastapi-ping-service.zip','ping-service-fastapi.zip']:
    print(p, Path(p).exists(), Path(p).stat().st_size if Path(p).exists() else None)
PY
[exit 0]
--- stdout ---
fastapi-ping-service.zip True 1189
ping-service-fastapi.zip True 1189

⌗
present_files
· Архив с FastAPI ping-сервисом
▾
// input
{
  "paths": [
    "ping-service-fastapi.zip"
  ],
  "caption": "Архив с FastAPI ping-сервисом"
}
// output
ERROR: ни один файл не найден в /workspace. Проверил пути: ping-service-fastapi.zip. Подсказка: пути должны быть относительно /workspace без ведущего /. Используй list_directory чтобы посмотреть актуальные имена.