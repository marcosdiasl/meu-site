# Ganhar com K (projeto pronto para Render)

Este projeto é um fullstack simples (Frontend + API) em FastAPI:
- Frontend: `static/` (SPA simples em HTML/CSS/JS)
- Backend: `backend/main.py` (FastAPI + SQLite)

## Rodar local (Windows)
1) Instale Python 3.10+
2) Abra o terminal dentro da pasta do projeto e rode:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 10000
```

Abra: http://127.0.0.1:10000

## Deploy no Render (Web Service)
1) Suba esta pasta para um repositório no GitHub
2) Render -> New + -> Web Service
3) Selecione o repo
4) Configure:

**Build Command**
```bash
pip install -r requirements.txt
```

**Start Command**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

## API de ações (formato solicitado)
Endpoint:
- POST `/api/acoes`

Retorna:
```json
{
  "acoes": [
    {"tipo":"seguir","target_url":"https://..."},
    {"tipo":"curtir","target_url":"https://..."}
  ]
}
```

> Troque a lógica em `backend/main.py` para buscar ações reais do seu sistema.
