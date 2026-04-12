"""
Servidor IPL-APS — serve a interface HTML e a API de dados.
Uso direto: python servidor_ipl.py
"""

import http.server
import json
import os
import threading
import webbrowser

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


_servidor_ativo = None


def iniciar(porta: int = PORT, abrir_browser: bool = True):
    global _servidor_ativo
    if _servidor_ativo:
        # já rodando — só abre o browser
        if abrir_browser:
            webbrowser.open(f"http://localhost:{porta}/")
        return _servidor_ativo, f"http://localhost:{porta}/"

    server = http.server.HTTPServer(("localhost", porta), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    _servidor_ativo = server
    url = f"http://localhost:{porta}/"
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
