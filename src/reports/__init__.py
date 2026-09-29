"""Reports: relatórios de negócio montados em blocos.

Cada bloco_*.py expõe TITULO, ICONE, PARTIAL, ITENS, consultar(filtros) e
montar_amostra(). relatorios.py compõe os blocos em páginas; galeria.py mostra
todos com dados de amostra. Os dados chegam por fonte.rodar(nome, params), que
esconde se a origem é o Oracle (hoje) ou o BigQuery (depois).
"""
