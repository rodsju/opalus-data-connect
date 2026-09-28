"""Provedores de IA cadastrados em Setup > AI Providers.

Este modulo e a CONFIGURACAO; src/ia.py e o USO. Antes os dois moravam juntos e
a configuracao vinha do .env -- agora vem de catalogo.provedor_ia, e a chave fica
cifrada com a senha mestra de IA_SENHA_MESTRA.

A senha mestra nunca vai para o banco, e a chave nunca volta para a tela: o CRUD
mostra so os quatro ultimos caracteres, guardados em claro em chave_final.
"""

import logging
import os
import re
import unicodedata
from dataclasses import dataclass

from . import catalogo

logger = logging.getLogger(__name__)

TIPOS = ("anthropic", "openai")

# O que o provedor sabe fazer. Protocolo (tipo) e oficio (capacidade) sao
# coisas diferentes: o mesmo endpoint openai serve chat e embeddings, mas um
# modelo nao faz os dois -- por isso o cadastro e por capacidade.
CAPACIDADES = ("llm", "embedding")


class ConfiguracaoInvalida(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


def senha_mestra():
    senha = (os.getenv("IA_SENHA_MESTRA") or "").strip()
    if not senha:
        raise ConfiguracaoInvalida(
            "Senha mestra não configurada",
            "Defina IA_SENHA_MESTRA no .env e rode make up. Sem ela não dá para "
            "cifrar nem decifrar as chaves dos provedores.",
        )
    return senha


def gerar_slug(nome):
    """"Provedor Padrão" -> "provedor-padrao". Derivado so na criacao."""
    base = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()


def separar_modelos(texto):
    """"gpt-5, gpt-5-mini , o3" -> ["gpt-5", "gpt-5-mini", "o3"]"""
    return [modelo.strip() for modelo in (texto or "").split(",") if modelo.strip()]


@dataclass(frozen=True)
class Provedor:
    """Um par (provedor, modelo) pronto para uso -- ja com a chave decifrada."""

    slug: str
    nome: str
    tipo: str
    modelo: str
    chave: str
    url: str = ""
    capacidade: str = "llm"

    @property
    def valor(self):
        # O <option> da pagina do objeto carrega o par nesse formato
        return f"{self.slug}::{self.modelo}"

    @property
    def rotulo(self):
        return f"{self.nome} · {self.modelo}"


# --------------------------------------------------------------------------
# Leitura para uso (chave decifrada)
# --------------------------------------------------------------------------

SQL_ATIVOS = """
SELECT slug, nome, tipo, url, modelos, capacidade,
       pgp_sym_decrypt(chave_cifrada, %s) AS chave
  FROM catalogo.provedor_ia
 WHERE ativo
   AND capacidade = %s
 ORDER BY nome
"""


def _decifrar(sql, params, descricao):
    try:
        return catalogo.consultar(sql, params, descricao)
    except catalogo.ConsultaFalhou as falha:
        if "Wrong key" in str(falha.causa) or "corrupt data" in str(falha.causa):
            raise ConfiguracaoInvalida(
                "Não conseguimos decifrar a chave",
                "A senha mestra em IA_SENHA_MESTRA não é a mesma que cifrou os "
                "provedores. Restaure a senha anterior ou recadastre as chaves.",
            ) from falha
        raise


def disponiveis(capacidade="llm"):
    """Um Provedor por par (provedor ativo, modelo), na ordem do nome.

    Filtra por capacidade: sem isso um modelo de embedding apareceria no select
    de gerar descricao, como se pudesse escrever texto.
    """
    linhas = _decifrar(
        SQL_ATIVOS, (senha_mestra(), capacidade), f"provedores ativos de {capacidade}"
    )
    pares = []
    for linha in linhas:
        for modelo in linha["modelos"]:
            pares.append(
                Provedor(
                    slug=linha["slug"],
                    nome=linha["nome"],
                    tipo=linha["tipo"],
                    modelo=modelo,
                    chave=linha["chave"],
                    url=linha["url"],
                    capacidade=linha["capacidade"],
                )
            )
    return pares


def escolher(valor=None, capacidade="llm"):
    """Provedor do par "slug::modelo" pedido, ou o primeiro da capacidade."""
    pares = disponiveis(capacidade)
    if not pares:
        oficio = "de embeddings" if capacidade == "embedding" else "de IA"
        raise ConfiguracaoInvalida(
            f"Nenhum provedor {oficio} configurado",
            f"Cadastre um em Setup › AI Providers com capacidade '{capacidade}'.",
        )
    if not valor:
        return pares[0]

    slug, _, modelo = valor.partition("::")
    for par in pares:
        if par.slug == slug and (not modelo or par.modelo == modelo):
            return par
    raise ConfiguracaoInvalida(
        f"O provedor '{valor}' não está ativo ou não tem capacidade '{capacidade}'"
    )


# --------------------------------------------------------------------------
# CRUD (a chave nunca sai daqui em claro)
# --------------------------------------------------------------------------

SQL_LISTAR = """
SELECT slug, nome, tipo, url, modelos, capacidade, chave_final, ativo, atualizado_em
  FROM catalogo.provedor_ia
 ORDER BY nome
"""

SQL_UM = """
SELECT slug, nome, tipo, url, modelos, capacidade, chave_final, ativo
  FROM catalogo.provedor_ia WHERE slug = %s
"""

SQL_CRIAR = """
INSERT INTO catalogo.provedor_ia
    (slug, nome, tipo, url, modelos, capacidade, chave_cifrada, chave_final, ativo)
VALUES (%s, %s, %s, %s, %s, %s, pgp_sym_encrypt(%s, %s), %s, %s)
"""

SQL_ATUALIZAR = """
UPDATE catalogo.provedor_ia
   SET nome = %s, tipo = %s, url = %s, modelos = %s, capacidade = %s, ativo = %s,
       atualizado_em = now()
 WHERE slug = %s
"""

SQL_TROCAR_CHAVE = """
UPDATE catalogo.provedor_ia
   SET chave_cifrada = pgp_sym_encrypt(%s, %s), chave_final = %s,
       atualizado_em = now()
 WHERE slug = %s
"""

SQL_EXCLUIR = "DELETE FROM catalogo.provedor_ia WHERE slug = %s"


def listar():
    return catalogo.consultar(SQL_LISTAR, (), "provedores cadastrados")


def buscar(slug):
    return catalogo.um(SQL_UM, (slug,), f"provedor {slug}")


def validar(nome, tipo, modelos, capacidade, chave, criando):
    faltando = []
    if not nome:
        faltando.append("nome")
    if not modelos:
        faltando.append("models")
    if criando and not chave:
        faltando.append("key")
    if faltando:
        raise ConfiguracaoInvalida(f"Preencha: {', '.join(faltando)}")
    if tipo not in TIPOS:
        raise ConfiguracaoInvalida(f"Type precisa ser um de {', '.join(TIPOS)}")
    if capacidade not in CAPACIDADES:
        raise ConfiguracaoInvalida(f"Capability precisa ser um de {', '.join(CAPACIDADES)}")
    # A Anthropic nao tem API de embeddings; quem serve e o formato OpenAI, que
    # todo provedor compativel (DeepSeek, OpenRouter, vLLM) tambem fala.
    if capacidade == "embedding" and tipo != "openai":
        raise ConfiguracaoInvalida(
            "Provedor de embedding precisa ser do tipo 'openai'",
            "A Anthropic não expõe API de embeddings. Endpoint compatível com o "
            "formato OpenAI (DeepSeek, OpenRouter, vLLM) entra como 'openai' com a "
            "URL própria.",
        )
    if not criando:
        return
    if not gerar_slug(nome):
        raise ConfiguracaoInvalida(
            "Não conseguimos derivar um slug desse nome",
            "Use ao menos uma letra ou número.",
        )


def criar(nome, tipo, url, modelos, capacidade, chave, ativo):
    modelos = separar_modelos(modelos)
    validar(nome, tipo, modelos, capacidade, chave, criando=True)
    slug = gerar_slug(nome)
    if buscar(slug):
        raise ConfiguracaoInvalida(
            f"Já existe um provedor com o slug '{slug}'",
            "Escolha outro nome — o slug é derivado dele.",
        )
    catalogo.executar(
        SQL_CRIAR,
        (slug, nome, tipo, url, modelos, capacidade, chave, senha_mestra(),
         chave[-4:], ativo),
        f"criação do provedor {slug}",
    )
    return slug


def atualizar(slug, nome, tipo, url, modelos, capacidade, chave, ativo):
    """Chave em branco mantem a atual: o UPDATE nem toca em chave_cifrada."""
    modelos = separar_modelos(modelos)
    validar(nome, tipo, modelos, capacidade, chave, criando=False)
    catalogo.executar(
        SQL_ATUALIZAR,
        (nome, tipo, url, modelos, capacidade, ativo, slug),
        f"atualização do provedor {slug}",
    )
    if chave:
        catalogo.executar(
            SQL_TROCAR_CHAVE,
            (chave, senha_mestra(), chave[-4:], slug),
            f"troca de chave do provedor {slug}",
        )


def excluir(slug):
    catalogo.executar(SQL_EXCLUIR, (slug,), f"exclusão do provedor {slug}")
