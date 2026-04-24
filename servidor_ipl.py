"""
Servidor IPL-APS — serve a interface HTML e a API de dados.
Uso direto: python servidor_ipl.py
"""

import http.server
import json
import logging
import os
import threading
import time
import webbrowser
from datetime import datetime, date, timedelta

PORT = 8765
_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(_DIR, "iclabs_v5.html")


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file(HTML_FILE, "text/html; charset=utf-8")
        elif self.path == "/api/territorio":
            self._serve_api()
        else:
            self.send_response(404); self.end_headers()

    def _serve_file(self, path: str, ctype: str):
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()

    def _serve_api(self):
        try:
            # Importa sempre fresh para refletir banco atualizado
            import importlib
            import sys
            if "ipl_engine" in sys.modules:
                importlib.reload(sys.modules["ipl_engine"])
            from ipl_engine import calcular_territorio
            dados = calcular_territorio()
            body = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            import traceback
            body = json.dumps({"erro": str(e), "trace": traceback.format_exc()},
                              ensure_ascii=False).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *_):
        pass  # silencia log


_servidor_ativo  = None
_agendador_ativo = False
_log = logging.getLogger("ipl.agendador")


# ── Agendador automático ──────────────────────────────────────────────────────
def _job_processar_emails() -> None:
    """Chama processaexames no modo não-interativo (últimos 3 dias, não lidos)."""
    try:
        import sys
        sys.path.insert(0, _DIR)
        from processaexames import processar_emails, criar_banco
        data_fim = date.today()
        data_ini = data_fim - timedelta(days=3)
        _log.info("Processando %s → %s", data_ini, data_fim)
        criar_banco()
        processar_emails(data_ini, data_fim, somente_nao_lidos=True)
        _log.info("Processamento automático concluído.")
    except Exception:
        _log.exception("Erro no processamento automático")


def _thread_agendador() -> None:
    """Thread daemon: dorme até a próxima hora par e processa e-mails (seg–sex)."""
    _log.info("Agendador iniciado — processará a cada 2 h (seg–sex)")
    while True:
        agora  = datetime.now()
        prox_h = ((agora.hour // 2) + 1) * 2
        if prox_h >= 24:
            prox_dt = (agora + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0)
        else:
            prox_dt = agora.replace(
                hour=prox_h, minute=0, second=0, microsecond=0)
        espera = max(1.0, (prox_dt - agora).total_seconds())
        _log.info("Próxima execução: %s  (em %.1f h)",
                  prox_dt.strftime("%Y-%m-%d %H:%M"), espera / 3600)
        time.sleep(espera)
        if datetime.now().weekday() >= 5:   # sáb=5, dom=6
            _log.info("Final de semana — ignorado.")
            continue
        _job_processar_emails()


def iniciar_agendador() -> None:
    """Inicia o agendador em background (idempotente — roda apenas uma vez)."""
    global _agendador_ativo
    if _agendador_ativo:
        return
    _agendador_ativo = True
    t = threading.Thread(target=_thread_agendador, daemon=True, name="agendador-emails")
    t.start()


def iniciar(porta: int = PORT, abrir_browser: bool = True):
    global _servidor_ativo
    if _servidor_ativo:
        # já rodando — só abre o browser
        if abrir_browser:
            webbrowser.open(f"http://localhost:{porta}/")
        return _servidor_ativo, f"http://localhost:{porta}/"

    url = f"http://localhost:{porta}/"
    try:
        server = http.server.HTTPServer(("localhost", porta), _Handler)
    except OSError as e:
        if e.errno == 98:  # Address already in use — servidor já rodando externamente
            if abrir_browser:
                webbrowser.open(url)
            return None, url
        raise
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    _servidor_ativo = server
    if abrir_browser:
        webbrowser.open(url)
    return server, url


if __name__ == "__main__":
    srv, url = iniciar()
    print(f"IPL-APS rodando em {url}  (Ctrl+C para encerrar)")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.shutdown()
        print("Servidor encerrado.")
