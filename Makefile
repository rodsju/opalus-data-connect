SHELL:=/bin/bash
# ARGS repassa o argumento solto do alvo (ex.: `make sh app`)
ARGS = $(filter-out $@,$(MAKECMDGOALS))
MAKEFLAGS += --silent
DOCKER_COMPOSE_FILE=$(shell echo -f docker-compose.yml -f docker-compose.override.yml)


_rebuild: 
	docker-compose ${DOCKER_COMPOSE_FILE} down
	docker-compose ${DOCKER_COMPOSE_FILE} build --no-cache --force-rm

up:
	docker-compose ${DOCKER_COMPOSE_FILE} up -d --remove-orphans
# 	docker-compose docker-compose.yml -f docker-compose.override.yml up -d --remove-orphans

up_debug: 
	docker-compose ${DOCKER_COMPOSE_FILE} stop app
	docker-compose ${DOCKER_COMPOSE_FILE} -f docker-compose.override.debug.yml up -d --remove-orphans

up_normal: 
	docker-compose ${DOCKER_COMPOSE_FILE} stop app
	docker-compose ${DOCKER_COMPOSE_FILE} up -d --remove-orphans

checkcode: 
	echo "verify pep8 ..."
	docker-compose ${DOCKER_COMPOSE_FILE} exec app flake8 .
	docker-compose ${DOCKER_COMPOSE_FILE} exec app isort . --check-only

flake8: 
	echo "verify pep8 ..."
	docker-compose ${DOCKER_COMPOSE_FILE} exec app black .
	docker-compose ${DOCKER_COMPOSE_FILE} exec app isort .
	docker-compose ${DOCKER_COMPOSE_FILE} exec app flake8 .

localflake8: 
	echo "verify pep8 ..."
	black . && isort . && flake8 .

log:
	docker-compose ${DOCKER_COMPOSE_FILE} logs -f --tail 200 app

logs:
	docker-compose ${DOCKER_COMPOSE_FILE} logs -f --tail 200

stop: 
	docker-compose ${DOCKER_COMPOSE_FILE} stop

# -------------------------------
# DOWN o serviço
# -------------------------------
down:
	docker-compose ${DOCKER_COMPOSE_FILE} down
# -------------------------------	

status: 
	docker-compose ${DOCKER_COMPOSE_FILE} ps

restart: 
	docker-compose ${DOCKER_COMPOSE_FILE} restart

sh: 
	docker-compose ${DOCKER_COMPOSE_FILE} exec ${ARGS} bash

# Mapeia o schema Oracle para o catalogo no Postgres.
# Ex.: make catalogo ARGS="--limite 3"
catalogo:
	docker-compose ${DOCKER_COMPOSE_FILE} exec app python scripts/mapear_oracle.py $(ARGS)

# Refaz SO as amostras: 100 linhas por objeto, os registros mais recentes quando
# a tabela deixa ordenar barato, sem mascaramento. NAO toca em estrutura,
# descricao de IA, embedding nem no atualizado_em -- por isso nenhuma descricao
# ja gerada aparece como "vencida" depois. Ver o docstring de mapear_oracle.py.
#
#   make amostras                                  # schema inteiro
#   make amostras ARGS="--tabelas CAPADMISSION"    # uma tabela
#   make amostras ARGS="--tabelas 'CAP%,GLB%'"     # por prefixo, curinga do SQL
#   make amostras ARGS="--limite 5"                # smoke test
#   make amostras ARGS="--amostra 50"              # menos linhas por objeto
#
# NAO use --pular-existentes aqui: ele pula o que ja esta em catalogo.objeto, e
# neste modo isso e o schema inteiro -- o run passaria por todos sem fazer nada.
# Commit e por objeto, entao para retomar depois de um Ctrl-C basta rodar de
# novo (refaz o que ja passou, sem estragar nada) ou recortar com --tabelas.
amostras:
	docker-compose ${DOCKER_COMPOSE_FILE} exec app python scripts/mapear_oracle.py --somente-amostras $(ARGS)

# Aplica scripts/catalogo_schema.sql no Postgres sem tocar no Oracle. Serve para
# mudanca de schema fora da VPN -- o mapeador completo precisaria do Oracle.
schema:
	docker-compose ${DOCKER_COMPOSE_FILE} exec app python scripts/mapear_oracle.py --somente-ddl

# Confere como o .env foi lido e se o Oracle responde, sem mapear nada
catalogo_env:
	docker-compose ${DOCKER_COMPOSE_FILE} exec app python scripts/mapear_oracle.py --conferir-env

# Testes das partes puras do mapeador (mascaramento, conversao, SQL da amostra)
catalogo_test:
	docker-compose ${DOCKER_COMPOSE_FILE} exec app pytest tests -v

# Processa um lote de descricoes de IA criado em Setup > Lote de descricoes.
# A pagina ja dispara sozinha; este alvo serve para RETOMAR um lote interrompido.
# Ex.: make lote ARGS="--job 7"
lote:
	docker-compose ${DOCKER_COMPOSE_FILE} exec app python scripts/descrever_lote.py $(ARGS)

# Vetoriza um lote criado em Setup > Lote de vetores. Mesmo script do lote de
# descricoes -- a tarefa gravada no lote e quem decide o que cada item faz.
# Ex.: make vetores ARGS="--job 8"
vetores:
	docker-compose ${DOCKER_COMPOSE_FILE} exec app python scripts/descrever_lote.py $(ARGS)

# Backup do Postgres do catalogo em ~/bkp/<pasta-do-projeto>/bd/bd_<timestamp>.dump
# Formato custom (-Fc), que restaura com pg_restore. O pg_dump roda dentro do
# container e o dump sai pelo stdout, entao nao precisa do binario no host.
BKP_DIR=$(HOME)/bkp/$(notdir $(CURDIR))/bd

bkp:
	mkdir -p $(BKP_DIR)
	docker-compose ${DOCKER_COMPOSE_FILE} up -d postgres
	docker-compose ${DOCKER_COMPOSE_FILE} exec -T postgres \
		pg_dump -U catalogo -d catalogo -Fc > $(BKP_DIR)/bd_$$(date +%Y%m%d_%H%M%S).dump
	ls -lh $(BKP_DIR) | tail -1

# Restaura um dump gerado pelo `make bkp`. O arquivo e obrigatorio:
#   make restore DUMP=~/bkp/opalus-data-connect/bd/bd_20260827_080630.dump
# --clean --if-exists derruba os objetos antes de recriar: o banco fica igual ao
# dump, e o que existir so no banco atual se perde.
# O `eval echo` expande o ~ do caminho: o zsh nao expande til depois de DUMP=.
restore:
	test -n "$(DUMP)" || { echo "informe o dump: make restore DUMP=$(BKP_DIR)/bd_AAAAMMDD_HHMMSS.dump"; ls -1t $(BKP_DIR)/*.dump 2>/dev/null | head -5; exit 1; }
	dump=$$(eval echo "$(DUMP)"); \
	test -f "$$dump" || { echo "dump nao encontrado: $$dump"; exit 1; }; \
	docker-compose ${DOCKER_COMPOSE_FILE} up -d postgres; \
	docker-compose ${DOCKER_COMPOSE_FILE} exec -T postgres \
		pg_restore -U catalogo -d catalogo --clean --if-exists --no-owner < "$$dump"; \
	echo "restaurado de $$dump"
