"""Extrai dados de CEP da API ViaCEP para a camada Bronze."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


BASE_DIR = Path(__file__).resolve().parent
PASTA_BRONZE = BASE_DIR / "datalake" / "bronze"
TIMEOUT_SEGUNDOS = 10


def normalizar_cep(cep: str) -> str:
    """Valida um CEP brasileiro e retorna somente seus oito dígitos."""
    cep = cep.strip()
    if not re.fullmatch(r"\d{5}-?\d{3}", cep):
        raise ValueError("CEP inválido. Informe exatamente 8 dígitos, com ou sem hífen.")
    return cep.replace("-", "")


def extrair_cep(
    cep: str,
    pasta_bronze: Path = PASTA_BRONZE,
    timeout: int = TIMEOUT_SEGUNDOS,
) -> tuple[Path, dict[str, Any]]:
    """Consulta o ViaCEP e arquiva a resposta bruta com timestamp."""
    cep_normalizado = normalizar_cep(cep)
    url_api = f"https://viacep.com.br/ws/{cep_normalizado}/json/"

    try:
        resposta = requests.get(url_api, timeout=timeout)
        resposta.raise_for_status()
        dados_extraidos = resposta.json()
    except requests.RequestException as erro:
        raise RuntimeError(f"Falha ao consultar o ViaCEP: {erro}") from erro
    except ValueError as erro:
        raise RuntimeError("O ViaCEP retornou uma resposta que não é um JSON válido.") from erro

    if not isinstance(dados_extraidos, dict):
        raise RuntimeError("O ViaCEP retornou um formato de dados inesperado.")

    pasta_bronze.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    caminho_arquivo = pasta_bronze / f"dados_cep_{timestamp}.json"
    caminho_arquivo.write_text(
        json.dumps(dados_extraidos, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    return caminho_arquivo, dados_extraidos


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extrai um CEP para a camada Bronze.")
    parser.add_argument("cep", nargs="?", help="CEP com 8 dígitos, com ou sem hífen")
    return parser


def main() -> int:
    args = criar_parser().parse_args()
    cep = args.cep or input("Digite o CEP (somente números): ")
    print("Iniciando extração da API...")
    try:
        caminho, dados = extrair_cep(cep)
    except (ValueError, RuntimeError) as erro:
        print(f"ERRO: {erro}")
        return 1

    if dados.get("erro") is True or dados.get("erro") == "true":
        print(f"AVISO: o ViaCEP informou que o CEP não existe. Resposta arquivada em: {caminho}")
    else:
        print(f"SUCESSO! Arquivo bruto salvo em: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
