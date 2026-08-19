"""Servidor HTTP local e restrito para o dashboard."""

from __future__ import annotations

import argparse
import http.server
import webbrowser
from functools import partial
from pathlib import Path
from urllib.parse import unquote, urlsplit


BASE_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORTA_PADRAO = 8000
EXTENSOES_DADOS = {".csv", ".json"}


class DashboardHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Expõe somente o dashboard e os arquivos de dados necessários."""

    def _caminho_permitido(self) -> bool:
        caminho_url = unquote(urlsplit(self.path).path)
        if caminho_url in {"/", "/index.html"}:
            return True

        caminho_relativo = caminho_url.lstrip("/")
        candidato = (BASE_DIR / caminho_relativo).resolve()
        raiz_datalake = (BASE_DIR / "datalake").resolve()
        try:
            candidato.relative_to(raiz_datalake)
        except ValueError:
            return False
        return candidato.is_file() and candidato.suffix.lower() in EXTENSOES_DADOS

    def send_head(self):  # type: ignore[no-untyped-def]
        if not self._caminho_permitido():
            self.send_error(404, "Recurso não encontrado")
            return None
        return super().send_head()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()


class ServidorDashboard(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


def iniciar_servidor(porta: int = PORTA_PADRAO, abrir_navegador: bool = True) -> None:
    handler = partial(DashboardHTTPRequestHandler, directory=str(BASE_DIR))
    with ServidorDashboard((HOST, porta), handler) as servidor:
        url = f"http://{HOST}:{porta}"
        print(f"Dashboard disponível em {url}")
        print("Para encerrar o servidor, pressione CTRL+C.")
        if abrir_navegador:
            webbrowser.open(url)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado pelo usuário.")


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve o dashboard localmente.")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    parser.add_argument("--sem-navegador", action="store_true")
    return parser


def main() -> None:
    args = criar_parser().parse_args()
    iniciar_servidor(args.porta, not args.sem_navegador)


if __name__ == "__main__":
    main()
