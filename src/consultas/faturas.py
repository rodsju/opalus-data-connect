"""Consultas › Faturas: uma linha por conta (fatura), somando os pacientes e orçamentos dela.

Agrega as mesmas linhas da Conta do paciente (conta × admissão × orçamento), então
os números das duas consultas fecham entre si. Orçado = soma dos orçamentos
distintos faturados na conta, cada um pelo valor inteiro (um orçamento pode ser
faturado em mais de uma conta).
"""

from ..reports import comum
from . import conta_paciente

SOMAS = ("bruto", "pacote", "pre_auditoria", "desconto_informativo", "faturamento_grupo", "particular",
         "fatura_operadora", "tributos_erp", "glosa_iw", "itens", "itens_pre_auditados")


def agrupar(linhas):
    """Linhas da Conta do paciente -> uma por conta. Puro."""
    contas = {}
    for l in linhas:
        c = contas.get(l["id_conta"])
        if c is None:
            c = contas[l["id_conta"]] = {
                k: l.get(k) for k in ("id_conta", "competencia", "protocolo", "data_entrega", "nota_fiscal", "nf_origem",
                                      "situacao", "unidade", "operadora", "pagador")}
            c.update({k: 0.0 for k in SOMAS})
            c.update(_pacientes=set(), _orcamentos={}, _tipos=set(), _origens=set(), glosa=None, recuperado=None,
                     perda=None)
        for k in SOMAS:
            c[k] += comum.num(l.get(k))
        c["_pacientes"].add(l.get("id_admissao"))
        if l.get("id_orcamento"):
            c["_orcamentos"][l["id_orcamento"]] = l.get("orcado")
        if l.get("tipo_nome"):
            c["_tipos"].add(l["tipo_nome"])
        if l.get("origem_glosa"):
            c["_origens"].update(l["origem_glosa"].split("/"))
        for k in ("glosa", "recuperado", "perda"):  # já vem uma vez por paciente na conta
            if l.get(k) is not None:
                c[k] = (c[k] or 0) + l[k]
    saida = []
    for c in contas.values():
        orcados = [v for v in c["_orcamentos"].values() if v is not None]
        saida.append({**{k: v for k, v in c.items() if not k.startswith("_")},
                      "pacientes": len(c["_pacientes"]), "orcamentos": len(c["_orcamentos"]),
                      "orcado": sum(orcados) if orcados else None,
                      "tipos": ", ".join(sorted(c["_tipos"])),
                      "origem_rotulo": (f"({'/'.join(sorted(c['_origens'], key=lambda o: o != 'xml'))})"
                                        if c["_origens"] else None),
                      "detalhe": f"/consultas/conta-paciente?mes={c['competencia']:%Y-%m}&busca={c['id_conta']}"
                      if c.get("competencia") else f"/consultas/conta-paciente?busca={c['id_conta']}"})
    return sorted(saida, key=lambda c: -c["fatura_operadora"])


def _passa(c, f):
    if f.get("fatura") and c.get("situacao") != f["fatura"]:
        return False
    for campo, filtro in (("pre_auditoria", "pre"), ("desconto_informativo", "desconto"), ("glosa", "glosa")):
        if not conta_paciente._com_sem(c.get(campo), f.get(filtro)):
            return False
    desfecho = f.get("desfecho")
    rec, perda = comum.num(c["recuperado"]) > 0, comum.num(c["perda"]) > 0
    if desfecho == "recuperado" and not rec or desfecho == "perda" and not perda:
        return False
    if desfecho == "ambos" and not (rec and perda) or desfecho == "aberto" and (not c["glosa"] or rec or perda):
        return False
    return True


def carregar(f):
    base = conta_paciente.carregar({k: f.get(k) for k in ("mes", "unidade", "tipo")})
    operadora = (f.get("operadora") or "").strip().upper()
    busca = (f.get("busca") or "").strip().upper()
    nf = (f.get("nf") or "").strip().lstrip("0")
    saida = []
    for c in agrupar(base):
        if not _passa(c, f):
            continue
        if operadora and operadora not in (c.get("operadora") or "").upper():
            continue
        if busca and busca not in (str(c["id_conta"]), (c.get("protocolo") or "").upper()):
            continue
        if nf == "-" and c.get("nota_fiscal") or nf not in ("", "-") and nf not in (c.get("nota_fiscal") or ""):
            continue
        saida.append(c)
    return saida


def resumo(contas):
    soma = lambda k: sum(comum.num(c.get(k)) for c in contas)  # noqa: E731
    return [
        {"rotulo": "Faturas", "valor": len(contas), "formato": "int", "icone": "receipt", "tom": "blue",
         "hint": f"{sum(1 for c in contas if c.get('nota_fiscal'))} com nota fiscal"},
        {"rotulo": "Faturamento", "valor": soma("faturamento_grupo"), "formato": "moeda_curta", "icone": "banknote",
         "tom": "cyan"},
        {"rotulo": "Pré-auditoria", "valor": soma("pre_auditoria"), "formato": "moeda_curta", "icone": "scan-search",
         "tom": "violet"},
        {"rotulo": "Fatura operadora", "valor": soma("fatura_operadora"), "formato": "moeda_curta",
         "icone": "building-2", "tom": "teal"},
        {"rotulo": "Glosa", "valor": soma("glosa"), "formato": "moeda_curta", "icone": "shield-x",
         "tom": "coral"},
    ]


CONSULTA = {
    "slug": "faturas", "titulo": "Faturas", "icone": "receipt", "larga": True,
    "descricao": "Uma linha por fatura (conta): nota fiscal, situação, pacientes e orçamentos, a cascata (bruto, "
                 "pacote, pré-auditoria, desconto, faturamento, fatura da operadora) e a glosa da planilha. A conta "
                 "abre a Conta do paciente com os pacientes e orçamentos dela.",
    "filtros": [
        {"nome": "mes", "rotulo": "Competência da conta", "tipo": "mes", "padrao": ""},
        {"nome": "unidade", "rotulo": "Unidade", "tipo": "select", "opcoes": conta_paciente._unidades},
        {"nome": "tipo", "rotulo": "Tipo de atendimento", "tipo": "select", "opcoes": conta_paciente.TIPOS},
        {"nome": "operadora", "rotulo": "Operadora (contém)", "tipo": "texto"},
        {"nome": "busca", "rotulo": "Conta ou protocolo", "tipo": "texto"},
        {"nome": "nf", "rotulo": "Nota fiscal (\"-\" = sem nota)", "tipo": "texto"},
        {"nome": "fatura", "rotulo": "Status da fatura", "tipo": "select",
         "opcoes": [(s, s) for s, _ in comum.SITUACOES_CONTA if s != "Simulação"]},
        {"nome": "pre", "rotulo": "Pré-auditoria", "tipo": "select", "opcoes": conta_paciente.COM_SEM},
        {"nome": "desconto", "rotulo": "Desconto", "tipo": "select", "opcoes": conta_paciente.COM_SEM},
        {"nome": "glosa", "rotulo": "Glosa", "tipo": "select", "opcoes": [("com", "Com glosa"),
                                                                                  ("sem", "Sem glosa")]},
        {"nome": "desfecho", "rotulo": "Recuperação e perda", "tipo": "select", "opcoes": conta_paciente.DESFECHOS},
    ],
    "colunas": [
        {"campo": "competencia", "rotulo": "Comp.", "formato": "data"},
        {"campo": "id_conta", "rotulo": "Conta", "formato": "mono", "sub": "protocolo", "link": "{detalhe}"},
        {"campo": "nota_fiscal", "rotulo": "Nota fiscal", "formato": "mono", "sub": "nf_origem"},
        {"campo": "operadora", "rotulo": "Operadora", "sub": "unidade"},
        {"campo": "situacao", "rotulo": "Situação", "formato": "badge"},
        {"campo": "pacientes", "rotulo": "Pacientes", "formato": "int", "num": True},
        {"campo": "orcamentos", "rotulo": "Orçamentos", "formato": "int", "num": True},
        {"campo": "orcado", "rotulo": "Orçado", "formato": "moeda", "num": True},
        {"campo": "bruto", "rotulo": "Bruto", "formato": "moeda", "num": True},
        {"campo": "pacote", "rotulo": "Pacote", "formato": "moeda", "num": True},
        {"campo": "pre_auditoria", "rotulo": "Pré-auditoria", "formato": "moeda", "num": True},
        {"campo": "desconto_informativo", "rotulo": "Desconto", "formato": "moeda", "num": True},
        {"campo": "faturamento_grupo", "rotulo": "Faturamento", "formato": "moeda", "num": True},
        {"campo": "fatura_operadora", "rotulo": "Fatura operadora", "formato": "moeda", "num": True},
        {"campo": "glosa", "rotulo": "Glosa", "formato": "moeda", "num": True, "sub": "origem_rotulo"},
        {"campo": "recuperado", "rotulo": "Recuperado (planilha)", "formato": "moeda", "num": True},
        {"campo": "perda", "rotulo": "Perda (planilha)", "formato": "moeda", "num": True},
        {"campo": "protocolo", "rotulo": "Protocolo", "so_csv": True},
        {"campo": "data_entrega", "rotulo": "Data de entrega", "formato": "data", "so_csv": True},
        {"campo": "nf_origem", "rotulo": "Origem da nota fiscal", "so_csv": True},
        {"campo": "unidade", "rotulo": "Unidade", "so_csv": True},
        {"campo": "pagador", "rotulo": "Pagador", "so_csv": True},
        {"campo": "tipos", "rotulo": "Tipos de atendimento", "so_csv": True},
        {"campo": "itens", "rotulo": "Itens", "so_csv": True},
        {"campo": "itens_pre_auditados", "rotulo": "Itens pré-auditados", "so_csv": True},
        {"campo": "particular", "rotulo": "Particular", "so_csv": True},
        {"campo": "tributos_erp", "rotulo": "Tributos (ERP)", "so_csv": True},
        {"campo": "glosa_iw", "rotulo": "Glosa IW (ERP)", "so_csv": True},
    ],
    "carregar": carregar,
    "resumo": resumo,
}
