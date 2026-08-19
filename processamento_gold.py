"""Agrega os dados da camada Silver e produz a camada Gold."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
PASTA_SILVER = BASE_DIR / "datalake" / "silver"
PASTA_GOLD = BASE_DIR / "datalake" / "gold"


def calcular_distribuicao(
    dados: list[dict[str, str]], chave: str
) -> dict[str, int]:
    """Calcula uma distribuição em ordem decrescente de frequência."""
    contagem = Counter((item.get(chave) or "Não Informado").strip() for item in dados)
    return dict(sorted(contagem.items(), key=lambda item: (-item[1], item[0])))


def processar_camada_gold(
    pasta_silver: Path = PASTA_SILVER,
    pasta_gold: Path = PASTA_GOLD,
) -> int:
    """Gera métricas Gold a partir do CSV consolidado da Silver."""
    print("Iniciando processamento da Camada Gold...")
    caminho_csv = pasta_silver / "consolidado_ceps.csv"
    if not caminho_csv.is_file():
        print(f"Erro: arquivo Silver não encontrado em {caminho_csv}")
        return 0

    with caminho_csv.open("r", encoding="utf-8-sig", newline="") as arquivo_csv:
        dados_silver = list(csv.DictReader(arquivo_csv))
    if not dados_silver:
        print("Nenhum dado encontrado no arquivo consolidado da Silver.")
        return 0

    metricas = {
        "distribuicao_por_regiao": calcular_distribuicao(dados_silver, "regiao"),
        "distribuicao_por_estado": calcular_distribuicao(dados_silver, "uf"),
        "distribuicao_por_cidade": calcular_distribuicao(dados_silver, "localidade"),
        "distribuicao_por_ddd": calcular_distribuicao(dados_silver, "ddd"),
    }
    relatorio: dict[str, Any] = {
        "metadata": {
            "data_geracao_relatorio": datetime.now().isoformat(
                sep=" ", timespec="seconds"
            ),
            "fonte_dados": "datalake/silver/consolidado_ceps.csv",
            "total_registros_analisados": len(dados_silver),
        },
        "metricas": metricas,
    }

    pasta_gold.mkdir(parents=True, exist_ok=True)
    saidas = {
        "relatorio_metricas.json": relatorio,
        "distribuicao_regiao.json": metricas["distribuicao_por_regiao"],
        "distribuicao_uf.json": metricas["distribuicao_por_estado"],
        "distribuicao_cidade.json": metricas["distribuicao_por_cidade"],
        "distribuicao_ddd.json": metricas["distribuicao_por_ddd"],
    }
    for nome_arquivo, conteudo in saidas.items():
        (pasta_gold / nome_arquivo).write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=4), encoding="utf-8"
        )

    print(f"Camada Gold concluída para {len(dados_silver)} CEP(s).")
    return len(dados_silver)


def main() -> int:
    return 0 if processar_camada_gold() > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
