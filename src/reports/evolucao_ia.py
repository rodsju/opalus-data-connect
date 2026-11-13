"""Tendência clínica do paciente na competência, por IA. Sob demanda e gravada.

Mesmo caminho de orcamento_ia: provedor do Setup › AI Providers, adaptador de
src/ia.py, resposta num esquema pydantic, conferida antes de gravar.

O que sai para o provedor: as evoluções do período (multiprofissionais) com os
campos rotulados do formulário -- a primeira de cada formulário inteira, as
seguintes só com o que mudou --, as intercorrências, as prescrições médicas e as
pendências por regra. Paciente só pelo código; nome, CPF e telefone saem do texto
livre (evolucao_campos.higienizar); campos que identificam profissional nem
entram. O payload NÃO é gravado (é texto clínico): só o hash, para reaproveitar.

Dois motores, escolhidos no detalhe: LLM (anthropic/openai; texto, sinais e pendências) ou Jev
(Decisions API do OpenRouter; só a decisão de cada pergunta, com probabilidade -- perguntas()).
Os dois gravam o mesmo formato de resultado.

Apoio à coordenação/auditoria: não substitui avaliação médica.
"""

import hashlib
import json
import logging
from typing import Literal

from pydantic import BaseModel

from .. import ia, provedores
from ..conciliacao import banco
from . import evolucao_campos

logger = logging.getLogger(__name__)

MAX_SINAIS = 8
MAX_PENDENCIAS = 6
RECENTES_INTEIRAS = 5

_BASE = """Você apoia a coordenação clínica da Opalus (home care, hospital de transição e ambulatório). \
Recebe, de UM paciente e UMA competência (mês), as evoluções clínicas multiprofissionais em ordem de data, as \
intercorrências, as prescrições médicas, o histórico de admissões (com o desfecho de cada uma) e as pendências \
de registro já apontadas por regras.

Cada evolução traz os campos do formulário. A primeira de cada formulário vem inteira ("tipo": "completa"); \
as seguintes trazem só o que mudou ("tipo": "mudancas") -- os profissionais copiam a evolução anterior, então \
ausência de mudança não é melhora nem piora. "[PACIENTE]", "[DOC]" e "[TEL]" são dados removidos de propósito.

{foco}

Também, para qualquer tipo:
- "tendencia": ao longo do período o paciente está "melhorando", "estavel" ou "piorando"? "indeterminado" quando \
os registros não permitem dizer (poucas evoluções, só cópias, campos vazios).
- "sinais": até 8 achados concretos que sustentam a conclusão (melhora, piora) ou merecem atenção (alerta). Em \
"id_evolucao", o id exato de evolucoes[].id de onde tirou o achado; 0 se vier de intercorrência, prescrição, \
sessão ou histórico.
- "pendencias": até 6 pendências do ponto de vista clínico (registro faltando, intercorrência sem reavaliação, \
conduta sem seguimento), cada uma com uma recomendação objetiva para a coordenação.
- "resumo": duas ou três frases, começando pela conclusão do foco.

Regras: use só os dados recebidos; não invente valores, datas nem diagnósticos; não sugira tratamento — você \
não substitui a avaliação médica.

Responda em português, SOMENTE com um objeto JSON exatamente neste formato (todos os campos obrigatórios):
{{
  "{campo}": "{opcoes}",
  "tendencia": "melhorando | estavel | piorando | indeterminado",
  "confianca": "alta | media | baixa",
  "resumo": "texto",
  "sinais": [{{"tipo": "melhora | piora | alerta", "evidencia": "o dado que sustenta", "id_evolucao": 0, "data": "dd/mm"}}],
  "pendencias": [{{"descricao": "texto", "recomendacao": "texto"}}]
}}
Nos campos com opções use exatamente um dos valores listados (sem a barra vertical)."""

# Pergunta de cada tipo de atendimento (CAPADMISSION.ADMISSIONTYPE). "valores": chave -> rótulo da tela.
FOCOS = {
    1: {"campo": "risco_internacao", "rotulo": "Risco de internação",
        "valores": {"alto": "alto", "medio": "médio", "baixo": "baixo", "indeterminado": "indeterminado"},
        # Jev: escala ordenada (score), do menor ao maior risco
        "escala": {"baixo": "Estável, sem intercorrência relevante nem piora; cuidado de manutenção.",
                   "medio": "Intercorrência controlada ou piora leve que pede vigilância.",
                   "alto": "Infecção, febre, dispneia, oligúria, sinais vitais alterados ou queda do estado geral "
                           "em curso, ou internação recente: chance real de internar."},
        "texto": """Paciente em HOME CARE. Pergunta principal ("risco_internacao"): qual o risco de este paciente \
precisar de internação hospitalar nas próximas semanas? "alto", "medio", "baixo" ou "indeterminado". Pese: \
intercorrências (quadro infeccioso, febre, dispneia, oligúria/anúria, alteração de sinais vitais, queda do estado \
geral), antibiótico em curso, piora de escores (NEAD, PPS, Katz) e de nível de consciência, piora respiratória \
ou de dispositivos (traqueostomia, sondas), e internações recentes em historico_admissoes / internacoes_90d."""},
    0: {"campo": "desfecho_provavel", "rotulo": "Desfecho provável",
        "valores": {"alta_casa": "alta para casa", "home_care": "vai para home care",
                    "hospital_agudo": "volta ao hospital", "permanencia_prolongada": "permanência prolongada",
                    "indeterminado": "indeterminado"},
        "criterios": {"alta_casa": "Autonomia recuperada, sem suporte contínuo: alta para casa.",
                      "home_care": "Estável, mas ainda dependente de cuidado/dispositivos: alta com home care.",
                      "hospital_agudo": "Piora clínica que exige transferência para hospital agudo.",
                      "permanencia_prolongada": "Sem progresso para alta: segue internado por muito tempo.",
                      "indeterminado": "Registros não permitem dizer."},
        "texto": """Paciente em HOSPITAL DE TRANSIÇÃO. Pergunta principal ("desfecho_provavel"): para onde o paciente \
caminha? "alta_casa" (alta sem suporte), "home_care" (alta com home care), "hospital_agudo" (piora que exige \
transferência a hospital), "permanencia_prolongada" (sem progresso para alta) ou "indeterminado". Pese: dias \
internado (dias_internado), desmame de O2/ventilação/traqueostomia, ganho funcional e de autonomia (mobilidade, \
alimentação por via oral, escores), intercorrências e o que veio antes em historico_admissoes."""},
    3: {"campo": "meta", "rotulo": "Meta da reabilitação",
        "valores": {"atingindo": "atingindo a meta", "estagnado": "estagnado", "piorando": "piorando",
                    "indeterminado": "indeterminado"},
        "criterios": {"atingindo": "Dor caindo e amplitude, força e função melhorando: perto da alta por objetivo.",
                      "estagnado": "Sem ganho claro entre as sessões.",
                      "piorando": "Dor, função ou adesão piorando.",
                      "indeterminado": "Sem ficha legível ou poucas sessões para dizer."},
        "texto": """Paciente de AMBULATÓRIO (reabilitação, em geral fisioterapia). Pergunta principal ("meta"): a \
reabilitação está funcionando? "atingindo" (dor caindo, amplitude de movimento, força e função melhorando -- \
perto de alta por objetivo), "estagnado", "piorando" ou "indeterminado". Use as evoluções e a agenda em \
"sessoes" (agendadas, compareceu, faltas, realizadas sem evolução): faltas e sessão realizada sem evolução são \
pendências; poucas sessões realizadas limitam a conclusão. Se "formularios_sem_conteudo" não estiver vazio, as \
fichas não puderam ser lidas: diga isso no resumo e use "indeterminado" em "meta" se não houver outro dado \
clínico."""},
}
FOCO_PADRAO = 1  # tipo desconhecido: lê como home care


def foco(tipo):
    return FOCOS.get(tipo, FOCOS[FOCO_PADRAO])


CRITERIOS_TENDENCIA = {
    "melhorando": "O quadro clínico melhora ao longo do período.",
    "estavel": "Sem mudança clínica relevante no período.",
    "piorando": "O quadro clínico piora ao longo do período.",
    "indeterminado": "Poucas evoluções, só cópias ou campos vazios: não dá para dizer.",
}
TETO_JEV = 45_000  # bytes do estado: o Jev lê 32 mil tokens, com as perguntas junto


def perguntas(tipo):
    """Perguntas tipadas da Decisions API (Jev) para o tipo de atendimento. Mesmas de FOCOS."""
    f = foco(tipo)
    principal = ({"type": "score", "instructions": f["texto"], "criteria": list(f["escala"].values())}
                 if "escala" in f else {"type": "choice", "instructions": f["texto"], "criteria": f["criterios"]})
    return {
        f["campo"]: principal,
        "tendencia": {"type": "choice", "instructions": "Ao longo do período o paciente está melhorando, estável ou "
                      "piorando do ponto de vista clínico?", "criteria": CRITERIOS_TENDENCIA},
        "alerta": {"type": "noul", "instructions": "Há sinal clínico que exige reavaliação médica agora?",
                   "criteria": {"true": "Intercorrência sem seguimento, sinal vital alterado, piora aguda ou "
                                        "infecção sem conduta registrada.",
                                "false": "Nada que peça reavaliação além do acompanhamento de rotina."}},
    }


def _confianca(valor):
    valor = valor if valor is not None else 0
    return "alta" if valor >= 0.8 else "media" if valor >= 0.5 else "baixa"


def resultado_jev(respostas, tipo):
    """Respostas do Jev -> o mesmo resultado que o LLM grava (lista, CSV e detalhe não mudam) + probabilidades."""
    f = foco(tipo)
    r_foco, r_tend, alerta = respostas[f["campo"]], respostas["tendencia"], respostas["alerta"].get("noul") or 0
    if r_foco["type"] == "score":  # posição na escala -> chave da opção mais provável
        chaves = list(f["escala"])
        nivel = max(r_foco["probabilities"], key=lambda k: r_foco["probabilities"][k])
        chave, prob_foco = chaves[int(nivel)], {chaves[int(k)]: v for k, v in r_foco["probabilities"].items()}
    else:
        chave, prob_foco = r_foco["choice"], r_foco.get("probabilities") or {}
    tendencia = r_tend["choice"]
    pct = lambda p: f"{round(100 * (p or 0))}%"  # noqa: E731
    resumo = (f"{f['rotulo']}: {f['valores'].get(chave, chave)} ({pct(prob_foco.get(chave))}) · tendência "
              f"{ROTULOS_TENDENCIA.get(tendencia, tendencia)} ({pct((r_tend.get('probabilities') or {}).get(tendencia))})"
              + (f" · sinal de alerta ({pct(alerta)})" if alerta >= 0.5 else ""))
    nucleo = MODELOS.get(tipo, MODELOS[FOCO_PADRAO])(**{
        f["campo"]: chave, "tendencia": tendencia, "resumo": resumo, "pendencias": [],
        "confianca": _confianca(min(r_foco.get("confidence") or 0, r_tend.get("confidence") or 0)),
        "sinais": [{"tipo": "alerta", "id_evolucao": 0, "data": "",
                    "evidencia": f"Jev: {pct(alerta)} de probabilidade de sinal clínico que exige reavaliação "
                                 "médica (sem texto: o Jev não explica, só decide)."}] if alerta >= 0.5 else []})
    return {**nucleo.model_dump(), "motor": "jev",
            "probabilidades": {f["campo"]: prob_foco, "tendencia": r_tend.get("probabilities") or {},
                               "alerta": alerta}}


def instrucoes(tipo):
    f = foco(tipo)
    return _BASE.format(foco=f["texto"], campo=f["campo"], opcoes=" | ".join(f["valores"]))


class SinalIA(BaseModel):
    tipo: Literal["melhora", "piora", "alerta"]
    evidencia: str
    id_evolucao: int
    data: str


class PendenciaIA(BaseModel):
    descricao: str
    recomendacao: str


class AnaliseEvolucao(BaseModel):
    tendencia: Literal["melhorando", "estavel", "piorando", "indeterminado"]
    confianca: Literal["alta", "media", "baixa"]
    resumo: str
    sinais: list[SinalIA]
    pendencias: list[PendenciaIA]


class AnaliseHomeCare(AnaliseEvolucao):
    risco_internacao: Literal["alto", "medio", "baixo", "indeterminado"]


class AnaliseTransicao(AnaliseEvolucao):
    desfecho_provavel: Literal["alta_casa", "home_care", "hospital_agudo", "permanencia_prolongada", "indeterminado"]


class AnaliseAmbulatorio(AnaliseEvolucao):
    meta: Literal["atingindo", "estagnado", "piorando", "indeterminado"]


MODELOS = {1: AnaliseHomeCare, 0: AnaliseTransicao, 3: AnaliseAmbulatorio}


def conclusao(resultado):
    """Resultado gravado -> (chave, 'Rótulo: valor') da pergunta do tipo; (None, None) em análise antiga."""
    for f in FOCOS.values():
        chave = (resultado or {}).get(f["campo"])
        if chave:
            return chave, f"{f['rotulo']}: {f['valores'].get(chave, chave)}"
    return None, None


ROTULOS_TENDENCIA = {"melhorando": "melhorando", "estavel": "estável", "piorando": "piorando",
                     "indeterminado": "indeterminado"}


def _data(valor, hora=False):
    if not valor:
        return None
    return f"{valor:%d/%m %H:%M}" if hora and hasattr(valor, "hour") else f"{valor:%d/%m}"


def _evolucao(e, nome):
    base = {"id": e["id_evolucao"], "data": _data(e["data"], hora=True), "especialidade": e["especialidade"],
            "medica": bool(e.get("medica")), "formulario": e.get("formulario")}
    if not e.get("mudou"):
        return {**base, "sem_mudanca": True}
    campos = {k: evolucao_campos.higienizar(v, nome) for k, v in e["mudou"].items()}
    return {**base, "tipo": "completa" if e.get("base") else "mudancas", "campos": campos}


def montar_payload(ctx, nome_paciente=None, teto=ia.TETO_PROMPT_BYTES - 4_000):
    """Contexto do detalhe -> texto JSON para o modelo, dentro do teto de bytes."""
    adm = ctx["admissao"]
    evolucoes = [_evolucao(e, nome_paciente) for e in ctx["evolucoes"]]
    dados = {
        "paciente": {"codigo": adm["paciente_codigo"], "tipo_atendimento": adm.get("tipo_nome"),
                     "competencia": ctx["mes"], "dias_no_periodo": ctx.get("dias_no_periodo")},
        "pendencias_regras": ctx["pendencias"],
        "intercorrencias": [{"data": _data(i["inicio"], hora=True), "classificacao": i["classificacao"],
                             "nivel": i.get("nivel"), "sem_evolucao_medica_48h": bool(i["sem_evolucao"])}
                            for i in ctx["intercorrencias"]],
        "prescricoes_medicas": [{"inicio": _data(p["inicio"]), "fim": _data(p["fim"]),
                                 "sem_evolucao_medica": bool(p["sem_evolucao"])} for p in ctx["prescricoes"]],
        "historico_admissoes": [{"tipo": h["tipo_nome"], "entrada": _data(h["entrada"]), "saida": _data(h["saida"]),
                                 "desfecho": h["desfecho_nome"]} for h in ctx.get("historico", [])],
        **ctx.get("por_tipo", {}),
        "formularios_sem_conteudo": ctx.get("formularios_indisponiveis", []),
        "evolucoes": evolucoes,
    }
    texto = json.dumps(dados, ensure_ascii=False, default=str)
    # Grande demais: as mais antigas perdem os campos (ficam data e especialidade). Saem antes
    # as não médicas, depois as mudanças médicas; por último a primeira de cada formulário e as recentes.
    antigas = evolucoes[:-RECENTES_INTEIRAS]
    candidatas = [e for medica in (False, True) for tipo in ("mudancas", "completa")
                  for e in antigas if e["medica"] is medica and e.get("tipo") == tipo and (tipo == "mudancas" or not medica)]
    candidatas += [e for e in antigas if e["medica"] and e.get("tipo") == "completa"] + evolucoes
    for e in candidatas:
        if len(texto.encode()) <= teto:
            break
        if e.pop("campos", None) is not None:
            e.pop("tipo", None)
            e["omitida"] = True
            texto = json.dumps(dados, ensure_ascii=False, default=str)
    return texto


def conferir(analise, payload_dict):
    """Recusa achado que cita evolução fora do payload. Devolve a análise, cortada nos máximos."""
    ids = {e["id"] for e in payload_dict["evolucoes"]}
    for s in analise.sinais:
        if s.id_evolucao and s.id_evolucao not in ids:
            raise ia.GeracaoFalhou("A IA citou uma evolução que não está no período", f"Evolução: {s.id_evolucao}")
    analise.sinais = analise.sinais[:MAX_SINAIS]
    analise.pendencias = analise.pendencias[:MAX_PENDENCIAS]
    return analise


def ultima(id_admissao, mes):
    return banco.um(
        "SELECT criado_em, autor, provedor, modelo, resultado, tokens_entrada, tokens_saida, payload_hash "
        "FROM conciliacao.analise_evolucao WHERE id_admissao = %s AND competencia = %s "
        "ORDER BY criado_em DESC LIMIT 1", (id_admissao, mes), "última análise da evolução")


def tendencias(ids, mes):
    """{id_admissao: {tendencia, conclusao, conclusao_chave}} da última análise de cada admissão na competência."""
    if not ids:
        return {}
    linhas = banco.consultar(
        "SELECT DISTINCT ON (id_admissao) id_admissao, resultado "
        "FROM conciliacao.analise_evolucao WHERE competencia = %s AND id_admissao = ANY(%s) "
        "ORDER BY id_admissao, criado_em DESC", (mes, sorted(ids)), "tendências da evolução")
    saida = {}
    for l in linhas:
        chave, texto = conclusao(l["resultado"])
        saida[l["id_admissao"]] = {"tendencia": (l["resultado"] or {}).get("tendencia"), "conclusao": texto,
                                   "conclusao_chave": chave}
    return saida


def escolher_motor(par=None):
    """Provedor do par "slug::modelo" entre LLM e decisão (Jev); sem par, o primeiro LLM."""
    if par:
        for capacidade in ("llm", "decisao"):
            try:
                return provedores.escolher(par, capacidade=capacidade)
            except provedores.ConfiguracaoInvalida:
                continue
    return provedores.escolher(par)


def motores():
    """(valor, rótulo) dos motores que podem analisar: LLM (texto + sinais) e Jev (decisão com probabilidade)."""
    saida = []
    for capacidade, tipo in (("llm", "texto + sinais"), ("decisao", "decisão com probabilidade")):
        try:
            saida += [(p.valor, f"{p.rotulo} — {tipo}") for p in provedores.disponiveis(capacidade)]
        except provedores.ConfiguracaoInvalida:
            continue
    return saida


def analisar(ctx, nome_paciente=None, autor=None, forcar=False, par=None):
    """Roda (ou reaproveita) a análise da admissão na competência. Devolve (registro, reaproveitada)."""
    banco.garantir_schema()
    prov = escolher_motor(par)
    jev = prov.capacidade == "decisao"
    tipo = ctx["admissao"].get("tipo")
    payload = montar_payload(ctx, nome_paciente, **({"teto": TETO_JEV} if jev else {}))
    # O motor entra no hash: análise do Jev não é reaproveitada para o LLM, nem o contrário
    hash_ = hashlib.sha256((prov.valor + payload).encode()).hexdigest()
    id_admissao, mes = ctx["admissao"]["id_admissao"], ctx["mes"]
    anterior = ultima(id_admissao, mes)
    if anterior and anterior["payload_hash"] == hash_ and not forcar:
        return anterior, True

    if jev:
        respostas, uso = ia.decidir(prov, json.loads(payload), perguntas(tipo))
        resultado = resultado_jev(respostas, tipo)
        entrada, saida = uso.get("input_tokens"), uso.get("output_tokens")
    else:
        analise, truncou, entrada, saida = ia._chamar_com_retentativa(
            prov, payload, len(ctx["evolucoes"]), instrucoes=instrucoes(tipo),
            modelo=MODELOS.get(tipo, MODELOS[FOCO_PADRAO]), esquema_nome="analise_evolucao")
        if truncou:
            raise ia.GeracaoFalhou(f"'{prov.slug}' truncou a resposta", "Tente um modelo sem raciocínio estendido.")
        resultado = {**conferir(analise, json.loads(payload)).model_dump(), "motor": "llm"}
    with banco.conexao() as con:
        con.execute(
            "INSERT INTO conciliacao.analise_evolucao (id_admissao, competencia, autor, provedor, modelo, "
            "payload_hash, resultado, tokens_entrada, tokens_saida) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (id_admissao, mes, autor, prov.slug, prov.modelo, hash_,
             json.dumps(resultado, ensure_ascii=False), entrada, saida))
    logger.info("evolucao_ia: admissão %s (%s) analisada por %s: %s · %s", id_admissao, mes, prov.rotulo,
                resultado["tendencia"], conclusao(resultado)[1])
    return ultima(id_admissao, mes), False
