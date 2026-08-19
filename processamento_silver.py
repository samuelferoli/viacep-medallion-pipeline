"""Limpa e consolida os dados da camada Bronze na camada Silver."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
PASTA_BRONZE = BASE_DIR / "datalake" / "bronze"
PASTA_SILVER = BASE_DIR / "datalake" / "silver"
PADRAO_ARQUIVO_BRONZE = re.compile(
    r"^dados_cep_(\d{8}_\d{6})(?:_(\d{6}))?\.json$"
)


def extrair_data_arquivo(nome_arquivo: str | Path) -> datetime:
    """Extrai o timestamp de um nome de arquivo Bronze."""
    correspondencia = PADRAO_ARQUIVO_BRONZE.fullmatch(Path(nome_arquivo).name)
    if not correspondencia:
        raise ValueError(f"Nome de arquivo Bronze inválido: {Path(nome_arquivo).name}")

    data_hora, microssegundos = correspondencia.groups()
    formato = "%Y%m%d_%H%M%S_%f" if microssegundos else "%Y%m%d_%H%M%S"
    valor = f"{data_hora}_{microssegundos}" if microssegundos else data_hora
    return datetime.strptime(valor, formato)


def limpar_e_padronizar(
    dados: dict[str, Any], arquivo_origem: str | Path, data_extracao: datetime
) -> dict[str, Any]:
    """Remove espaços, normaliza valores vazios e adiciona linhagem."""
    dados_limpos: dict[str, Any] = {}
    for chave, valor in dados.items():
        if isinstance(valor, str):
            valor = valor.strip()
            dados_limpos[chave] = valor or None
        else:
            dados_limpos[chave] = valor

    cep = str(dados.get("cep") or "").replace("-", "").strip()
    if not re.fullmatch(r"\d{8}", cep):
        raise ValueError("registro sem um CEP válido")

    dados_limpos["cep"] = cep
    dados_limpos["metadata_arquivo_origem"] = Path(arquivo_origem).name
    dados_limpos["metadata_data_extracao"] = data_extracao.isoformat(sep=" ")
    dados_limpos["metadata_data_processamento"] = datetime.now().isoformat(
        sep=" ", timespec="seconds"
    )
    return dados_limpos


def _cabecalhos_consolidados(registros: list[dict[str, Any]]) -> list[str]:
    """Obtém a união estável de campos para suportar mudanças no schema da API."""
    cabecalhos: list[str] = []
    for registro in registros:
        for chave in registro:
            if chave not in cabecalhos:
                cabecalhos.append(chave)
    return cabecalhos


def processar_camada_silver(
    pasta_bronze: Path = PASTA_BRONZE,
    pasta_silver: Path = PASTA_SILVER,
) -> int:
    """Processa toda a Bronze e mantém o registro mais recente de cada CEP."""
    print("Iniciando processamento da Camada Silver...")
    arquivos_bronze = sorted(pasta_bronze.glob("dados_cep_*.json"))
    if not arquivos_bronze:
        print("Nenhum arquivo encontrado na camada Bronze para processar.")
        return 0

    print(f"Encontrados {len(arquivos_bronze)} arquivos na camada Bronze.")
    ceps_unicos: dict[str, tuple[dict[str, Any], datetime]] = {}

    for caminho_arquivo in arquivos_bronze:
        try:
            data_extracao = extrair_data_arquivo(caminho_arquivo)
            dados_brutos = json.loads(caminho_arquivo.read_text(encoding="utf-8"))
            if not isinstance(dados_brutos, dict):
                raise ValueError("o JSON raiz não é um objeto")
            if dados_brutos.get("erro") is True or dados_brutos.get("erro") == "true":
                print(f"Ignorando {caminho_arquivo.name}: resposta de CEP inválido.")
                continue

            dados_processados = limpar_e_padronizar(
                dados_brutos, caminho_arquivo, data_extracao
            )
            cep = dados_processados["cep"]
            anterior = ceps_unicos.get(cep)
            if anterior is None or data_extracao > anterior[1]:
                ceps_unicos[cep] = (dados_processados, data_extracao)
        except (OSError, json.JSONDecodeError, ValueError) as erro:
            print(f"Ignorando {caminho_arquivo.name}: {erro}.")

    if not ceps_unicos:
        print("Nenhum registro válido foi encontrado na camada Bronze.")
        return 0

    pasta_silver.mkdir(parents=True, exist_ok=True)
    registros = [ceps_unicos[cep][0] for cep in sorted(ceps_unicos)]

    for dados_limpos in registros:
        caminho_silver = pasta_silver / f"cep_{dados_limpos['cep']}.json"
        caminho_silver.write_text(
            json.dumps(dados_limpos, ensure_ascii=False, indent=4), encoding="utf-8"
        )

    nomes_esperados = {f"cep_{registro['cep']}.json" for registro in registros}
    for arquivo_antigo in pasta_silver.glob("cep_*.json"):
        if arquivo_antigo.name not in nomes_esperados:
            arquivo_antigo.unlink()

    caminho_csv = pasta_silver / "consolidado_ceps.csv"
    with caminho_csv.open("w", encoding="utf-8", newline="") as arquivo_csv:
        escritor = csv.DictWriter(
            arquivo_csv, fieldnames=_cabecalhos_consolidados(registros)
        )
        escritor.writeheader()
        escritor.writerows(registros)

    print(f"Processamento concluído. {len(registros)} CEP(s) únicos salvos na Silver.")
    return len(registros)


def main() -> int:
    return 0 if processar_camada_silver() > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
