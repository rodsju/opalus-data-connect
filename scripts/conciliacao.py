"""Linha de comando da Conciliação (roda dentro do container: make conciliacao ARGS=...).

    schema                         aplica scripts/conciliacao_schema.sql
    premissas                      grava as sementes de data/conciliacao no Postgres
    carga ARQUIVO.csv [--hoje D]   carrega a base de glosa (mesmo fluxo do upload)
    cruzar [--carga N]             cruza a carga com o ERP (precisa do Oracle/VPN)
    tiss [--url URL]               sincroniza a Tabela 38 (motivos de glosa) com a ANS
    tiss-xml ARQ.xml... [--md DIR] carrega XMLs TISS de volta e grava o .md de divergências
"""

import argparse
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import log as log_mod  # noqa: E402
from src.conciliacao import banco, cargas, cruzamento, premissas, tiss, tiss_cruzamento, tiss_divergencias  # noqa: E402


def main(argv=None):
    log_mod.configurar()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("schema")
    sub.add_parser("premissas")
    c = sub.add_parser("carga")
    c.add_argument("arquivo")
    c.add_argument("--hoje", help="data de referência AAAA-MM-DD (padrão: hoje)")
    c.add_argument("--sem-cruzar", action="store_true")
    x = sub.add_parser("cruzar")
    x.add_argument("--carga", type=int)
    t = sub.add_parser("tiss")
    t.add_argument("--url", help="zip de uma versão específica (padrão: a vigente, lida na página da ANS)")
    xm = sub.add_parser("tiss-xml")
    xm.add_argument("arquivos", nargs="+")
    xm.add_argument("--md", help="pasta onde gravar divergencias_<protocolo>.md")
    args = p.parse_args(argv)

    banco.garantir_schema()
    if args.comando == "premissas":
        for tipo, (n, avisos) in premissas.semear().items():
            print(f"{tipo}: {n} linhas" + (f" ({len(avisos)} avisos)" if avisos else ""))
            for aviso in avisos[:5]:
                print("   ", aviso)
    elif args.comando == "carga":
        hoje = datetime.date.fromisoformat(args.hoje) if args.hoje else datetime.date.today()
        conteudo = pathlib.Path(args.arquivo).read_bytes()
        carga_id, rel = cargas.gravar(conteudo, pathlib.Path(args.arquivo).name, hoje, autor="cli")
        print(f"carga {carga_id}: {rel['linhas']} linhas, {rel['rejeitadas']} rejeitadas")
        for d in rel["divergencias"]:
            print(f"   diverge {d['campo']}: {d['linhas']}")
        if not args.sem_cruzar:
            print(cruzamento.executar(carga_id))
    elif args.comando == "cruzar":
        print(cruzamento.executar(args.carga))
    elif args.comando == "tiss":
        r = tiss.sincronizar(autor="cli", url=args.url)
        print({k: r[k] for k in ("versao", "versao_anterior", "linhas", "vigentes", "descontinuados", "novos", "alterados")})
    elif args.comando == "tiss-xml":
        for caminho in map(pathlib.Path, args.arquivos):
            try:
                arquivo_id, resumo, repetido = tiss_cruzamento.gravar(caminho.read_bytes(), caminho.name, autor="cli")
            except tiss_cruzamento.ArquivoRecusado as falha:
                print(f"{caminho.name}: recusado -- {falha.motivo}")
                continue
            print(f"{caminho.name}: retorno #{arquivo_id}{' (já carregado)' if repetido else ''} {resumo['por_situacao']}")
            if args.md:
                destino = pathlib.Path(args.md) / f"divergencias_{'_'.join(resumo['protocolos'])}.md"
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(tiss_divergencias.gerar(arquivo_id) + "\n", encoding="utf-8")
                print(f"   {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
