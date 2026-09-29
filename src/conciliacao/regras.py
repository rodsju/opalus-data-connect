"""As fórmulas da aba BASE OPALUS, como funções puras.

Cada função traz, no docstring, a fórmula do Excel que ela reproduz (tirada do
próprio base_glosa.xlsx). A regra é reproduzir a planilha, inclusive nas
esquisitices -- o objetivo da carga é bater com ela; onde o comportamento dela
parece errado, o comentário diz, e a correção fica como opção explícita.

Convenções do Excel que importam aqui:
- célula vazia vale 0 em comparação (DATA RECEBIMENTO vazia é "=0");
- XLOOKUP de texto não diferencia maiúscula de minúscula, mas espaço conta;
- ROUND arredonda metade para longe do zero (ROUND_HALF_UP no Decimal).
"""

import dataclasses
import datetime
import decimal
import re
import unicodedata

ZERO = decimal.Decimal("0")
CENTAVO = decimal.Decimal("0.01")

STATUS_A_VENCER = "A VENCER"
STATUS_RECEBIDO = "RECEBIDO"
STATUS_EM_ATRASO = "EM ATRASO"

GLOSA_ANALISE_OPALUS = "ANÁLISE OPALUS"
GLOSA_PAGO = "PAGO"
GLOSA_ACATADO_ANALISE = "ACATADO / ANÁLISE OPERADORA"
GLOSA_ACATADO = "ACATADO"
GLOSA_ANALISE_OPERADORA = "ANÁLISE OPERADORA"
GLOSA_MANTIDA = "GLOSA MANTIDA"
# Ordem do ciclo, usada nos gráficos
STATUS_GLOSA = [GLOSA_ANALISE_OPALUS, GLOSA_ANALISE_OPERADORA, GLOSA_ACATADO_ANALISE,
                GLOSA_ACATADO, GLOSA_PAGO, GLOSA_MANTIDA]

# Classificações canônicas e as grafias que aparecem na planilha
CLASSIFICACOES = {
    "OPERADORA": ["OPERADORA", "OPERAODRA", "OPERDORA", "OPERADOIRA"],
    "CADASTRO": ["CADASTRO", "CADATRO"],
    "SISTEMA": ["SISTEMA", "SISITEMA"],
    "FATURAMENTO": ["FATURAMENTO", "FATURMENTO", "FATRURAMENTO", "FATIRAMENTO", "FATURAENTO",
                    "FATURA,MENTO", "FTAURAMENTO"],
    "COMERCIAL": ["COMERCIAL", "COMERCIAL/OXIGENO"],
    "AUDITORIA": ["AUDITORIA"],
    "CAPTAÇÃO": ["CAPTACAO"],
    "NÚCLEO": ["NUCLEO"],
    "PRORROGAÇÃO": ["PRORROGACAO"],
}


def chave(texto):
    """Chave de busca nas premissas: sem acento, caixa alta, espaço único nas pontas e no meio.

    Mais tolerante que o XLOOKUP (que casa 'CASSI ' só com 'CASSI '). Quando a
    tolerância muda o resultado em relação à planilha, a divergência aparece no
    relatório da carga -- e quase sempre é a planilha errando por um espaço.
    """
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())


def zero(valor):
    """Célula vazia vale 0, como no Excel."""
    if valor is None:
        return ZERO
    # float do driver Oracle: pelo str, senão 0.1 vira 0.1000000000000000055511...
    return decimal.Decimal(str(valor)) if isinstance(valor, float) else decimal.Decimal(valor)


def arredondar(valor, casas=CENTAVO):
    return decimal.Decimal(valor).quantize(casas, rounding=decimal.ROUND_HALF_UP)


# --------------------------------------------------------------------------
# Premissas (as tabelas de apoio da planilha)
# --------------------------------------------------------------------------


@dataclasses.dataclass
class Premissas:
    de_para: dict = dataclasses.field(default_factory=dict)   # (empresa, convenio) -> convenio_formula
    imposto: dict = dataclasses.field(default_factory=dict)   # (empresa, convenio_formula) -> dict
    prazo: dict = dataclasses.field(default_factory=dict)     # convenio_formula -> dias
    recurso: dict = dataclasses.field(default_factory=dict)   # convenio -> dias de prazo para recorrer
    aging: list = dataclasses.field(default_factory=list)     # [(dia_inicial, grupo)] ordenado

    @classmethod
    def de_linhas(cls, de_para=(), imposto=(), prazo=(), recurso=(), aging=()):
        """Monta a partir das linhas das tabelas (list[dict]), como vêm do banco ou do CSV."""
        return cls(
            de_para={(chave(l["empresa"]), chave(l["convenio"])): l["convenio_formula"] for l in de_para},
            imposto={(chave(l["empresa"]), chave(l["convenio"])): l for l in imposto},
            prazo={chave(l["convenio"]): int(l["prazo"]) for l in prazo if l.get("prazo") is not None},
            recurso={chave(l["convenio"]): int(l["prazo_recurso"]) for l in recurso
                     if l.get("prazo_recurso") is not None},
            aging=sorted((int(l["dia"]), l["grupo"]) for l in aging),
        )


# --------------------------------------------------------------------------
# Fórmulas
# --------------------------------------------------------------------------


def convenio_formula(empresa, convenio, premissas):
    """CONVENIO FORMULA
    =XLOOKUP([EMPRESA]&[CONVENIO]; TABELA_CONVENIO_FORMULA[EMPRESA]&[CONVENIO];
             TABELA_CONVENIO_FORMULA[CONVENIO FORMULA]; "N"; 0)
    Não achou -> "N", como na planilha.
    """
    return premissas.de_para.get((chave(empresa), chave(convenio)), "N")


_DATA_NO_FIM = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})\s*$")


def competencia(periodo):
    """COMPETENCIA = 1º dia do mês da data FINAL de "01/06/2026 a 30/06/2026".
    =IFERROR(DATE(YEAR(RIGHT(periodo;10));MONTH(RIGHT(periodo;10));1); <mesmo com RIGHT 8>)
    """
    achou = _DATA_NO_FIM.search((periodo or "").strip())
    if not achou:
        return None
    _, mes, ano = (int(x) for x in achou.groups())
    if ano < 100:
        ano += 2000
    try:
        return datetime.date(ano, mes, 1)
    except ValueError:
        return None


def prazo(conv_formula, premissas):
    """PRAZO =XLOOKUP([CONVENIO FORMULA]; PRAZO_RECEBIMENTO[CONVENIO]; PRAZO_RECEBIMENTO[PRAZOS]; 0; 0)"""
    return premissas.prazo.get(chave(conv_formula), 0)


def mais_dias(data, dias):
    if data is None:
        return None
    return data + datetime.timedelta(days=int(dias or 0))


def primeiro_dia(data):
    """Mes (DA PREVISAO) =DATE(YEAR(N);MONTH(N);1)"""
    return data.replace(day=1) if data else None


def aliquota(empresa, conv_formula, premissas, na_data=None, usar_alternativas=False):
    """Imposto retido da tabela PREMISSAS, por empresa + convênio fórmula.

    A planilha usa só a coluna IMPOSTO: DATA_ALT1/IMPOSTO_ALT1 existem na tabela
    mas nenhuma fórmula lê (em set/2026, MUTUA e PORTO SEGURO BAR têm alíquota
    nova a partir de abr e fev/2026 que a planilha não aplica). Com
    `usar_alternativas=True` a alíquota passa a valer pela data.
    Não achou -> 0 (o XLOOKUP da planilha devolve 0 e o líquido vira o bruto).
    """
    linha = premissas.imposto.get((chave(empresa), chave(conv_formula)))
    if not linha:
        return None
    valor = zero(linha.get("imposto"))
    if usar_alternativas and na_data:
        for n in (1, 2):
            data_alt, imposto_alt = linha.get(f"data_alt{n}"), linha.get(f"imposto_alt{n}")
            if data_alt and imposto_alt is not None and na_data >= data_alt:
                valor = zero(imposto_alt)
    return valor


def liquido(valor, imposto):
    """=ROUND((imposto - 1) * -valor; 2), que é valor × (1 − imposto)."""
    return arredondar(zero(valor) * (1 - zero(imposto)))


def status_recebimento(r, hoje):
    """STATUS -- a SWITCH(TRUE; ...) da planilha, na mesma ordem de precedência.

    r precisa de: data_contratual, data_recebimento, data_reapresentacao,
    devolucao, prazo, valor_recebido. `hoje` é a célula W2 ("HOJE").
    """
    contratual = r.get("data_contratual")
    recebido_em = r.get("data_recebimento")
    reapresentacao = r.get("data_reapresentacao")
    devolucao = r.get("devolucao")
    prazo_ = r.get("prazo") or 0

    if contratual and contratual > hoje:
        return STATUS_A_VENCER if not recebido_em else STATUS_RECEBIDO
    if devolucao and not reapresentacao:
        return STATUS_A_VENCER if mais_dias(devolucao, prazo_) > hoje else STATUS_EM_ATRASO
    if reapresentacao and recebido_em and recebido_em > reapresentacao:
        return STATUS_RECEBIDO
    if reapresentacao and zero(r.get("valor_recebido")) < 1:
        return STATUS_EM_ATRASO if mais_dias(reapresentacao, prazo_) < hoje else STATUS_A_VENCER
    if recebido_em:
        return STATUS_RECEBIDO
    # Sem data contratual o Excel compara 0+prazo com hoje: sempre atrasado.
    if not contratual or contratual < hoje:
        return STATUS_EM_ATRASO
    return STATUS_A_VENCER


def dias_atraso(r, status, hoje):
    """DIAS DE ATRASO: só existe para EM ATRASO. Reapresentada conta do prazo da reapresentação."""
    if status != STATUS_EM_ATRASO:
        return None
    if r.get("data_reapresentacao"):
        return (hoje - mais_dias(r["data_reapresentacao"], r.get("prazo") or 0)).days
    if r.get("data_contratual"):
        return (hoje - r["data_contratual"]).days
    return None


def faixa_aging(dias, premissas):
    """AGING =XLOOKUP([DIAS DE ATRASO]; Guia_Aging[Dia]; Guia_Aging[Grupo]; ""; -1)
    -1 = igual ou o próximo menor; abaixo da primeira faixa, vazio.
    """
    if dias is None:
        return None
    grupo = None
    for inicio, nome in premissas.aging:
        if dias >= inicio:
            grupo = nome
    return grupo


def status_glosa(r):
    """STATUS DA GLOSA -- a SWITCH da planilha, na mesma ordem (o primeiro que casa vence)."""
    glosa = zero(r.get("glosa"))
    recursado = zero(r.get("valor_recursado"))
    acatada = zero(r.get("glosa_acatada"))
    recebido_liq = zero(r.get("valor_recurso_liquido"))
    mantida = zero(r.get("glosa_mantida"))
    recebido_em = r.get("data_receb_recurso")

    if glosa != 0 and recursado == 0 and acatada == 0 and recebido_liq == 0:
        return GLOSA_ANALISE_OPALUS
    if recebido_em and recebido_liq != 0:
        return GLOSA_PAGO
    if recursado != 0 and acatada != 0 and (recursado - mantida) != 0:
        return GLOSA_ACATADO_ANALISE
    if acatada != 0 and recursado == 0:
        return GLOSA_ACATADO
    if recursado != 0 and acatada == 0 and recebido_liq == 0 and mantida == 0:
        return GLOSA_ANALISE_OPERADORA
    if recebido_em and recebido_liq == 0 and mantida != 0:
        return GLOSA_MANTIDA
    return None


def prazo_recurso(r, st_glosa, premissas):
    """DATA DE PRAZO P/ RECURSO
    =IF([STATUS DA GLOSA]<>""; [DATA RECEBIMENTO] + INDEX(PREMISSAS_RECURSO[PRAZO];
        MATCH([CONVENIO]; PREMISSAS_RECURSO[CONVENIO]; 0)); "")
    Busca pelo CONVENIO digitado (não pelo convênio fórmula). Sem prazo cadastrado
    a planilha dá #N/D; aqui volta None e a linha fica pendente de premissa.
    """
    if not st_glosa or not r.get("data_recebimento"):
        return None
    dias = premissas.recurso.get(chave(r.get("convenio")))
    return mais_dias(r["data_recebimento"], dias) if dias is not None else None


def normalizar_classificacao(bruta):
    """'OPERAODRA ' -> 'OPERADORA'. Desconhecida volta em caixa alta, para não sumir."""
    if bruta is None:
        return None
    alvo = chave(bruta)
    if alvo in ("", "0"):
        return None
    for canonica, grafias in CLASSIFICACOES.items():
        if alvo in grafias:
            return canonica
    return alvo


# --------------------------------------------------------------------------
# Linha inteira
# --------------------------------------------------------------------------


def calcular(r, premissas, hoje, usar_alternativas=False):
    """Preenche os campos calculados de uma linha e devolve (linha, pendências).

    Pendência = premissa que faltou (sem de-para, sem prazo, sem imposto, sem
    prazo de recurso): o cálculo segue como a planilha seguiria, mas a linha
    fica marcada para alguém cadastrar a premissa.
    """
    pendencias = []
    saida = dict(r)
    # O CONVENIO FORMULA é coluna de fórmula, mas o time sobrescreve à mão por
    # filial (CASSI em BSB vira CASSI-BSB; na base de set/2026, 471 linhas
    # diferem do de-para, e nem por filial a escolha é consistente). Então o
    # valor que veio na linha prevalece; o de-para só entra quando vem vazio.
    do_de_para = convenio_formula(r.get("empresa"), r.get("convenio"), premissas)
    informado = (r.get("convenio_formula_planilha") or "").strip()
    conv = informado if informado and informado.upper() != "N" else do_de_para
    saida["convenio_formula_de_para"] = do_de_para
    saida["convenio_formula_manual"] = bool(informado) and chave(informado) != chave(do_de_para)
    if conv == "N":
        pendencias.append("sem de-para de convênio")
    saida["convenio_formula"] = conv
    saida["competencia"] = competencia(r.get("periodo"))
    dias = prazo(conv, premissas)
    if not dias:
        pendencias.append("sem prazo de recebimento")
    saida["prazo"] = dias
    saida["data_contratual"] = mais_dias(r.get("data_entrega"), dias)
    saida["mes_previsao"] = primeiro_dia(saida["data_contratual"])

    imposto = aliquota(r.get("empresa"), conv, premissas, saida["competencia"], usar_alternativas)
    if imposto is None:
        pendencias.append("sem alíquota de imposto")
    saida["imposto"] = imposto
    saida["valor_liquido"] = liquido(r.get("valor_faturado"), imposto)
    saida["base_calculo_1"] = zero(r.get("valor_faturado")) - zero(r.get("glosa"))
    saida["base_calculo_2"] = liquido(saida["base_calculo_1"], imposto)

    saida["status"] = status_recebimento(saida, hoje)
    saida["dias_atraso"] = dias_atraso(saida, saida["status"], hoje)
    saida["aging"] = faixa_aging(saida["dias_atraso"], premissas)

    saida["classificacao"] = normalizar_classificacao(r.get("classificacao_bruta"))
    saida["status_glosa"] = status_glosa(saida)
    saida["prazo_recurso"] = prazo_recurso(saida, saida["status_glosa"], premissas)
    if saida["status_glosa"] and saida["prazo_recurso"] is None and r.get("data_recebimento"):
        pendencias.append("sem prazo de recurso")
    return saida, pendencias


# Colunas calculadas que dá para comparar com o que a planilha trouxe
COMPARAVEIS = ["convenio_formula", "competencia", "prazo", "data_contratual", "valor_liquido",
               "base_calculo_1", "base_calculo_2", "status", "dias_atraso", "aging",
               "status_glosa", "prazo_recurso"]


def divergencias(linha):
    """Campos em que o recálculo difere do valor que veio da planilha (quando veio)."""
    saida = []
    for campo in COMPARAVEIS:
        planilha = linha.get(f"{campo}_planilha")
        app = linha.get(campo)
        # Data vazia no Excel somada a um prazo vira 1900 (0 + 31 dias): é vazio.
        if isinstance(planilha, datetime.date) and planilha.year < 1901:
            planilha = None
        if planilha is None and app in (None, ""):
            continue
        if campo not in linha or f"{campo}_planilha" not in linha:
            continue
        if isinstance(app, decimal.Decimal) or isinstance(planilha, decimal.Decimal):
            if abs(zero(app) - zero(planilha)) > CENTAVO:
                saida.append(campo)
        elif isinstance(app, str) or isinstance(planilha, str):
            if chave(app) != chave(planilha):
                saida.append(campo)
        elif app != planilha:
            saida.append(campo)
    return saida
