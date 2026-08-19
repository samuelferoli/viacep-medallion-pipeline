"""Executa o pipeline completo de CEPs em um único comando."""

from __future__ import annotations

import argparse

from extracao_bronze import extrair_cep
from processamento_gold import processar_camada_gold
from processamento_silver import processar_camada_silver


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executa o pipeline Bronze -> Silver -> Gold.")
    parser.add_argument(
        "--cep",
        action="append",
        default=[],
        help="CEP a extrair; repita a opção para consultar mais de um CEP",
    )
    parser.add_argument(
        "--somente-processar",
        action="store_true",
        help="Não consulta a API; reprocessa os arquivos já existentes na Bronze",
    )
    return parser


def main() -> int:
    args = criar_parser().parse_args()
    if not args.somente_processar:
        ceps = args.cep or [input("Digite o CEP (somente números): ")]
        for cep in ceps:
            try:
                caminho, _ = extrair_cep(cep)
                print(f"Bronze gerada: {caminho.name}")
            except (ValueError, RuntimeError) as erro:
                print(f"ERRO ao extrair {cep}: {erro}")
                return 1

    total_silver = processar_camada_silver()
    total_gold = processar_camada_gold() if total_silver else 0
    if not total_gold:
        return 1

    print(f"Pipeline concluído com sucesso para {total_gold} CEP(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
