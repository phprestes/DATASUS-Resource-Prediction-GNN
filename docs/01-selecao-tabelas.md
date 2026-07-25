# Seleção de tabelas e colunas do CNES

Este arquivo é a **fonte da verdade** do schema usado pelo projeto. É lido em
tempo de import por [`src/schema.py`](../src/schema.py), que dele deriva
`FACT_TABLES`, `CNES_USEFUL_COLUMNS`, `CNES_DTYPES`, `CNES_PKEY` e `CNES_FKEY`.
Editar este arquivo muda o pipeline; não existe uma segunda lista em código
para manter em sincronia.

Substitui `docs/SelecaoTabelas_v1.pdf` e `docs/SelecaoTabelas_v2.pdf`, que
ficam no repositório apenas como registro histórico.

## Critério de seleção

Uma coluna só é `util` se passar em **dois** filtros independentes:

1. **Semântico** — a coluna significa algo para a pergunta de pesquisa.
   Herdado da classificação Útil / Não Útil do `SelecaoTabelas_v2.pdf`, que foi
   lida do `DICIONARIO_DE_DADOS_CNES_2025.pdf`.
2. **Empírico** — a coluna não é degenerada nos dados reais: não está 100% nula
   em todos os snapshots medidos, e não é constante em todos eles.

A versão anterior da seleção aplicava só o primeiro. Isso deixava passar
colunas que o dicionário descreve como significativas mas que, no banco de
produção, não carregam informação nenhuma. O caso que motivou a mudança:
`DT_ATUALIZACAO_ORIGEM` é descrita como "data da primeira entrada no banco de
produção federal" e é semanticamente útil, mas chega 100% nula em
`rlEstabEquipamento` e preenchida em `rlEstabComplementar` — a diferença é
invisível para quem lê só o dicionário.

### Vocabulário de `classificacao`

| valor | significado |
|---|---|
| `util` | passou nos dois filtros; entra em `CNES_USEFUL_COLUMNS` |
| `descartada` | falhou em um dos filtros; a justificativa diz qual |
| `pendente` | semanticamente útil, ainda sem medição; resolvida pelo `notebook/00_analise_alvo.ipynb` |

### Escopo da tabela

O campo **escopo** de cada tabela vale `incluida` ou `fora`. Só as `incluida`
entram em `FACT_TABLES`, ou seja, só elas são ingeridas do ZIP. Antes desta
revisão, 57 tabelas eram ingeridas e 13 delas descartadas em silêncio na
conversão para Parquet, por não terem entrada em `CNES_USEFUL_COLUMNS`. O
descarte agora é declarado, com motivo escrito, e acontece antes do download
virar trabalho perdido.

## Notas de nomenclatura

Os nomes divergem entre o dicionário Oracle e os arquivos CSV distribuídos pelo
CNES. As tabelas abaixo usam o **nome do CSV**, que é o que o código vê. Três
deformações são recorrentes:

- **Datas embrulhadas.** O header do CSV é a própria expressão SQL da extração,
  `TO_CHAR(DT_ATUALIZACAO,'DD/MM/YYYY')`, achatada pelo `normalize_names=True`
  do DuckDB para `to_chardt_atualizacaoddmmyyyy`. Em `tbCargaHorariaSus` o
  alias da tabela sobrevive dentro do nome: `to_charadt_atualizacaoddmmyyyy`.
- **Nomes diferentes para a mesma coisa.** `RL_NASF_CNES` no dicionário é
  `rlNasfEsf` no CSV. `CO_PROFISSIONAL` em `RL_ESTAB_UNID_ACOLHIM` é
  `co_profissional_sus`. `SEQ_EQUIPE` em `RL_EQUIPE_ALDEIA` é `co_seq_equipe`.
- **Caixa.** O dicionário é `SCREAMING_SNAKE_CASE`; o CSV é `snake_case` e os
  nomes de tabela são `camelCase`.

## Legenda das colunas

- **dtype** — tipo de destino aplicado na conversão para Parquet por
  `src/to_parquet.py`. `datetime64[ns]` dispara `try_strptime` com máscara
  `%d/%m/%Y` e anula datas anteriores a 1900-01-01, sentinela do CNES.
- **pkey** / **fkey_para** — o grafo relacional entregue ao RelBench.

### Chave primária e chave natural

São coisas diferentes e as duas aparecem nos metadados de cada tabela.

**Chave primária** é a chave da *entidade*, usada pelo RelBench para ligar
tabelas — quase sempre `co_unidade`. Ela **não é única**: `rlEstabEquipamento`
tem uma linha por equipamento de cada estabelecimento, não uma por
estabelecimento.

**Chave natural** é o conjunto de colunas que identifica uma *linha*, e é o que
`src/changes.py` precisa para distinguir uma modificação de uma remoção seguida
de inserção ao comparar dois snapshots. É opcional: quando não declarada, o
diff opera por presença da tupla inteira e não classifica modificações — o que
infla a taxa de mudança, porque cada alteração conta como dois eventos.

As chaves naturais hoje declaradas são **hipóteses derivadas do dicionário**,
ainda não verificadas contra os dados. Confirmar sua unicidade é item do
`notebook/00_analise_alvo.ipynb`.
- **nulos** — percentual de nulos medido, por snapshot, na ordem
  201701 e 202501. `n/m` = não medida.

## Resumo
- Tabelas no dicionário: 57
- Tabelas `incluida`: 44
- Tabelas `fora`: 13
- Colunas `util`: 389
- Colunas `descartada` pelo filtro semântico: 521
- Colunas `descartada` pelo filtro empírico: 1
- Colunas `pendente`: 0

### Tabelas fora de escopo

| tabela | motivo |
|---|---|
| `rlEstabEndCompl` | filtro semântico: todas as 23 colunas do dicionário são Não Útil |
| `rlEstabEquipeMun` | filtro semântico: todas as 10 colunas do dicionário são Não Útil |
| `rlEstabOrgParc` | filtro semântico: todas as 24 colunas do dicionário são Não Útil |
| `rlEstabRepresentante` | filtro semântico: todas as 11 colunas do dicionário são Não Útil |
| `rlEstabTeleCnes` | filtro semântico: todas as 10 colunas do dicionário são Não Útil |
| `rlJustifPtProf` | filtro semântico: todas as 12 colunas do dicionário são Não Útil |
| `rlJustifPtProfLog` | filtro semântico: todas as 13 colunas do dicionário são Não Útil |
| `rlNasfEsf` | filtro semântico: todas as 11 colunas do dicionário são Não Útil |
| `tbEquipeAtendCompl` | filtro semântico: todas as 11 colunas do dicionário são Não Útil |
| `tbEquipeChDifer` | filtro semântico: todas as 14 colunas do dicionário são Não Útil |
| `tbEstabBanco` | filtro semântico: todas as 10 colunas do dicionário são Não Útil |
| `tbJustificaDesligaPrf` | filtro semântico: todas as 15 colunas do dicionário são Não Útil |
| `tbLocalGerenteAdministrador` | filtro semântico: todas as 5 colunas do dicionário são Não Útil |

## Tabelas

### rlAdmGerenciaCnes

- **Dicionário:** `RL_ADM_GERENCIA_CNES` — Gerente/Administrador x Contratos do Estab
- **Escopo:** incluida
- **Chave primária:** `nu_cnpj_adm`
- **Linhas medidas:** 201701: 878, 202501: 4.517

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `nu_cnpj_adm` | VARCHAR2(14) | string | util | sim | - | 0/0 | Número do CNPJ do Gerente/Administrador [2] |
| `co_unidade` | VARCHAR2(31) | string | util | - | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde [2] |
| `to_chardt_vigencia_inicialddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Vigência Inicial do Contrato [2] |
| `to_chardt_vigencia_finalddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Vigência Final do Contrato [3] |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro [3] |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro [3] |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal [3] |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal [3] |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência [3] |
| `nu_seq_processo` | NUMBER | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga [3] |

### rlCooperativa

- **Dicionário:** `RL_COOPERATIVA` — Cooperativas
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 1.731, 202501: 2.323

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_cooperativa` | VARCHAR2(31) | string | util | - | - | 0/0 | Código CNES da Cooperativa |
| `co_cbo` | VARCHAR2(5) | category | util | - | - | 0/0 | Código Brasileiro de Ocupação, especialidade prestada pela Cooperativa |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |

### rlEquipeAldeia

- **Dicionário:** `RL_EQUIPE_ALDEIA` — Aldeias Atendidas das Equipes
- **Escopo:** incluida
- **Chave primária:** `co_municipio`
- **Linhas medidas:** 201701: 0, 202501: 275

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_municipio` | VARCHAR2(6) | category | util | sim | `tbEquipe` | 0 | Código do Município da Equipe [3] |
| `co_area` | VARCHAR2(4) | string | util | - | `tbEquipe` | 0 | Código da Área da Equipe [3] |
| `co_seq_equipe` | NUMBER(8) | string | util | - | `tbEquipe` | 0 | Sequencial da Equipe [3] |
| `co_aldeia` | NUMBER | category | util | - | - | 0 | Código da Aldeia [4] |
| `co_unidade` | VARCHAR2(31) | string | util | - | `tbEstabelecimento` | 0 | Código do Estabelecimento de Saúde [5] |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0 | Data da Última Atualização do Registro [5] |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0 | filtro semântico: Último Usuário que atualizou o Registro [5] |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal [5] |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal [5] |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência [6] |
| `nu_seq_processo` | NUMBER | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga [6] |

### rlEquipeNasfEsf

- **Dicionário:** `RL_EQUIPE_NASF_ESF` — ESF das Equipes NASF
- **Escopo:** incluida
- **Chave primária:** `co_municipio`
- **Linhas medidas:** 201701: 22.337, 202501: 85.806

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_municipio` | VARCHAR2(6) | category | util | sim | `tbEquipe` | 0/0 | Código do Município da Equipe NASF |
| `co_area` | VARCHAR2(4) | string | util | - | `tbEquipe` | 0/0 | Código da Área da Equipe NASF |
| `seq_equipe` | NUMBER(8) | string | util | - | `tbEquipe` | 0/0 | Sequencial da Equipe NASF |
| `co_municipio_esf` | VARCHAR2(6) | category | util | - | - | 0/0 | Código do Município da Equipe ESF vinculada |
| `co_area_esf` | VARCHAR2(4) | string | util | - | - | 0/0 | Código da Área da Equipe ESF vinculada |
| `seq_equipe_esf` | NUMBER(8) | string | util | - | - | 0/0 | Sequencial da Equipe ESF vinculada |
| `nu_sequencial` | NUMBER(8) | string | util | - | - | 0/0 | Sequencial único do registro de vínculo |
| `co_unidade` | VARCHAR2(31) | string | util | - | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `tp_equipe_esf` | VARCHAR2(2) | category | util | - | - | 0/0 | Tipo da Equipe ESF |
| `co_cnes_esf` | VARCHAR2(7) | string | util | - | - | 0/0 | CNES da Equipe ESF |
| `no_fantasia_esf` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome Fantasia da Equipe ESF |
| `co_segmento_esf` | VARCHAR2(2) | category | util | - | - | 0/1 | Código do Segmento da Equipe ESF |
| `ds_segmento_esf` | VARCHAR2(60) | string | descartada | - | - | 0/1 | filtro semântico: Descrição do Segmento da Equipe ESF |
| `ds_area_esf` | VARCHAR2(60) | string | descartada | - | - | 0/1 | filtro semântico: Descrição da Área da Equipe ESF |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabAtendPrestConv

- **Dicionário:** `RL_ESTAB_ATEND_PREST_CONV` — Atendimento Prestado por Unidade
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 599.097, 202501: 993.135

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_atendimento_prestado` | CHAR(2) | category | util | - | - | 0/0 | Código do Atendimento Prestado pelo Estabelecimento |
| `co_convenio` | CHAR(2) | category | util | - | - | 0/0 | Código do Convênio |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 1/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |

### rlEstabAtenPsico

- **Dicionário:** `RL_ESTAB_ATEN_PSICO` — Atenção Psicossocial
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 974, 202501: 1.365

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `tp_estrutura` | CHAR(1) | category | util | - | - | 0/0 | Tipo da Estrutura (0 – Alugada, 1 - Própria) |
| `st_parceria_ong` | CHAR(1) | category | util | - | - | 0/0 | Informa se possui parceria com ONG (S – Sim, N - Não) |
| `nu_cnpj_ong` | VARCHAR2(14) | string | util | - | - | 94/93 | CNPJ da ONG (se houver parceria) |
| `nu_vagas_acol_notur` | NUMBER(4) | Int64 | util | - | - | 0/0 | Número de vagas para Acolhimento Noturno |
| `co_profissional_sus` | VARCHAR2(16) | string | util | - | `tbCargaHorariaSus` | 0/0 | Código do Profissional de Saúde |
| `co_cbo` | VARCHAR2(6) | category | util | - | `tbCargaHorariaSus` | 0/0 | Código Brasileiro de Ocupação |
| `tp_sus_nao_sus` | CHAR(1) | category | util | - | `tbCargaHorariaSus` | 0/0 | Indica se o Profissional faz Atendimento ao SUS (S - Sim, N - Não) |
| `ind_vinculacao` | VARCHAR2(6) | category | util | - | - | 0/0 | Indica a vinculação, o tipo e o sub tipo de vínculo do Profissional |
| `co_cnes_referencia` | VARCHAR2(7) | string | util | - | - | 0/0 | CNES do Hospital Geral de Referência |
| `st_unidade_regional` | CHAR(1) | category | util | - | - | 0/0 | Indica se a Atenção Psicossocial possui Unidade Regional (S - Sim, N - Não) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(100) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabAvaliacao

- **Dicionário:** `RL_ESTAB_AVALIACAO` — Metodologia/Classificação do Estabelecimento
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 1.317, 202501: 1.721

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_avaliacao` | VARCHAR2(2) | category | util | - | - | 0/0 | Código da Avaliação (Metodologia) |
| `co_classificacao` | VARCHAR2(2) | category | util | - | - | 0/0 | Código da Classificação da Metodologia |
| `to_chardt_avaliacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Avaliação |
| `dt_avaliacao_final` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final da Avaliação |
| `co_instituicao_avaliadora` | VARCHAR2(2) | category | util | - | - | 91/42 | Código da Instituição Avaliadora |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabCentralReg

- **Dicionário:** `RL_ESTAB_CENTRAL_REG` — Bases Descentralizadas
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 2.368, 202501: 3.204

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde [2] |
| `co_seq_central` | VARCHAR2(5) | string | util | - | - | 0/0 | Sequencial da Base Descentralizada [2] |
| `no_central` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome da Base Descentralizada [2] |
| `co_subtipo_central` | VARCHAR2(3) | category | util | - | - | 0/0 | SubTipo da Base Descentralizada [2] |
| `co_tipo_logradouro` | VARCHAR2(3) | string | descartada | - | - | 1/1 | filtro semântico: Código do Tipo de Logradouro [2] |
| `no_logradouro` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Logradouro [3] |
| `nu_numero` | VARCHAR2(10) | string | descartada | - | - | 0/0 | filtro semântico: Número do Logradouro [3] |
| `no_complemento` | VARCHAR2(60) | string | descartada | - | - | 87/86 | filtro semântico: Complemento do Logradouro [3] |
| `no_bairro` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Bairro [3] |
| `co_cep` | VARCHAR2(8) | string | descartada | - | - | 0/0 | filtro semântico: Código de Endereçamento Postal (CEP) [3] |
| `co_municipio_end` | VARCHAR2(7) | category | util | - | - | 0/0 | Código do Município [3] |
| `nu_ddd_tel` | VARCHAR2(3) | string | descartada | - | - | 37/45 | filtro semântico: DDD do Telefone [3] |
| `nu_telefone` | VARCHAR2(40) | string | descartada | - | - | 36/44 | filtro semântico: Número do Telefone [3] |
| `nu_ddd_fax` | VARCHAR2(3) | string | descartada | - | - | 88/90 | filtro semântico: DDD do Fax [3] |
| `nu_fax` | VARCHAR2(40) | string | descartada | - | - | 88/90 | filtro semântico: Número do Fax [3] |
| `no_url` | VARCHAR2(60) | string | descartada | - | - | 99/99 | filtro semântico: URL [3] |
| `no_e_mail` | VARCHAR2(60) | string | descartada | - | - | 76/78 | filtro semântico: E-mail [3] |
| `dt_ativacao` | DATE | datetime64[ns] | util | - | - | 0/0 | Data de Ativação [3] |
| `dt_desativacao` | DATE | datetime64[ns] | util | - | - | 100/100 | Data de Desativação [4] |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro [4] |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro [4] |
| `st_status` | CHAR(1) | string | descartada | - | - | n/m | filtro semântico: Status do Registro [5] |
| `st_statusmov` | CHAR(1) | string | descartada | - | - | n/m | filtro semântico: Status de Movimentação do Registro [5] |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal [6] |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal [6] |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência [6] |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga [6] |

### rlEstabColetaSelRejeito

- **Dicionário:** `RL_ESTAB_COLETA_SEL_REJEITO` — Coleta Seletiva de Rejeitos
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 496.094, 202501: 841.582

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_coleta_rejeito` | CHAR(2) | category | util | - | - | 0/0 | Código da Coleta de Rejeito |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 1/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |

### rlEstabComissaoOutro

- **Dicionário:** `RL_ESTAB_COMISSAO_OUTRO` — Comissões
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 76.572, 202501: 93.048

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_comissao` | CHAR(2) | category | util | - | - | 0/0 | Código da Comissão |
| `dt_ativacao` | DATE | string | descartada | - | - | 100/77 | filtro semântico: Data de Ativação da Comissão |
| `dt_desativacao` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data de Desativação da Comissão |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabComplementar

- **Dicionário:** `RL_ESTAB_COMPLEMENTAR` — Leitos Hospitalares
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Chave natural:** `co_unidade`, `co_leito`, `co_tipo_leito`
- **Linhas medidas:** 201701: 53.489, 202501: 59.848

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde. Chave estrangeira para a tabela de estabelecimentos |
| `co_leito` | VARCHAR(2) | category | util | - | - | 0/0 | Código do Leito. Fundamental para análises de capacidade hospitalar por tipo de leito |
| `co_tipo_leito` | VARCHAR(2) | category | util | - | - | 0/0 | Código do Tipo de Leito. Pode ser uma sub-categoria ou especialização de CO LEITO |
| `tp_altacomp` | CHAR(1) | string | descartada | - | - | 100/100 | filtro semântico: Sem Uso |
| `qt_exist` | INTEGER | Int64 | util | - | - | 0/0 | Quantidade de Leitos Existentes. Métrica quantitativa primária |
| `qt_contr` | INTEGER | string | descartada | - | - | 100/100 | filtro semântico: Sem Uso |
| `qt_sus` | INTEGER | Int64 | util | - | - | 0/0 | Quantidade de Leitos Disponíveis para o SUS. Métrica quantitativa essencial |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 0/0 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabEqpEmbarcacao

- **Dicionário:** `RL_ESTAB_EQP_EMBARCACAO` — Embarcações de Apoio
- **Escopo:** incluida
- **Chave primária:** `co_municipio`
- **Linhas medidas:** 201701: 22, 202501: 1.019

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_municipio` | VARCHAR2(6) | category | util | sim | `tbEquipe` | 0/0 | Código do Município da Equipe |
| `co_area` | VARCHAR2(4) | string | util | - | `tbEquipe` | 0/0 | Código da Área da Equipe |
| `seq_equipe` | NUMBER(8) | string | util | - | `tbEquipe` | 0/0 | Sequencial da Equipe |
| `nu_embarcacao` | VARCHAR2(3) | string | util | - | - | 0/0 | Número da Embarcação de Apoio |
| `no_embarcacao` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome da Embarcação de Apoio |
| `ds_comunidade_atendida` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Comunidade Atendida da Embarcação de Apoio |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabEqpUnidApoio

- **Dicionário:** `RL_ESTAB_EQP_UNID_APOIO` — Unidades de Apoio
- **Escopo:** incluida
- **Chave primária:** `co_municipio`
- **Linhas medidas:** 201701: 10, 202501: 1.166

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_municipio` | VARCHAR2(6) | category | util | sim | `tbEquipe` | 0/0 | Código do Município da Equipe |
| `co_area` | VARCHAR2(4) | string | util | - | `tbEquipe` | 0/0 | Código da Área da Equipe |
| `seq_equipe` | NUMBER(8) | string | util | - | `tbEquipe` | 0/0 | Sequencial da Equipe |
| `co_endereco_complementar` | VARCHAR2(5) | string | util | - | - | 0/0 | Código do Endereço Complementar. Mantida como atributo: a tabela destino `rlEstabEndCompl` está fora de escopo, então a chave estrangeira não tem para onde apontar |
| `co_unidade` | VARCHAR2(31) | string | util | - | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde. Corrigido: `src/constant.py` apontava esta coluna para `rlEstabEndCompl` |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabEquipamento

- **Dicionário:** `RL_ESTAB_EQUIPAMENTO` — Equipamentos
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Chave natural:** `co_unidade`, `co_equipamento`, `co_tipo_equipamento`, `tp_sus`
- **Linhas medidas:** 201701: 747.500, 202501: 1.247.979

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_equipamento` | CHAR(2) | category | util | - | - | 0/0 | Código do Equipamento |
| `co_tipo_equipamento` | CHAR(1) | category | util | - | - | 0/0 | Código do Tipo de Equipamento |
| `qt_existente` | NUMBER(3) | Int64 | util | - | - | 0/0 | Quantidade de Equipamentos Existentes |
| `qt_uso` | NUMBER(3) | Int64 | util | - | - | 0/0 | Quantidade de Equipamentos em Uso |
| `tp_sus` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Equipamento está disponível para o SUS (1-Sim, 2-Não) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 1/2 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabEquipeProf

- **Dicionário:** `RL_ESTAB_EQUIPE_PROF` — Profissionais das Equipes
- **Escopo:** incluida
- **Chave primária:** `co_municipio`
- **Linhas medidas:** 201701: 553.581, 202501: 815.769

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_municipio` | VARCHAR2(6) | category | util | sim | `tbEquipe` | 0/0 | Código do Município |
| `co_area` | VARCHAR2(4) | string | util | - | `tbEquipe` | 0/0 | Código da Área da Equipe |
| `seq_equipe` | NUMBER(8) | string | util | - | `tbEquipe` | 0/0 | Sequencial da Equipe |
| `co_profissional_sus` | VARCHAR2(16) | string | util | - | `tbCargaHorariaSus` | 0/0 | Código do Profissional de Saúde |
| `co_unidade` | VARCHAR2(31) | string | util | - | `tbCargaHorariaSus` | 0/0 | Código do Estabelecimento de Saúde |
| `co_cbo` | VARCHAR2(6) | category | util | - | `tbCargaHorariaSus` | 0/0 | Código Brasileiro de Ocupação |
| `tp_sus_nao_sus` | CHAR(1) | category | util | - | `tbCargaHorariaSus` | 0/0 | Indica se o Profissional faz Atendimento ao SUS (S-Sim, N-Não) |
| `ind_vinculacao` | CHAR(6) | category | util | - | - | 0/0 | Indica a vinculação, o tipo e o sub tipo de vínculo |
| `co_microarea` | VARCHAR2(16) | category | util | - | - | 51/100 | MicroArea da Equipe |
| `dt_entrada` | DATE | datetime64[ns] | util | - | - | 0/0 | Data de Entrada do Profissional na Equipe |
| `dt_desligamento` | DATE | datetime64[ns] | util | - | - | 99/99 | Data de Desligamento do Profissional na Equipe |
| `co_cnes_outraequipe` | VARCHAR2(7) | string | descartada | - | - | 100/100 | filtro semântico: CNES no qual o Profissional completa a Carga Horária |
| `co_municipio_outraequipe` | VARCHAR2(6) | string | descartada | - | - | 100/100 | filtro semântico: Código do Município no qual o Profissional completa a Carga Horária |
| `co_area_outraequipe` | VARCHAR2(7) | string | descartada | - | - | 100/100 | filtro semântico: Código da Área na qual o Profissional completa a Carga Horária |
| `co_profissional_sus_compl` | VARCHAR2(16) | string | descartada | - | - | 100/100 | filtro semântico: Profissional de Carga Horária Complementar |
| `co_cbo_ch_compl` | VARCHAR2(16) | string | descartada | - | - | 100/100 | filtro semântico: CBO do Profissional de Carga Horária Complementar |
| `st_equipeminima` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Profissional pertence a Equipe Mínima (1-Sim, 2-Não) |
| `co_mun_atuacao` | VARCHAR2(6) | string | descartada | - | - | 100/100 | filtro semântico: Código do Município de atuação da microárea do Profissional na Equipe |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `no_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabInstFisiAssist

- **Dicionário:** `RL_ESTAB_INST_FISI_ASSIST` — Instalações Físicas para Assistência
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 677.016, 202501: 1.037.063

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_instalacao` | CHAR(2) | category | util | - | - | 0/0 | Código da Instalação |
| `qt_instalacao` | NUMBER(20,5) | Int64 | util | - | - | 0/0 | Quantidade de Instalações |
| `nu_leitos` | NUMBER(20,5) | Int64 | util | - | - | 0/0 | Quantidade de Leitos / Equipos |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 1/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabPoloAldeia

- **Dicionário:** `RL_ESTAB_POLO_ALDEIA` — Aldeia / Polo-Base do Estabelecimento
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 78, 202501: 1.502

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_aldeia` | VARCHAR2(60) | category | util | - | - | 42/64 | Código da Aldeia |
| `co_polobase` | VARCHAR2(3) | category | util | - | - | 58/55 | Código do Polo-Base |
| `co_dsei` | VARCHAR2(4) | category | util | - | - | 100/82 | Código do DSEI (Distrito Sanitário Especial Indígena) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabProfComissao

- **Dicionário:** `RL_ESTAB_PROF_COMISSAO` — Profissionais da Comissão
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 0, 202501: 49.178

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0 | Código do Estabelecimento de Saúde |
| `co_comissao` | VARCHAR(2) | category | util | - | - | 0 | Código da Comissão |
| `co_profissional_sus` | VARCHAR2(16) | string | util | - | - | 0 | Código do Profissional de Saúde |
| `co_cbo` | VARCHAR2(6) | category | util | - | - | 0 | Código Brasileiro de Ocupação |
| `tp_sus_nao_sus` | CHAR(1) | category | util | - | - | 0 | Indica se o Profissional faz Atendimento ao SUS (S-Sim, N-Não) |
| `tp_vinculacao` | VARCHAR2(6) | category | util | - | - | 0 | Indica a vinculação, o tipo e o sub tipo de vínculo do Profissional |
| `st_resp_tecnico` | VARCHAR(1) | category | util | - | - | 0 | Indica se é Responsável Técnico da Comissão |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabProgFundo

- **Dicionário:** `RL_ESTAB_PROG_FUNDO` — Gestão de Atividades/Nível de Atenção
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 413.792, 202501: 629.017

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_atividade` | CHAR(2) | category | util | - | - | 0/0 | Código da Atividade / Nível de Atenção |
| `tp_estadual_municipal` | CHAR(1) | category | util | - | - | 0/0 | Indicador de Gestão (1-Estadual, 2Municipal) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 1/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |

### rlEstabRegimeRes

- **Dicionário:** `RL_ESTAB_REGIME_RES` — Unidade de Atenção em Regime Residencial
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 25, 202501: 113

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `tp_modulo` | CHAR(1) | category | util | - | - | 0/0 | Tipo de Módulo (0 – 1 módulo/15 vagas, 1 - 2 módulos/30 vagas) |
| `nu_vagas_existentes` | NUMBER(5) | Int64 | util | - | - | 0/0 | Número de vagas existentes |
| `nu_vagas_sus` | NUMBER(5) | Int64 | util | - | - | 0/0 | Número de vagas SUS |
| `dt_ativacao` | DATE | datetime64[ns] | util | - | - | 0/0 | Data de Ativação |
| `dt_desativacao` | DATE | datetime64[ns] | descartada | - | - | 100/100 | filtro empírico: 100% nula em todos os snapshots medidos |
| `co_profissional_sus` | VARCHAR2(16) | string | util | - | `tbCargaHorariaSus` | 0/0 | Código do Profissional (Coordenador do Regime Residencial) |
| `co_cbo` | VARCHAR2(6) | category | util | - | `tbCargaHorariaSus` | 0/0 | CBO do Coordenador |
| `tp_sus_nao_sus` | CHAR(1) | category | util | - | `tbCargaHorariaSus` | 0/0 | Indica se o Coordenador faz Atendimento ao SUS (S-Sim, N-Não) |
| `ind_vinculacao` | VARCHAR(6) | category | util | - | - | 0/0 | Vínculo do Coordenador com o Estabelecimento |
| `co_cnes_caps_ref` | VARCHAR(7) | string | util | - | - | 0/0 | CNES do CAPS de Referência |
| `co_prof_sus_caps_ref` | VARCHAR2(16) | string | util | - | `tbCargaHorariaSus` | 0/0 | Código do Coordenador do CAPS de Referência |
| `co_cbo_caps_ref` | VARCHAR2(6) | category | util | - | `tbCargaHorariaSus` | 0/0 | CBO do Coordenador do CAPS de Referência |
| `tp_sus_nao_sus_caps_ref` | CHAR(1) | string | descartada | - | `tbCargaHorariaSus` | 0/0 | filtro semântico: Atendimento SUS do Coord. CAPS Ref (S-Sim, N-Não) |
| `ind_vinculacao_caps_ref` | VARCHAR(6) | category | util | - | - | 0/0 | Vínculo do Coord. CAPS Ref |
| `co_cnes_unid_basica_ref` | VARCHAR(7) | string | util | - | - | 0/0 | CNES da Unidade Básica de Referência |
| `co_cnes_hosp_geral_ref` | VARCHAR(7) | string | util | - | - | 0/0 | CNES do Hospital Geral de Referência |
| `st_unidade_regional` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Regime Residencial possui Unidade Regional (S-Sim, N-Não) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(100) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabSamu

- **Dicionário:** `RL_ESTAB_SAMU` — Veículos SAMU
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 4.926, 202501: 14.769

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `dt_ativacao` | DATE | datetime64[ns] | util | - | - | 0/0 | Data de Ativação |
| `co_unidade_central` | VARCHAR2(31) | string | util | - | - | 0/0 | Código do Estabelecimento SAMU (Central de Regulação) |
| `co_seq_central` | VARCHAR2(5) | string | util | - | - | 0/0 | Sequencial do SAMU |
| `co_placa` | VARCHAR2(7) | string | descartada | - | - | 1/1 | filtro semântico: Placa do Veículo |
| `nu_chassi` | VARCHAR2(30) | string | descartada | - | - | 1/1 | filtro semântico: Número do Chassi |
| `co_prefixo_aeronave` | VARCHAR(10) | string | util | - | - | 100/100 | Prefixo da Aeronave (se aplicável) |
| `nu_embarca_marinha` | VARCHAR(10) | string | util | - | - | 100/100 | Nº Identificador da Embarcação na Marinha do Brasil (se aplicável) |
| `dt_desativacao` | DATE | datetime64[ns] | util | - | - | 86/39 | Data de Desativação |
| `co_desativacao` | VARCHAR2(3) | category | util | - | - | 0/0 | Código do Motivo de Desativação |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(10) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlEstabServClass

- **Dicionário:** `RL_ESTAB_SERV_CLASS` — Serviço Especializado/Classificação
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 765.030, 202501: 1.308.190

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_servico` | VARCHAR2(3) | category | util | - | - | 0/0 | Código do Serviço Especializado |
| `co_classificacao` | VARCHAR2(3) | category | util | - | - | 0/0 | Código da Classificação do Serviço |
| `tp_caracteristica` | CHAR(1) | category | util | - | - | 0/0 | Tipo do Serviço (1-Próprio, 2-Terceirizado, 3-Próprio e Terceirizado) |
| `co_cnpjcpf` | VARCHAR2(14) | string | util | - | - | 0/0 | Código CNES do Terceiro que presta o Serviço |
| `co_ambulatorial` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Serviço Atende Ambulatorial Não SUS (1-Sim, 2-Não) |
| `co_ambulatorial_sus` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Serviço Atende Ambulatorial SUS (1-Sim, 2-Não) |
| `co_hospitalar` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Serviço Atende Hospitalar Não SUS (1-Sim, 2-Não) |
| `co_hospitalar_sus` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Serviço Atende Hospitalar SUS (1-Sim, 2-Não) |
| `co_end_compl` | VARCHAR2(5) | string | descartada | - | - | 0/0 | filtro semântico: Código do Endereço Complementar |
| `st_ativo_sn` | CHAR(1) | string | descartada | - | - | 100/100 | filtro semântico: Sem Uso |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `dt_atualizacao_origem` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |

### rlEstabServicoApoio

- **Dicionário:** `RL_ESTAB_SERVICO_APOIO` — Serviços de Apoio
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 383.554, 202501: 540.869

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_servico_apoio` | CHAR(2) | category | util | - | - | 0/0 | Código do Serviço de Apoio |
| `co_caracteristica` | CHAR(1) | category | util | - | - | 0/0 | Código da Característica (1-Próprio, 2Terceirizado, 3-Ambos) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |

### rlEstabSipac

- **Dicionário:** `RL_ESTAB_SIPAC` — Habilitações, Incentivos e Regras Contratuais
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 85.876, 202501: 110.584

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `cod_sub_grupo_habilitacao` | VARCHAR2(4) | category | util | - | - | 0/0 | Código do item (Habilitação, Incentivo, Regra Contratual, etc.), dependendo do tipo de registro |
| `cmtp_inicio` | VARCHAR2(6) | string | util | - | - | 0/0 | Competência Inicial de validade do registro (AAAAMM) |
| `cmtp_fim` | VARCHAR2(6) | string | util | - | - | 0/0 | Competência Final de validade do registro (AAAAMM) |
| `nu_leitos` | NUMBER(3) | Int64 | util | - | - | 89/86 | Quantidade de Leitos (utilizado especificamente para habilitações que exigem contagem de leitos) |
| `no_portaria` | VARCHAR2(50) | string | descartada | - | - | 2/1 | filtro semântico: Número da Portaria que instituiu a habilitação ou incentivo |
| `dt_lancamento` | DATE | string | descartada | - | - | n/m | filtro semântico: Data de Lançamento do registro |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 2/1 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `tp_habilitacao` | VARCHAR2(2) | category | util | - | - | 0/0 | Tipo de Registro. Domínios: C (Regras Contratuais), E (Estab. Ensino), F (Filantrópicos), G (Gestão/Metas), H (Habilitações), I (Incentivos), A (IAPI), R (RAS) |

### rlEstabSubTipo

- **Dicionário:** `RL_ESTAB_SUB_TIPO` — Subtipo de Estabelecimento
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 55.352, 202501: 115.393

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde. [1] |
| `co_tipo_unidade` | VARCHAR2(2) | category | util | - | - | 0/0 | Código do Tipo de Estabelecimento. [2] |
| `co_sub_tipo_unidade` | VARCHAR2(3) | category | util | - | - | 0/0 | Código do SubTipo de Estabelecimento. [2] |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro. [2] |
| `co_usuario` | VARCHAR2(100) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro. [2] |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 0/0 | filtro semântico: Data da primeira entrada no Banco de Produção Federal. [2] |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal. [3] |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência. [3] |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga. [3] |

### rlEstabUnidAcolhim

- **Dicionário:** `RL_ESTAB_UNID_ACOLHIM` — Unidades de Acolhimento
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 154, 202501: 217

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `sq_acolhimento` | NUMBER(10) | string | util | - | - | 0/0 | Sequencial da Unidade de Acolhimento |
| `no_acolhimento` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome da Unidade de Acolhimento |
| `nu_acolhimento` | VARCHAR(10) | string | descartada | - | - | 0/0 | filtro semântico: Número da Unidade de Acolhimento |
| `tp_acolhimento` | CHAR(1) | category | util | - | - | 0/0 | Tipo da Unidade de Acolhimento |
| `no_logradouro` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Logradouro |
| `ds_complemento` | VARCHAR2(60) | string | descartada | - | - | 86/78 | filtro semântico: Complemento |
| `nu_logradouro` | VARCHAR2(10) | string | descartada | - | - | 0/0 | filtro semântico: Número do Logradouro |
| `no_bairro` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Bairro |
| `co_municipio` | VARCHAR2(6) | category | util | - | - | 0/0 | Código do Município |
| `co_cep` | VARCHAR2(8) | string | util | - | - | 0/0 | Código de Endereçamento Postal (CEP) |
| `co_ddd` | VARCHAR2(3) | string | descartada | - | - | 2/2 | filtro semântico: DDD do Telefone |
| `nu_telefone` | VARCHAR2(40) | string | descartada | - | - | 1/0 | filtro semântico: Número do Telefone |
| `tp_estrutura` | CHAR(1) | category | util | - | - | 0/0 | Tipo de Estrutura da Unidade (0-Alugada, 1-Própria) |
| `st_parceria_ong` | CHAR(1) | category | util | - | - | 0/0 | Informa se possui parceria com ONG (SSim, N-Não) |
| `nu_cnpj_ong` | VARCHAR(14) | string | util | - | - | 86/85 | CNPJ da ONG |
| `nu_vagas` | NUMBER(4) | Int64 | util | - | - | 0/0 | Número de vagas da Unidade de Acolhimento |
| `co_profissional_sus` | VARCHAR2(16) | string | util | - | - | 0/0 | Código do Profissional de Saúde |
| `co_cbo` | VARCHAR2(6) | category | util | - | `tbCargaHorariaSus` | 0/0 | Código Brasileiro de Ocupação |
| `tp_sus_nao_sus` | CHAR(1) | category | util | - | `tbCargaHorariaSus` | 0/0 | Indica se o Profissional faz Atendimento ao SUS (S-Sim, N-Não) |
| `ind_vinculacao` | VARCHAR(6) | category | util | - | - | 0/0 | Indica a vinculação, o tipo e o sub tipo de vínculo |
| `dt_ativacao` | DATE | datetime64[ns] | util | - | - | 0/0 | Data de Ativação |
| `dt_desativacao` | DATE | datetime64[ns] | util | - | - | 99/100 | Data de Desativação |
| `co_cnes_referencia` | VARCHAR(7) | string | descartada | - | - | 0/0 | filtro semântico: CNES do Hospital Geral de Referência |
| `st_unidade_regional` | CHAR(1) | category | util | - | - | 0/0 | Indica se a Unidade de Acolhimento possui Unidade Regional (S-Sim, N-Não) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(100) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlMunAtenPsico

- **Dicionário:** `RL_MUN_ATEN_PSICO` — Unidades Regionais da Atenção Psicossocial
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 868, 202501: 1.011

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_municipio` | VARCHAR2(6) | category | util | - | - | 0/0 | Código do Município que compõe a regional |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(100) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlMunRegimeRes

- **Dicionário:** `RL_MUN_REGIME_RES` — Unidades Regionais - Regime Residencial
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 4, 202501: 101

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_municipio` | VARCHAR2(6) | category | util | - | - | 0/0 | Código do Município |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(100) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### rlMunUnidAcolhim

- **Dicionário:** `RL_MUN_UNID_ACOLHIM` — Unidades Regionais da Unidade de Acolhimento
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 80, 202501: 175

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `sq_acolhimento` | NUMBER(10) | string | descartada | - | - | 0/0 | filtro semântico: Sequencial da Unidade de Acolhimento |
| `co_municipio` | VARCHAR2(6) | category | util | - | - | 0/0 | Código do Município |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(100) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbArea

- **Dicionário:** `TB_AREA` — Áreas
- **Escopo:** incluida
- **Chave primária:** `co_municipio`
- **Linhas medidas:** 201701: 50.527, 202501: 69.293

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_municipio` | VARCHAR2(6) | category | util | sim | `tbSegmento` | 0/0 | Código do Município |
| `co_area` | VARCHAR2(4) | string | util | - | - | 0/0 | Código da Área |
| `ds_area` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Descrição da Área |
| `cd_segmento` | VARCHAR2(2) | category | util | - | `tbSegmento` | 0/0 | Código do Segmento |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 66/48 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbCargaHorariaSus

- **Dicionário:** `TB_CARGA_HORARIA_SUS` — Vínculos do Profissional no Estabelecimento
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 3.575.325, 202501: 6.104.979

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_profissional_sus` | VARCHAR2(16) | string | util | - | - | 0/0 | Código do Profissional de Saúde |
| `co_cbo` | VARCHAR2(6) | category | util | - | - | 0/0 | Código Brasileiro de Ocupação |
| `tp_sus_nao_sus` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Profissional faz Atendimento SUS (S-Sim, N-Não) |
| `ind_vinculacao` | VARCHAR2(6) | category | util | - | - | 0/0 | Indica a vinculação, o tipo e o sub tipo vínculo |
| `tp_terceiro_sih` | CHAR(1) | string | descartada | - | - | 45/44 | filtro semântico: Sem Uso |
| `qt_carga_horaria_ambulatorial` | NUMBER(3) | Int64 | util | - | - | 0/0 | Quantidade de Carga Horária Ambulat rial |
| `qt_carga_hor_hosp_sus` | NUMBER(4) | Int64 | util | - | - | 0/0 | Quantidade de Carga Horária Hospitala |
| `qt_carga_horaria_outros` | NUMBER(3) | Int64 | util | - | - | 0/0 | Quantidade de Carga Horária Outros |
| `co_conselho_classe` | CHAR(2) | string | descartada | - | - | 26/27 | filtro semântico: Código do Órgão Emissor |
| `nu_registro` | VARCHAR2(13) | string | descartada | - | - | 26/27 | filtro semântico: Número do Registro no Conselho Classe |
| `sg_uf_crm` | VARCHAR2(2) | string | descartada | - | - | 48/38 | filtro semântico: UF do CRM |
| `tp_preceptor` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Profissional é Preceptor Equipe (1=Sim, 2=Não) |
| `tp_residente` | CHAR(1) | category | util | - | - | 0/0 | Indica se o Profissional é Residente Equipe (1=Sim, 2=Não) |
| `nu_cnpj_det_vinc` | VARCHAR(14) | string | descartada | - | - | n/m | filtro semântico: Número do CNPJ do Empregador |
| `to_charadt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_charadt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do R torno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbDadosProfissionalSus

- **Dicionário:** `TB_DADOS_PROFISSIONAL_SUS` — Profissionais
- **Escopo:** incluida
- **Chave primária:** `co_profissional_sus`
- **Linhas medidas:** 201701: 3.917.468, 202501: 7.067.344

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_profissional_sus` | VARCHAR2(16) | string | util | sim | - | 0/0 | Código do Profissional de Saúde |
| `co_cpf` | VARCHAR2(11) | string | descartada | - | - | 0/0 | filtro semântico: CPF do Profissional |
| `no_profissional` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome do Profissional |
| `co_cns` | VARCHAR2(15) | string | descartada | - | - | 0/0 | filtro semântico: Código do Cartão Nacional de Saúde |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro] |
| `st_nmprof_cadsus` | CHAR(1) | string | descartada | - | - | 40/67 | filtro semântico: Indica se o Nome do Profissional veio do CadWeb |
| `co_nacionalidade` | VARCHAR2(3) | string | descartada | - | - | 100/100 | filtro semântico: Código de Nacionalidade |
| `co_seq_inclusao` | NUMBER(8) | string | descartada | - | - | 59/77 | filtro semântico: Código Sequencial de Inclusão |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 87/93 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal[cite: 218] |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbDialise

- **Dicionário:** `TB_DIALISE` — Diálise
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 985, 202501: 1.261

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `qt_sala_hbsag_pos` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Salas HBSAG+ |
| `qt_sala_hbsag_neg` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Salas HBSAG- |
| `qt_sala_dpi` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Salas DPI |
| `qt_sala_dpac` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Salas DPAC |
| `qt_sala_reag_pos` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Salas de Reuso HBSAG+ |
| `qt_sala_reag_neg` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Salas de Reuso HBSAG- |
| `qt_sala_rehcv` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Salas de Reuso HCV+ |
| `nu_maqh_prop` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Máquinas de Proporção |
| `nu_maqh_outr` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Outras Máquinas |
| `co_nefro_responsavel` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome do Nefrologista Responsável |
| `co_cpf_nefro` | VARCHAR2(11) | string | descartada | - | - | 0/0 | filtro semântico: CPF do Nefrologista |
| `co_cpf_diretor` | VARCHAR2(11) | string | descartada | - | - | 0/0 | filtro semântico: CPF do Diretor Responsável pelas informações |
| `no_diretor_responsavel` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome do Diretor Responsável pelas informações |
| `tp_filtro_areia` | CHAR(1) | category | util | - | - | 0/0 | Indica se faz Tratamento de Água com Filtro de Areia (1-Sim, 2-Não) |
| `tp_filtro_carvao` | CHAR(1) | category | util | - | - | 0/0 | Indica se faz Tratamento de Água com Filtro de Carvão (1-Sim, 2-Não) |
| `tp_abrandador` | CHAR(1) | category | util | - | - | 0/0 | Indica se faz Tratamento de Água com Abrandador (1-Sim, 2-Não) |
| `tp_deoinizador` | CHAR(1) | category | util | - | - | 0/0 | Indica se faz Tratamento de Água com Deionizador (1-Sim, 2-Não) |
| `tp_osmose_reversa` | CHAR(1) | category | util | - | - | 0/0 | Indica se faz Tratamento de Água com Máquina de Osmose Reversa (1-Sim, 2-Não) |
| `tp_outros_trat_agua` | CHAR(1) | category | util | - | - | 0/0 | Indica se faz Tratamento de Água com outros Tipos de Equipamento (1-Sim, 2-Não) |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbEquipe

- **Dicionário:** `TB_EQUIPE` — Equipes
- **Escopo:** incluida
- **Chave primária:** `co_municipio`
- **Linhas medidas:** 201701: 52.657, 202501: 120.722

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_municipio` | VARCHAR2(6) | category | util | sim | `tbArea` | 0/0 | Código do Município |
| `co_area` | VARCHAR2(4) | string | util | - | `tbArea` | 0/0 | Código da Área da Equipe |
| `seq_equipe` | NUMBER(8) | string | util | - | - | 0/0 | Sequencial da Equipe |
| `co_unidade` | VARCHAR2(31) | string | util | - | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `tp_equipe` | VARCHAR2(2) | category | util | - | - | 0/0 | Tipo de Equipe |
| `co_sub_tipo_equipe` | VARCHAR2(2) | string | descartada | - | - | 20/100 | filtro semântico: SubTipo de Equipe |
| `no_referencia` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome de Referência da Equipe |
| `dt_ativacao` | DATE | datetime64[ns] | util | - | - | 0/0 | Data de Ativação da Equipe |
| `dt_desativacao` | DATE | datetime64[ns] | util | - | - | 97/97 | Data de Desativação da Equipe |
| `tp_pop_assist_quilomb` | CHAR(1) | category | util | - | - | 0/0 | Atende População Quilombola (1-Sim, 2 Não) |
| `tp_pop_assist_assent` | CHAR(1) | category | util | - | - | 0/0 | Atende População Assentada (1-Sim, 2 Não) |
| `tp_pop_assist_geral` | CHAR(1) | category | util | - | - | 0/0 | Atende População Geral (1-Sim, 2-Não) |
| `tp_pop_assist_escola` | CHAR(1) | category | util | - | - | 0/0 | Atende População Escolar (1-Sim, 2-Não |
| `tp_pop_assist_pronasci` | CHAR(1) | category | util | - | - | 0/0 | Atende População Pronasci (1-Sim, 2 Não) |
| `tp_pop_assist_indigena` | CHAR(1) | category | util | - | - | 0/0 | Atende População Indígena (1-Sim, 2 Não) |
| `tp_pop_assist_ribeirinha` | CHAR(1) | category | util | - | - | 0/0 | Atende População Ribeirinha (1-Sim, 2 Não) |
| `tp_pop_assist_situacao_rua` | CHAR(1) | category | util | - | - | 1/0 | Atende População em Situação de Rua (1 Sim, 2-Não) |
| `tp_pop_assist_priv_liberdade` | CHAR(1) | category | util | - | - | 1/0 | Atende População Privada de Liberdad (1-Sim, 2-Não) |
| `tp_pop_assist_conflito_lei` | CHAR(1) | category | util | - | - | 1/0 | Atende População em Conflito com a Le (1-Sim, 2-Não) |
| `tp_pop_assist_adol_conf_lei` | CHAR(1) | category | util | - | - | 2/0 | Atende Adolescente em Conflito com a Le (1-Sim, 2-Não) |
| `co_cnes_uom` | VARCHAR2(7) | string | descartada | - | - | 100/100 | filtro semântico: CNES da UOM (Unidade Odontológic Móvel) |
| `nu_ch_amb_uom` | NUMBER | string | descartada | - | - | 0/0 | filtro semântico: Quantidade de Carga Horária da UOM |
| `cd_motivo_desativ` | VARCHAR2(2) | category | util | - | - | 97/97 | Código do Motivo de Desativação d Equipe |
| `cd_tp_desativ` | VARCHAR2(2) | category | util | - | - | 97/97 | Código do Tipo de Desativação da Equipe |
| `co_prof_sus_preceptor` | VARCHAR2(16) | string | descartada | - | - | 100/100 | filtro semântico: Código do Profissional Preceptor n equipe |
| `co_cnes_preceptor` | VARCHAR2(7) | string | descartada | - | - | 100/100 | filtro semântico: CNES no qual o Profissional está vinculad como Preceptor |
| `co_equipe` | VARCHAR(10) | string | util | - | - | 0/0 | Código da Equipe (Identificador Naciona de Equipe - INE) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `no_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 27/0 | filtro semântico: Data da Primeira entrada no Banco d Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Re torno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbEstabAtivSecundaria

- **Dicionário:** `TB_ESTAB_ATIV_SECUNDARIA` — Atividades Secundárias do Estabelecimento
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 0, 202501: 713.614

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0 | Código do Estabelecimento de Saúde |
| `co_atividade_secundaria` | VARCHAR2(3) | category | util | - | - | 0 | Código da Atividade Secundária (FK da tabela TB_ATIVIDADE) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbEstabelecimento

- **Dicionário:** `TB_ESTABELECIMENTO` — Estabelecimentos de Saúde
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 329.811, 202501: 560.166

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | - | 0/0 | Código do Estabelecimento de Saúde |
| `co_cnes` | VARCHAR2(7) | string | util | - | - | 0/0 | Código Nacional do Estabelecimento de Saúde |
| `nu_cnpj_mantenedora` | VARCHAR2(14) | string | util | - | - | 73/79 | CNPJ da Mantenedora |
| `tp_pfpj` | CHAR(1) | category | util | - | - | 0/0 | Indica se é Pessoa Física ou Jurídica |
| `nivel_dep` | CHAR(1) | category | util | - | - | 0/0 | Identificador da Situação do Estabelecimento |
| `no_razao_social` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Razão Social |
| `no_fantasia` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome Fantasia |
| `no_logradouro` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Logradouro |
| `nu_endereco` | VARCHAR2(10) | string | descartada | - | - | 0/0 | filtro semântico: Número |
| `no_complemento` | VARCHAR2(20) | string | descartada | - | - | 59/52 | filtro semântico: Complemento |
| `no_bairro` | VARCHAR2(40) | string | descartada | - | - | 0/0 | filtro semântico: Bairro |
| `co_cep` | VARCHAR2(8) | string | util | - | - | 0/0 | Código de Endereçamento Postal |
| `co_regiao_saude` | VARCHAR2(4) | category | util | - | - | 45/57 | Código da Região de Saúde |
| `co_micro_regiao` | VARCHAR2(6) | string | descartada | - | - | 96/100 | filtro semântico: Código da Microregião de Saúde |
| `co_distrito_sanitario` | VARCHAR2(4) | string | descartada | - | - | 93/93 | filtro semântico: Código do Distrito Sanitário |
| `co_distrito_administrativo` | VARCHAR2(4) | string | descartada | - | - | 99/100 | filtro semântico: Código do Módulo Assistencial |
| `nu_telefone` | VARCHAR2(13) | string | descartada | - | - | 21/23 | filtro semântico: Telefone |
| `nu_fax` | VARCHAR2(13) | string | descartada | - | - | 76/100 | filtro semântico: Fax |
| `no_email` | VARCHAR2(30) | string | descartada | - | - | 59/46 | filtro semântico: e-Mail |
| `nu_cpf` | VARCHAR2(11) | string | descartada | - | - | 64/71 | filtro semântico: CPF do Estabelecimento |
| `nu_cnpj` | VARCHAR2(14) | string | descartada | - | - | 62/49 | filtro semântico: CNPJ do Estabelecimento |
| `co_atividade` | CHAR(2) | string | descartada | - | - | 0/0 | filtro semântico: Código da Atividade de Ensino / Pesquisa |
| `co_clientela` | CHAR(2) | category | util | - | - | 2/1 | Código de Fluxo da Clientela |
| `nu_alvara` | VARCHAR2(25) | string | descartada | - | - | 32/32 | filtro semântico: Número do Alvará (Vigilância Sanitária) |
| `dt_expedicao` | DATE | string | descartada | - | - | 33/32 | filtro semântico: Data de Expedição do Alvará |
| `tp_orgao_expedidor` | CHAR(2) | string | descartada | - | - | 31/31 | filtro semântico: Órgão Expedidor (Vigilância Sanitária) |
| `dt_val_lic_sani` | DATE | string | descartada | - | - | 87/59 | filtro semântico: Data de Validade do Licenciamento Sanitário |
| `tp_lic_sani` | VARCHAR(1) | string | descartada | - | - | 87/59 | filtro semântico: Tipo do Licenciamento Sanitário |
| `tp_unidade` | CHAR(2) | category | util | - | - | 0/0 | Tipo de Estabelecimento |
| `co_turno_atendimento` | CHAR(2) | category | util | - | - | 0/0 | Código do Turno de Atendimento |
| `co_estado_gestor` | CHAR(2) | category | util | - | - | 0/0 | Sigla do Estado |
| `co_municipio_gestor` | VARCHAR2(7) | category | util | - | - | 0/0 | Código do Município |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `co_cpfdiretorcln` | VARCHAR2(11) | string | descartada | - | - | 63/8 | filtro semântico: CPF do Diretor Clínico ou Gerente |
| `reg_diretorcln` | VARCHAR2(60) | string | descartada | - | - | 75/42 | filtro semântico: Registro no Conselho de Classe |
| `st_adesao_filantrop` | CHAR(1) | string | descartada | - | - | 99/100 | filtro semântico: Indica adesão ao Prog. de Reestruturação de Hosp. Filantrópico |
| `co_motivo_desab` | VARCHAR2(2) | category | util | - | - | 91/80 | Código do Motivo de Desativação |
| `no_url` | VARCHAR2(60) | string | descartada | - | - | 99/98 | filtro semântico: Endereço URL |
| `nu_latitude` | VARCHAR2(30) | float64 | util | - | - | 99/11 | Latitude do Endereço |
| `nu_longitude` | VARCHAR2(30) | float64 | util | - | - | 99/11 | Longitude do Endereço |
| `to_chardt_atu_geoddmmyyyy` | DATE | string | descartada | - | - | 99/21 | filtro semântico: Data de atualização das Coordenadas |
| `no_usuario_geo` | VARCHAR2(60) | string | descartada | - | - | 99/21 | filtro semântico: Usuário que atualizou as Coordenadas |
| `co_natureza_jur` | VARCHAR2(4) | category | util | - | - | 0/0 | Código da Natureza Jurídica |
| `tp_estab_sempre_aberto` | CHAR(1) | category | util | - | - | 58/9 | Indica se fica sempre aberto / Ininterrupto |
| `st_geracredito_gerente_sgif` | VARCHAR(1) | string | descartada | - | - | 100/100 | filtro semântico: Indica direcionamento de crédito para Gerente no SGIF |
| `st_conexao_internet` | VARCHAR(1) | category | util | - | - | 100/7 | Possui Conexão Internet |
| `co_tipo_estabelecimento` | VARCHAR2(3) | category | util | - | - | 100/8 | Código do Tipo de Estabelecimento |
| `co_atividade_principal` | VARCHAR2(3) | category | util | - | - | 100/8 | Código da Atividade Principal |
| `st_contrato_formalizado` | VARCHAR(1) | category | util | - | - | 100/59 | Indica contrato formalizado com o SUS |
| `co_tipo_unidade` | CHAR(2) | string | descartada | - | - | 100/100 | filtro semântico: Sem Uso |
| `no_fantasia_abrev` | VARCHAR2(21) | string | descartada | - | - | 100/100 | filtro semântico: Sem Uso |
| `tp_gestao` | CHAR(1) | category | util | - | - | 0/0 | Tipo de Gestão |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 0/0 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Retorno no BPF |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |

### tbEstabHorarioAtend

- **Dicionário:** `TB_ESTAB_HORARIO_ATEND` — Horário de Funcionamento do Estabelecimento
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 684.738, 202501: 2.631.274

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_dia_semana` | NUMBER(2) | category | util | - | - | 0/0 | Código do dia da semana (1-Domingo, 2Segunda, 3-Terça, 4-Quarta, 5-Quinta, 6Sexta, 7-Sábado) |
| `hr_inicio_atendimento` | VARCHAR2(5) | string | util | - | - | 0/0 | Horário de Início de Funcionamento |
| `hr_fim_atendimento` | VARCHAR2(5) | string | util | - | - | 0/0 | Horário de Fim de Funcionamento |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbHemoterapia

- **Dicionário:** `TB_HEMOTERAPIA` — Hemoterapia
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 1.924, 202501: 2.292

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `nu_srecepcad` | NUMBER(3) | Int64 | util | - | - | 51/51 | Número de Salas de Recepção |
| `nu_striaghmt` | NUMBER(3) | Int64 | util | - | - | 57/58 | Número de Salas de Triagem Hematológica |
| `nu_striagcln` | NUMBER(3) | Int64 | util | - | - | 58/58 | Número de Salas de Triagem Clínica |
| `nu_scoleta` | NUMBER(3) | Int64 | util | - | - | 52/51 | Número de Salas de Coleta |
| `nu_saferese` | NUMBER(3) | Int64 | util | - | - | 72/71 | Número de Salas de Aférese |
| `nu_sprestoq` | NUMBER(3) | Int64 | util | - | - | 63/64 | Número de Salas de Pré-Estoque |
| `nu_sproces` | NUMBER(3) | Int64 | util | - | - | 59/59 | Número de Salas de Processamento |
| `nu_sestoque` | NUMBER(3) | Int64 | util | - | - | 48/48 | Número de Salas de Estoque |
| `nu_sdistrib` | NUMBER(3) | Int64 | util | - | - | 62/62 | Número de Salas de Distribuição |
| `nu_sorologia` | NUMBER(3) | Int64 | util | - | - | 65/65 | Número de Salas de Sorologia |
| `nu_simunohem` | NUMBER(3) | Int64 | util | - | - | 52/51 | Número de Salas de Imunohematologia |
| `nu_spretranf` | NUMBER(3) | Int64 | util | - | - | 38/40 | Número de Salas de Pré-Transfusionais |
| `nu_shemostas` | NUMBER(3) | Int64 | util | - | - | 75/73 | Número de Salas de Hemostasia |
| `nu_scontrolq` | NUMBER(3) | Int64 | util | - | - | 64/63 | Número de Salas de Controle de Qualidade |
| `nu_sbiomolec` | NUMBER(3) | Int64 | util | - | - | 77/75 | Número de Salas de Biologia Molecular |
| `nu_simunfen` | NUMBER(3) | Int64 | util | - | - | 73/71 | Número de Salas de Imunofenotipagem |
| `nu_stransfus` | NUMBER(3) | Int64 | util | - | - | 47/49 | Número de Salas de Transfusão |
| `nu_ssgdoador` | NUMBER(3) | Int64 | util | - | - | 64/65 | Número de Salas de Seguimento Doador |
| `qt_ecadrecli` | NUMBER(3) | Int64 | util | - | - | 52/52 | Quantidade de Cadeiras Reclináveis |
| `qt_ecentrefr` | NUMBER(3) | Int64 | util | - | - | 51/50 | Quantidade de Centrífugas Refrigeradas |
| `qt_erfguasng` | NUMBER(3) | Int64 | util | - | - | 17/16 | Quantidade de Refrigeradores para Guarda de Sangue |
| `qt_econgrapd` | NUMBER(3) | Int64 | util | - | - | 64/64 | Quantidade de Congeladores Rápidos |
| `qt_eextaplsm` | NUMBER(3) | Int64 | util | - | - | 64/64 | Quantidade de Extratores Automáticos de Plasma |
| `qt_efreez18` | NUMBER(3) | Int64 | util | - | - | 41/41 | Quantidade de Freezers -18◦ C |
| `qt_efreez30` | NUMBER(3) | Int64 | util | - | - | 56/53 | Quantidade de Freezers -30◦ C |
| `qt_eagitplqt` | NUMBER(3) | Int64 | util | - | - | 51/47 | Quantidade de Agitadores de Plaquetas |
| `qt_eseladora` | NUMBER(3) | Int64 | util | - | - | 52/48 | Quantidade de Seladoras |
| `qt_eirradhem` | NUMBER(3) | Int64 | util | - | - | 75/73 | Quantidade de Irradiadores de Hemocomponentes |
| `qt_eagltnosc` | NUMBER(3) | Int64 | util | - | - | 47/48 | Quantidade de Aglutinoscópios |
| `qt_emaqafres` | NUMBER(3) | Int64 | util | - | - | 70/68 | Quantidade de Máquinas de Aférese |
| `qt_erfgareag` | NUMBER(3) | Int64 | util | - | - | 25/25 | Quantidade de Refrigeradores para Guarda de Reagentes |
| `qt_erfgamsts` | NUMBER(3) | Int64 | util | - | - | 38/35 | Quantidade de Refrigeradores para Guarda de Amostras de Sangue |
| `qt_ecapfllam` | NUMBER(3) | Int64 | util | - | - | 60/59 | Quantidade de Capelas de Fluxo Laminar |
| `no_rhemot` | VARCHAR2(60) | string | descartada | - | - | 51/53 | filtro semântico: Nome do Hemoterapeuta Responsável |
| `no_rhemat` | VARCHAR2(60) | string | descartada | - | - | 63/66 | filtro semântico: Nome do Hematologista Responsável |
| `no_retecso` | VARCHAR2(60) | string | descartada | - | - | 70/72 | filtro semântico: Nome do Técnico / Sorologista Responsável |
| `no_mrcapac` | VARCHAR2(60) | string | descartada | - | - | 54/57 | filtro semântico: Nome do Médico Capacitado Responsável |
| `co_cpfmrhemot` | VARCHAR2(11) | string | descartada | - | - | 51/54 | filtro semântico: CPF do Hemoterapeuta Responsável |
| `co_cpfmrhemat` | VARCHAR2(11) | string | descartada | - | - | 63/66 | filtro semântico: CPF do Hematologista Responsável |
| `co_cpfmrtecso` | VARCHAR2(11) | string | descartada | - | - | 70/72 | filtro semântico: CPF do Técnico / Sorologista Responsável |
| `co_cpfmcapac` | VARCHAR2(11) | string | descartada | - | - | 53/57 | filtro semântico: CPF do Médico Capacitado Responsável |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbMantenedora

- **Dicionário:** `TB_MANTENEDORA` — Mantenedoras
- **Escopo:** incluida
- **Chave primária:** `nu_cnpj_mantenedora`
- **Linhas medidas:** 201701: 9.686, 202501: 9.908

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `nu_cnpj_mantenedora` | VARCHAR2(14) | string | util | sim | - | 0/0 | CNPJ da Mantenedora |
| `co_banco` | VARCHAR2(3) | category | util | - | - | 11/12 | Código do Banco |
| `nu_agencia` | VARCHAR2(5) | string | descartada | - | - | 11/12 | filtro semântico: Número da Agência |
| `nu_conta_corrente` | VARCHAR2(14) | string | descartada | - | - | 11/12 | filtro semântico: Número da Conta Corrente |
| `no_razao_social` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Razão Social da Mantenedora |
| `no_logradouro` | VARCHAR2(40) | string | descartada | - | - | 0/0 | filtro semântico: Logradouro |
| `nu_endereco` | VARCHAR2(5) | string | descartada | - | - | 0/0 | filtro semântico: Número |
| `no_complemento` | VARCHAR2(30) | string | descartada | - | - | 79/79 | filtro semântico: Complemento do Logradouro |
| `no_bairro` | VARCHAR2(30) | string | descartada | - | - | 0/0 | filtro semântico: Bairro |
| `co_cep` | VARCHAR2(8) | string | util | - | - | 0/0 | Código de Endereçamento Postal |
| `co_municipio` | VARCHAR2(7) | category | util | - | - | 0/1 | Código do Município |
| `co_regiao_saude` | VARCHAR2(4) | category | util | - | - | 22/23 | Código da Região de Saúde |
| `nu_telefone` | VARCHAR2(13) | string | descartada | - | - | 16/16 | filtro semântico: Telefone |
| `to_chardt_preenchimentoddmmyyyy` | DATE | string | descartada | - | - | 0/0 | filtro semântico: Data do Preenchimento da FCES |
| `st_fms_fes` | CHAR(1) | category | util | - | - | 1/1 | Identifica se é Fundo Municipal ou Estadual de Saúde |
| `nu_cnpj_fms_fes` | VARCHAR2(14) | string | descartada | - | - | 71/69 | filtro semântico: Número do CNPJ do Fundo |
| `co_natureza_jur` | VARCHAR2(4) | category | util | - | - | 2/2 | Código da Natureza Jurídica da Mantenedora |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `co_gestor` | VARCHAR2(7) | category | util | - | - | 0/0 | Código do Gestor |
| `co_municipio_mant` | VARCHAR2(6) | category | util | - | - | 0/0 | Código do Município da Mantenedora |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no BPF |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |

### tbProfResidencia

- **Dicionário:** `TB_PROF_RESIDENCIA` — Profissionais da Residência Terapêutica
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 4.353, 202501: 8.490

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbResidenciaMed` | 0/0 | Código do Estabelecimento de Saúde |
| `nu_residencia` | NUMBER(8) | string | util | - | `tbResidenciaMed` | 0/0 | Sequencial de Residência |
| `co_profissional_sus` | VARCHAR2(16) | string | util | - | `tbCargaHorariaSus` | 0/0 | Código do Profissional de Saúde |
| `co_cbo` | VARCHAR2(6) | category | util | - | `tbCargaHorariaSus` | 0/0 | Código Brasileiro de Ocupação |
| `ind_vinculacao` | CHAR(6) | category | util | - | - | 0/0 | Indica a vinculação, o tipo e o sub tipo de vínculo do Profissional com o Estabelecimento |
| `tp_sus_nao_sus` | CHAR(1) | category | util | - | `tbCargaHorariaSus` | 0/0 | Indica se o Profissional faz Atendimento ao SUS (S-Sim, N-Não) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR(16) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbQuimioRadio

- **Dicionário:** `TB_QUIMIO_RADIO` — Quimioterapia e Radioterapia
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 985, 202501: 1.305

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `nu_salarsimu` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Salas de Simulação - Radioterapia |
| `nu_salarplan` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Salas de Planejamento - Radioterapia |
| `co_cpfmedradm` | VARCHAR2(11) | string | descartada | - | - | 20/23 | filtro semântico: CPF do Administrador Responsável |
| `co_cpfmroncpd` | VARCHAR2(11) | string | descartada | - | - | 74/80 | filtro semântico: CPF do Oncologista Pediátrico |
| `co_cpfmrciron` | VARCHAR2(11) | string | descartada | - | - | 55/58 | filtro semântico: CPF do Cirurgião Oncologista |
| `co_cpfmr_rad` | VARCHAR2(11) | string | descartada | - | - | 70/72 | filtro semântico: CPF do Radioterapeuta |
| `co_cpfmr_fis` | VARCHAR2(11) | string | descartada | - | - | 71/73 | filtro semântico: CPF do Físico Nuclear |
| `nu_slararmfo` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Salas de Armazenamento de Fontes |
| `nu_slarconfm` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Salas de Confecção de Máscaras |
| `nu_slarmolde` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Salas de Molde |
| `nu_slarbolcp` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Salas de Bloco Personalizado |
| `nu_slaqarmaz` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Salas de Armazenagem - Quimioterapia |
| `nu_slaqprepa` | NUMBER(2) | Int64 | util | - | - | 0/0 | Quantidade de Salas de Preparo - Quimioterapia |
| `nu_slaqcdura` | NUMBER(2) | Int64 | util | - | - | 0/0 | Qtd. Salas/Equipamentos Quimio Curta Duração |
| `nu_slaqldura` | NUMBER(2) | Int64 | util | - | - | 0/0 | Qtd. Salas/Equipamentos Quimio Longa Duração |
| `nu_slacpflul` | NUMBER(2) | Int64 | util | - | - | 0/0 | Qtd. Salas/Equipamentos Capela Fluxo Laminar |
| `qt_eqrsimula` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Simuladores - Radioterapia |
| `qt_eqracell6` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Acelerador Linear até 6 MeV |
| `qt_eqr_6seme` | NUMBER(2) | Int64 | util | - | - | 1/1 | Qtd. Acelerador Linear > 6 MeV s/ elétrons |
| `qt_eqr_6come` | NUMBER(2) | Int64 | util | - | - | 1/1 | Qtd. Acelerador Linear > 6 MeV c/ elétrons |
| `qt_rortv1050` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Equipamentos Ortovoltagem 10-50 Kv |
| `qt_rorv50150` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Equipamentos Ortovoltagem 50-150 Kv |
| `qt_rov150500` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Equipamentos Ortovoltagem 150-500 Kv |
| `qt_runidcoba` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Unidade de Cobalto |
| `qt_eqrbrbaix` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Equipamentos de Braquiterapia Baixa |
| `qt_eqrbrmedi` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Equipamentos de Braquiterapia Média |
| `qt_eqrbralta` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Equipamentos de Braquiterapia Alta |
| `qt_eqrmonita` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Monitor de Área |
| `qt_eqrmoniti` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Monitor Individual |
| `qt_eqrsispln` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade de Sist. Comp. Planejamento |
| `qt_eqrdoscli` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade Dosímetro Clínico |
| `qt_eqrfonsel` | NUMBER(2) | Int64 | util | - | - | 1/1 | Quantidade Fontes Seladas |
| `no_medradm` | VARCHAR2(60) | string | descartada | - | - | 20/23 | filtro semântico: Nome do Administrador Responsável |
| `no_mroncpd` | VARCHAR2(60) | string | descartada | - | - | 74/81 | filtro semântico: Nome do Oncologista Pediátrico |
| `no_mrciron` | VARCHAR2(60) | string | descartada | - | - | 55/58 | filtro semântico: Nome do Cirurgião Oncológico |
| `no_mr_rad` | VARCHAR2(60) | string | descartada | - | - | 70/72 | filtro semântico: Nome do Radioterapeuta |
| `no_mrfis` | VARCHAR2(60) | string | descartada | - | - | 71/73 | filtro semântico: Nome do Físico Nuclear |
| `co_cpfmronc` | VARCHAR2(11) | string | descartada | - | - | 31/34 | filtro semântico: CPF do Oncologista Clínico |
| `no_mrong` | VARCHAR2(60) | string | descartada | - | - | n/m | filtro semântico: Nome do Oncologista Clínico |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no BPF |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbResidenciaMed

- **Dicionário:** `TB_RESIDENCIA_MED` — Residência Terapêutica
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 902, 202501: 1.293

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `sq_residencia` | NUMBER(6) | string | util | - | - | 0/0 | Sequencial da Residência |
| `nu_residencia` | VARCHAR2(10) | string | descartada | - | - | 0/0 | filtro semântico: Número da Residência |
| `no_referencia` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Nome de Referência da Residência |
| `no_logradouro` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Logradouro |
| `ds_complemento` | VARCHAR2(60) | string | descartada | - | - | 75/74 | filtro semântico: Complemento |
| `nu_logradouro` | VARCHAR2(10) | string | descartada | - | - | 0/0 | filtro semântico: Número do Logradouro |
| `no_bairro` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Bairro |
| `co_municipio` | VARCHAR2(6) | category | util | - | - | 0/0 | Código do Município |
| `co_cep` | VARCHAR2(8) | string | util | - | - | 0/0 | Código de Endereçamento Postal |
| `co_ddd` | VARCHAR2(3) | string | descartada | - | - | 25/28 | filtro semântico: DDD |
| `nu_telefone` | VARCHAR2(40) | string | descartada | - | - | 21/26 | filtro semântico: Número do Telefone |
| `tp_srt` | CHAR(1) | string | descartada | - | - | 18/8 | filtro semântico: Sem Uso |
| `nu_cuidadores` | NUMBER(4) | Int64 | util | - | - | 0/0 | Número de Cuidadores |
| `nu_capacidade_masc` | NUMBER(4) | Int64 | util | - | - | 0/0 | Capacidade de Residência para o Sexo Masculino |
| `nu_capacidade_fem` | NUMBER(4) | Int64 | util | - | - | 0/0 | Capacidade de Residência para o Sexo Feminino |
| `co_profissional_sus` | VARCHAR2(16) | string | descartada | - | - | 0/0 | filtro semântico: Código do Profissional de Saúde |
| `co_cbo` | VARCHAR2(6) | string | descartada | - | `tbCargaHorariaSus` | 0/0 | filtro semântico: Código Brasileiro de Ocupação |
| `tp_sus_nao_sus` | CHAR(1) | category | util | - | `tbCargaHorariaSus` | 0/0 | Indica se o Profissional faz Atendimento ao SUS (S-Sim, N-Não) |
| `ind_vinculacao` | CHAR(6) | string | descartada | - | - | 0/0 | filtro semântico: Indica a vinculação, o tipo e o sub tipo de vínculo |
| `dt_ativacao` | DATE | datetime64[ns] | util | - | - | 0/1 | Data de Ativação da Residência |
| `dt_desativacao` | DATE | datetime64[ns] | util | - | - | 97/97 | Data de Desativação da Residência |
| `st_parceria_ong` | CHAR(01) | category | util | - | - | 27/14 | Informa se possui parceria com ONG (SSim, N-Não) |
| `nu_cnpj_ong` | VARCHAR(14) | string | util | - | - | 83/75 | CNPJ da ONG |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `no_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbSegmento

- **Dicionário:** `TB_SEGMENTO` — Segmentos
- **Escopo:** incluida
- **Chave primária:** `co_municipio`
- **Linhas medidas:** 201701: 16.580, 202501: 21.170

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_municipio` | VARCHAR2(6) | category | util | sim | - | 0/0 | Código do Município |
| `co_segmento` | VARCHAR2(2) | category | util | - | - | 0/0 | Código do Segmento |
| `ds_segmento` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Descrição do Segmento |
| `tp_segmento` | CHAR(1) | category | util | - | - | 0/0 | Tipo do Segmento (1-Urbano, 2-Rural) |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `co_usuario` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 81/63 | filtro semântico: Data da primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |

### tbServicoReferenciado

- **Dicionário:** `TB_SERVICO_REFERENCIADO` — Serviço Referenciado
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Linhas medidas:** 201701: 14.320, 202501: 16.774

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | nulos | justificativa |
|---|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | 0/0 | Código do Estabelecimento de Saúde |
| `co_servico_referenciado` | CHAR(2) | category | util | - | - | 0/0 | Código do Serviço Referenciado |
| `tp_servico_referenciado` | CHAR(1) | category | util | - | - | 0/0 | Indica o Tipo de Serviço Referenciado (1Diálise, 2-Quimio/Radio, 3-Hemoterapia) |
| `co_cnpj` | VARCHAR2(14) | string | util | - | - | 0/0 | CNPJ da Unidade Referenciada |
| `no_razao_social` | VARCHAR2(60) | string | descartada | - | - | 0/0 | filtro semântico: Razão Social da Unidade Referenciada |
| `co_municipio` | VARCHAR2(6) | category | util | - | - | 0/0 | Código do Município da Unidade Referenciada |
| `co_usuario` | VARCHAR2(12) | string | descartada | - | - | 0/0 | filtro semântico: Último Usuário que atualizou o Registro |
| `to_chardt_atualizacaoddmmyyyy` | DATE | datetime64[ns] | util | - | - | 0/0 | Data da Última Atualização do Registro |
| `to_chardt_atualizacao_origemddmmyyyy` | DATE | string | descartada | - | - | 100/100 | filtro semântico: Data da Primeira entrada no Banco de Produção Federal |
| `dt_cmtp_inicio` | DATE | string | descartada | - | - | n/m | filtro semântico: Data da Primeira entrada ou Data do Retorno no Banco de Produção Federal |
| `dt_cmtp_fim` | DATE | string | descartada | - | - | n/m | filtro semântico: Data Final de Competência |
| `nu_seq_processo` | NUMBER(8) | string | descartada | - | - | n/m | filtro semântico: Número do Processo da Última Carga |
