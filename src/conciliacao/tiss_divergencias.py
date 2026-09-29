"""Documento (.md) das divergências entre o XML TISS de volta, a planilha e o ERP.

Um documento por arquivo carregado. Para cada guia (= admissão na conta):
faturado do ERP, informado e glosa no XML, faturado e glosa na planilha, motivo
do XML × da planilha e o status do recurso (que só a planilha tem). O XML é a
fonte da glosa; a planilha, do recurso. Paciente só por código ('P' + ID).
"""

import collections
import decimal

from ..reports import bloco_pre_auditoria
from . import banco

CENTAVO = decimal.Decimal("0.01")

OK = "✓"
SEM_GLOSA = "✓ pago integral (sem glosa no XML nem na planilha)"
VALOR = "valor diverge"
MOTIVO = "motivo diverge"
SO_XML = "só no XML"
SO_PLANILHA = "só na planilha"


def _m(valor):
    v = decimal.Decimal(valor or 0).quantize(CENTAVO)
    inteiro, _, cent = f"{abs(v):,.2f}".partition(".")
    return ("-" if v < 0 else "") + "R$ " + inteiro.replace(",", ".") + "," + cent


def marcar(xml_glosa, xml_motivos, planilha):
    """Marcações de uma guia. planilha: {'glosa', 'motivos'} ou None. Puro."""
    xml_glosa = decimal.Decimal(xml_glosa or 0)
    tem_planilha = planilha is not None and decimal.Decimal(planilha["glosa"] or 0) > 0
    if xml_glosa <= 0 and not tem_planilha:
        return [SEM_GLOSA]
    if xml_glosa > 0 and not tem_planilha:
        return [SO_XML]
    if xml_glosa <= 0:
        return [SO_PLANILHA]
    marcas = []
    if abs(xml_glosa - decimal.Decimal(planilha["glosa"])) > CENTAVO:
        marcas.append(VALOR)
    if not set(planilha["motivos"]) & set(xml_motivos):
        marcas.append(MOTIVO)
    return marcas or [OK]


def _dados(arquivo_id):
    arquivo = banco.um("SELECT id, arquivo, operadora_nome, operadora_ans, numero_demonstrativo, data_emissao, padrao, "
                       "informado, liberado, glosa, resumo FROM conciliacao.tiss_arquivo WHERE id = %s", (arquivo_id,),
                       "arquivo TISS")
    if not arquivo:
        return None, [], {}, {}
    guias = banco.consultar(
        "SELECT id, protocolo, guia_prestador, situacao, regra, id_conta, id_admissao, id_paciente, faturado_erp, "
        "informado, liberado, glosa, motivo_principal FROM conciliacao.tiss_guia WHERE arquivo_id = %s "
        "ORDER BY glosa DESC, guia_prestador", (arquivo_id,), "guias TISS")
    itens = collections.defaultdict(list)
    for i in banco.consultar(
            "SELECT i.guia_id, i.descricao, i.tabela, i.codigo, i.quantidade, i.informado, i.liberado, i.glosa, "
            "i.motivos, i.id_item_erp FROM conciliacao.tiss_item i JOIN conciliacao.tiss_guia g ON g.id = i.guia_id "
            "WHERE g.arquivo_id = %s AND i.glosa > 0 ORDER BY i.glosa DESC", (arquivo_id,), "itens glosados TISS"):
        itens[i["guia_id"]].append(i)
    contas = sorted({g["id_conta"] for g in guias if g["id_conta"]})
    planilha = collections.defaultdict(lambda: {"glosa": decimal.Decimal(0), "motivos": [], "status": [], "linhas": []})
    if contas:
        for l in banco.consultar(
                "SELECT g.linha, g.glosa, g.motivo, g.status_glosa, g.valor_faturado, x.id_conta, x.id_admissao "
                "FROM conciliacao.glosa_linha g JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa "
                "AND c.tipo = 'glosa' JOIN conciliacao.cruzamento x ON x.carga_id = g.carga_id AND x.linha = g.linha "
                "WHERE x.id_conta = ANY(%s)", (contas,), "planilha das contas do XML"):
            p = planilha[(l["id_conta"], l["id_admissao"])]
            p["glosa"] += decimal.Decimal(l["glosa"] or 0)
            p["linhas"].append(l["linha"])
            if l["motivo"] and l["motivo"] not in p["motivos"]:
                p["motivos"].append(l["motivo"])
            if l["status_glosa"] and l["status_glosa"] not in p["status"]:
                p["status"].append(l["status_glosa"])
    return arquivo, guias, itens, planilha


def gerar(arquivo_id):
    """Markdown das divergências de um arquivo carregado, ou None se o arquivo não existe."""
    arquivo, guias, itens, planilha = _dados(arquivo_id)
    if arquivo is None:
        return None
    textos = bloco_pre_auditoria.descricoes()
    desc = lambda c: (textos.get(c, ("",))[0] or "").capitalize()  # noqa: E731
    linhas_tabela, contagem, detalhes = [], collections.Counter(), []
    usadas = set()
    for g in guias:
        chave = (g["id_conta"], g["id_admissao"])
        p = planilha.get(chave)
        usadas.add(chave)
        motivos_xml = sorted({m["codigo"] for i in itens.get(g["id"], []) for m in (i["motivos"] or [])})
        marcas = marcar(g["glosa"], motivos_xml, p)
        contagem.update(marcas)
        paciente = f"P{g['id_paciente']}" if g["id_paciente"] else "—"
        linhas_tabela.append(
            f"| {g['guia_prestador']} | {g['id_conta'] or '—'} / {g['id_admissao'] or '—'} | {paciente} "
            f"| {g['situacao']} | {_m(g['faturado_erp'])} | {_m(g['informado'])} | {_m(g['glosa'])} "
            f"| {', '.join(motivos_xml) or '—'} | {_m(p['glosa']) if p else '—'} | {', '.join(p['motivos']) if p else '—'} "
            f"| {', '.join(p['status']) if p else '—'} | {' · '.join(marcas)} |")
        for i in itens.get(g["id"], []):
            motivos = "; ".join(f"{m['codigo']} {desc(m['codigo'])}".strip() for m in (i["motivos"] or []))
            detalhes.append(f"| {g['guia_prestador']} | {i['descricao']} | {i['tabela']} · {i['codigo']} "
                            f"| {i['quantidade']} | {_m(i['informado'])} | {_m(i['liberado'])} | {_m(i['glosa'])} "
                            f"| {motivos or '—'} | {i['id_item_erp'] or '—'} |")
    so_planilha = [(k, v) for k, v in planilha.items() if k not in usadas and v["glosa"] > 0]
    resumo = arquivo["resumo"] or {}
    total_planilha = sum((planilha[(g["id_conta"], g["id_admissao"])]["glosa"] for g in guias
                          if (g["id_conta"], g["id_admissao"]) in planilha), decimal.Decimal(0))
    faturado_erp = sum((decimal.Decimal(g["faturado_erp"] or 0) for g in guias), decimal.Decimal(0))
    partes = [
        f"# Divergências XML × planilha × ERP — demonstrativo {arquivo['numero_demonstrativo']}",
        "",
        f"- **Operadora:** {arquivo['operadora_nome']} (ANS {arquivo['operadora_ans']}) · TISS {arquivo['padrao']}",
        f"- **Arquivo:** `{arquivo['arquivo']}` · emitido em {arquivo['data_emissao']:%d/%m/%Y}"
        if arquivo["data_emissao"] else f"- **Arquivo:** `{arquivo['arquivo']}`",
        f"- **Protocolos:** {', '.join(resumo.get('protocolos', []))}",
        f"- **Guias:** {len(guias)} · casamento com o ERP: "
        + ", ".join(f"{k} {v}" for k, v in (resumo.get("por_situacao") or {}).items()),
        "",
        "Regra: o XML é a fonte da glosa (valor, motivo e item) e sobrepõe a planilha no que divergir; recurso, "
        "recuperado e perda continuam vindo da planilha. Paciente só por código (P + ID do ERP).",
        "",
        "## Totais",
        "",
        "| | Faturado ERP | Informado (XML) | Liberado (XML) | Glosa (XML) | Glosa (planilha) |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Arquivo | {_m(faturado_erp)} | {_m(arquivo['informado'])} | {_m(arquivo['liberado'])} "
        f"| {_m(arquivo['glosa'])} | {_m(total_planilha)} |",
        "",
        "## Resultado",
        "",
        *[f"- **{k}:** {v} guia(s)" for k, v in contagem.most_common()],
        *([f"- **{SO_PLANILHA} (admissão fora do XML):** {len(so_planilha)} linha(s) de glosa da planilha "
           "nestas contas sem guia no XML"] if so_planilha else []),
        "",
        "## Por guia (admissão na conta)",
        "",
        "| Guia | Conta / admissão | Paciente | ERP | Faturado ERP | Informado (XML) | Glosa (XML) | Motivos (XML) "
        "| Glosa (planilha) | Motivo (planilha) | Status (planilha) | Marcação |",
        "|---|---|---|---|---:|---:|---:|---|---:|---|---|---|",
        *linhas_tabela,
        "",
    ]
    if detalhes:
        partes += ["## Itens glosados (XML)", "",
                   "| Guia | Procedimento | Tabela · código | Qtd | Informado | Liberado | Glosa | Motivos | Item ERP |",
                   "|---|---|---|---:|---:|---:|---:|---|---|", *detalhes, ""]
    if so_planilha:
        partes += ["## Glosa na planilha sem guia no XML", "",
                   "| Conta / admissão | Glosa (planilha) | Motivo | Status |", "|---|---:|---|---|",
                   *[f"| {k[0]} / {k[1] or '—'} | {_m(v['glosa'])} | {', '.join(v['motivos'])} | {', '.join(v['status'])} |"
                     for k, v in so_planilha], ""]
    motivos_citados = sorted({c for g in guias for i in itens.get(g["id"], []) for m in (i["motivos"] or [])
                              for c in [m["codigo"]]} | {c for v in planilha.values() for c in v["motivos"]})
    if motivos_citados:
        partes += ["## Motivos citados (Tabela 38 TISS)", "",
                   *[f"- **{c}** — {desc(c) or 'sem descrição na Tabela 38 sincronizada'}" for c in motivos_citados],
                   ""]
    return "\n".join(partes)
