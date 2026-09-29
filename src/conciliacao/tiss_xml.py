"""Leitura do XML TISS de volta (DEMONSTRATIVO_ANALISE_CONTA) mandado pela operadora.

Um arquivo = um demonstrativo, com um ou mais protocolos (lotes entregues); cada
protocolo tem as guias, e cada guia os itens com valor informado, processado e
liberado e os motivos de glosa (Tabela 38). Vale para TISS 4.01 e 4.02, em
ISO-8859-1 ou UTF-8: o namespace é ignorado e a codificação vem do próprio XML.

O XML de ida (ENVIO_LOTE_GUIAS) não se importa -- no futuro o sistema o gera.
Ele serviu para fechar os vínculos com o ERP: numeroGuiaPrestador = conta +
admissão (CAPPAYMENT.ID + CAPADMISSION.ID), numeroProtocolo =
CAPPAYMENT.CLI_PROTOCOENTREGA, senha = CAPBUDGET.AUTHORIZEXTCODE.

Glosa do item = informado − liberado. A soma de valorGlosa da relacaoGlosa não
serve: com dois motivos no mesmo item, cada um pode vir com o total (compressa do
protocolo 226689537: 1714 e 1402 com 1.710,58 cada). O primeiro motivo é o
principal. Privacidade: a carteira do beneficiário vira hash
(privacidade.pseudonimo) e nomes de profissional não são lidos.
"""

import dataclasses
import datetime
import decimal
import xml.etree.ElementTree as ET

from . import privacidade

RETORNO = "DEMONSTRATIVO_ANALISE_CONTA"
ENVIO = "ENVIO_LOTE_GUIAS"
ZERO = decimal.Decimal("0")


class XmlInvalido(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


@dataclasses.dataclass
class Item:
    sequencial: int | None
    data: datetime.date | None
    tabela: str
    codigo: str
    descricao: str
    quantidade: decimal.Decimal
    informado: decimal.Decimal
    processado: decimal.Decimal
    liberado: decimal.Decimal
    motivos: list  # [{"codigo", "valor", "tipo"}] na ordem do XML

    @property
    def glosa(self):
        return self.informado - self.liberado

    @property
    def motivo_principal(self):
        return self.motivos[0]["codigo"] if self.motivos else None


@dataclasses.dataclass
class Guia:
    protocolo: str
    guia_prestador: str
    guia_operadora: str
    senha: str
    carteira_hash: str | None
    situacao: str
    informado: decimal.Decimal
    processado: decimal.Decimal
    liberado: decimal.Decimal
    motivos: list  # motivoGlosaGuia: [{"codigo", "descricao"}]
    itens: list

    @property
    def glosa(self):
        return self.informado - self.liberado

    @property
    def motivo_principal(self):
        """O do item glosado de maior valor; senão, o primeiro da guia."""
        glosados = sorted((i for i in self.itens if i.glosa > 0 and i.motivos), key=lambda i: -i.glosa)
        if glosados:
            return glosados[0].motivo_principal
        return self.motivos[0]["codigo"] if self.motivos else None


@dataclasses.dataclass
class Protocolo:
    numero: str
    lote_prestador: str
    data: datetime.date | None
    situacao: str
    informado: decimal.Decimal
    processado: decimal.Decimal
    liberado: decimal.Decimal


@dataclasses.dataclass
class Demonstrativo:
    tipo: str
    padrao: str
    numero: str
    operadora_ans: str
    operadora_nome: str
    operadora_cnpj: str
    data_emissao: datetime.date | None
    protocolos: list
    guias: list

    @property
    def informado(self):
        return sum((g.informado for g in self.guias), ZERO)

    @property
    def liberado(self):
        return sum((g.liberado for g in self.guias), ZERO)

    @property
    def glosa(self):
        return sum((g.glosa for g in self.guias), ZERO)


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _filho(elemento, nome):
    for f in elemento:
        if _local(f.tag) == nome:
            return f
    return None


def _filhos(elemento, nome):
    return [f for f in elemento if _local(f.tag) == nome]


def _texto(elemento, *caminho):
    atual = elemento
    for nome in caminho:
        atual = _filho(atual, nome) if atual is not None else None
    return (atual.text or "").strip() if atual is not None and atual.text else ""


def _busca(elemento, nome):
    """Primeiro descendente com esse nome local."""
    for e in elemento.iter():
        if _local(e.tag) == nome:
            return e
    return None


def _dec(valor):
    try:
        return decimal.Decimal(valor) if valor else ZERO
    except decimal.InvalidOperation as falha:
        raise XmlInvalido("valor numérico inválido no XML", valor) from falha


def _data(valor):
    try:
        return datetime.date.fromisoformat(valor[:10]) if valor else None
    except ValueError:
        return None


def _item(d):
    return Item(
        sequencial=int(_texto(d, "sequencialItem")) if _texto(d, "sequencialItem").isdigit() else None,
        data=_data(_texto(d, "dataRealizacao")),
        tabela=_texto(d, "procedimento", "codigoTabela"),
        codigo=_texto(d, "procedimento", "codigoProcedimento"),
        descricao=_texto(d, "procedimento", "descricaoProcedimento"),
        quantidade=_dec(_texto(d, "qtdExecutada")),
        informado=_dec(_texto(d, "valorInformado")),
        processado=_dec(_texto(d, "valorProcessado")),
        liberado=_dec(_texto(d, "valorLiberado")),
        motivos=[{"codigo": _texto(r, "tipoGlosa"), "valor": str(_dec(_texto(r, "valorGlosa")))}
                 for r in _filhos(d, "relacaoGlosa")],
    )


def _guia(g, protocolo):
    carteira = _texto(g, "numeroCarteira")
    return Guia(
        protocolo=protocolo,
        guia_prestador=_texto(g, "numeroGuiaPrestador"),
        guia_operadora=_texto(g, "numeroGuiaOperadora"),
        senha=_texto(g, "senha"),
        carteira_hash=privacidade.pseudonimo(carteira) if carteira else None,
        situacao=_texto(g, "situacaoGuia"),
        informado=_dec(_texto(g, "valorInformadoGuia")),
        processado=_dec(_texto(g, "valorProcessadoGuia")),
        liberado=_dec(_texto(g, "valorLiberadoGuia")),
        motivos=[{"codigo": _texto(m, "codigoGlosa"), "descricao": _texto(m, "descricaoGlosa")}
                 for m in _filhos(g, "motivoGlosaGuia")],
        itens=[_item(d) for d in _filhos(g, "detalhesGuia")],
    )


def ler(conteudo):
    """bytes do XML -> Demonstrativo. XmlInvalido se não for um retorno TISS de análise de conta."""
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as falha:
        raise XmlInvalido("o arquivo não é um XML válido", str(falha)) from falha
    if _local(raiz.tag) != "mensagemTISS":
        raise XmlInvalido("não é uma mensagem TISS", f"raiz <{_local(raiz.tag)}>")
    identificacao = _busca(raiz, "identificacaoTransacao")
    tipo = _texto(identificacao if identificacao is not None else raiz, "tipoTransacao")
    if tipo == ENVIO:
        raise XmlInvalido("XML de envio (ENVIO_LOTE_GUIAS): não é importado",
                          "Só o retorno da operadora entra; o envio será gerado pelo sistema no futuro.")
    if tipo != RETORNO:
        raise XmlInvalido(f"transação TISS '{tipo or '?'}' não é suportada",
                          f"Esperado {RETORNO} (demonstrativo de análise de conta).")
    cabecalho = _busca(raiz, "cabecalhoDemonstrativo")
    if cabecalho is None:
        raise XmlInvalido("demonstrativo sem cabeçalho", "falta <cabecalhoDemonstrativo>")
    protocolos, guias = [], []
    for conta in (e for e in raiz.iter() if _local(e.tag) == "dadosConta"):
        for p in _filhos(conta, "dadosProtocolo"):
            numero = _texto(p, "numeroProtocolo")
            protocolos.append(Protocolo(
                numero=numero, lote_prestador=_texto(p, "numeroLotePrestador"), data=_data(_texto(p, "dataProtocolo")),
                situacao=_texto(p, "situacaoProtocolo"), informado=_dec(_texto(p, "valorInformadoProtocolo")),
                processado=_dec(_texto(p, "valorProcessadoProtocolo")),
                liberado=_dec(_texto(p, "valorLiberadoProtocolo"))))
            guias += [_guia(g, numero) for g in _filhos(p, "relacaoGuias")]
    if not guias:
        raise XmlInvalido("demonstrativo sem guias", "nenhum <relacaoGuias> no arquivo")
    return Demonstrativo(
        tipo=tipo, padrao=_texto(_busca(raiz, "cabecalho"), "Padrao"),
        numero=_texto(cabecalho, "numeroDemonstrativo"), operadora_ans=_texto(cabecalho, "registroANS"),
        operadora_nome=_texto(cabecalho, "nomeOperadora"), operadora_cnpj=_texto(cabecalho, "numeroCNPJ"),
        data_emissao=_data(_texto(cabecalho, "dataEmissao")), protocolos=protocolos, guias=guias)
