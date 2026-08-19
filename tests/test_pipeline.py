import csv
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from extracao_bronze import extrair_cep, normalizar_cep
from processamento_gold import calcular_distribuicao, processar_camada_gold
from processamento_silver import (
    extrair_data_arquivo,
    limpar_e_padronizar,
    processar_camada_silver,
)


class TestExtracaoBronze(unittest.TestCase):
    def test_normaliza_cep_com_ou_sem_hifen(self):
        self.assertEqual(normalizar_cep("01001-000"), "01001000")
        self.assertEqual(normalizar_cep("01001000"), "01001000")

    def test_rejeita_cep_invalido(self):
        for cep in ("123", "abcdefgh", "01001 000"):
            with self.subTest(cep=cep), self.assertRaises(ValueError):
                normalizar_cep(cep)

    @patch("extracao_bronze.requests.get")
    def test_extracao_usa_timeout_e_salva_json(self, requisicao_get):
        resposta = Mock()
        resposta.json.return_value = {"cep": "01001-000", "uf": "SP"}
        resposta.raise_for_status.return_value = None
        requisicao_get.return_value = resposta

        with tempfile.TemporaryDirectory() as temporario:
            caminho, dados = extrair_cep("01001000", Path(temporario), timeout=3)

            requisicao_get.assert_called_once_with(
                "https://viacep.com.br/ws/01001000/json/", timeout=3
            )
            self.assertEqual(json.loads(caminho.read_text(encoding="utf-8")), dados)
            self.assertRegex(caminho.name, r"dados_cep_\d{8}_\d{6}_\d{6}\.json")

    @patch("extracao_bronze.requests.get")
    def test_converte_erro_de_rede_em_erro_da_aplicacao(self, requisicao_get):
        requisicao_get.side_effect = requests.Timeout("tempo excedido")
        with tempfile.TemporaryDirectory() as temporario:
            with self.assertRaisesRegex(RuntimeError, "Falha ao consultar"):
                extrair_cep("01001000", Path(temporario))


class TestCamadaSilver(unittest.TestCase):
    def test_extrai_timestamp_antigo_e_novo(self):
        self.assertEqual(
            extrair_data_arquivo("dados_cep_20260702_142537.json"),
            datetime(2026, 7, 2, 14, 25, 37),
        )
        self.assertEqual(
            extrair_data_arquivo("dados_cep_20260702_142537_123456.json"),
            datetime(2026, 7, 2, 14, 25, 37, 123456),
        )

    def test_limpa_campos_e_adiciona_linhagem(self):
        dados = {"cep": "01001-000", "bairro": " Sé ", "complemento": ""}
        resultado = limpar_e_padronizar(
            dados,
            "dados_cep_20260702_142537.json",
            datetime(2026, 7, 2, 14, 25, 37),
        )
        self.assertEqual(resultado["cep"], "01001000")
        self.assertEqual(resultado["bairro"], "Sé")
        self.assertIsNone(resultado["complemento"])
        self.assertEqual(
            resultado["metadata_arquivo_origem"],
            "dados_cep_20260702_142537.json",
        )

    def test_deduplica_e_remove_saida_obsoleta(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            bronze = raiz / "bronze"
            silver = raiz / "silver"
            bronze.mkdir()
            silver.mkdir()
            (silver / "cep_99999999.json").write_text("{}", encoding="utf-8")
            (bronze / "dados_cep_20260101_100000.json").write_text(
                json.dumps({"cep": "01001-000", "bairro": "Antigo"}),
                encoding="utf-8",
            )
            (bronze / "dados_cep_20260102_100000.json").write_text(
                json.dumps({"cep": "01001-000", "bairro": "Atual", "novo": "campo"}),
                encoding="utf-8",
            )
            (bronze / "dados_cep_20260103_100000.json").write_text(
                json.dumps({"erro": True}), encoding="utf-8"
            )

            self.assertEqual(processar_camada_silver(bronze, silver), 1)
            registro = json.loads(
                (silver / "cep_01001000.json").read_text(encoding="utf-8")
            )
            self.assertEqual(registro["bairro"], "Atual")
            self.assertEqual(registro["novo"], "campo")
            self.assertFalse((silver / "cep_99999999.json").exists())
            with (silver / "consolidado_ceps.csv").open(
                encoding="utf-8", newline=""
            ) as arquivo:
                self.assertEqual(len(list(csv.DictReader(arquivo))), 1)


class TestCamadaGold(unittest.TestCase):
    def test_calcula_distribuicao_com_nao_informado(self):
        dados = [{"uf": "SP"}, {"uf": "RJ"}, {"uf": "SP"}, {"uf": ""}]
        self.assertEqual(
            calcular_distribuicao(dados, "uf"),
            {"SP": 2, "Não Informado": 1, "RJ": 1},
        )

    def test_gera_relatorio_consistente(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            silver = raiz / "silver"
            gold = raiz / "gold"
            silver.mkdir()
            with (silver / "consolidado_ceps.csv").open(
                "w", encoding="utf-8", newline=""
            ) as arquivo:
                escritor = csv.DictWriter(
                    arquivo, fieldnames=["cep", "uf", "regiao", "localidade", "ddd"]
                )
                escritor.writeheader()
                escritor.writerows(
                    [
                        {"cep": "01001000", "uf": "SP", "regiao": "Sudeste", "localidade": "São Paulo", "ddd": "11"},
                        {"cep": "20040002", "uf": "RJ", "regiao": "Sudeste", "localidade": "Rio de Janeiro", "ddd": "21"},
                    ]
                )

            self.assertEqual(processar_camada_gold(silver, gold), 2)
            relatorio = json.loads(
                (gold / "relatorio_metricas.json").read_text(encoding="utf-8")
            )
            self.assertEqual(relatorio["metadata"]["total_registros_analisados"], 2)
            self.assertEqual(
                relatorio["metricas"]["distribuicao_por_regiao"], {"Sudeste": 2}
            )


if __name__ == "__main__":
    unittest.main()
