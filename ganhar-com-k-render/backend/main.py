import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
DB_PATH = os.getenv("DB_PATH", os.path.join(ROOT_DIR, "app.db"))

app = FastAPI(title="Ganhar com K - Fullstack (Render)")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wallet (
        user_id INTEGER PRIMARY KEY,
        saldo_disponivel REAL NOT NULL DEFAULT 0,
        saldo_bloqueado REAL NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_earnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        amount REAL NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        type_code TEXT NOT NULL DEFAULT 'TT',
        payout_amount REAL NOT NULL DEFAULT 0.01,
        opened_link INTEGER NOT NULL DEFAULT 0,
        opened_at TEXT,
        claimed_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        submitted_at TEXT,
        reviewed_at TEXT,
        validity TEXT NOT NULL DEFAULT 'pending',
        profile_username TEXT,
        action_tipo TEXT,
        action_target_url TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wallet_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        claim_id INTEGER,
        withdraw_id INTEGER,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS payout_profile (
        user_id INTEGER PRIMARY KEY,
        payout_method TEXT NOT NULL DEFAULT 'PIX',
        pix_key TEXT,
        pix_key_type TEXT,
        bank_name TEXT,
        agency TEXT,
        account TEXT,
        account_type TEXT,
        cpf TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS withdraw_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL,
        requested_at TEXT NOT NULL,
        processed_at TEXT,
        notes TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    conn.commit()

    cur.execute("SELECT id FROM users WHERE email = ?", ("demo@ganharcomk.local",))
    row = cur.fetchone()
    if not row:
        now = datetime.utcnow().isoformat()
        cur.execute("INSERT INTO users (name, email, created_at) VALUES (?,?,?)",
                    ("Marcos", "demo@ganharcomk.local", now))
        user_id = cur.lastrowid
        cur.execute("INSERT INTO wallet (user_id, saldo_disponivel, saldo_bloqueado, updated_at) VALUES (?,?,?,?)",
                    (user_id, 0.0, 0.0, now))
        cur.execute("INSERT INTO payout_profile (user_id, payout_method, cpf, updated_at) VALUES (?,?,?,?)",
                    (user_id, "PIX", "000.000.000-00", now))
        for i in range(10):
            d = (datetime.utcnow() - timedelta(days=9-i)).date().isoformat()
            cur.execute("INSERT INTO daily_earnings (user_id, date, amount) VALUES (?,?,?)", (user_id, d, 0.0))
        conn.commit()
    conn.close()

@app.on_event("startup")
def _startup():
    init_db()

class ActionItem(BaseModel):
    tipo: str
    target_url: str

class ActionsResponse(BaseModel):
    acoes: List[ActionItem]

class ActionsRequest(BaseModel):
    origem: str = "instagram"
    acao: str = "listar"
    claim_id: Optional[int] = None
    botao: Optional[str] = None

class ClaimCreateRequest(BaseModel):
    origem: str = "instagram"

class ClaimConfirmRequest(BaseModel):
    opened_link: bool = True
    opened_at: Optional[str] = None
    user_note: Optional[str] = None

class WithdrawRequestIn(BaseModel):
    amount: float = Field(..., gt=0)

def get_demo_user_id() -> int:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", ("demo@ganharcomk.local",))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(500, "Demo user not found")
    return int(row["id"])

@app.post("/api/acoes", response_model=ActionsResponse)
def list_actions(req: ActionsRequest):
    actions = [
        {"tipo": "seguir", "target_url": "https://www.instagram.com/instagram/"},
        {"tipo": "curtir", "target_url": "https://www.instagram.com/p/CxHc4y8x7oA/"},
    ]
    return {"acoes": actions}

@app.post("/api/claims")
def claim_create(req: ClaimCreateRequest):
    user_id = get_demo_user_id()
    now = datetime.utcnow()
    expires = now + timedelta(seconds=120)

    actions = list_actions(ActionsRequest(origem=req.origem, acao="listar")).get("acoes", [])
    if not actions:
        raise HTTPException(404, "Nenhuma ação disponível")

    action = actions[0]
    payout = 0.01

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO claims (user_id, status, payout_amount, claimed_at, expires_at, validity, action_tipo, action_target_url)
        VALUES (?,?,?,?,?,?,?,?)
    """, (user_id, "claimed", payout, now.isoformat(), expires.isoformat(), "pending", action["tipo"], action["target_url"]))
    claim_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"claim_id": claim_id, "expires_at": expires.isoformat(), "action": action}

@app.get("/api/claims/{claim_id}")
def claim_get(claim_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM claims WHERE id = ?", (claim_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Claim não encontrado")
    return dict(row)

@app.post("/api/claims/{claim_id}/opened")
def claim_opened(claim_id: int):
    now = datetime.utcnow().isoformat()
    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE claims SET opened_link = 1, opened_at = ? WHERE id = ?", (now, claim_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404, "Claim não encontrado")
    conn.commit()
    conn.close()
    return {"ok": True, "opened_at": now}

@app.post("/api/claims/{claim_id}/confirm")
def claim_confirm(claim_id: int, body: ClaimConfirmRequest):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM claims WHERE id = ?", (claim_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Claim não encontrado")

    status = row["status"]
    expires_at = datetime.fromisoformat(row["expires_at"])
    now = datetime.utcnow()

    if now >= expires_at:
        cur.execute("UPDATE claims SET status = 'expired' WHERE id = ?", (claim_id,))
        conn.commit()
        conn.close()
        raise HTTPException(400, "Tempo expirado")

    if status != "claimed":
        conn.close()
        raise HTTPException(400, f"Não pode confirmar no status: {status}")

    if not row["opened_link"] and not body.opened_link:
        conn.close()
        raise HTTPException(400, "Você precisa acessar o link antes de confirmar")

    payout = float(row["payout_amount"])
    submitted_at = now.isoformat()
    cur.execute("""
        UPDATE claims
        SET status='submitted', submitted_at=?, validity='pending'
        WHERE id=?
    """, (submitted_at, claim_id))

    cur.execute("SELECT saldo_bloqueado, saldo_disponivel FROM wallet WHERE user_id = ?", (row["user_id"],))
    w = cur.fetchone()
    if not w:
        conn.close()
        raise HTTPException(500, "Wallet não encontrada")

    new_blocked = float(w["saldo_bloqueado"]) + payout
    cur.execute("UPDATE wallet SET saldo_bloqueado=?, updated_at=? WHERE user_id=?",
                (new_blocked, submitted_at, row["user_id"]))

    cur.execute("""
        INSERT INTO wallet_transactions (user_id, claim_id, type, amount, description, created_at)
        VALUES (?,?,?,?,?,?)
    """, (row["user_id"], claim_id, "credit_blocked", payout, "Ação enviada para confirmação", submitted_at))

    conn.commit()
    conn.close()
    return {"ok": True, "status": "submitted"}

@app.get("/api/dashboard")
def dashboard():
    user_id = get_demo_user_id()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM users WHERE id=?", (user_id,))
    u = cur.fetchone()
    cur.execute("SELECT saldo_disponivel, saldo_bloqueado FROM wallet WHERE user_id=?", (user_id,))
    w = cur.fetchone()
    cur.execute("""
        SELECT date, amount FROM daily_earnings
        WHERE user_id=?
        ORDER BY date DESC
        LIMIT 14
    """, (user_id,))
    earnings = [dict(r) for r in cur.fetchall()][::-1]
    conn.close()
    return {
        "user": {"id": user_id, "name": u["name"] if u else "Usuário"},
        "wallet": {"saldo_disponivel": w["saldo_disponivel"] if w else 0.0, "saldo_bloqueado": w["saldo_bloqueado"] if w else 0.0},
        "daily_earnings": earnings,
    }

@app.get("/api/historico-acoes")
def historico_acoes(limit: int = 50, q: str = ""):
    user_id = get_demo_user_id()
    conn = db()
    cur = conn.cursor()
    query = """
        SELECT id, submitted_at, claimed_at, type_code, profile_username, payout_amount, validity, status
        FROM claims
        WHERE user_id=?
    """
    params = [user_id]
    if q.strip():
        query += " AND (CAST(id AS TEXT) LIKE ? OR COALESCE(profile_username,'') LIKE ? OR COALESCE(validity,'') LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    query += " ORDER BY COALESCE(submitted_at, claimed_at) DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"items": rows}

@app.get("/api/payout-profile")
def payout_profile():
    user_id = get_demo_user_id()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payout_profile WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {"user_id": user_id, "payout_method": "PIX", "cpf": ""}

@app.post("/api/payout-profile")
def payout_profile_update(body: Dict[str, Any]):
    user_id = get_demo_user_id()
    now = datetime.utcnow().isoformat()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM payout_profile WHERE user_id=?", (user_id,))
    exists = cur.fetchone() is not None

    fields = {
        "payout_method": body.get("payout_method", "PIX"),
        "pix_key": body.get("pix_key"),
        "pix_key_type": body.get("pix_key_type"),
        "bank_name": body.get("bank_name"),
        "agency": body.get("agency"),
        "account": body.get("account"),
        "account_type": body.get("account_type"),
        "cpf": body.get("cpf"),
        "updated_at": now,
    }

    if exists:
        cur.execute("""
            UPDATE payout_profile SET payout_method=?, pix_key=?, pix_key_type=?, bank_name=?, agency=?, account=?, account_type=?, cpf=?, updated_at=?
            WHERE user_id=?
        """, (fields["payout_method"], fields["pix_key"], fields["pix_key_type"], fields["bank_name"], fields["agency"], fields["account"],
              fields["account_type"], fields["cpf"], fields["updated_at"], user_id))
    else:
        cur.execute("""
            INSERT INTO payout_profile (user_id, payout_method, pix_key, pix_key_type, bank_name, agency, account, account_type, cpf, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (user_id, fields["payout_method"], fields["pix_key"], fields["pix_key_type"], fields["bank_name"], fields["agency"], fields["account"],
              fields["account_type"], fields["cpf"], fields["updated_at"]))

    conn.commit()
    conn.close()
    return {"ok": True}

@app.post("/api/withdraw")
def withdraw(body: WithdrawRequestIn):
    user_id = get_demo_user_id()
    amount = float(body.amount)
    min_withdraw = float(os.getenv("MIN_WITHDRAW", "5.0"))

    if amount < min_withdraw:
        raise HTTPException(400, f"Saque mínimo é R$ {min_withdraw:.2f}")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT saldo_disponivel FROM wallet WHERE user_id=?", (user_id,))
    w = cur.fetchone()
    if not w:
        conn.close()
        raise HTTPException(500, "Wallet não encontrada")

    saldo = float(w["saldo_disponivel"])
    if amount > saldo:
        conn.close()
        raise HTTPException(400, "Saldo insuficiente")

    now = datetime.utcnow().isoformat()
    cur.execute("""
        INSERT INTO withdraw_requests (user_id, amount, status, requested_at)
        VALUES (?,?,?,?)
    """, (user_id, amount, "requested", now))
    wid = cur.lastrowid

    new_saldo = saldo - amount
    cur.execute("UPDATE wallet SET saldo_disponivel=?, updated_at=? WHERE user_id=?", (new_saldo, now, user_id))

    cur.execute("""
        INSERT INTO wallet_transactions (user_id, withdraw_id, type, amount, description, created_at)
        VALUES (?,?,?,?,?,?)
    """, (user_id, wid, "debit", amount, "Solicitação de saque", now))

    conn.commit()
    conn.close()
    return {"ok": True, "withdraw_id": wid}

@app.get("/api/withdraws")
def withdraws():
    user_id = get_demo_user_id()
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, amount, status, requested_at, processed_at FROM withdraw_requests
        WHERE user_id=?
        ORDER BY requested_at DESC
        LIMIT 100
    """, (user_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"items": rows}

app.mount("/static", StaticFiles(directory=os.path.join(ROOT_DIR, "static"), html=True), name="static")

@app.get("/")
def index():
    return FileResponse(os.path.join(ROOT_DIR, "static", "index.html"))

@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    return FileResponse(os.path.join(ROOT_DIR, "static", "index.html"))

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})
