"""Leitura do CSV da planilha e das premissas, sem banco."""

import datetime
import pathlib
import sys
from decimal import Decimal as D

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.conciliacao import cargas, csv_leitor, layout_glosa, premissas, regras  # noqa: E402

CABECALHO = ("EMPRESA;FILIAL;CONVENIO;PACIENTES ATIVOS POR PERIODO;PERIODO ATENDIMENTO;PROTOCOLO;"
             "VALOR FATURADO;DATA ENTREGA  FATURAMENTO;GLOSA;DATA RECEBIMENTO;STATUS")


def csv_planilha(*linhas, totais=True):
    topo = ";;;;;;47409814,74;;10802168,25;;\n\n\n\n\n" if totais else ""
    return (topo + CABECALHO + "\n" + "\n".join(linhas) + "\n").encode("utf-8-sig")


@pytest.mark.parametrize("bruto,esperado", [
    ("1.234,56", D("1234.56")), ("R$ 1.234,56", D("1234.56")), ("1234.56", D("1234.56")),
    ("(10,00)", D("-10.00")), ("-", None), ("", None), ("#VALUE!", None), ("0,01", D("0.01")),
])
def test_numero(bruto, esperado):
    assert csv_leitor.numero(bruto) == esperado


@pytest.mark.parametrize("bruto", ["330220783688_0", "abc", "NaN", "1.2.3,4,5"])
def test_numero_recusa_lixo(bruto):
    # "_" passaria no Decimal() e viraria outro número: protocolo não é valor
    with pytest.raises(ValueError):
        csv_leitor.numero(bruto)


@pytest.mark.parametrize("bruto,esperado", [
    ("18/11/2025", datetime.date(2025, 11, 18)), ("2025-11-18", datetime.date(2025, 11, 18)),
    ("45979", datetime.date(2025, 11, 18)), ("18/11/25", datetime.date(2025, 11, 18)),
    ("", None), ("0", None), ("#N/D", None),
])
def test_data(bruto, esperado):
    assert csv_leitor.data(bruto) == esperado


def test_acha_o_cabecalho_depois_das_linhas_de_total():
    cab, corpo, linha = csv_leitor.ler_linhas(csv_planilha("PLENO SAUDE;RJ;CASSI;FULANO;01/06/2026 a 30/06/2026;"
                                                           "123456;1.000,00;02/07/2026;100,00;;"))
    assert linha == 6
    assert "DATA ENTREGA FATURAMENTO" in cab  # espaço duplo normalizado
    assert len(corpo) == 1


def test_separador_virgula_e_cp1252():
    texto = "EMPRESA,FILIAL,CONVENIO,PACIENTE,PERIODO,PROTOCOLO,VALOR FATURADO,GLOSA\n" \
            "PLENO SAÚDE,RJ,CASSI,JOSÉ,01/06/2026 a 30/06/2026,1,\"1.000,50\",10\n"
    cab, corpo, _ = csv_leitor.ler_linhas(texto.encode("cp1252"))
    indice, faltando, _ = layout_glosa.mapear(cab)
    assert faltando == []
    registro, erros = layout_glosa.converter(corpo[0], indice)
    assert erros == [] and registro["empresa"] == "PLENO SAÚDE" and registro["valor_faturado"] == D("1000.50")


def test_protocolo_com_sublinhado_fica_texto():
    cab, corpo, _ = csv_leitor.ler_linhas(csv_planilha("PREMIER;PREMIER;BRADESCO;FULANO;01/04/2026 a 30/04/2026;"
                                                       "330227850099_0;114762;15/05/2026;86862;;"))
    indice, _, _ = layout_glosa.mapear(cab)
    registro, _ = layout_glosa.converter(corpo[0], indice)
    assert registro["protocolo"] == "330227850099_0"


def test_coluna_calculada_vira_planilha():
    cab, corpo, _ = csv_leitor.ler_linhas(csv_planilha("P;RJ;CASSI;F;01/06/2026 a 30/06/2026;1;10;;1;;RECEBIDO"))
    indice, _, _ = layout_glosa.mapear(cab)
    registro, _ = layout_glosa.converter(corpo[0], indice)
    assert registro["status_planilha"] == "RECEBIDO" and "status" not in registro


def test_linha_invalida_e_rejeitada_sem_derrubar_a_carga():
    premissas_ = regras.Premissas.de_linhas(prazo=[{"convenio": "N", "prazo": 30}])
    conteudo = csv_planilha(
        "P;RJ;CASSI;F;01/06/2026 a 30/06/2026;1;10,00;02/07/2026;1,00;;",
        "P;RJ;CASSI;G;01/06/2026 a 30/06/2026;2;abc;02/07/2026;1,00;;",   # valor inválido
        "P;RJ;CASSI;;01/06/2026 a 30/06/2026;3;10,00;02/07/2026;1,00;;",  # paciente vazio
    )
    linhas, relatorio = cargas.processar(conteudo, premissas_, datetime.date(2026, 9, 18))
    assert len(linhas) == 1 and relatorio["rejeitadas"] == 2
    motivos = " ".join(" ".join(r["erros"]) for r in relatorio["rejeitadas_amostra"])
    assert "valor_faturado" in motivos and "paciente" in motivos
    assert relatorio["totais"]["glosa"] == 1.0


def test_coluna_obrigatoria_faltando_reprova_o_arquivo():
    conteudo = b"EMPRESA;PROTOCOLO;GLOSA\nP;1;10\n"
    with pytest.raises(cargas.CargaInvalida) as falha:
        cargas.processar(conteudo, regras.Premissas(), datetime.date(2026, 9, 18))
    assert "VALOR FATURADO" in falha.value.motivo


def test_comparar_cargas():
    antes = [{"linha": 1, "protocolo": "1", "paciente": "A", "periodo": "x", "convenio": "C",
              "status_glosa": "ANÁLISE OPALUS", "glosa": D("10")},
             {"linha": 2, "protocolo": "2", "paciente": "B", "periodo": "x", "convenio": "C", "glosa": D("5")}]
    agora = [{**antes[0], "status_glosa": "ANÁLISE OPERADORA"},
             {"linha": 3, "protocolo": "3", "paciente": "C", "periodo": "x", "convenio": "C", "glosa": D("1")}]
    diff = cargas.comparar(agora, antes)
    assert diff["novas"] == 1 and diff["removidas"] == 1
    assert diff["status_alterado"] == [{"de": "ANÁLISE OPALUS", "para": "ANÁLISE OPERADORA", "linhas": 1}]


def test_premissa_repetida_fica_com_a_primeira_e_lixo_vira_vazio():
    conteudo = "convenio;prazo_recurso;previsao_pagto\nAMIL;90;30\nAMIL;10;10\nCASSI;PRÉ;60\n".encode()
    linhas, avisos = premissas.ler_csv("recurso", conteudo)
    assert [(l["convenio"], l["prazo_recurso"]) for l in linhas] == [("AMIL", 90), ("CASSI", None)]
    assert any("repetido" in a for a in avisos) and any("PRÉ" in a for a in avisos)


def test_sementes_existem_e_carregam():
    premissas_ = premissas.carregar_sementes()
    assert premissas_.de_para and premissas_.imposto and premissas_.prazo and premissas_.aging


def test_pseudonimo_estavel_e_sem_o_nome():
    from src.conciliacao import privacidade

    codigo = privacidade.pseudonimo("Fulana de Tal")
    assert codigo == privacidade.pseudonimo("  FULANA  DE TAL ")   # mesma pessoa, mesmo código
    assert codigo != privacidade.pseudonimo("Fulana de Tai")
    assert codigo.startswith("X") and len(codigo) == 9 and "FULANA" not in codigo
    assert privacidade.pseudonimo("") is None


def test_consultas_de_tela_nunca_selecionam_o_nome_do_paciente():
    import re

    from src.reports import sql_pg

    for sql in sql_pg.CONSULTAS.values():
        assert not re.search(r"\bg\.paciente\b(?!_codigo)", sql), sql[:80]
