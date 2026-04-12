"""
setup_auth.py — Inicializa auth.db com USFs, admin e usuários por território.

Uso:
    python setup_auth.py            # cria/recria tudo
    python setup_auth.py --reset    # apaga e recria
    python setup_auth.py --add-user # modo interativo para adicionar usuário

Executar UMA VEZ antes de iniciar o gateway.
"""

import sqlite3, os, sys, getpass
import bcrypt as _bcrypt
from dotenv import load_dotenv

load_dotenv()

AUTH_DB  = os.getenv("AUTH_DB",  "auth.db")
DATA_DIR = os.getenv("DATA_DIR", "/home/drelima/exames")

def _hash(senha: str) -> str:
    return _bcrypt.hashpw(senha.encode(), _bcrypt.gensalt(12)).decode()

def _verify(senha: str, hashed: str) -> bool:
    return _bcrypt.checkpw(senha.encode(), hashed.encode())

# ─────────────────────────────────────────────────────────────────────────────
# 12 USFs do município — edite nomes/CNES conforme necessário
# db_path: caminho absoluto do banco SQLite de cada USF
# ─────────────────────────────────────────────────────────────────────────────
USFs = [
    {
        "id":       "usf_vila_amorim",
        "nome":     "USF VILA AMORIM",
        "cnes":     "0086185",
        "db_path":  os.path.join(DATA_DIR, "exames.db"),   # banco já existente
        "ativa":    True,
    },
    {
        "id":       "usf_central",
        "nome":     "USF CENTRAL",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_central", "exames.db"),
        "ativa":    False,   # sem dados ainda
    },
    {
        "id":       "usf_jardim_gardenia",
        "nome":     "USF JARDIM GARDÊNIA",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_jardim_gardenia", "exames.db"),
        "ativa":    False,
    },
    {
        "id":       "usf_jardim_imperador",
        "nome":     "USF JARDIM IMPERADOR",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_jardim_imperador", "exames.db"),
        "ativa":    False,
    },
    {
        "id":       "usf_sertaozinho",
        "nome":     "USF SERTÃOZINHO",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_sertaozinho", "exames.db"),
        "ativa":    False,
    },
    {
        "id":       "usf_palmeiras",
        "nome":     "USF PALMEIRAS",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_palmeiras", "exames.db"),
        "ativa":    False,
    },
    {
        "id":       "usf_nova_veneza",
        "nome":     "USF NOVA VENEZA",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_nova_veneza", "exames.db"),
        "ativa":    False,
    },
    {
        "id":       "usf_alto_tiete",
        "nome":     "USF ALTO TIETÊ",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_alto_tiete", "exames.db"),
        "ativa":    False,
    },
    {
        "id":       "usf_pimentas",
        "nome":     "USF PIMENTAS",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_pimentas", "exames.db"),
        "ativa":    False,
    },
    {
        "id":       "usf_tres_pontes",
        "nome":     "USF TRÊS PONTES",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_tres_pontes", "exames.db"),
        "ativa":    False,
    },
    {
        "id":       "usf_santa_rosa",
        "nome":     "USF PARQUE SANTA ROSA",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_santa_rosa", "exames.db"),
        "ativa":    False,
    },
    {
        "id":       "usf_jardim_leblon",
        "nome":     "USF JARDIM LEBLON",
        "cnes":     "",
        "db_path":  os.path.join(DATA_DIR, "data", "usf_jardim_leblon", "exames.db"),
        "ativa":    False,
    },
]


def criar_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usfs (
            id       TEXT PRIMARY KEY,
            nome     TEXT NOT NULL,
            cnes     TEXT DEFAULT '',
            db_path  TEXT NOT NULL,
            ativa    INTEGER DEFAULT 0,
            criado_em TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            username       TEXT    UNIQUE NOT NULL,
            password_hash  TEXT    NOT NULL,
            nome_completo  TEXT    DEFAULT '',
            role           TEXT    NOT NULL CHECK(role IN ('admin','user')),
            usf_id         TEXT    REFERENCES usfs(id),
            ativo          INTEGER DEFAULT 1,
            criado_em      TEXT    DEFAULT (datetime('now','localtime')),
            ultimo_login   TEXT
        );

        CREATE TABLE IF NOT EXISTS sessoes_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER REFERENCES usuarios(id),
            usf_id     TEXT,
            ip         TEXT,
            acao       TEXT,
            momento    TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()


def popular_usfs(conn: sqlite3.Connection) -> None:
    for u in USFs:
        conn.execute("""
            INSERT OR REPLACE INTO usfs (id, nome, cnes, db_path, ativa)
            VALUES (?, ?, ?, ?, ?)
        """, (u["id"], u["nome"], u["cnes"], u["db_path"], int(u["ativa"])))
    conn.commit()
    print(f"  {len(USFs)} USFs registradas.")


def criar_admin(conn: sqlite3.Connection) -> None:
    senha = os.getenv("ADMIN_PASSWORD", "")
    if not senha:
        raise SystemExit("❌ Defina ADMIN_PASSWORD no .env antes de executar o setup.")
    h = _hash(senha)
    conn.execute("""
        INSERT OR IGNORE INTO usuarios (username, password_hash, nome_completo, role, usf_id)
        VALUES ('ryan.nascimento', ?, 'Ryan Nascimento', 'admin', NULL)
    """, (h,))
    # Atualiza hash se já existia (caso senha mude no .env)
    conn.execute("""
        UPDATE usuarios SET password_hash=?, role='admin', usf_id=NULL
        WHERE username='ryan.nascimento'
    """, (h,))
    conn.commit()
    print(f"  Usuário admin criado/atualizado (senha do .env).")


def criar_usuario_usf(conn: sqlite3.Connection, username: str, senha: str,
                      usf_id: str, nome_completo: str = "") -> None:
    """Cria ou atualiza um usuário vinculado a uma USF específica."""
    h = _hash(senha)
    conn.execute("""
        INSERT OR REPLACE INTO usuarios
            (username, password_hash, nome_completo, role, usf_id)
        VALUES (?, ?, ?, 'user', ?)
    """, (username, h, nome_completo, usf_id))
    conn.commit()


def criar_usuarios_padrao(conn: sqlite3.Connection) -> None:
    """Cria um usuário padrão para a USF Vila Amorim (já tem dados)."""
    criar_usuario_usf(
        conn,
        username="vilaamorim",
        senha="VilAAmorim@2025",
        usf_id="usf_vila_amorim",
        nome_completo="Usuário USF Vila Amorim",
    )
    print("  Usuário 'vilaamorim' criado para USF VILA AMORIM.")


def listar_usuarios(conn: sqlite3.Connection) -> None:
    rows = conn.execute("""
        SELECT u.username, u.role, u.nome_completo, s.nome AS usf_nome, u.ativo
        FROM usuarios u
        LEFT JOIN usfs s ON u.usf_id = s.id
        ORDER BY u.role DESC, u.username
    """).fetchall()
    print(f"\n  {'Username':<20} {'Role':<8} {'USF':<25} {'Nome':<30} {'Ativo'}")
    print("  " + "─"*90)
    for r in rows:
        usf_n = r[3] or "(todas)"
        print(f"  {r[0]:<20} {r[1]:<8} {usf_n:<25} {r[2]:<30} {'✓' if r[4] else '✗'}")


def modo_add_user(conn: sqlite3.Connection) -> None:
    print("\n── Adicionar novo usuário ──")
    username = input("  Username: ").strip()
    senha    = getpass.getpass("  Senha: ")
    nome     = input("  Nome completo: ").strip()
    print("\n  USFs disponíveis:")
    usfs = conn.execute("SELECT id, nome FROM usfs ORDER BY nome").fetchall()
    for i, (uid, unome) in enumerate(usfs):
        print(f"  [{i}] {uid:<30} {unome}")
    idx = int(input("  Número da USF: "))
    usf_id = usfs[idx][0]
    criar_usuario_usf(conn, username, senha, usf_id, nome)
    print(f"  ✓ Usuário '{username}' criado para {usf_id}")


def main() -> None:
    reset    = "--reset"    in sys.argv
    add_user = "--add-user" in sys.argv

    if reset and os.path.exists(AUTH_DB):
        os.remove(AUTH_DB)
        print(f"  Auth DB apagado: {AUTH_DB}")

    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row

    print(f"\n[setup_auth] Banco: {AUTH_DB}")

    if add_user:
        modo_add_user(conn)
        listar_usuarios(conn)
        conn.close()
        return

    print("  Criando schema...")
    criar_schema(conn)
    print("  Populando USFs...")
    popular_usfs(conn)
    print("  Criando admin...")
    criar_admin(conn)
    print("  Criando usuários padrão...")
    criar_usuarios_padrao(conn)

    print("\n── Resultado ─────────────────────────────────────────────────────────")
    listar_usuarios(conn)

    print(f"\n  ✓ auth.db pronto em: {os.path.abspath(AUTH_DB)}")
    print("  Altere a senha do admin após o primeiro login!\n")

    conn.close()


if __name__ == "__main__":
    main()
