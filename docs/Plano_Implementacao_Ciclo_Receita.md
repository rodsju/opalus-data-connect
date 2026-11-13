# Plano Geral de Implementação — Plataforma do Ciclo da Receita

**Base:** Cadernos Funcionais do Ciclo da Receita (Blocos 1 a 12)
**Data:** outubro/2026
**Público:** diretoria

---

## 1. Resumo executivo

Os cadernos descrevem uma plataforma que acompanha cada real da receita, da **regra do contrato** até o **dinheiro no caixa**:

> REGRA → PREVISÃO → CONTA → ENVIO → GLOSA → RECURSO → RECUPERAÇÃO → RECEBIMENTO → RESULTADO
> Valendo para todas as etapas: rastreabilidade, responsáveis, SLA, indicadores, alertas e integração.

**Onde estamos hoje.** A plataforma já **lê o IW (ERP) e a planilha de glosa, cruza as duas e mostra os números**. A parte de glosa e recurso é a mais avançada: há relatórios de glosa por operadora, motivo, unidade e competência, funil de status, prazos de recurso, recuperado e perda, além da importação dos XML de retorno das operadoras. Também já existem a conta do paciente de ponta a ponta (orçamento → pré-auditoria → fatura → glosa), o risco de glosa por orçamento e a análise com IA antes do envio.

**A principal diferença entre o hoje e o caderno.** A plataforma atual é de **leitura e análise**. O caderno pede também uma plataforma de **trabalho e decisão**: registrar regras contratuais com vigência, abrir pendências com dono e prazo, pedir justificativa, travar antes de perder prazo de recurso e guardar evidências e histórico. Essa camada ainda não existe e é o maior bloco de trabalho pela frente.

**Situação por bloco:**

| Situação | Blocos |
|---|---|
| 🟢 Avançado | 5 (Glosa, recurso e recuperado) |
| 🟡 Parcial | 3 (Conferência da conta), 4 (Envio, protocolo e NF), 8 (Indicadores) |
| 🟠 Inicial | 2 (Previsão), 6 (Contas a receber), 7 (Agendas e causa), 9 (Rastreabilidade), 10 (Governança) |
| ⚪ Não iniciado | 1 (Regras contratuais), 11 (Responsáveis e SLA), 12 (Dashboard executivo) |

**Proposta.** Implantar em **5 ondas**. Cada onda entrega algo utilizável e prepara a seguinte. A primeira usa dados que **já estão carregados e ainda não aparecem em nenhuma tela**, como vencimentos, atraso e previsão de recebimento da planilha, e por isso pode dar resultado rápido ao Financeiro.

---

## 2. Situação atual × caderno, bloco a bloco

Legenda: 🟢 avançado · 🟡 parcial · 🟠 inicial · ⚪ não iniciado

### Bloco 1 — Regras contratuais e tabelas ⚪
- **O caderno pede:** contrato e aditivo como "motor de regra", com vigência, escopo (operadora → contrato → programa → serviço → paciente), tabela aplicável (SIMPRO, Brasíndice, própria, congelada), exceções e explicação de cada regra aplicada.
- **Já temos:** parâmetros simples por convênio (prazo de pagamento, prazo de recurso, impostos, de-para de convênios). Eles podem ser editados na tela, mas não têm vigência, documento de origem nem histórico.
- **Falta:** praticamente todo o bloco. O IW tem tabelas de contrato e tabela de preço que ainda não usamos e são o ponto de partida.

### Bloco 2 — Previsão, autorização e ajuste da receita 🟠
- **O caderno pede:** previsão viva (orçamento → autorização/senha → execução), recálculo em alta, rehospitalização ou mudança de PAD, controle de prorrogação futura e forecast explicado ("ponte" de R$ 5,20 mi para R$ 5,06 mi).
- **Já temos:** orçamentos por status de autorização, orçamentos autorizados ainda não faturados e controle de senha (vencida ou a vencer).
- **Falta:** forecast e sua ponte explicativa, recálculo por eventos do paciente, comparação entre prorrogação autorizada e novo cenário, e PAD (ainda não localizamos onde o PAD fica no IW).

### Bloco 3 — Conta, conferência e trabalho por exceção 🟡
- **O caderno pede:** confrontar contrato × PAD × autorização × realizado, intercorrência clínica × processual, impacto na margem (pacote), conta simulada, conta apta e fila de exceções priorizada.
- **Já temos:**
  - pré-auditoria (o que foi cortado antes do envio e por quê);
  - risco de glosa por orçamento: sem senha, senha vencida, faturado acima do orçado, item não orçado, preço divergente, histórico de glosa;
  - análise com IA da conta antes do envio;
  - contas paradas antes da operadora.
- **Falta:** a comparação com contrato e PAD, o impacto financeiro das intercorrências (hoje elas só aparecem na visão clínica), a classificação "conta apta" e a fila de exceções com prazo e próxima ação.

### Bloco 4 — TISS, envio, protocolo, NF e acompanhamento 🟡
- **O caderno pede:** validar o TISS antes do envio, registrar canal, protocolo e NF, gatilho de NF parametrizável, alerta "conta fechada sem NF", previsão de recebimento por regra contratual, status da operadora e alertas.
- **Já temos:**
  - importação dos XML de retorno das operadoras;
  - guias exportadas sem retorno;
  - divergência entre o retorno e o ERP;
  - contas por etapa (aberta, liberada, exportada, baixada).
- **Falta:**
  - validação antes do envio;
  - controle de NF (no IW o número da NF aparece em só cerca de 15% das contas, um problema de dado a resolver);
  - parametrização do momento da NF;
  - painel de acompanhamento e alertas desta etapa.

### Bloco 5 — Pré-análise, faturado, recurso, glosa acatada e recuperado 🟢
- **O caderno pede:** a trajetória de cada valor (apto, em regularização, acatado, glosado, em recurso, recuperado) e o vínculo entre a competência de origem e o caixa.
- **Já temos:**
  - glosa da planilha e dos XML cruzada com o IW;
  - funil de status, prazo de recurso por faixa, recorrido, recuperado e perda;
  - motivos TISS (tabela ANS sempre atualizada);
  - origem da glosa;
  - evolução por competência.
- **Falta:** o estado **"em regularização para faturamento futuro"**, o quadro **"recuperado por competência × caixa"** e o controle do recurso como tarefa (hoje ele é só leitura da planilha).

### Bloco 6 — Contas a receber, caixa e resultado 🟠
- **O caderno pede:** recebível rastreável, previsto × recebido, aging, pagamento parcial explicado, "atraso real da operadora" só depois de validar as pendências internas, caixa projetado e modelos de NF A, B e C.
- **Já temos:** a cascata faturado → líquido → recebido → saldo para as contas com glosa. Os dados de vencimento, dias de atraso, aging e data prevista de recebimento **já estão carregados na base, mas não aparecem em nenhuma tela**.
- **Falta:** os painéis de recebíveis, aging, caixa previsto × realizado e competência × caixa, além da parametrização dos modelos de NF por operadora.

### Bloco 7 — Agendas de ação, prazos e causa da pendência 🟠
- **O caderno pede:** três agendas separadas (Comercial, Planejamento Financeiro e Calendário de Recurso), origem da glosa em 7 categorias para orientar a busca de evidência e causa raiz depois.
- **Já temos:** glosas sem recurso agrupadas por proximidade do prazo e classificação inicial da origem da glosa.
- **Falta:** as agendas como listas de trabalho (com responsável, documento e status) e a classificação padronizada de origem com subcausa.

### Bloco 8 — Indicadores de performance 🟡
- **O caderno pede:** forecast × faturamento, receita postergada, glosa acatada por momento, recursos, reversão 100%, receita retida e em negociação, tempos de cada etapa, visão por operadora e filial, e tendência.
- **Já temos:** os indicadores de glosa, recurso, recuperado, perda e taxa de recuperação, por operadora, unidade, motivo e competência.
- **Falta:** forecast, receita postergada, **reversão 100%**, receita retida e negociação (com aging), tempos entre etapas, intercorrência e visão por período de caixa.

### Bloco 9 — Rastreabilidade, evidências e histórico 🟠
- **O caderno pede:** linha do tempo única do valor, evidência ligada a cada evento, histórico de alterações (antes, depois, quem, quando, por quê), dossiê da cobrança e o **Lote IW** como eixo do ciclo.
- **Já temos:** a "história" da conta (orçamento → pré-auditoria → fatura → glosa), o histórico de cada carga da planilha com comparação entre versões e a indicação da fonte (XML ou planilha).
- **Falta:**
  - anexos e evidências;
  - registro de alterações com justificativa;
  - dossiê completo;
  - ligação pelo Lote IW (precisa de confirmação do TI sobre onde o lote fica no IW).

### Bloco 10 — Governança, parametrização e integrações 🟠
- **O caderno pede:** parametrização por operadora, contrato, programa, vigência e escopo, regra formalizada × prática não formalizada, exposição financeira dessa prática, perfis de acesso, auditoria de alterações e conflito entre fontes visível.
- **Já temos:**
  - a plataforma lê o IW sem duplicar o que ele calcula;
  - os parâmetros são editáveis;
  - a tabela de motivos da ANS é sincronizada;
  - divergências entre planilha, XML e IW aparecem em vez de serem sobrescritas.
- **Falta:**
  - vigência e histórico nos parâmetros;
  - status "formalizada / em formalização / não formalizada";
  - **perfis de acesso** (hoje todos os usuários veem tudo);
  - trilha de auditoria.

### Bloco 11 — Responsáveis, SLA, complexidade e escalonamento ⚪
- **O caderno pede:** cada pendência com dono, prazo, complexidade e próxima ação, SLA configurável, alerta progressivo, **trava antes de perder o prazo**, justificativa obrigatória, ciência do gestor e visões individual, do gestor e executiva.
- **Já temos:** nada desta camada.
- **Falta:** o bloco inteiro. Ele depende da "camada de trabalho" descrita na Seção 3.

### Bloco 12 — Visão consolidada e dashboard executivo ⚪
- **O caderno pede:** uma tela que conecte todos os blocos, com três linhas de indicadores (formação da receita, glosa/recurso e recebíveis).
- **Já temos:** indicadores no topo de cada relatório, mas nenhuma visão única.
- **Falta:** o painel executivo. Uma primeira versão é possível já na Onda 1 com os dados que existem e cresce a cada onda.

---

## 3. As quatro fundações que faltam

Quase todo o trabalho restante depende de quatro bases que ainda não existem:

1. **Camada de trabalho (pendências).** Hoje a plataforma mostra; precisa passar a permitir **agir**: abrir pendência, atribuir responsável, definir prazo, registrar justificativa, anexar evidência, encerrar e reabrir. Os Blocos 3, 7, 9 e 11 dependem dela.
2. **Cadastro de regras com vigência e origem.** Contratos, aditivos, tabelas e parâmetros com início, fim, escopo, documento de origem e status de formalização, sem apagar a regra anterior. Os Blocos 1, 4, 6 e 10 dependem dele.
3. **Perfis de acesso e trilha de auditoria.** Perfis de consulta, operação, faturamento, Comercial, Financeiro e gestor, com registro de quem alterou o quê e quando. São obrigatórios antes de liberar a plataforma para registrar decisões.
4. **Dados ainda não conectados.** Contratos e tabelas de preço, contas a receber e reconhecimento de receita, integração de NF, PAD e Lote IW. Parte já foi identificada no IW e parte precisa de confirmação do TI.

---

## 4. Plano em ondas

O esforço é relativo (P = pequeno, M = médio, G = grande). Os prazos em calendário serão definidos depois que as decisões da Seção 5 forem tomadas.

### Onda 1 — Visibilidade financeira com o que já temos · esforço M
*Objetivo: resultado rápido para o Financeiro e a diretoria, sem depender de nenhum cadastro novo.*
- Painel de **contas a receber**: a vencer, vencido, aging por faixa, por operadora, filial e competência (Bloco 6).
- **Previsto × recebido** e **competência × caixa** (Blocos 5 e 6).
- Quadro **"Receita recuperada por competência × caixa"** (Bloco 5).
- Indicadores novos: **reversão 100%** e taxa de reversão integral, e tempos glosa → recurso → recuperação (Bloco 8).
- Alerta de **conta fechada / exportada sem NF** e relatório de qualidade do dado de NF no IW (Bloco 4).
- **Dashboard executivo, versão 1**, com o que já existe (Bloco 12).

### Onda 2 — Fundações: acesso, histórico e regras com vigência · esforço M
*Objetivo: preparar a plataforma para registrar decisões com segurança.*
- Perfis de acesso e controle do que cada perfil vê e faz, incluindo o nome do paciente (Bloco 10).
- Trilha de auditoria: antes, depois, quem, quando e por quê (Blocos 9 e 10).
- Parâmetros atuais ganham **vigência, documento de origem, responsável e histórico** (Bloco 10).
- Parametrização inicial manual do momento da NF (modelos A, B e C), do prazo de recurso e do prazo de pagamento por operadora (Blocos 4, 6 e 10).

### Onda 3 — Trabalho por exceção, recurso e SLA · esforço G
*Objetivo: nenhuma glosa recorrível perde prazo sem decisão registrada.*
- **Calendário de Recurso** como lista de trabalho: responsável, documentos, dias restantes, status (Bloco 7).
- **Origem da glosa** padronizada (operacional, documental, Comercial, assistencial, operadora, contratual, outro) com subcausa, apontando a evidência necessária (Bloco 7).
- **Sinalizadores progressivos** e **trava de decisão** antes de vencer o prazo, com justificativa obrigatória e ciência do gestor (Bloco 11).
- **SLA configurável** por área e tipo de pendência, definido junto com as áreas, e escalonamento por valor e risco (Bloco 11).
- **Agenda Comercial** e **Agenda de Planejamento Financeiro** (Bloco 7).
- Visões "Minhas pendências", do gestor e executiva, e o indicador de **oportunidade de recurso perdida** (Bloco 11).
- Estado **"em regularização para faturamento futuro"** (Bloco 5).
- **Receita temporariamente retida / em negociação** com aging (Bloco 8).

### Onda 4 — Regras contratuais e conferência da conta · esforço G
*Objetivo: a plataforma passa a saber qual regra vale para cada conta e por quê.*
- Cadastro de **contrato, aditivo, tabela e vigência**, com escopo e hierarquia operadora → contrato → programa → serviço → paciente, aproveitando as tabelas de contrato e preço do IW (Bloco 1).
- Status da regra (formalizada, em formalização, não formalizada) e **exposição financeira das práticas não formalizadas**, enviada à Agenda Comercial (Bloco 10).
- Conferência **autorização × contrato** (ex.: 28 fisioterapias autorizadas, contrato permite 16) e **realizado × PAD** (Bloco 3).
- **Intercorrência com impacto financeiro**, clínica real × processual, sem bloquear o cuidado (Blocos 3 e 8).
- **Conta apta × fila de exceções** priorizada por prazo, impacto, risco e recorrência, e conta simulada (Bloco 3).
- Previsão de recebimento calculada pela regra contratual (NF + X, protocolo + Y, aceite + Z) (Blocos 4 e 6).

### Onda 5 — Previsão viva, dossiê e integrações · esforço G
*Objetivo: fechar o ciclo da previsão ao resultado e reduzir trabalho manual.*
- **Forecast explicado** (ponte: admissões, altas, rehospitalizações, mudanças de PAD) e recálculo por eventos do paciente (Bloco 2).
- Controle de **prorrogação futura** × novo cenário, com sinalização de ajuste (Bloco 2).
- **Dossiê da cobrança** e linha do tempo única pelo Lote IW, com evidências anexadas (Bloco 9).
- **Validação TISS antes do envio** e painel completo de envio, protocolo, NF e status da operadora (Bloco 4).
- Integrações com operadoras (XML, demonstrativos, portais, API), com registro da fonte de cada informação (Blocos 4 e 10).
- Futuro: geração de XML, de recurso e de documentos pela plataforma.

O dashboard executivo (Bloco 12) evolui a cada onda até a visão completa do caderno.

---

## 5. Decisões e insumos necessários da diretoria

1. **SLAs por área:** o caderno determina que sejam definidos *com as áreas*. É preciso indicar quem conduz essa definição antes da Onda 3.
2. **Dono do cadastro de contratos e aditivos:** quem cadastra, quem valida e qual a fonte oficial dos documentos (Onda 4).
3. **Planilha de glosa:** hoje ela é a fonte de recurso, recuperado e perda. É preciso definir até quando continua e quando o registro passa a ser feito direto na plataforma (Onda 3).
4. **Pedidos ao TI do IW:**
   - onde fica o **PAD**;
   - onde fica o **Lote IW**;
   - por que a NF aparece em poucas contas;
   - acesso de leitura às tabelas de contas a receber e integração de NF.
5. **Perfis de acesso:** quais perfis existem e quem pode ver o nome do paciente e dados clínicos (Onda 2).
6. **Prioridade entre as Ondas 3 e 4:** a proposta é proteger primeiro os prazos de recurso (perda evitável imediata) e depois as regras contratuais. A diretoria pode inverter se a prioridade for a conferência da conta.

---

## 6. Riscos e cuidados

- **Qualidade do dado no IW:** a glosa deixou de ser registrada no IW em jul/2025 e a NF aparece só em parte das contas. Os indicadores dependem de corrigir isso na origem.
- **Dependência da planilha** até a Onda 3: os erros de digitação seguem sendo detectados (a plataforma já aponta divergências), mas não evitados.
- **Cadastro contratual é trabalho humano:** sem as pessoas responsáveis alimentando contratos e aditivos, a Onda 4 não entrega valor.
- **Adesão ao SLA:** o caderno é claro que o SLA "não deve virar punição". A comunicação com as áreas precisa reforçar isso.

---

## 7. Princípios que o plano preserva

- A plataforma **não decide conduta clínica nem bloqueia atendimento**: ela sinaliza para revisão.
- **Não duplica o IW**: o que o IW já calcula, a plataforma lê, confronta e explica.
- **Regra nova não apaga regra antiga**: toda regra tem vigência e origem.
- **Automação não elimina decisão humana**: a justificativa assistencial, a exceção, a negociação e o acatamento continuam com pessoas.
- **Nada some em silêncio**: prazo perdido, conflito entre fontes e alteração sempre ficam registrados.

---

## 8. Próximos passos imediatos

1. Validar este plano e a ordem das ondas com a diretoria.
2. Encaminhar ao TI do IW os pedidos do item 4 da Seção 5.
3. Iniciar a Onda 1 (contas a receber, competência × caixa, reversão 100% e dashboard executivo v1).
4. Em paralelo, definir os perfis de acesso e os responsáveis por SLA e por contratos.
