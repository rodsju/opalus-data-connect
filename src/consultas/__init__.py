"""Consultas: ferramentas de trabalho, linha a linha.

Regra do app: Reports são leitura agregada (KPIs, gráficos, rankings por
dimensão) e nunca listam paciente ou protocolo; Consultas são onde se procura
o caso concreto -- lista filtrável, paginada, exportável em CSV, com link para
o detalhe. Paciente aparece só pelo código (P + ID do ERP, ou X…).
"""
