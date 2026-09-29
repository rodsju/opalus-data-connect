"""Peças compartilhadas pelos blocos: período, filtros e utilitários de montagem."""

import concurrent.futures
import datetime
import threading

from . import fonte
from .fonte import ConsultaFalhou  # noqa: F401  (reexportado para os blocos)


class PeriodoInvalido(Exception):
    pass


def periodo(mes):
    """'2026-06' -> (2026-06-01, 2026-07-01). O fim é EXCLUSIVO, como nas SQLs."""
    try:
        ano, numero = (mes or "").strip().split("-")
        inicio = datetime.date(int(ano), int(numero), 1)
    except (ValueError, TypeError) as falha:
        raise PeriodoInvalido(f"'{mes}' não é um mês no formato AAAA-MM") from falha
    fim = (inicio.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return inicio, fim


def mes_padrao(hoje=None):
    """Mês anterior ao corrente: o último que já fechou competência."""
    hoje = hoje or datetime.date.today()
    anterior = hoje.replace(day=1) - datetime.timedelta(days=1)
    return anterior.strftime("%Y-%m")


MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def rotulo_mes(inicio):
    return f"{MESES[inicio.month - 1]}/{inicio.year}"


class Filtros:
    """Recorte de uma página + memória das consultas já feitas nela.

    Blocos diferentes pedem a mesma consulta (o resumo e o bloco de status leem
    contas_por_status). Sem cache entre requisições, mas dentro de uma página a
    mesma consulta roda uma vez só -- quem chega depois espera a do primeiro.
    """

    TIPOS = {"": "Todos os tipos", "0": "Hospital de transição", "1": "Home care", "3": "Ambulatorial"}

    def __init__(self, mes, unidade="", convenio="", motivo="", tipo=""):
        # mes vazio = todas as competências (só relatórios com periodo_opcional)
        self.mes = (mes or "").strip()
        self.inicio, self.fim = periodo(self.mes) if self.mes else (None, None)
        self.unidade = (unidade or "").strip()
        self.convenio = (convenio or "").strip()
        self.motivo = (motivo or "").strip()
        # Tipo de atendimento: código de CAPADMISSION.ADMISSIONTYPE ("" = todos)
        tipo = str("" if tipo is None else tipo).strip()
        self.tipo = tipo if tipo in self.TIPOS else ""
        self._memo = {}
        self._trava = threading.Lock()

    @property
    def rotulo_tipo(self):
        return self.TIPOS.get(self.tipo, "")

    @property
    def rotulo_periodo(self):
        return rotulo_mes(self.inicio) if self.inicio else "todas"

    def params(self, com_periodo=True):
        binds = {"UNIDADE": self.unidade or None, "TIPO": int(self.tipo) if self.tipo else None}
        if self.convenio:
            binds["CONVENIO"] = self.convenio
        if self.motivo:
            binds["MOTIVO"] = self.motivo if self.motivo != "(sem código)" else None
        if com_periodo:
            binds.update(DT_INI=self.inicio, DT_FIM=self.fim)
        return binds

    def rodar(self, nome, limite=None, com_periodo=True, unidade=True):
        params = self.params(com_periodo)
        if not unidade:
            params["UNIDADE"] = None
            params.pop("CONVENIO", None)
            params.pop("MOTIVO", None)
        chave = (nome, limite, com_periodo, unidade)
        with self._trava:
            futuro = self._memo.get(chave)
            dono = futuro is None
            if dono:
                futuro = self._memo[chave] = concurrent.futures.Future()
        if dono:
            try:
                futuro.set_result(fonte.rodar(nome, params, limite=limite))
            except Exception as erro:  # noqa: BLE001 -- repassado a quem espera
                futuro.set_exception(erro)
        return futuro.result()


# --------------------------------------------------------------------------
# Montagem
# --------------------------------------------------------------------------


def num(valor):
    return float(valor) if valor is not None else 0.0


def pct(parte, todo):
    return (num(parte) / num(todo) * 100) if num(todo) else None


def somar_por(linhas, chave, campos):
    """Agrupa list[dict] por `chave`, somando `campos`. Mantém a ordem de chegada."""
    saida = {}
    for linha in linhas:
        grupo = saida.setdefault(linha.get(chave), {chave: linha.get(chave), **{c: 0.0 for c in campos}})
        for campo in campos:
            grupo[campo] += num(linha.get(campo))
    return list(saida.values())


def ordenar(linhas, campo):
    return sorted(linhas, key=lambda linha: num(linha.get(campo)), reverse=True)


def com_participacao(linhas, campo):
    """Acrescenta pct (do total) e pct_acum (pareto) em cada linha já ordenada."""
    total = sum(num(linha.get(campo)) for linha in linhas)
    acumulado = 0.0
    for linha in linhas:
        acumulado += num(linha.get(campo))
        linha["pct"] = pct(linha.get(campo), total)
        linha["pct_acum"] = pct(acumulado, total)
    return total


def top_com_outros(linhas, rotulo, campos, n, nome_outros="Demais"):
    """Primeiras n linhas + uma linha somando o resto (se houver resto)."""
    if len(linhas) <= n:
        return list(linhas)
    resto = {rotulo: f"{nome_outros} ({len(linhas) - n})", "outros": True}
    for campo in campos:
        resto[campo] = sum(num(linha.get(campo)) for linha in linhas[n:])
    return list(linhas[:n]) + [resto]


def grafico(tipo, rotulos, series, formato="moeda", **extra):
    """Especificação lida por static/js/reports.js. Valores já em float."""
    return {
        "tipo": tipo,
        "rotulos": [str(r) for r in rotulos],
        "series": [{**s, "valores": [round(num(v), 2) for v in s["valores"]]} for s in series],
        "formato": formato,
        **extra,
    }


# Situação da conta -> tom do badge/cor da série. A ordem é a do ciclo de vida.
SITUACOES_CONTA = [
    ("Exportada (fechada)", "success"),
    ("Liberada (não exportada)", "info"),
    ("Aberta (não liberada)", "warning"),
    ("Baixada (write-off)", "danger"),
    ("Simulação", "neutral"),
]
TOM_SITUACAO_CONTA = dict(SITUACOES_CONTA)
SITUACOES_ABERTAS = {"Aberta (não liberada)", "Liberada (não exportada)"}

SITUACOES_ORCAMENTO = [
    ("Autorizado (operadora)", "success"),
    ("Autorizado (interno)", "info"),
    ("Liberado", "violet"),
    ("Pendente", "warning"),
    ("Cancelado", "danger"),
]
TOM_SITUACAO_ORCAMENTO = dict(SITUACOES_ORCAMENTO)


def cascata(passos):
    """[(rótulo, valor, tipo, descrição)] -> gráfico de cascata + linhas da tabela.

    tipo: 'total' (barra desde o zero), 'neg' (sai do acumulado: perda, vermelho),
    'saida' (sai do acumulado mas é bom: recebido, verde), 'pos' (soma, verde).

    A participação de cada passo é sobre o primeiro total (o topo da cascata).
    """
    topo = num(passos[0][1]) if passos else 0
    linhas = [{"rotulo": r, "valor": num(v), "tipo": t, "descricao": d, "pct": pct(v, topo)}
              for r, v, t, d in passos]
    return {
        "grafico": grafico("cascata", [l["rotulo"] for l in linhas],
                           [{"nome": "Cascata", "valores": [l["valor"] for l in linhas]}],
                           passos=[l["tipo"] for l in linhas]),
        "passos": linhas,
    }
