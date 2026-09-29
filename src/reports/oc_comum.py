"""Peças comuns aos blocos de Ocupação (bloco_oc_*)."""

import datetime

from . import comum, fonte

HT, HC, AMB = 0, 1, 3
JANELA_DIAS = 90


def leitos(filtros=None):
    """{unidade: leitos} vigentes hoje (hospital de transição), no recorte dos filtros. Parâmetro no Postgres.

    Com filtro de unidade, só a dela; com filtro de tipo que não seja transição, nenhum (não há leito).
    """
    if filtros is not None and filtros.tipo not in ("", str(HT)):
        return {}
    try:
        cap = {l["unidade"]: int(l["leitos"]) for l in fonte.rodar("oc_leitos", {}) if l["tipo_atendimento"] == HT}
    except comum.ConsultaFalhou:
        return {}
    if filtros is not None and filtros.unidade:
        cap = {u: n for u, n in cap.items() if u.strip().upper() == filtros.unidade.strip().upper()}
    return cap


def atual(filtros):
    return filtros.rodar("ocupacao_atual", com_periodo=False)


def historico(filtros):
    """Censo diário dos últimos JANELA_DIAS dias. Guardado na memória da página (dois blocos usam)."""
    chave = ("ocupacao_historico", "janela")
    if chave not in filtros._memo:
        fim = datetime.date.today() + datetime.timedelta(days=1)
        params = {**filtros.params(com_periodo=False), "DT_INI": fim - datetime.timedelta(days=JANELA_DIAS),
                  "DT_FIM": fim}
        filtros._memo[chave] = fonte.rodar("ocupacao_historico", params)
    return filtros._memo[chave]


def por_unidade_ht(linhas_atual, capacidade):
    """Linhas de hospital de transição com leitos, livres e taxa por unidade."""
    ocup = {l["unidade"]: l for l in linhas_atual if l["tipo"] == HT}
    unidades = sorted(set(ocup) | set(capacidade))
    saida = []
    for u in unidades:
        o = ocup.get(u, {})
        n, cap = int(comum.num(o.get("ocupados"))), capacidade.get(u)
        saida.append({"unidade": u, "leitos": cap, "ocupados": n, "livres": (cap - n) if cap else None,
                      "taxa": comum.pct(n, cap) if cap else None,
                      "permanencia": comum.num(o.get("permanencia_media")) if o else None})
    return sorted(saida, key=lambda x: -(x["leitos"] or 0))
