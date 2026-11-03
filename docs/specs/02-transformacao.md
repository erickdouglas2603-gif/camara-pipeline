# Spec 02 — Transformação (raw → refined)

## Objetivo
Gerar o schema `refined` no `camara.duckdb` a partir do `raw`: cada coluna com tipo certo, nome padronizado
e falso nulo resolvido. **O refined não corrige fato**: não filtra linha, não deduplica, não preenche valor.
Linha suspeita ganha flag (`bln_`), não é apagada. Quem filtra é o mart.

## Regras gerais
1. **Mesmo grão e mesma contagem da raw** em todas as tabelas. Se a contagem mudar, a carga falha.
2. **Nomes**: snake_case, sem acento, prefixo pelo tipo do campo:
   `id_` identificador · `cod_` código/sigla · `des_` texto · `tp_` tipo · `bln_` booleano ·
   `data_` data · `ts_` data e hora · `vlr_` dinheiro · `qtd_` contagem · `num_` outro número.
   Tabelas do refined: nome da entidade no singular (`refined.deputado`).
3. **Tipos**: ids numéricos `BIGINT`; id de votação `VARCHAR` (ex.: "2576389-4", nunca converter);
   dinheiro `DECIMAL(14,2)` (nunca DOUBLE); datas `DATE`; data e hora `TIMESTAMP`.
4. **Conversão falha alto**: usar `CAST`, nunca `TRY_CAST`. Valor que não converte derruba a carga.
   Os únicos valores trocados por NULL são os falsos nulos listados nesta spec, via `NULLIF`.
5. **Colunas que saem**: `cpf` (deputados e cota), `txtPassageiro` (cota) e as colunas `uri*`/`url*`
   quando o id que elas carregam já existe em outra coluna. Colunas não listadas abaixo não vão para o refined
   (continuam na raw).
6. **Id a partir de uri**: `CAST(split_part(uri, '/', -1) AS BIGINT)`. Nunca cortar por tamanho fixo.
7. Booleanos vindos de `'1'`/`'0'`: `'1'` → TRUE, `'0'` → FALSE, NULL → NULL. Qualquer outro valor: falhar.
   Não usar `CAST(x AS BOOLEAN)` (aceita 't', 'yes' etc.). Usar CASE pesquisado:
   `CASE WHEN x IS NULL THEN NULL WHEN x = '1' THEN TRUE WHEN x = '0' THEN FALSE ELSE error('...') END`.
   (`CASE x WHEN NULL` nunca casa: NULL = NULL não é verdadeiro.)
8. Falso nulo: `NULLIF` antes do `CAST`, ex.: `CAST(NULLIF(ideDocumento, '0') AS BIGINT)`.

## Organização do código
- `sql/refined/<tabela>.sql`: um arquivo por tabela, contendo só o `SELECT`.
- `pipeline/transformacao.py`: lê cada arquivo, executa `CREATE OR REPLACE TABLE refined.<tabela> AS <select>`,
  tudo numa transação única, na ordem abaixo (autoria depende de proposição; presença depende de evento).
  Depois roda as conferências; se alguma falhar, desfaz tudo e mostra qual falhou.
- Antes de conectar: se `camara.duckdb` não existir, avisar "rode a ingestão primeiro" e `sys.exit(1)`
  (sem chamar `conectar()`, que criaria o arquivo vazio). Se o banco estiver travado (ui.py aberto), avisar e sair.
- Se um `CAST` falhar: ROLLBACK, mostrar a tabela que falhou, `sys.exit(1)`.
- Ordem: deputado, votacao, voto, orientacao, proposicao, autoria, tema, evento, presenca, despesa.

## Tabelas

### refined.deputado ← raw.deputados
Grão: um deputado relevante para o projeto. Chave: `id_deputado`.
**Exceção à regra 1**: entra quem tem `idLegislaturaFinal >= 57` (648) **ou** aparece em algum fato
(`votacoesVotos.deputado_id`, `eventosPresencaDeputados.idDeputado`, `proposicoesAutores.idDeputadoAutor`,
`ceap.ideCadastro`). Regra de modelagem: a dimensão cobre todos os fatos, então nenhum JOIN perde linha.
Fora da 57 há 9 deputados na presença (ex-deputados em eventos de 2025) e 33 na autoria (proposições antigas);
pode haver sobreposição. Contagem esperada: **690** = 648 + 42 de fora da 57 (9 da presença + 33 da autoria,
sem sobreposição; voto e despesa não acrescentam ninguém; nenhum id de fato ausente de `raw.deputados`).
Medido na raw do retrato de 03/11/2026 15:49.
Decisão de escopo: o histórico desde 1826 não entra em nenhum indicador. A raw mantém os 7.889.

| origem | destino | tipo | regra |
|---|---|---|---|
| uri | id_deputado | BIGINT | regra 6 |
| nome | des_nome | VARCHAR | nome parlamentar, o nome de exibição |
| nomeCivil | des_nome_civil | VARCHAR | |
| idLegislaturaInicial | num_legislatura_inicial | INTEGER | |
| idLegislaturaFinal | num_legislatura_final | INTEGER | |
| siglaSexo | cod_sexo | VARCHAR | |
| dataNascimento | data_nascimento | DATE | |
| dataFalecimento | data_falecimento | DATE | NULL = vivo |
| ufNascimento | cod_uf_nascimento | VARCHAR | |
| municipioNascimento | des_municipio_nascimento | VARCHAR | |
| urlRedeSocial | des_url_rede_social | VARCHAR | |
| urlWebsite | des_url_website | VARCHAR | |
| (calculada) | bln_legislatura_atual | BOOLEAN | `idLegislaturaFinal >= 57`; TRUE esperado: 648. Marts de "deputados atuais" filtram por aqui |

Sai: `cpf`.

### refined.votacao ← raw.votacoes
Grão: uma votação (13.827). Chave: `id_votacao`.

| origem | destino | tipo | regra |
|---|---|---|---|
| id | id_votacao | VARCHAR | não converter |
| data | data_votacao | DATE | o mês da votação sai daqui |
| dataHoraRegistro | ts_registro | TIMESTAMP | |
| idOrgao | id_orgao | BIGINT | |
| siglaOrgao | cod_orgao | VARCHAR | |
| idEvento | id_evento | BIGINT | |
| aprovacao | bln_aprovada | BOOLEAN | regra 7; vazio (107, PLEN) fica NULL |
| votosSim | qtd_votos_sim | INTEGER | |
| votosNao | qtd_votos_nao | INTEGER | |
| votosOutros | qtd_votos_outros | INTEGER | |
| descricao | des_votacao | VARCHAR | |
| ultimaAberturaVotacao_dataHoraRegistro | ts_ultima_abertura | TIMESTAMP | |
| ultimaAberturaVotacao_descricao | des_ultima_abertura | VARCHAR | |
| ultimaApresentacaoProposicao_dataHoraRegistro | ts_ultima_apresentacao | TIMESTAMP | |
| ultimaApresentacaoProposicao_descricao | des_ultima_apresentacao | VARCHAR | |
| ultimaApresentacaoProposicao_idProposicao | id_proposicao | BIGINT | falso nulo: `0` → NULL |
| (calculada) | bln_orgao_teste | BOOLEAN | `siglaOrgao = 'TESTECOM'` |

Saem: `uri`, `uriOrgao`, `uriEvento`, `ultimaApresentacaoProposicao_uriProposicao`.

### refined.voto ← raw.votacoesVotos
Grão: o voto de um deputado numa votação (175.067). Chave: (`id_votacao`, `id_deputado`).

| origem | destino | tipo | regra |
|---|---|---|---|
| idVotacao | id_votacao | VARCHAR | |
| deputado_id | id_deputado | BIGINT | |
| dataHoraVoto | ts_voto | TIMESTAMP | hora do registro do voto |
| voto | des_voto | VARCHAR | NULL = votação secreta (421), mantém |
| deputado_nome | des_nome_deputado | VARCHAR | só rastreio; nome de exibição vem de `deputado` |
| deputado_siglaPartido | cod_partido | VARCHAR | partido no momento do voto |
| deputado_siglaUf | cod_uf | VARCHAR | |
| deputado_idLegislatura | num_legislatura | INTEGER | |
| deputado_urlFoto | des_url_foto | VARCHAR | |

Saem: `uriVotacao`, `deputado_uri`, `deputado_uriPartido`.

### refined.orientacao ← raw.votacoesOrientacoes
Grão: a orientação de uma bancada numa votação (4.947). Chave: (`id_votacao`, `cod_bancada`).

| origem | destino | tipo | regra |
|---|---|---|---|
| idVotacao | id_votacao | VARCHAR | |
| siglaOrgao | cod_orgao | VARCHAR | |
| descricao | des_votacao | VARCHAR | |
| siglaBancada | cod_bancada | VARCHAR | |
| orientacao | des_orientacao | VARCHAR | NULL (1.205) mantém |

Saem: `uriVotacao`, `uriBancada`.

### refined.proposicao ← raw.proposicoes
Grão: uma proposição (107.587). Chave: `id_proposicao`.

| origem | destino | tipo | regra |
|---|---|---|---|
| id | id_proposicao | BIGINT | |
| siglaTipo | cod_sigla_tipo | VARCHAR | ex.: PL, PEC |
| codTipo | cod_tipo | INTEGER | |
| descricaoTipo | des_tipo | VARCHAR | |
| numero | num_proposicao | INTEGER | |
| ano | num_ano | INTEGER | ano da proposição, não do arquivo |
| ementa | des_ementa | VARCHAR | |
| ementaDetalhada | des_ementa_detalhada | VARCHAR | |
| keywords | des_keywords | VARCHAR | |
| dataApresentacao | ts_apresentacao | TIMESTAMP | |
| urlInteiroTeor | des_url_inteiro_teor | VARCHAR | |
| ultimoStatus_dataHora | ts_ultimo_status | TIMESTAMP | |
| ultimoStatus_idOrgao | id_orgao_ultimo_status | BIGINT | |
| ultimoStatus_siglaOrgao | cod_orgao_ultimo_status | VARCHAR | |
| ultimoStatus_regime | des_regime | VARCHAR | |
| ultimoStatus_descricaoTramitacao | des_tramitacao | VARCHAR | |
| ultimoStatus_idSituacao | cod_situacao | INTEGER | |
| ultimoStatus_descricaoSituacao | des_situacao | VARCHAR | |
| ultimoStatus_apreciacao | des_apreciacao | VARCHAR | |

Saem: `uri`, `uriOrgaoNumerador`, `uriPropAnterior`, `uriPropPrincipal`, `uriPropPosterior`, `urnFinal`,
`ultimoStatus_sequencia`, `ultimoStatus_uriRelator`, `ultimoStatus_uriOrgao`, `ultimoStatus_idTipoTramitacao`,
`ultimoStatus_despacho`, `ultimoStatus_url`.

### refined.autoria ← raw.proposicoesAutores
Grão: um autor de uma proposição (154.579). Chave: (`id_proposicao`, `num_ordem_assinatura`).

| origem | destino | tipo | regra |
|---|---|---|---|
| idProposicao | id_proposicao | BIGINT | |
| idDeputadoAutor | id_deputado | BIGINT | NULL quando o autor não é deputado (15.162) |
| codTipoAutor | cod_tipo_autor | INTEGER | |
| tipoAutor | des_tipo_autor | VARCHAR | |
| nomeAutor | des_nome_autor | VARCHAR | |
| siglaPartidoAutor | cod_partido | VARCHAR | |
| siglaUFAutor | cod_uf | VARCHAR | |
| ordemAssinatura | num_ordem_assinatura | INTEGER | |
| proponente | bln_proponente | BOOLEAN | regra 7 |
| (calculada) | bln_proposicao_cadastrada | BOOLEAN | existe em `refined.proposicao`? (FALSE esperado: 56) |

Saem: `uriProposicao`, `uriAutor`, `uriPartidoAutor`.

### refined.tema ← raw.proposicoesTemas
Grão: um tema de uma proposição (40.909). Chave: (`id_proposicao`, `cod_tema`).

| origem | destino | tipo | regra |
|---|---|---|---|
| uriProposicao | id_proposicao | BIGINT | regra 6 |
| siglaTipo | cod_sigla_tipo | VARCHAR | |
| numero | num_proposicao | INTEGER | |
| ano | num_ano | INTEGER | |
| codTema | cod_tema | INTEGER | |
| tema | des_tema | VARCHAR | |
| relevancia | num_relevancia | INTEGER | 0, 1 ou 2 |

### refined.evento ← raw.eventos
Grão: um evento (3.225). Chave: `id_evento`.

| origem | destino | tipo | regra |
|---|---|---|---|
| id | id_evento | BIGINT | |
| dataHoraInicio | ts_inicio | TIMESTAMP | |
| dataHoraFim | ts_fim | TIMESTAMP | |
| situacao | des_situacao | VARCHAR | |
| descricao | des_evento | VARCHAR | |
| descricaoTipo | des_tipo_evento | VARCHAR | |
| localExterno | des_local_externo | VARCHAR | |
| localCamara.nome | des_local_nome | VARCHAR | |
| localCamara.predio | des_local_predio | VARCHAR | |
| localCamara.sala | des_local_sala | VARCHAR | |
| localCamara.andar | des_local_andar | VARCHAR | |
| urlDocumentoPauta | des_url_pauta | VARCHAR | |
| (calculada) | bln_realizado | BOOLEAN | `situacao LIKE 'Encerrada%'` |

Sai: `uri`.

### refined.presenca ← raw.eventosPresencaDeputados
Grão: a presença de um deputado num evento (110.042). Chave: (`id_evento`, `id_deputado`).

| origem | destino | tipo | regra |
|---|---|---|---|
| idEvento | id_evento | BIGINT | |
| idDeputado | id_deputado | BIGINT | |
| dataHoraInicio | ts_inicio_evento | TIMESTAMP | |
| (calculada) | bln_evento_cadastrado | BOOLEAN | existe em `refined.evento`? (FALSE esperado: conferir com a ficha) |

Saem: `uriEvento`, `uriDeputado`.

### refined.despesa ← raw.ceap
Grão: uma linha de despesa da cota (209.081). Não há chave natural: chave substituta `id_despesa`.

**Chave**: `md5` de todas as 32 colunas da raw (inclusive `cpf` e `txtPassageiro`, antes de saírem), na ordem
da raw, cada uma com `coalesce(coluna, '<NULL>')`, unidas por `'|'`. O coalesce é obrigatório: `concat_ws`
pula NULL, e aí `('a', NULL, 'b')` e `(NULL, 'a', 'b')` gerariam o mesmo hash.
Cópias exatas na raw: 0 (provado em 03/11/2026), então o hash é único.
Limitação: a chave é estável dentro de uma carga. Se a Câmara corrigir qualquer campo, o id da linha muda.

| origem | destino | tipo | regra |
|---|---|---|---|
| (calculada) | id_despesa | VARCHAR | ver acima |
| ideCadastro | id_deputado | BIGINT | liga com voto/deputado; NULL nas lideranças |
| nuDeputadoId | cod_deputado_cota | BIGINT | id interno da cota, 1:1 com ideCadastro |
| (calculada) | tp_beneficiario | VARCHAR | `'lideranca'` se `ideCadastro` é NULL, senão `'deputado'` |
| txNomeParlamentar | des_nome_parlamentar | VARCHAR | nas lideranças é o nome da liderança |
| nuCarteiraParlamentar | num_carteira_parlamentar | INTEGER | |
| nuLegislatura | num_legislatura | INTEGER | |
| codLegislatura | cod_legislatura | INTEGER | |
| sgUF | cod_uf | VARCHAR | falso nulo: `'NA'` → NULL |
| sgPartido | cod_partido | VARCHAR | última filiação do ano, não a da data da despesa; `'S.PART.'` mantém |
| numSubCota | cod_subcota | INTEGER | |
| txtDescricao | des_subcota | VARCHAR | |
| numEspecificacaoSubCota | cod_especificacao_subcota | INTEGER | |
| txtDescricaoEspecificacao | des_especificacao_subcota | VARCHAR | |
| txtFornecedor | des_fornecedor | VARCHAR | |
| txtCNPJCPF | cod_cnpj_fornecedor | VARCHAR | só dígitos (`regexp_replace(x, '[^0-9]', '', 'g')`); fica só se tiver 14 dígitos (CNPJ); 11 dígitos (CPF) ou vazio → NULL |
| (calculada) | tp_fornecedor | VARCHAR | pelo nº de dígitos: 14 → `'PJ'`, 11 → `'PF'`, vazio → NULL; outro tamanho: falhar |
| txtNumero | cod_documento_fiscal | VARCHAR | |
| indTipoDocumento | tp_documento | VARCHAR | valores como vieram |
| datEmissao | ts_emissao | TIMESTAMP | NULL mantém (8.675) |
| vlrDocumento | vlr_documento | DECIMAL(14,2) | |
| vlrGlosa | vlr_glosa | DECIMAL(14,2) | NULL mantém (835) |
| vlrLiquido | vlr_liquido | DECIMAL(14,2) | o valor do gasto; negativo mantém |
| vlrRestituicao | vlr_restituicao | DECIMAL(14,2) | |
| numMes | num_mes | INTEGER | |
| numAno | num_ano | INTEGER | |
| (calculada) | data_competencia | DATE | `make_date(numAno, numMes, 1)`; o mês do gasto sai daqui |
| numParcela | num_parcela | INTEGER | |
| txtTrecho | des_trecho | VARCHAR | |
| numLote | num_lote | BIGINT | |
| numRessarcimento | num_ressarcimento | BIGINT | |
| datPagamentoRestituicao | ts_pagamento_restituicao | TIMESTAMP | |
| ideDocumento | id_documento | BIGINT | falso nulo: `0` → NULL; não é chave (repete) |
| urlDocumento | des_url_documento | VARCHAR | |

Saem: `cpf`, `txtPassageiro` e o CPF de fornecedor pessoa física.
Nenhum CPF chega ao refined. O hash usa as colunas da raw, mas md5 não devolve o valor original.

## Conferências (a carga só confirma se todas passarem)
Os números são fixos de propósito: valem para o retrato registrado no manifesto. Um retrato novo faz a carga
falhar e obriga a revisar a spec (decisão consciente; projeto de retrato único).
Cada verificação atômica conta 1. Rodar todas, listar todas as que falharam, ROLLBACK e `sys.exit(1)`.

1. Contagem de cada tabela refined = contagem da raw de origem (exceto `deputado`: ver a regra da tabela).
1b. Filtrar `deputado` não pode gerar órfão: todo `id_deputado` de `voto`, `presenca`, `autoria`
    e `despesa` (quando não NULL) existe em `refined.deputado`. Esperado: 0 órfãos em cada uma.
2. Chave de cada tabela sem repetição e sem NULL.
3. `votacao`: `id_proposicao` NULL = 7.219 · `bln_aprovada` NULL = 107 · `bln_orgao_teste` TRUE = 1.
4. `voto`: `des_voto` NULL = 421, todos na votação `2576389-4`.
5. `despesa`: `tp_beneficiario = 'lideranca'` = 937 ·
   `id_documento` NULL = 7.842 (7.841 zeros + 1 NULL original) ·
   `sum(vlr_liquido)` = 240.347.478,45 · todo `cod_cnpj_fornecedor` não NULL tem 14 dígitos ·
   `tp_fornecedor = 'PF'` ⇒ `cod_cnpj_fornecedor` NULL ·
   `cod_uf` NULL = 937 (verificação separada da de liderança).
6. `autoria`: `bln_proposicao_cadastrada` FALSE = 56.
7. `presenca`: `bln_evento_cadastrado` FALSE = 2.
8. `tema`: `count(distinct id_proposicao)` = 19.754.

Saída no terminal: uma linha por tabela (nome, linhas) e "Conferências: N de N OK".

## Decisões registradas
- CPF de fornecedor pessoa física não entra no refined (dado pessoal, repositório público).
  Consequência: no indicador 10 (concentração de fornecedores), pessoa física é agrupada por `des_fornecedor`.
- `deputado`: legislatura 57 + quem aparece em algum fato (opção A). Medido: só legislatura 57 deixava
  9 deputados órfãos na presença e 33 na autoria. Descartadas a opção B (flag nos fatos, risco de JOIN errado
  no mart) e a C (os 7.889, peso morto).