"""Conciliação: recebe a planilha de glosa por CSV, refaz as contas dela e cruza com o ERP.

O ERP parou de registrar glosa em jul/2025 e o time passou a controlar tudo no
base_glosa.xlsx. Este pacote sistematiza o que a planilha faz:

  csv_leitor.py    lê o CSV (pt-BR ou exportado do Excel) e acha o cabeçalho
  layout_glosa.py  quais colunas a base tem, com sinônimos, e o tipo de cada uma
  regras.py        as fórmulas da planilha como funções puras
  premissas.py     imposto, prazos, de-para de convênio e aging, no Postgres
  cargas.py        grava cada upload como uma foto e ativa a mais recente
  cruzamento.py    casa cada linha com a conta do ERP (protocolo + paciente)
  paginas.py       as páginas /conciliacao/*
"""
