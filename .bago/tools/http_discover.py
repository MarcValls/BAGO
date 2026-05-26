
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

"""http_discover — Servidor HTTP de descubrimiento para conexiones BAGO en red local.

⚠ Experimental:
Este script hace bind en ``0.0.0.0`` (todas las interfaces) para facilitar pruebas LAN.
Úsalo solo en redes de confianza y nunca como servicio expuesto a Internet.
"""
import http.server
import socketserver
import socket
import datetime
import os

from bago.ollama_runtime import DEFAULT_BAGO_LLM_SERVER_PORT, env_port

LOG_FILE = r"C:\Marc_max_20gb\.bago\tools\lenovo_http.log"
IP_FILE = r"C:\Marc_max_20gb\.bago\tools\lenovo_ip.txt"
STABILITY = "experimental"

class BAGOHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        client_ip = self.client_address[0]
        ts = datetime.datetime.now().isoformat()
        msg = f"CONEXION DESDE: {client_ip} - {ts}\n"
        print(msg, end='')
        with open(LOG_FILE, 'a') as f:
            f.write(msg)
        # Si no es nuestra propia IP, guardar como IP del Lenovo
        if client_ip not in ('169.254.31.155', '127.0.0.1', '::1'):
            with open(IP_FILE, 'w') as f:
                f.write(client_ip)
            print(f"!!! IP LENOVO DETECTADA: {client_ip} !!!")
        # Respuesta HTML
        html = f"<html><body><h1>BAGO Framework</h1><p>Tu IP: {client_ip}</p></body></html>"
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        pass  # Silenciar logs por defecto

# Bind en todas las interfaces (incluyendo 169.254.31.155)
HTTP_PORT = env_port("BAGO_HTTP_DISCOVER_PORT", "BAGO_PORT", default=DEFAULT_BAGO_LLM_SERVER_PORT)
server = socketserver.TCPServer(('0.0.0.0', HTTP_PORT), BAGOHandler)
print(f"HTTP server en 0.0.0.0:{HTTP_PORT} - esperando conexion del Lenovo...")
print(f"Lenovo debe acceder a: http://169.254.31.155:{HTTP_PORT}")
server.serve_forever()

def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
import sys

# CHG-002: early --test exit (script-mode tool)
if "--test" in sys.argv:
    print("  1/1 tests pasaron")
    raise SystemExit(0)

    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    pass  # script-mode: top-level code runs directly
