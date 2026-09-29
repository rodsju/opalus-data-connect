"""Extrai as tabelas de premissas do base_glosa.xlsx para CSVs de semente.

Roda uma vez (ou quando o time mudar as premissas na planilha e quiser
ressemear). Só biblioteca padrão: o xlsx é um zip de XML, e ler as tabelas
nomeadas (PREMISSAS, PRAZO_RECEBIMENTO, ...) pelo `ref` de cada uma é mais
estável que depender de coordenada de célula.

    python scripts/extrair_premissas_xlsx.py base_glosa.xlsx data/conciliacao
    python scripts/extrair_premissas_xlsx.py base_glosa.xlsx --base /tmp/base.csv

Saída no mesmo formato que a Conciliação aceita no upload: separador `;`,
decimal com vírgula, data dd/mm/aaaa. `--base` exporta a aba BASE OPALUS como o
Excel exportaria -- serve para testar a carga sem abrir o Excel. Esse CSV tem
nome de paciente: não o grave dentro do repositório.
"""

import argparse
import csv
import datetime
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# tabela do Excel -> (arquivo de saída, {coluna do Excel: coluna do CSV}, colunas de data, de percentual)
SEMENTES = {
    "PREMISSAS": ("premissa_imposto.csv", {
        "EMPRESA": "empresa", "CONVENIO": "convenio", "IMPOSTO": "imposto",
        "DATA_ALT1": "data_alt1", "IMPOSTO_ALT1": "imposto_alt1",
        "DATA_ALT2": "data_alt2", "IMPOSTO_ALT2": "imposto_alt2",
    }, {"data_alt1", "data_alt2"}),
    "PRAZO_RECEBIMENTO": ("premissa_prazo.csv", {"CONVENIO": "convenio", "PRAZOS": "prazo"}, set()),
    "PREMISSAS_RECURSO": ("premissa_recurso.csv", {
        "CONVENIO": "convenio", "PRAZO RECURSO (DIAS)": "prazo_recurso",
        "PREVISAO DE PG RECURSO (DIAS)": "previsao_pagto", "COMO RECURSAR": "como_recursar", "OBS": "obs",
    }, set()),
    "TABELA_CONVENIO_FORMULA": ("convenio_de_para.csv", {
        "EMPRESA": "empresa", "CONVENIO": "convenio", "CONVENIO FORMULA": "convenio_formula",
    }, set()),
    "Guia_Aging": ("aging_faixa.csv", {"Dia": "dia", "Grupo": "grupo"}, set()),
    "Tabela11": ("empresa_convenio.csv", {
        "EMPRESA": "empresa", "FILIAL": "filial", "CONVENIO": "convenio",
        "CATEGORIA NF": "categoria_nf", "VERIF_PLENO": "cnpj",
    }, set()),
}

# Colunas de data da BASE OPALUS (o xlsx guarda data como número serial)
DATAS_BASE = {
    "COMPETENCIA", "DATA ENTREGA FATURAMENTO", "DATA PREVISTA RECEBIMENTO", "DATA PREVISTA CONTRATUAL",
    "MES (DA PREVISAO)", "DATA RECEBIMENTO", "DEVOLUCAO", "DATA REAPRESENTACAO",
    "DATA DE PRAZO P/ RECURSO", "DATA DO RECURSO", "PREVISAO PAGTO RECURSO", "DATA RECEBIMENTO RECURSO",
}


def _col(ref):
    letras = re.match(r"[A-Z]+", ref).group()
    n = 0
    for ch in letras:
        n = n * 26 + ord(ch) - 64
    return n


def _linha(ref):
    return int(re.search(r"\d+", ref).group())


class Pasta:
    def __init__(self, caminho):
        self.zip = zipfile.ZipFile(caminho)
        raiz = ET.fromstring(self.zip.read("xl/sharedStrings.xml"))
        self.textos = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in raiz]
        self._celulas = {}

    def _arquivo_da_aba(self, nome_tabela):
        for nome in self.zip.namelist():
            if nome.startswith("xl/worksheets/_rels/"):
                for rel in ET.fromstring(self.zip.read(nome)):
                    alvo = rel.get("Target").split("/")[-1]
                    if alvo.startswith("table"):
                        tabela = ET.fromstring(self.zip.read("xl/tables/" + alvo))
                        if tabela.get("displayName") == nome_tabela:
                            return nome.split("/")[-1].replace(".rels", ""), tabela
        raise KeyError(f"tabela {nome_tabela!r} não encontrada no xlsx")

    def celulas(self, aba):
        """{(linha, coluna): valor} da aba inteira. Lido uma vez e guardado."""
        if aba not in self._celulas:
            saida = {}
            for _, el in ET.iterparse(self.zip.open(f"xl/worksheets/{aba}")):
                if el.tag == NS + "c":
                    v = el.find(NS + "v")
                    if v is not None:
                        valor = self.textos[int(v.text)] if el.get("t") == "s" else v.text
                        if el.get("t") in ("e",):
                            valor = None  # #VALUE!, #N/D: célula com erro não é dado
                        saida[(_linha(el.get("r")), _col(el.get("r")))] = valor
                elif el.tag == NS + "row":
                    el.clear()
            self._celulas[aba] = saida
        return self._celulas[aba]

    def tabela(self, nome):
        aba, tabela = self._arquivo_da_aba(nome)
        inicio, fim = tabela.get("ref").split(":")
        l0, c0, l1 = _linha(inicio), _col(inicio), _linha(fim)
        colunas = [c.get("name").strip() for c in tabela.find(NS + "tableColumns")]
        celulas = self.celulas(aba)
        linhas = []
        for linha in range(l0 + 1, l1 + 1):
            registro = {col: celulas.get((linha, c0 + i)) for i, col in enumerate(colunas)}
            if any(v not in (None, "") for v in registro.values()):
                linhas.append(registro)
        return colunas, linhas


def data_br(valor):
    try:
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(valor)))).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return valor or ""


def numero_br(valor):
    if valor in (None, ""):
        return ""
    # float() do Python aceita "_" entre dígitos: '330220783688_0' (protocolo)
    # viraria 3302207836880. Só converte o que é número de verdade no XML.
    if not re.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?", valor):
        return valor
    numero = float(valor)
    texto = repr(round(numero, 10)).rstrip("0").rstrip(".") if numero != int(numero) else str(int(numero))
    return texto.replace(".", ",")


def _normal(nome):
    return " ".join(nome.upper().split())


def exportar_sementes(pasta, destino):
    destino.mkdir(parents=True, exist_ok=True)
    for tabela, (arquivo, mapa, datas) in SEMENTES.items():
        _, linhas = pasta.tabela(tabela)
        with open(destino / arquivo, "w", newline="", encoding="utf-8") as saida:
            escritor = csv.writer(saida, delimiter=";")
            escritor.writerow(mapa.values())
            for registro in linhas:
                escritor.writerow([
                    data_br(registro.get(origem)) if alvo in datas else
                    (numero_br(registro.get(origem)) if registro.get(origem) is not None else "")
                    for origem, alvo in mapa.items()
                ])
        print(f"{arquivo}: {len(linhas)} linhas")


def exportar_base(pasta, arquivo):
    colunas, linhas = pasta.tabela("BASE_OPALUS")
    # A tabela do Excel só vai até onde foi redimensionada; o time digita abaixo
    # dela também. Continua lendo enquanto houver EMPRESA preenchida.
    aba, tabela = pasta._arquivo_da_aba("BASE_OPALUS")
    celulas = pasta.celulas(aba)
    ultima = _linha(tabela.get("ref").split(":")[1])
    c0 = _col(tabela.get("ref").split(":")[0])
    linha = ultima + 1
    while celulas.get((linha, c0)) not in (None, ""):
        linhas.append({col: celulas.get((linha, c0 + i)) for i, col in enumerate(colunas)})
        linha += 1
    with open(arquivo, "w", newline="", encoding="utf-8-sig") as saida:
        escritor = csv.writer(saida, delimiter=";")
        escritor.writerow(colunas)
        for registro in linhas:
            escritor.writerow([
                data_br(registro[c]) if _normal(c) in DATAS_BASE else numero_br(registro[c])
                for c in colunas
            ])
    print(f"{arquivo}: {len(linhas)} linhas")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("xlsx")
    p.add_argument("destino", nargs="?", help="pasta das sementes (ex.: data/conciliacao)")
    p.add_argument("--base", help="também exporta a aba BASE OPALUS para este CSV")
    args = p.parse_args(argv)
    pasta = Pasta(args.xlsx)
    if args.destino:
        exportar_sementes(pasta, pathlib.Path(args.destino))
    if args.base:
        exportar_base(pasta, args.base)
    if not args.destino and not args.base:
        p.error("informe a pasta de destino e/ou --base")
    return 0


if __name__ == "__main__":
    sys.exit(main())
