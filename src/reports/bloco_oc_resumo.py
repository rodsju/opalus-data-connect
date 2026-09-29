"""KPIs da ocupação: hospital de transição (taxa) e home care (censo)."""

from . import comum, oc_comum

TITULO = "Ocupação agora"
ICONE = "bed"
PARTIAL = "reports/bloco_resumo.html"
LARGURA = "faixa"
ITENS = [
    {"chave": "ocupado", "titulo": "Ocupado",
     "negocio": "Paciente em atendimento ocupa uma vaga: admissão com status em andamento e sem alta.",
     "tecnico": "CAPADMISSION.STATUS = 1 e CHECKOUTDATE nulo. Tipo pela admissão: 0 hospital de transição, "
     "1 home care, 3 ambulatorial."},
    {"chave": "taxa", "titulo": "Taxa de ocupação",
     "negocio": "Ocupados ÷ leitos, só no hospital de transição. Home care não tem leito: mostra o censo.",
     "tecnico": "Leitos do parâmetro 'Leitos por unidade' (Conciliação › Premissas), vigente hoje; unidade sem "
     "leitos cadastrados fica fora da taxa."},
]


def consultar(filtros):
    return montar(oc_comum.atual(filtros), oc_comum.leitos(filtros))


def montar(atual, capacidade):
    ht = oc_comum.por_unidade_ht(atual, capacidade)
    com_leitos = [u for u in ht if u["leitos"]]
    ocupados_ht = sum(u["ocupados"] for u in ht)
    leitos = sum(u["leitos"] for u in com_leitos)
    ocup_com_leitos = sum(u["ocupados"] for u in com_leitos)
    hc = [l for l in atual if l["tipo"] == oc_comum.HC]
    ativos_hc = sum(int(comum.num(l["ocupados"])) for l in hc)
    perm = sum(comum.num(l["permanencia_media"]) * comum.num(l["ocupados"]) for l in atual if l["tipo"] == oc_comum.HT)
    sem_leitos = [u["unidade"] for u in ht if u["ocupados"] and not u["leitos"]]
    cards = [
        {"rotulo": "Ocupação hospitalar", "valor": comum.pct(ocup_com_leitos, leitos), "formato": "pct",
         "icone": "bed", "tom": "blue", "barra": comum.pct(ocup_com_leitos, leitos),
         "hint": f"{ocup_com_leitos} de {leitos} leitos" + (f" · sem leitos: {', '.join(sem_leitos)}" if sem_leitos else "")},
        {"rotulo": "Ocupados (transição)", "valor": ocupados_ht, "formato": "int", "icone": "user-check", "tom": "teal",
         "hint": f"{len(com_leitos)} unidades"},
        {"rotulo": "Leitos livres", "valor": max(leitos - ocup_com_leitos, 0), "formato": "int", "icone": "bed-single",
         "tom": "amber", "hint": "capacidade − ocupados"},
        {"rotulo": "Permanência média", "valor": (perm / ocupados_ht) if ocupados_ht else None, "formato": "int",
         "icone": "calendar-clock", "tom": "violet", "hint": "dias desde a entrada (transição)"},
        {"rotulo": "Home care ativos", "valor": ativos_hc, "formato": "int", "icone": "house", "tom": "magenta",
         "hint": f"{len(hc)} unidades · sem taxa (não há leito)"},
    ]
    return {"vazio": not atual, "cards": cards}


AMOSTRA_ATUAL = [
    {"unidade": "Premier Brooklin HSP", "tipo": 0, "ocupados": 63, "permanencia_media": 222},
    {"unidade": "Premier Barra HSP", "tipo": 0, "ocupados": 42, "permanencia_media": 510},
    {"unidade": "Premier Flamengo HSP", "tipo": 0, "ocupados": 41, "permanencia_media": 1268},
    {"unidade": "Premier Leblon HSP", "tipo": 0, "ocupados": 24, "permanencia_media": 444},
    {"unidade": "Premier Niterói HSP", "tipo": 0, "ocupados": 14, "permanencia_media": 253},
    {"unidade": "PLENO RJ HC", "tipo": 1, "ocupados": 420, "permanencia_media": 700},
    {"unidade": "Geriatrics HC", "tipo": 1, "ocupados": 310, "permanencia_media": 540},
]
AMOSTRA_LEITOS = {"Premier Brooklin HSP": 90, "Premier Barra HSP": 45, "Premier Flamengo HSP": 51,
                  "Premier Leblon HSP": 41, "Premier Niterói HSP": 22}


def montar_amostra():
    return montar(AMOSTRA_ATUAL, AMOSTRA_LEITOS)
