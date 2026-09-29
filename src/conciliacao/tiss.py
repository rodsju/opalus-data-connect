"""Sincroniza os motivos de glosa (Tabela 38 do padrão TISS) direto da ANS.

A tabela é pública: vem no "Componente de Representação de Conceitos em Saúde"
do Padrão TISS (gov.br/ans), um zip de ~400 MB com as tabelas TUSS. A Tabela 38
("Terminologia de mensagens (glosas, negativas e outras)") está na aba "Tab 38"
do xlsx "TUSS - Demais terminologias", que tem menos de 1 MB. Por isso nada de
baixar o zip inteiro: o servidor da ANS aceita Range, então se lê o diretório
central do zip pelo fim do arquivo e depois só os bytes daquele xlsx.

Fluxo: descobrir a versão vigente na página do padrão -> achar o zip -> extrair o
xlsx -> ler a aba -> gravar em conciliacao.motivo_tiss e registrar a execução.

A tabela ACUMULA. A versão 202607 cortou 170 dos 640 códigos da 202507, e as
operadoras seguem glosando com eles (na planilha de set/2026, 1702, 2401, 2514...
somam R$ 7,4 mi). Então cada sincronização lê a versão vigente e a anterior
disponível; código que saiu fica gravado com vigente=false e a última versão em
que apareceu. Nada que já foi gravado é apagado.
Sincronização manual (botão em Conciliação › Premissas ou `make conciliacao ARGS=tiss`).
"""

import datetime
import io
import json
import logging
import re
import struct
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib

from . import banco

logger = logging.getLogger(__name__)

PAGINA_PADRAO = ("https://www.gov.br/ans/pt-br/assuntos/prestadores/"
                 "padrao-para-troca-de-informacao-de-saude-suplementar-2013-tiss")
_VERSAO = re.compile(r'href="([^"]*/padrao-tiss-(?:janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|'
                     r'setembro|outubro|novembro|dezembro)-\d{4})"', re.I)
_ZIP = re.compile(r'href="([^"]*Representacao_de_Conceitos_em_Saude_(\d{6})\.zip)"', re.I)
# Só se aceita URL da própria ANS: o endereço pode vir de formulário.
HOSTS_ANS = {"www.gov.br", "gov.br", "www.ans.gov.br", "ans.gov.br"}
TIMEOUT = 60
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
EPOCA_EXCEL = datetime.date(1899, 12, 30)


class SincronizacaoFalhou(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


def _validar_url(url):
    host = urllib.parse.urlparse(url).hostname or ""
    if urllib.parse.urlparse(url).scheme != "https" or host not in HOSTS_ANS:
        raise SincronizacaoFalhou("endereço fora da ANS", f"{url} -- só se aceita https em gov.br/ans.gov.br")


def _get(url, intervalo=None):
    _validar_url(url)
    pedido = urllib.request.Request(url, headers={"User-Agent": "opalus-data-connect/tiss-sync"})
    if intervalo:
        pedido.add_header("Range", f"bytes={intervalo[0]}-{intervalo[1]}")
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta:
            if intervalo and resposta.status != 206:
                raise SincronizacaoFalhou("o servidor da ANS ignorou o pedido parcial (Range)", url)
            return resposta.read(), resposta.headers
    except SincronizacaoFalhou:
        raise
    except Exception as falha:  # noqa: BLE001 -- rede: vira mensagem para a página
        raise SincronizacaoFalhou(f"não foi possível acessar {urllib.parse.urlparse(url).hostname}",
                                  str(falha)) from falha


def descobrir_zip(pagina=PAGINA_PADRAO, obter=_get):
    """(url do zip, versão AAAAMM) do padrão vigente, lendo a página da ANS."""
    html = obter(pagina)[0].decode("utf-8", "replace")
    achou = _ZIP.search(html)
    if not achou:
        versao = _VERSAO.search(html)
        if not versao:
            raise SincronizacaoFalhou("não achei a versão vigente do Padrão TISS na página da ANS", pagina)
        html = obter(urllib.parse.urljoin(pagina, versao.group(1)))[0].decode("utf-8", "replace")
        achou = _ZIP.search(html)
        if not achou:
            raise SincronizacaoFalhou("não achei o zip de Representação de Conceitos na página da versão",
                                      versao.group(1))
    return urllib.parse.urljoin(pagina, achou.group(1)), achou.group(2)


# --------------------------------------------------------------------------
# Zip remoto: só o membro que interessa
# --------------------------------------------------------------------------


def extrair_membro(ler_intervalo, tamanho, filtro):
    """Bytes do primeiro membro do zip cujo nome satisfaz `filtro(nome)`.

    `ler_intervalo(inicio, fim)` devolve os bytes [inicio, fim] (inclusive) do
    arquivo. Lê o fim (EOCD), o diretório central e só o membro escolhido.
    Zip < 4 GB, sem ZIP64 (o da ANS tem ~400 MB).
    """
    cauda = ler_intervalo(max(0, tamanho - 65_557), tamanho - 1)
    pos = cauda.rfind(b"PK\x05\x06")
    if pos < 0:
        raise SincronizacaoFalhou("zip da ANS sem diretório central (arquivo truncado?)")
    tam_dir, inicio_dir = struct.unpack("<II", cauda[pos + 12:pos + 20])
    diretorio = ler_intervalo(inicio_dir, inicio_dir + tam_dir - 1)

    i = 0
    while i < len(diretorio):
        if diretorio[i:i + 4] != b"PK\x01\x02":
            break
        flags, metodo = struct.unpack("<HH", diretorio[i + 8:i + 12])
        comprimido, _, n_nome, n_extra, n_coment = struct.unpack("<IIHHH", diretorio[i + 20:i + 34])
        deslocamento = struct.unpack("<I", diretorio[i + 42:i + 46])[0]
        bruto = diretorio[i + 46:i + 46 + n_nome]
        nome = bruto.decode("utf-8" if flags & 0x800 else "cp437")
        i += 46 + n_nome + n_extra + n_coment
        if not filtro(nome):
            continue
        cabecalho = ler_intervalo(deslocamento, deslocamento + 29)
        n_nome_local, n_extra_local = struct.unpack("<HH", cabecalho[26:30])
        inicio = deslocamento + 30 + n_nome_local + n_extra_local
        dados = ler_intervalo(inicio, inicio + comprimido - 1) if comprimido else b""
        if metodo == 0:
            return nome, dados
        if metodo == 8:
            return nome, zlib.decompress(dados, -15)
        raise SincronizacaoFalhou(f"método de compressão {metodo} não suportado", nome)
    raise SincronizacaoFalhou("o zip da ANS não tem o xlsx 'TUSS - Demais terminologias'")


def _eh_demais_terminologias(nome):
    base = nome.rsplit("/", 1)[-1].upper()
    return "DEMAIS TERMINOLOGIAS" in base and base.endswith(".XLSX") and not base.startswith("~$")


# --------------------------------------------------------------------------
# Leitura da aba "Tab 38"
# --------------------------------------------------------------------------


def _data(valor):
    if valor in (None, ""):
        return None
    try:
        return EPOCA_EXCEL + datetime.timedelta(days=int(float(valor)))
    except ValueError:
        try:
            return datetime.datetime.strptime(valor.strip(), "%d/%m/%Y").date()
        except ValueError:
            return None


def ler_tabela_38(xlsx):
    """xlsx (bytes) -> list[{codigo, descricao, inicio_vigencia, fim_vigencia, fim_implantacao}]."""
    pasta = zipfile.ZipFile(io.BytesIO(xlsx))
    textos = []
    if "xl/sharedStrings.xml" in pasta.namelist():
        textos = ["".join(t.text or "" for t in si.iter(NS + "t"))
                  for si in ET.fromstring(pasta.read("xl/sharedStrings.xml"))]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(pasta.read("xl/_rels/workbook.xml.rels"))}
    aba = next((rels[s.get(NS_REL + "id")] for s in ET.fromstring(pasta.read("xl/workbook.xml")).find(NS + "sheets")
                if re.fullmatch(r"tab\s*38", (s.get("name") or "").strip(), re.I)), None)
    if not aba:
        raise SincronizacaoFalhou("o xlsx da ANS não tem a aba 'Tab 38'")
    caminho = aba.lstrip("/") if aba.startswith("/") else "xl/" + aba
    linhas, cabecalho = [], None
    for linha in ET.fromstring(pasta.read(caminho)).iter(NS + "row"):
        valores = {}
        for celula in linha.findall(NS + "c"):
            v = celula.find(NS + "v")
            if v is None:
                t = celula.find(NS + "is")
                texto = "".join(x.text or "" for x in t.iter(NS + "t")) if t is not None else None
            else:
                texto = textos[int(v.text)] if celula.get("t") == "s" else v.text
            valores[re.match(r"[A-Z]+", celula.get("r")).group()] = texto
        if cabecalho is None:
            if (valores.get("A") or "").strip().upper().startswith("CÓDIGO DO TERMO"):
                cabecalho = True
            continue
        codigo = (valores.get("A") or "").strip()
        if not re.fullmatch(r"\d{3,5}", codigo):
            continue
        linhas.append({
            "codigo": codigo,
            "descricao": " ".join((valores.get("B") or "").split()),
            "inicio_vigencia": _data(valores.get("C")),
            "fim_vigencia": _data(valores.get("D")),
            "fim_implantacao": _data(valores.get("E")),
        })
    if not linhas:
        raise SincronizacaoFalhou("a aba 'Tab 38' veio sem códigos", "o layout da planilha da ANS pode ter mudado")
    return linhas


# --------------------------------------------------------------------------
# Sincronização
# --------------------------------------------------------------------------


def baixar(url=None, obter=_get):
    """(linhas, versão, url). Sem url, descobre a versão vigente na página da ANS."""
    versao = None
    if url:
        _validar_url(url)
        achou = re.search(r"_(\d{6})\.zip", url)
        versao = achou.group(1) if achou else None
    else:
        url, versao = descobrir_zip(obter=obter)
    _, cabecalhos = obter(url, (0, 0))
    faixa = cabecalhos.get("Content-Range", "")
    tamanho = int(faixa.rsplit("/", 1)[-1]) if "/" in faixa else int(cabecalhos.get("Content-Length", 0))
    if not tamanho:
        raise SincronizacaoFalhou("não consegui saber o tamanho do zip da ANS", url)
    nome, xlsx = extrair_membro(lambda a, b: obter(url, (a, b))[0], tamanho, _eh_demais_terminologias)
    logger.info("tiss: %s extraído de %s (%d bytes)", nome, url, len(xlsx))
    return ler_tabela_38(xlsx), versao, url


def _url_versao(versao):
    return f"https://www.ans.gov.br/arquivos/extras/tiss/Padrao_TISS_Representacao_de_Conceitos_em_Saude_{versao}.zip"


def versao_anterior(versao, obter=_get, meses=24):
    """A versão publicada mais recente antes de `versao` (AAAAMM) que a ANS ainda serve, ou None."""
    ano, mes = int(versao[:4]), int(versao[4:])
    for _ in range(meses):
        ano, mes = (ano, mes - 1) if mes > 1 else (ano - 1, 12)
        candidata = f"{ano}{mes:02d}"
        try:
            obter(_url_versao(candidata), (0, 0))
            return candidata
        except SincronizacaoFalhou:
            continue
    return None


def mesclar(existentes, anterior, vigente, versao_anterior_, versao_vigente):
    """Código -> linha. A vigente vence; o que só existe antes fica com vigente=False."""
    saida = {}
    for l in existentes:
        saida[l["codigo"]] = {**l, "vigente": False}
    for l in anterior:
        saida[l["codigo"]] = {**l, "vigente": False, "versao": versao_anterior_}
    for l in vigente:
        saida[l["codigo"]] = {**l, "vigente": True, "versao": versao_vigente}
    return saida


def comparar(atuais, anteriores):
    antes = {l["codigo"]: l.get("descricao") for l in anteriores}
    agora = {l["codigo"]: l.get("descricao") for l in atuais}
    return {"novos": sorted(set(agora) - set(antes)), "removidos": sorted(set(antes) - set(agora)),
            "alterados": sorted(c for c in set(agora) & set(antes) if agora[c] != antes[c])}


COLUNAS = ["codigo", "descricao", "inicio_vigencia", "fim_vigencia", "fim_implantacao", "vigente", "versao"]


def sincronizar(autor=None, url=None, obter=_get):
    """Baixa a Tabela 38 vigente (e a da versão anterior) e grava conciliacao.motivo_tiss."""
    banco.garantir_schema()
    vigente, versao, url = baixar(url, obter)
    anterior_versao = versao_anterior(versao, obter) if versao else None
    anterior = baixar(_url_versao(anterior_versao), obter)[0] if anterior_versao else []
    existentes = banco.consultar(f"SELECT {', '.join(COLUNAS)} FROM conciliacao.motivo_tiss", (), "motivos TISS")
    mescladas = mesclar(existentes, anterior, vigente, anterior_versao, versao)
    diferenca = comparar(list(mescladas.values()), existentes)
    resumo = {"versao": versao, "versao_anterior": anterior_versao, "url": url, "linhas": len(mescladas),
              "vigentes": sum(1 for l in mescladas.values() if l["vigente"]),
              "descontinuados": sum(1 for l in mescladas.values() if not l["vigente"]),
              "novos": len(diferenca["novos"]), "alterados": len(diferenca["alterados"]),
              "exemplos": {k: v[:10] for k, v in diferenca.items() if k != "removidos"}}
    with banco.conexao() as con:
        with con.cursor() as cur:
            cur.execute("DELETE FROM conciliacao.motivo_tiss")
            cur.executemany(
                f"INSERT INTO conciliacao.motivo_tiss ({', '.join(COLUNAS)}) VALUES ({', '.join(['%s'] * len(COLUNAS))})",
                [[l.get(c) for c in COLUNAS] for l in sorted(mescladas.values(), key=lambda x: x["codigo"])],
            )
            cur.execute(
                "INSERT INTO conciliacao.sincronizacao (fonte, versao, url, autor, linhas, detalhes) "
                "VALUES ('tiss_tabela_38', %s, %s, %s, %s, %s)",
                (versao, url, autor, len(mescladas), json.dumps(resumo)),
            )
    logger.info("tiss: tabela 38 %s (+ %s) sincronizada: %s", versao, anterior_versao,
                {k: resumo[k] for k in ("linhas", "vigentes", "descontinuados", "novos", "alterados")})
    return resumo


def ultima_sincronizacao():
    return banco.um(
        "SELECT versao, url, autor, executada_em, linhas, detalhes FROM conciliacao.sincronizacao "
        "WHERE fonte = 'tiss_tabela_38' ORDER BY executada_em DESC LIMIT 1", (), "última sincronização TISS")
