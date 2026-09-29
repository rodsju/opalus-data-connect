"""Sincronização da Tabela 38 (TISS) com a ANS, sem rede: zip e páginas simulados."""

import datetime
import io
import os
import pathlib
import sys
import zipfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.conciliacao import tiss  # noqa: E402

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
NS_R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def xlsx_tabela_38(linhas):
    """xlsx mínimo com aba 'Capa' e 'Tab 38' no layout da ANS (cabeçalho na linha 6)."""
    textos = ["Tabela 38 - Terminologia de mensagens", "Código do Termo", "Termo",
              "Data de início de vigência", "Data de fim de vigência"]
    for codigo, termo in linhas:
        textos += [codigo, termo]
    idx = {t: i for i, t in enumerate(textos)}
    s = lambda ref, t: f'<c r="{ref}" t="s"><v>{idx[t]}</v></c>'  # noqa: E731
    corpo = f'<row r="4">{s("A4", textos[0])}</row><row r="6">{s("A6", "Código do Termo")}{s("B6", "Termo")}</row>'
    for n, (codigo, termo) in enumerate(linhas, start=7):
        corpo += f'<row r="{n}">{s(f"A{n}", codigo)}{s(f"B{n}", termo)}<c r="C{n}"><v>39037</v></c></row>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", f'<workbook {NS} {NS_R}><sheets><sheet name="Capa" r:id="r1"/>'
                                      f'<sheet name="Tab 38" r:id="r2"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="r1" Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", f'<sst {NS}>' + "".join(f"<si><t>{t}</t></si>" for t in textos) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {NS}><sheetData/></worksheet>')
        z.writestr("xl/worksheets/sheet2.xml", f'<worksheet {NS}><sheetData>{corpo}</sheetData></worksheet>')
    return buf.getvalue()


def zip_ans(xlsx):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # enchimento incompressível, como os PDFs/xlsx grandes do zip real
        z.writestr("Padrao/TUSS 22 - PROCEDIMENTOS.xlsx", os.urandom(200_000), zipfile.ZIP_STORED)
        z.writestr("Padrao/TUSS - Demais terminologias - VERSÃO 202607.xlsx", xlsx)
        z.writestr("Padrao/TUSS 19.pdf", os.urandom(200_000), zipfile.ZIP_STORED)
    return buf.getvalue()


def test_le_a_aba_tab_38():
    linhas = tiss.ler_tabela_38(xlsx_tabela_38([("1705", "VALOR APRESENTADO A MAIOR"), ("3108", "ITEM  INCLUSO")]))
    assert [(l["codigo"], l["descricao"]) for l in linhas] == [("1705", "VALOR APRESENTADO A MAIOR"),
                                                              ("3108", "ITEM INCLUSO")]
    assert linhas[0]["inicio_vigencia"] == datetime.date(2006, 11, 16)


def test_extrai_so_o_membro_pedido_por_intervalos():
    xlsx = xlsx_tabela_38([("1702", "COBRANÇA EM DUPLICIDADE")])
    arquivo = zip_ans(xlsx)
    pedidos = []

    def ler(inicio, fim):
        pedidos.append((inicio, fim))
        return arquivo[inicio:fim + 1]

    nome, conteudo = tiss.extrair_membro(ler, len(arquivo), tiss._eh_demais_terminologias)
    assert "Demais terminologias" in nome and conteudo == xlsx
    assert sum(fim - inicio + 1 for inicio, fim in pedidos) < len(arquivo)  # não baixou tudo


def test_descobre_o_zip_pela_pagina_da_versao():
    paginas = {
        tiss.PAGINA_PADRAO: b'<a href="https://www.gov.br/ans/x/padrao-tiss-julho-2026">Julho/2026</a>',
        "https://www.gov.br/ans/x/padrao-tiss-julho-2026":
            b'<a href="https://www.ans.gov.br/arquivos/extras/tiss/'
            b'Padrao_TISS_Representacao_de_Conceitos_em_Saude_202607.zip">Baixar</a>',
    }
    url, versao = tiss.descobrir_zip(obter=lambda u, intervalo=None: (paginas[u], {}))
    assert versao == "202607" and url.endswith("_202607.zip")


def test_versao_anterior_pula_as_que_nao_existem():
    existentes = {tiss._url_versao("202605")}

    def obter(url, intervalo=None):
        if url not in existentes:
            raise tiss.SincronizacaoFalhou("404")
        return b"", {}

    assert tiss.versao_anterior("202607", obter) == "202605"
    assert tiss.versao_anterior("202607", lambda *a, **k: (_ for _ in ()).throw(tiss.SincronizacaoFalhou("x")),
                                meses=3) is None


def test_mesclar_mantem_codigos_que_sairam_da_vigente():
    existentes = [{"codigo": "0001", "descricao": "ANTIGO", "vigente": True, "versao": "201712"}]
    anterior = [{"codigo": "1702", "descricao": "DUPLICIDADE"}, {"codigo": "1705", "descricao": "A MAIOR (velho)"}]
    vigente = [{"codigo": "1705", "descricao": "VALOR APRESENTADO A MAIOR"}]
    m = tiss.mesclar(existentes, anterior, vigente, "202605", "202607")
    assert m["1705"]["vigente"] and m["1705"]["descricao"] == "VALOR APRESENTADO A MAIOR"
    assert (m["1702"]["vigente"], m["1702"]["versao"]) == (False, "202605")
    assert m["0001"]["vigente"] is False  # nunca apaga o que já foi gravado


@pytest.mark.parametrize("url", ["http://www.ans.gov.br/x.zip", "https://evil.com/x.zip",
                                 "https://www.gov.br.evil.com/x.zip", "file:///etc/passwd"])
def test_so_aceita_endereco_da_ans(url):
    with pytest.raises(tiss.SincronizacaoFalhou):
        tiss._validar_url(url)
