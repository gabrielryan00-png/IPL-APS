"""
gateway.py — IPL-APS Gateway Municipal
FastAPI + JWT + isolamento por USF

Uso:
    python gateway.py              # porta 8080
    PORT=443 python gateway.py     # com TLS configurado no nginx

Roles:
    admin  → acessa todos os territórios, gerencia usuários e USFs
    user   → acessa somente seu usf_id
"""

import os, sqlite3, sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt as _bcrypt
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ─── Configuração ────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("JWT_SECRET_KEY", "TROQUE_ISSO_NO_.ENV")
ALGORITHM    = os.getenv("JWT_ALGORITHM",  "HS256")
EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "10"))
AUTH_DB      = os.getenv("AUTH_DB",  "auth.db")
DATA_DIR     = os.getenv("DATA_DIR", "/home/drelima/exames")
HTML_FILE    = os.path.join(DATA_DIR, "iclabs_v5.html")

def _hash_pw(s: str) -> str:
    return _bcrypt.hashpw(s.encode(), _bcrypt.gensalt(12)).decode()

def _verify_pw(s: str, h: str) -> bool:
    return _bcrypt.checkpw(s.encode(), h.encode())
bearer   = HTTPBearer(auto_error=False)

# ─── FastAPI ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="IPL-APS Gateway",
    description="Sistema de Prioridade Laboratorial — Rede Municipal Suzano",
    version="2.0",
    docs_url="/docs",       # Swagger UI (desativar em prod: docs_url=None)
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # em prod: restringir ao domínio municipal
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Helpers de banco ────────────────────────────────────────────────────────
def _auth_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(AUTH_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _get_usuario(username: str) -> Optional[sqlite3.Row]:
    with _auth_conn() as conn:
        return conn.execute(
            "SELECT * FROM usuarios WHERE username=? AND ativo=1", (username,)
        ).fetchone()


def _get_usf(usf_id: str) -> Optional[sqlite3.Row]:
    with _auth_conn() as conn:
        return conn.execute(
            "SELECT * FROM usfs WHERE id=?", (usf_id,)
        ).fetchone()


def _log_acesso(usuario_id: int, usf_id: str, ip: str, acao: str) -> None:
    try:
        with _auth_conn() as conn:
            conn.execute(
                "INSERT INTO sessoes_log (usuario_id, usf_id, ip, acao) VALUES (?,?,?,?)",
                (usuario_id, usf_id or "", ip, acao)
            )
            conn.execute(
                "UPDATE usuarios SET ultimo_login=datetime('now','localtime') WHERE id=?",
                (usuario_id,)
            )
    except Exception:
        pass


# ─── JWT ─────────────────────────────────────────────────────────────────────
def _criar_token(username: str, role: str, usf_id: Optional[str]) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    payload = {
        "sub":    username,
        "role":   role,
        "usf_id": usf_id,
        "exp":    exp,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _verificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Dependências de autenticação ────────────────────────────────────────────
async def _token_payload(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    return _verificar_token(creds.credentials)


async def _requer_admin(payload: dict = Depends(_token_payload)) -> dict:
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return payload


# ─── Models ──────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class AlterarSenhaRequest(BaseModel):
    senha_atual:  str
    senha_nova:   str


class NovoUsuarioRequest(BaseModel):
    username:      str
    password:      str
    nome_completo: str = ""
    usf_id:        str


# ─── Rotas públicas ──────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, tags=["Interface"])
async def dashboard():
    """Serve o dashboard HTML. O JS interno gerencia login via JWT."""
    if not os.path.exists(HTML_FILE):
        return HTMLResponse("<h2>iclabs_v5.html não encontrado.</h2>", status_code=404)
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/api/login", tags=["Autenticação"])
async def login(body: LoginRequest, request: Request):
    """
    Autentica usuário e retorna JWT.

    Resposta:
    - `token`: Bearer token (10h)
    - `role`: 'admin' | 'user'
    - `usf_id`: ID da USF do usuário (null para admin)
    - `usfs`: lista de USFs acessíveis
    """
    user = _get_usuario(body.username)
    if not user or not _verify_pw(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    role   = user["role"]
    usf_id = user["usf_id"]
    token  = _criar_token(body.username, role, usf_id)

    # Monta lista de USFs acessíveis
    with _auth_conn() as conn:
        if role == "admin":
            usfs = conn.execute(
                "SELECT id, nome, cnes, ativa FROM usfs ORDER BY nome"
            ).fetchall()
        else:
            usfs = conn.execute(
                "SELECT id, nome, cnes, ativa FROM usfs WHERE id=?", (usf_id,)
            ).fetchall()

    usfs_list = [dict(u) for u in usfs]

    _log_acesso(user["id"], usf_id, request.client.host, "LOGIN")

    return {
        "token":         token,
        "role":          role,
        "usf_id":        usf_id,
        "username":      body.username,
        "nome_completo": user["nome_completo"],
        "usfs":          usfs_list,
        "expires_in":    EXPIRE_HOURS * 3600,
    }


@app.get("/api/me", tags=["Autenticação"])
async def me(payload: dict = Depends(_token_payload)):
    """Retorna informações do usuário autenticado."""
    return {
        "username": payload["sub"],
        "role":     payload["role"],
        "usf_id":   payload.get("usf_id"),
    }


# ─── Rotas de território ─────────────────────────────────────────────────────
@app.get("/api/territorio/{usf_id}", tags=["Território"])
async def get_territorio(
    usf_id:  str,
    request: Request,
    payload: dict = Depends(_token_payload),
):
    """
    Retorna dados do território (pacientes, IPL, vigilância) para uma USF.

    - **admin**: pode acessar qualquer usf_id
    - **user**: só acessa seu próprio usf_id
    """
    role         = payload["role"]
    user_usf_id  = payload.get("usf_id")

    # Autorização: usuário comum só vê seu território
    if role != "admin" and user_usf_id != usf_id:
        raise HTTPException(status_code=403, detail="Acesso negado a este território")

    usf = _get_usf(usf_id)
    if not usf:
        raise HTTPException(status_code=404, detail=f"USF '{usf_id}' não encontrada")

    if not usf["ativa"] and role != "admin":
        raise HTTPException(status_code=423, detail="Território ainda sem dados")

    db_path = usf["db_path"]
    if not os.path.exists(db_path):
        # USF cadastrada mas banco ainda não existe — retorna estrutura vazia
        return {
            "id":         usf_id,
            "nome":       usf["nome"],
            "pacientes":  [],
            "vigilancia": [],
            "sem_dados":  True,
        }

    # Importa engine com contexto isolado por requisição
    sys.path.insert(0, DATA_DIR)
    from ipl_engine import calcular_territorio

    dados = calcular_territorio(db_path=db_path)
    dados["nome_usf"]  = usf["nome"]
    dados["cnes"]      = usf["cnes"]
    dados["usf_id"]    = usf_id
    dados["sem_dados"] = False

    _log_acesso(
        _get_usuario(payload["sub"])["id"],
        usf_id,
        request.client.host,
        f"GET_TERRITORIO:{usf_id}"
    )

    return dados


@app.get("/api/usfs", tags=["Território"])
async def listar_usfs(payload: dict = Depends(_token_payload)):
    """
    Lista USFs acessíveis ao usuário autenticado.
    - Admin vê todas.
    - User vê apenas a própria.
    """
    with _auth_conn() as conn:
        if payload["role"] == "admin":
            rows = conn.execute(
                "SELECT id, nome, cnes, ativa FROM usfs ORDER BY nome"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, nome, cnes, ativa FROM usfs WHERE id=?",
                (payload.get("usf_id"),)
            ).fetchall()
    return [dict(r) for r in rows]


# ─── Rotas admin ─────────────────────────────────────────────────────────────
@app.get("/api/admin/usuarios", tags=["Admin"])
async def listar_usuarios(payload: dict = Depends(_requer_admin)):
    """Lista todos os usuários (admin apenas)."""
    with _auth_conn() as conn:
        rows = conn.execute("""
            SELECT u.id, u.username, u.nome_completo, u.role,
                   u.usf_id, s.nome AS usf_nome, u.ativo, u.ultimo_login
            FROM usuarios u
            LEFT JOIN usfs s ON u.usf_id = s.id
            ORDER BY u.role DESC, u.username
        """).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/admin/usuarios", tags=["Admin"], status_code=201)
async def criar_usuario(
    body:    NovoUsuarioRequest,
    payload: dict = Depends(_requer_admin),
):
    """Cria novo usuário vinculado a uma USF (admin apenas)."""
    usf = _get_usf(body.usf_id)
    if not usf:
        raise HTTPException(status_code=404, detail=f"USF '{body.usf_id}' não existe")
    h = _hash_pw(body.password)
    try:
        with _auth_conn() as conn:
            conn.execute("""
                INSERT INTO usuarios (username, password_hash, nome_completo, role, usf_id)
                VALUES (?, ?, ?, 'user', ?)
            """, (body.username, h, body.nome_completo, body.usf_id))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username já existe")
    return {"ok": True, "username": body.username, "usf_id": body.usf_id}


@app.delete("/api/admin/usuarios/{username}", tags=["Admin"])
async def desativar_usuario(
    username: str,
    payload:  dict = Depends(_requer_admin),
):
    """Desativa usuário (soft-delete) — admin apenas."""
    if username == "ryan.nascimento":
        raise HTTPException(status_code=400, detail="Não é possível desativar o admin")
    with _auth_conn() as conn:
        conn.execute(
            "UPDATE usuarios SET ativo=0 WHERE username=?", (username,)
        )
    return {"ok": True}


@app.get("/api/admin/log", tags=["Admin"])
async def log_acessos(
    limit:   int  = 100,
    payload: dict = Depends(_requer_admin),
):
    """Últimos acessos ao sistema (admin apenas)."""
    with _auth_conn() as conn:
        rows = conn.execute("""
            SELECT l.momento, u.username, l.usf_id, l.ip, l.acao
            FROM sessoes_log l
            JOIN usuarios u ON l.usuario_id = u.id
            ORDER BY l.momento DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.put("/api/admin/usfs/{usf_id}/ativar", tags=["Admin"])
async def ativar_usf(
    usf_id:  str,
    payload: dict = Depends(_requer_admin),
):
    """Ativa ou desativa uma USF. Quando ativada, o db_path precisa existir."""
    usf = _get_usf(usf_id)
    if not usf:
        raise HTTPException(status_code=404, detail="USF não encontrada")
    nova_ativa = 0 if usf["ativa"] else 1
    if nova_ativa and not os.path.exists(usf["db_path"]):
        raise HTTPException(
            status_code=422,
            detail=f"db_path não existe: {usf['db_path']}"
        )
    with _auth_conn() as conn:
        conn.execute("UPDATE usfs SET ativa=? WHERE id=?", (nova_ativa, usf_id))
    return {"ok": True, "usf_id": usf_id, "ativa": bool(nova_ativa)}


# ─── Alteração de senha (qualquer usuário autenticado) ───────────────────────
@app.put("/api/alterar-senha", tags=["Autenticação"])
async def alterar_senha(
    body:    AlterarSenhaRequest,
    payload: dict = Depends(_token_payload),
):
    """Usuário altera a própria senha."""
    user = _get_usuario(payload["sub"])
    if not _verify_pw(body.senha_atual, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    if len(body.senha_nova) < 8:
        raise HTTPException(status_code=400, detail="Senha nova deve ter ao menos 8 caracteres")
    h = _hash_pw(body.senha_nova)
    with _auth_conn() as conn:
        conn.execute(
            "UPDATE usuarios SET password_hash=? WHERE username=?",
            (h, payload["sub"])
        )
    return {"ok": True}


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    print(f"\n  IPL-APS Gateway iniciando em http://0.0.0.0:{port}")
    print(f"  Swagger UI: http://0.0.0.0:{port}/docs\n")
    uvicorn.run(
        "gateway:app",
        host="0.0.0.0",
        port=port,
        reload=False,           # True apenas em desenvolvimento
        workers=2,
    )
