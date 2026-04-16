"""
launcher.py — Ponto de entrada único do IPL-APS.

Inicia o servidor gateway (FastAPI, porta 8080) em background thread
e abre o menu principal Tkinter. Ao fechar o menu, o servidor encerra.

Uso:
    python launcher.py
    ./IPL-APS          (executável gerado pelo PyInstaller)
"""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

# ── Ajusta BASE_DIR para funcionar tanto como script quanto como executável ──
if getattr(sys, "frozen", False):
    # Executável PyInstaller — arquivos estão em sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS          # type: ignore[attr-defined]
else:
    BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

# Diretório de trabalho = onde ficam os dados e o .env
os.chdir(BASE_DIR)
sys.path.insert(0, BUNDLE_DIR)


# ── Carrega .env antes de tudo ────────────────────────────────────────────────
def _ensure_env():
    """Garante que existe um .env com as configurações mínimas."""
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        _wizard_primeiro_uso(env_path)


def _wizard_primeiro_uso(env_path: str):
    """Janela de primeiro uso: coleta as credenciais e grava o .env."""
    root = tk.Tk()
    root.title("IPL-APS — Configuração Inicial")
    root.geometry("500x400")
    root.resizable(False, False)

    tk.Label(root, text="Bem-vindo ao IPL-APS", font=("Helvetica", 14, "bold")).pack(pady=12)
    tk.Label(root, text="Configure as credenciais antes de continuar:", font=("Helvetica", 10)).pack()

    frame = tk.Frame(root, padx=20)
    frame.pack(fill=tk.BOTH, expand=True, pady=10)

    fields = {}
    labels = [
        ("GMAIL_EMAIL",    "E-mail Gmail (que recebe os laudos):"),
        ("GMAIL_SENHA",    "Senha de App Gmail (16 caracteres):"),
        ("REMETENTE_LAB",  "E-mail remetente do laboratório (opcional):"),
        ("ADMIN_PASSWORD", "Senha do administrador (mín. 8 chars):"),
        ("DATA_DIR",       f"Pasta dos dados (padrão: {BASE_DIR}):"),
    ]
    for key, label in labels:
        tk.Label(frame, text=label, anchor="w").pack(fill=tk.X, pady=(6, 0))
        e = tk.Entry(frame, width=55, show="*" if "SENHA" in key or "PASSWORD" in key else "")
        if key == "DATA_DIR":
            e.insert(0, BASE_DIR)
            e.config(show="")
        e.pack(fill=tk.X)
        fields[key] = e

    def _salvar():
        import secrets
        vals = {k: v.get().strip() for k, v in fields.items()}
        if not vals["GMAIL_EMAIL"] or not vals["GMAIL_SENHA"]:
            messagebox.showwarning("Atenção", "Gmail e senha de app são obrigatórios.")
            return
        if not vals["ADMIN_PASSWORD"] or len(vals["ADMIN_PASSWORD"]) < 8:
            messagebox.showwarning("Atenção", "Senha do admin deve ter pelo menos 8 caracteres.")
            return
        if not vals["DATA_DIR"]:
            vals["DATA_DIR"] = BASE_DIR

        jwt_key = secrets.token_hex(32)
        auth_db = os.path.join(vals["DATA_DIR"], "auth.db")

        lines = [
            "# IPL-APS — Configuração gerada pelo instalador\n",
            f'GMAIL_EMAIL={vals["GMAIL_EMAIL"]}\n',
            f'GMAIL_SENHA={vals["GMAIL_SENHA"]}\n',
            f'REMETENTE_LAB={vals["REMETENTE_LAB"]}\n',
            f'JWT_SECRET_KEY={jwt_key}\n',
            "JWT_ALGORITHM=HS256\n",
            "JWT_EXPIRE_HOURS=10\n",
            f'DATA_DIR={vals["DATA_DIR"]}\n',
            f'AUTH_DB={auth_db}\n',
            f'ADMIN_PASSWORD={vals["ADMIN_PASSWORD"]}\n',
        ]
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        messagebox.showinfo("Configuração salva", f".env criado em:\n{env_path}")
        root.destroy()

    tk.Button(root, text="Salvar e continuar", command=_salvar,
              bg="#0066cc", fg="white", font=("Helvetica", 11, "bold"),
              padx=12, pady=6).pack(pady=14)
    root.mainloop()

    if not os.path.exists(env_path):
        sys.exit(0)


# ── Inicializa banco de autenticação se não existir ───────────────────────────
def _ensure_auth_db():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    auth_db = os.getenv("AUTH_DB", os.path.join(BASE_DIR, "auth.db"))
    if not os.path.exists(auth_db):
        try:
            import setup_auth
            setup_auth.main()
        except Exception as e:
            messagebox.showwarning("Auth DB", f"Aviso ao criar banco de auth:\n{e}")


# ── Gateway FastAPI em background thread ──────────────────────────────────────
_gateway_started = threading.Event()


def _run_gateway():
    """Executa o servidor FastAPI dentro do processo atual (thread dedicada)."""
    try:
        import uvicorn
        from gateway import app as fastapi_app
        _gateway_started.set()
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8080,
                    log_level="error", access_log=False)
    except Exception as e:
        print(f"[gateway] Erro: {e}", file=sys.stderr)
        _gateway_started.set()   # desbloqueia mesmo com erro


def _start_gateway():
    t = threading.Thread(target=_run_gateway, daemon=True, name="gateway")
    t.start()
    # Aguarda até 5 s para o gateway responder
    _gateway_started.wait(timeout=5)
    time.sleep(1)   # margem extra para o bind do socket


# ── Splash screen enquanto o gateway sobe ────────────────────────────────────
def _splash():
    splash = tk.Tk()
    splash.overrideredirect(True)
    w, h = 340, 120
    sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
    splash.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
    splash.configure(bg="#0d1117")
    tk.Label(splash, text="IPL-APS", font=("Helvetica", 22, "bold"),
             bg="#0d1117", fg="#58a6ff").pack(pady=(18, 4))
    tk.Label(splash, text="Iniciando servidor…",
             font=("Helvetica", 10), bg="#0d1117", fg="#8b949e").pack()
    splash.update()
    return splash


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    _ensure_env()
    _ensure_auth_db()

    splash = _splash()
    _start_gateway()
    splash.destroy()

    # Importa e abre o menu principal
    from menu_principal import MenuPrincipal
    root = tk.Tk()
    MenuPrincipal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
