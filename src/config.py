"""Configuracao geral do app, em catalogo.configuracao.

src/provedores.py cadastra QUEM pode ser chamado; aqui fica QUAL desses
cadastros o app usa quando ninguem escolhe na hora. A pagina do objeto tem um
select de provedor em cada botao, entao la nada disso e preciso -- mas a API de
descricoes (src/api.py) nao tem tela nenhuma, e sem um padrao ela teria de exigir
o modelo em todo request.

O valor guardado e o mesmo "slug::modelo" dos <option> da tela (Provedor.valor),
para que o padrao e a escolha manual sejam a mesma coisa escrita do mesmo jeito.
"""

import logging

from . import catalogo, provedores

logger = logging.getLogger(__name__)

# Par provedor::modelo usado para vetorizar quando ninguem escolhe. Vazio =
# "o primeiro provedor de embedding ativo", que e o que provedores.escolher(None)
# ja faz -- ou seja, o app funciona sem nunca configurar nada.
EMBEDDING_PAR = "embedding_par"

CHAVES = {
    EMBEDDING_PAR: "Par provedor::modelo usado para vetorizar sem escolha explícita",
}

SQL_TODAS = "SELECT chave, valor, atualizado_em, atualizado_por FROM catalogo.configuracao"
SQL_UMA = "SELECT valor FROM catalogo.configuracao WHERE chave = %s"
SQL_GRAVAR = """
INSERT INTO catalogo.configuracao (chave, valor, atualizado_por)
VALUES (%s, %s, %s)
ON CONFLICT (chave) DO UPDATE SET
    valor          = EXCLUDED.valor,
    atualizado_por = EXCLUDED.atualizado_por,
    atualizado_em  = now()
"""
SQL_APAGAR = "DELETE FROM catalogo.configuracao WHERE chave = %s"


def ler(chave, padrao=""):
    linha = catalogo.um(SQL_UMA, (chave,), f"configuração {chave}")
    return linha["valor"] if linha else padrao


def todas():
    """{chave: valor} com TODAS as chaves conhecidas, inclusive as nao gravadas.

    Devolver so o que esta na tabela faria a resposta da API mudar de formato
    conforme o banco -- quem consome teria de adivinhar o conjunto de chaves.
    """
    gravadas = {
        linha["chave"]: linha["valor"]
        for linha in catalogo.consultar(SQL_TODAS, (), "configuração geral")
    }
    return {chave: gravadas.get(chave, "") for chave in CHAVES}


def validar(chave, valor):
    """Recusa chave desconhecida e valor que nao resolve num provedor ativo.

    Conferir na hora de gravar, e nao na de usar: um par invalido so apareceria
    na proxima vetorizacao, longe de quem o digitou.
    """
    if chave not in CHAVES:
        raise provedores.ConfiguracaoInvalida(
            f"Chave desconhecida: '{chave}'",
            f"As chaves aceitas são: {', '.join(sorted(CHAVES))}.",
        )
    if chave == EMBEDDING_PAR and valor:
        # Levanta ConfiguracaoInvalida sozinho se o par nao existir ou nao for
        # de embedding.
        provedores.escolher(valor, capacidade="embedding")


def definir(chave, valor, por=None):
    """Grava a chave. Valor vazio apaga a linha, voltando ao comportamento padrao."""
    valor = (valor or "").strip()
    validar(chave, valor)
    if not valor:
        catalogo.executar(SQL_APAGAR, (chave,), f"limpeza da configuração {chave}")
    else:
        catalogo.executar(SQL_GRAVAR, (chave, valor, por), f"configuração {chave}")
    logger.info("configuração %s definida por %s: %r", chave, por or "anônimo", valor)


def par_de_embedding():
    """O par configurado, ou None para deixar provedores.escolher decidir."""
    return ler(EMBEDDING_PAR) or None
