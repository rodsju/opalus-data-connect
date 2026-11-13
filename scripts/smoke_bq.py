"""Roda cada consulta de sql_bq.CONSULTAS no BigQuery e mostra linhas e tempo.

    BQ_PROJECT=atlas-dw-hml-511718 BQ_DATASET=bronze_iw_opalus \\
        python -m scripts.smoke_bq [AAAA-MM] [--dry-run]

--dry-run só valida a SQL (colunas, tipos) sem ler dados.
Sai com código 1 se alguma consulta falhar.
"""

import sys
import time

from src.reports import comum, fonte_bq, sql_bq


def main(argv):
    dry = "--dry-run" in argv
    meses = [a for a in argv if not a.startswith("--")]
    mes = meses[0] if meses else comum.mes_padrao()
    inicio, fim = comum.periodo(mes)
    params = {"DT_INI": inicio, "DT_FIM": fim, "UNIDADE": None, "TIPO": None, "ID": 0}
    cfg = fonte_bq._config()
    print(f"BigQuery {cfg['projeto']}.{cfg['dataset']} | competência {mes} | {'dry-run' if dry else 'execução'}")

    falhas = 0
    for nome, sql in sql_bq.CONSULTAS.items():
        sql = fonte_bq.qualificar(sql, cfg)
        t0 = time.perf_counter()
        try:
            if dry:
                from google.cloud import bigquery

                job = fonte_bq._cliente_para(cfg).query(sql, job_config=bigquery.QueryJobConfig(
                    dry_run=True, use_query_cache=False, query_parameters=fonte_bq.parametros(sql, params)))
                info = f"{job.total_bytes_processed / 1e6:8.1f} MB"
            else:
                linhas = fonte_bq.executar(sql, params, cfg)
                info = f"{len(linhas):6d} linhas"
                if linhas and "bruto" in linhas[0]:
                    chaves = ("bruto", "faturamento_grupo", "fatura_operadora")
                    total = {k: sum(linha[k] or 0 for linha in linhas) for k in chaves}
                    info += "  " + "  ".join(f"{k}={v:,.2f}" for k, v in total.items())
        except Exception as erro:  # noqa: BLE001 -- smoke: mostra e segue
            falhas += 1
            info = f"FALHOU: {getattr(erro, 'motivo', None) or str(erro).splitlines()[0]}"
        print(f"  {nome:32s} {(time.perf_counter() - t0) * 1000:7.0f} ms  {info}")
    print(f"{len(sql_bq.CONSULTAS) - falhas}/{len(sql_bq.CONSULTAS)} ok")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
