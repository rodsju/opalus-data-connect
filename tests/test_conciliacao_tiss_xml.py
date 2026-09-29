"""XML TISS de volta: leitura, casamento com o ERP e marcação das divergências -- sem banco."""

import decimal
import pathlib

import pytest

from src.conciliacao import tiss_cruzamento, tiss_divergencias, tiss_xml

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "tiss_retorno_226689537.xml"
D = decimal.Decimal


@pytest.fixture(scope="module")
def demo():
    return tiss_xml.ler(FIXTURE.read_bytes())


def test_le_o_demonstrativo(demo):
    assert demo.tipo == tiss_xml.RETORNO and demo.padrao == "4.02.00" and demo.numero == "16792592"
    assert demo.operadora_ans == "346659" and str(demo.data_emissao) == "2026-05-19"
    assert [p.numero for p in demo.protocolos] == ["226689537"]
    assert len(demo.guias) == 3 and sum(len(g.itens) for g in demo.guias) == 32 + 32 + 1
    assert demo.glosa == D("2816.92")


def test_glosa_do_item_e_informado_menos_liberado(demo):
    compressa = next(i for g in demo.guias for i in g.itens if i.codigo == "0000266381")
    # dois motivos, cada um com o total: a glosa não é a soma de valorGlosa
    assert [m["codigo"] for m in compressa.motivos] == ["1714", "1402"]
    assert compressa.glosa == D("1710.58") and compressa.motivo_principal == "1714"
    guia = next(g for g in demo.guias if g.guia_prestador == "8045327820")
    assert guia.glosa == D("1106.34") and guia.motivo_principal == "1714"


def test_carteira_vira_hash(demo):
    assert all(g.carteira_hash and g.carteira_hash.startswith("X") for g in demo.guias)
    assert "0000000000000000" not in repr(demo)


def test_recusa_envio_e_lixo():
    envio = b'<?xml version="1.0"?><ans:mensagemTISS xmlns:ans="x"><ans:cabecalho><ans:identificacaoTransacao>' \
            b'<ans:tipoTransacao>ENVIO_LOTE_GUIAS</ans:tipoTransacao></ans:identificacaoTransacao></ans:cabecalho>' \
            b'</ans:mensagemTISS>'
    with pytest.raises(tiss_xml.XmlInvalido, match="não é importado"):
        tiss_xml.ler(envio)
    with pytest.raises(tiss_xml.XmlInvalido, match="XML válido"):
        tiss_xml.ler(b"isto nao e xml")


def test_casa_guia_pela_conta_mais_admissao(demo):
    guia = next(g for g in demo.guias if g.guia_prestador == "8045325216")
    adm = {"id_admissao": 25216, "faturado": D("5557.68")}
    contas = {80453: {25216: adm, 27820: {"id_admissao": 27820, "faturado": D("14388.34")}}}
    assert tiss_cruzamento.casar_guia(guia, contas, {}) == (
        tiss_cruzamento.CONCILIADO, "guia = conta + admissão", 80453, adm)
    divergente = {80453: {25216: {**adm, "faturado": D("5000")}}}
    assert tiss_cruzamento.casar_guia(guia, divergente, {})[0] == tiss_cruzamento.DIVERGENTE
    assert tiss_cruzamento.casar_guia(guia, {}, {})[0] == tiss_cruzamento.PROTOCOLO_NAO_ACHADO
    # guia com outro número, mas o valor bate com uma admissão da conta
    outra = {80453: {99999: {"id_admissao": 99999, "faturado": D("5557.68")}}}
    assert tiss_cruzamento.casar_guia(guia, outra, {})[1] == "valor da admissão"


def test_casa_item_glosado_por_valor(demo):
    guia = next(g for g in demo.guias if g.guia_prestador == "8045327820")
    erp = [{"id_item": 1, "cobrado": D("3847.10"), "qtd": D("31"), "preco": D("124.10")},
           {"id_item": 34440746, "cobrado": D("10541.24"), "qtd": D("62"), "preco": D("170.02")}]
    casados = tiss_cruzamento.casar_itens(guia.itens, erp)
    aquacel = [n for n, i in enumerate(guia.itens) if i.glosa > 0]
    assert aquacel and all(casados[n] == 34440746 for n in aquacel)
    assert 1 not in casados.values()  # procedimento sem glosa não é casado


def test_marcacao_das_divergencias():
    m = tiss_divergencias.marcar
    assert m(0, [], None) == [tiss_divergencias.SEM_GLOSA]
    assert m(D("10"), ["1714"], None) == [tiss_divergencias.SO_XML]
    assert m(0, [], {"glosa": D("5"), "motivos": ["1705"]}) == [tiss_divergencias.SO_PLANILHA]
    assert m(D("1710.58"), ["1402", "1714"], {"glosa": D("1710.58"), "motivos": ["1705"]}) == [tiss_divergencias.MOTIVO]
    assert m(D("10"), ["1714"], {"glosa": D("12"), "motivos": ["1714"]}) == [tiss_divergencias.VALOR]
    assert m(D("10"), ["1714"], {"glosa": D("10"), "motivos": ["1714"]}) == [tiss_divergencias.OK]
