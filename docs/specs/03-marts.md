# Spec 03 — Marts (refined → marts)

## Objetivo
Gerar o schema `marts` no `camara.duckdb`: um `.sql` por indicador, prontos para o dashboard.
**Regra de negócio mora aqui**: filtro, recorte, corte de amostra e classificação. O dashboard não calcula nada.

## Regras gerais
1. **Um arquivo por mart** em `sql/marts/`, contendo só o `SELECT`. A **1ª linha** é o grão:
   `-- grão: <o que é uma linha>`. As linhas seguintes de comentário explicam as decisões.
2. **Nomes das tabelas**: `dim_<Assunto>` para dimensão e `agg_<Assunto>_<Detalhe>` para indicador.
   Campos com o mesmo padrão de prefixos do refined (`id_`, `cod_`, `des_`, `qtd_`, `vlr_`, `pct_`, `bln_`...).
   Novo prefixo: `pct_` para percentual, guardado de 0 a 100 com 1 casa (`DECIMAL(5,1)`).
3. **Dinheiro** continua `DECIMAL`: nunca guardar nem somar dinheiro em DOUBLE; divisão com CAST para DECIMAL
   na mesma expressão (no DuckDB, `DECIMAL / x` devolve DOUBLE). Média de dinheiro: `DECIMAL(14,2)`.
4. **Divisão por zero** vira NULL (`NULLIF(denominador, 0)`), nunca erro e nunca zero.
5. **Grupo pequeno não vira indicador**: onde há corte de amostra, a linha continua no mart com o valor NULL
   e `bln_amostra_suficiente = FALSE`. O leitor vê que o grupo existe e por que está sem valor.
6. **Partido de um deputado nos marts**: o do **último voto em 2025** (`arg_max(cod_partido, ts_voto)`),
   calculado uma vez na `dim_Deputado`. NULL para quem não votou.

## Alteração na transformação (adendo à spec 02)
O de-para `dados/de_para_bancada.csv` (versionado; criado por nós, não é dado da Câmara) vira `refined.de_para_bancada`,
carregado pelo `pipeline/transformacao.py` antes das tabelas que dependem dele.
- Leitura com as mesmas regras da ingestão: tudo texto, UTF-8, sem inferência de tipo.
- Colunas: `cod_partido` (VARCHAR), `cod_bancada_origem` (VARCHAR). Grão: uma grafia de bancada que vale para um partido.
- Conferências novas: 27 linhas · (`cod_partido`, `cod_bancada_origem`) sem repetição · 22 `cod_bancada_origem` distintos ·
  todo `cod_partido` de `refined.voto` existe no de-para (0 faltando) · depois do JOIN com `orientacao`,
  (`id_votacao`, `cod_partido`) não repete (0 colisões) · JOIN casa 3.283 orientações.

## Organização do código
- O nome da tabela não sai do nome do arquivo (`00_dim_deputado.sql` → `dim_Deputado`): `pipeline/marts.py` tem uma lista
  explícita (arquivo, tabela, chave). Verifica que a ordem da lista segue a numeração dos arquivos e que nenhum `.sql`
  de `sql/marts/` ficou fora dela.
- `sql/marts/<nn>_<nome>.sql`; `pipeline/marts.py` executa `CREATE OR REPLACE TABLE marts.<tabela> AS <select>`
  numa transação, em ordem numérica (a `dim_Deputado`, arquivo `00`, vem primeiro), roda as conferências
  e segue o mesmo padrão do `transformacao.py`: banco ausente ou travado → avisa e sai; falha → ROLLBACK,
  lista as falhas, `sys.exit(1)`; saída com uma linha por tabela e "Conferências: N de N OK".
- Lógica em `construir(con)`, sem BEGIN/COMMIT, testável num banco em memória (aula 4).

## Números a medir antes de codar
Assim como no 690 da spec 02: medir na base, escrever aqui e só depois codar.
Medido no retrato de 03/11/2026 15:49 (raw/refined no `camara.duckdb`).
- [x] Deputados no universo de 2025 (`dim_Deputado.bln_universo_2025 = TRUE`): **564**
  (573 dos 690 exerceram em 2025; 9 deles são de fora da 57).
- [x] Votações apertadas (M04): **7** das 550 (3 do PLEN). Nenhuma margem entre 4,95 e 5: arredondar
  `pct_margem` para 1 casa antes do corte não muda o número.
- [x] Fornecedores que somam 80% do gasto (M10): **1.452** de 19.663 chaves (raiz/CNPJ fictício/nome PF),
  incluindo o que cruza a linha.
- [x] Votos orientados pelo Governo dentro das regras (M12): **129.694** (86.259 alinhados), somando os
  deputados do universo. Sem o filtro de universo dá o mesmo número; nenhum voto secreto (NULL) cai em
  votação com orientação do Governo.

---

## M00 · `marts.dim_Deputado` — `00_dim_deputado.sql`
Grão: um deputado do `refined.deputado` (690).

| campo | regra |
|---|---|
| id_deputado, des_nome, bln_legislatura_atual | do refined |
| cod_partido | partido do último voto em 2025 (regra 6) |
| cod_uf | UF do último voto em 2025 |
| bln_exerceu_2025 | aparece em `voto`, `presenca` ou `despesa` (com `tp_beneficiario = 'deputado'`) |
| bln_universo_2025 | `bln_legislatura_atual AND bln_exerceu_2025` |

**Decisão:** o universo dos indicadores por deputado (M01, M06, M11, M12) é `bln_universo_2025`. Os 648 da legislatura 57
incluem suplentes que só exerceram em 2023–2024; com eles no universo, entrariam com zero em tudo sem ter faltado a nada.
Os 42 de fora da 57 (ex-deputados em eventos, autores antigos) também ficam fora.

## M01 · `marts.agg_Presenca_Deputado` — `01_presenca_deputado.sql`
Grão: um deputado do universo de 2025.

| campo | regra |
|---|---|
| id_deputado, des_nome, cod_partido, cod_uf | da `dim_Deputado` |
| qtd_eventos_presente | eventos distintos com presença, com `bln_realizado` e `des_tipo_evento <> 'Teste do Painel Eletrônico'` |

- Parte da dimensão com LEFT JOIN: deputado sem presença aparece com 0, não some.
- Todos os tipos de evento contam igual, exceto o teste do painel (73 eventos do tipo, 69 realizados, 26 com presença):
  é teste de equipamento, como o TESTECOM.
- É contagem, não taxa: o denominador exigiria saber de que órgãos o deputado é membro (limitação no README).

## M02 · `marts.agg_Fidelidade_Partido` — `02_fidelidade_partido.sql`
Grão: um partido que aparece nos votos (20).

Ligação: `voto.cod_partido` → `de_para_bancada` → `orientacao.cod_bancada` (mesma votação).
| campo | regra |
|---|---|
| cod_partido | |
| qtd_votos | todos os votos do partido em 2025 |
| qtd_votos_orientados | votos com orientação `Sim`/`Não`/`Obstrução` e voto diferente de `Artigo 17` |
| qtd_votos_fieis | dos orientados, voto = orientação |
| pct_cobertura | orientados / votos |
| bln_amostra_suficiente | `pct_cobertura >= 20` |
| pct_fidelidade | fiéis / orientados; NULL se a amostra é insuficiente |

- Fora: orientação `Liberado` (não há o que seguir), orientação NULL (a bancada não orientou), voto `Artigo 17` (presidente).
- Fiel é **voto igual à orientação**, sem exceção. `Obstrução` + `Não` é infiel: obstrução tira o deputado do quórum,
  e votar `Não` conta para o quórum, ajudando a votação a acontecer (confirmar no Regimento Interno e citar no README).
- Abstenção contra `Sim`/`Não`/`Obstrução` é infiel.
- Corte de 20%: fica no buraco natural entre 4,3% (SOLIDARIEDADE) e 22,5% (PSB). Os 11 partidos abaixo dele
  orientam pelo bloco, cuja composição não está nos dados.

## M03 · `marts.agg_Coesao_Partido` — `03_coesao_partido.sql`
Grão: um partido (os que têm pelo menos um grupo válido).

1. Grupo = (votação, partido), contando votos `Sim`, `Não`, `Obstrução` e `Abstenção` (a abstenção é uma posição).
2. Coesão do grupo = votos na opção mais votada / total do grupo. O empate entra: 5 × 5 dá 50%, e a conta não precisa saber qual opção venceu.
3. Só grupos com **3 ou mais deputados**. Com 1 deputado, a coesão é 100% por definição, não por união (1.004 grupos);
   com 2, só pode dar 50% ou 100%.
4. Coesão do partido = média simples das coesões dos grupos (cada votação pesa igual).

| campo | regra |
|---|---|
| cod_partido | |
| qtd_votacoes | grupos válidos do partido |
| pct_coesao_media | média do item 4 |

## M04 · `marts.agg_Votacao_Apertada` — `04_votacao_apertada.sql`
Grão: uma votação nominal (550): placar `qtd_votos_sim + qtd_votos_nao + qtd_votos_outros > 0` e `NOT bln_orgao_teste`.

| campo | regra |
|---|---|
| id_votacao, data_votacao, cod_orgao, qtd_votos_sim, qtd_votos_nao, qtd_votos_outros, bln_aprovada | do refined |
| pct_margem | `abs(sim − não) / (sim + não)`; NULL se sim + não = 0 |
| bln_apertada | `pct_margem < 5` |
| bln_resultado_contra_placar | `(bln_aprovada AND não > sim) OR (NOT bln_aprovada AND sim > não)`; NULL se `bln_aprovada` é NULL; empate é FALSE (quem decide é o desempate) |

- Todos os órgãos entram. A margem é proporcional, então numa comissão de 10 votos só o empate é apertado.
- Achado: 2 votações com mais Sim foram rejeitadas (quórum qualificado) e 2 com mais Não foram aprovadas.
  Os 2 empates (um aprovado, 2220819-82 na CE com 17 × 17, e um rejeitado) não contam.
  A flag deixa o dashboard mostrar isso sem calcular.

## M05 · `marts.agg_Proposicao_Tema_Deputado` — `05_proposicao_tema_deputado.sql`
Grão: deputado × tema × tipo de proposição.

Recorte: proposições **apresentadas em 2025** (`num_ano = 2025`), autor deputado (`id_deputado` não NULL) e proponente (`bln_proponente`),
e autor no universo de 2025 (JOIN com `dim_Deputado` onde `bln_universo_2025`). Sem esse JOIN entrariam 31 ex-deputados
hoje em outra casa (391 proposições de 2025, 3 deles com tema): autoria de senador não é produção de deputado de 2025.
| campo | regra |
|---|---|
| id_deputado, des_nome | |
| cod_tema, des_tema | |
| cod_sigla_tipo | o tipo fica como coluna: o dashboard filtra (PL × requerimento de informação × indicação...) |
| qtd_proposicoes | `count(DISTINCT id_proposicao)` |

- `num_ano = 2025` porque o indicador é **autoria**: uma proposição de 2009 que tramitou em 2025 não é produção de 2025
  de quem a apresentou em 2009.
- Proposição com vários proponentes conta para cada um, e com vários temas conta em cada tema.
  **A soma do mart é maior que o total de proposições, por construção** (README).
- Só 18% das proposições têm tema; emenda e requerimento quase nunca têm.

## M06 · `marts.agg_Gasto_Deputado` — `06_gasto_deputado.sql`
Grão: um deputado do universo de 2025.

| campo | regra |
|---|---|
| id_deputado, des_nome, cod_partido, cod_uf | da `dim_Deputado` |
| vlr_total | soma de `vlr_liquido` (0 se não teve despesa) |
| qtd_meses_com_despesa | `count(DISTINCT data_competencia)` |
| vlr_media_mensal | total / meses; NULL se 0 meses |

- Lideranças fora (não são deputados). A média mensal é a comparação justa entre mandato inteiro e suplência curta.

## M07 · `marts.agg_Gasto_Categoria` — `07_gasto_categoria.sql`
Grão: uma subcota (21).

| campo | regra |
|---|---|
| cod_subcota, des_subcota | 1 para 1, provado |
| qtd_despesas | linhas |
| vlr_total | soma de `vlr_liquido` |
| pct_total | sobre o total geral |

- **Lideranças entram**: o indicador é sobre o total da cota (R$ 240,3 mi). Auxílio-moradia entra com total negativo.

## M08 · `marts.agg_Gasto_Mensal` — `08_gasto_mensal.sql`
Grão: um mês de competência (12).

| campo | regra |
|---|---|
| data_competencia | |
| qtd_despesas, vlr_total | |

- Dezembro **fica**. Tem menos linhas (10.792), mas o valor (R$ 18,2 mi) é igual ao dos meses vizinhos: os dados
  não mostram que ele esteja incompleto. Cortar tiraria R$ 18 mi e o M08 deixaria de bater com o M07. Nota no README:
  notas emitidas até mar/2026 entram por competência; um retrato novo pode mudar dezembro.

## M09 · `marts.agg_Gasto_UF` — `09_gasto_uf.sql`
Grão: uma UF (27).

| campo | regra |
|---|---|
| cod_uf | |
| qtd_deputados | deputados com despesa na UF |
| qtd_deputado_meses | soma, por deputado, dos meses com despesa |
| vlr_total | |
| vlr_medio_deputado_mes | total / deputado-meses |

- Divide por **deputado-mês**, não por deputado: SP tem 78 deputados com despesa para 70 cadeiras, AP tem 14 para 8.
  Dividir por deputado pune a UF que teve troca de mandato. Lideranças fora (não têm UF).

## M10 · `marts.agg_Fornecedor_Pareto` — `10_fornecedor_pareto.sql`
Grão: um fornecedor.

Chave do fornecedor (`cod_fornecedor`):
- PJ com CNPJ real → **raiz** (8 primeiros dígitos). O indicador é concentração em empresas: pelo CNPJ completo,
  a Telefônica (19 filiais) vira 19 fornecedores pequenos e some do Pareto.
- CNPJ que começa com `00000000` → **CNPJ completo** e `bln_cnpj_ficticio = TRUE`. São códigos internos
  (Celular Funcional, Ramal, Linha Direta), um software (Adobe) e um nome de pessoa. Na raiz, virariam uma empresa
  `00000000` que não existe, com R$ 1,4 mi.
- PF → `des_fornecedor` (não há CPF no refined, por decisão da spec 02).

| campo | regra |
|---|---|
| cod_fornecedor | regra acima |
| tp_fornecedor | PJ / PF |
| bln_cnpj_ficticio | |
| des_fornecedor | nome mais frequente da chave |
| qtd_despesas, vlr_total | |
| num_posicao | ordem por `vlr_total` decrescente (desempate por `cod_fornecedor`) |
| pct_acumulado | soma acumulada / total geral |
| bln_top_80 | o fornecedor está entre os que somam os primeiros 80% (inclui o que cruza a linha) |

- Lideranças entram (concentração do gasto total).

## M11 · `marts.agg_Participacao_Deputado` — `11_participacao_deputado.sql`
Grão: um deputado do universo de 2025.

Base: **só as nominais do Plenário** (`cod_orgao = 'PLEN'`, 429). Deputado só vota em comissão de que é membro,
e quem é membro de qual comissão não está nos dados.
| campo | regra |
|---|---|
| id_deputado, des_nome, cod_partido, cod_uf | |
| data_primeiro_voto, data_ultimo_voto | menor e maior `data_votacao` em que ele votou no Plenário |
| qtd_votacoes_no_periodo | nominais do Plenário entre as duas datas (inclusive) |
| qtd_votos_registrados | votos dele nessas votações (qualquer valor, inclusive `Artigo 17` e o voto secreto) |
| pct_participacao | registrados / no período |

- A janela entre o primeiro e o último voto não cobra do suplente as votações de antes da posse.
  Limitação: quem saiu e voltou fica com a janela inteira. Quem não votou no Plenário tem as datas e o pct NULL.

## M12 · `marts.agg_Alinhamento_Governo` — `12_alinhamento_governo.sql`
Grão: um deputado do universo de 2025.

Orientação: a linha `cod_bancada = 'Governo'` da votação. Mesmas regras do M02: entram `Sim`/`Não`/`Obstrução`;
ficam fora `Liberado`, NULL e voto `Artigo 17`; alinhado = voto igual à orientação.
| campo | regra |
|---|---|
| id_deputado, des_nome, cod_partido, cod_uf | |
| qtd_votos_orientados, qtd_votos_alinhados | |
| bln_amostra_suficiente | `qtd_votos_orientados >= 30` |
| pct_alinhamento | alinhados / orientados; NULL se a amostra é insuficiente |

- Corte de 30 votos: regra de bolso para não ranquear suplente com 4 votos (README).

---

## Conferências (a carga só confirma se todas passarem)
Mesmo padrão da spec 02: números fixos do retrato, cada verificação atômica conta 1.

1. Cada mart tem chave (o grão) sem repetição e sem NULL.
2. Contagens: `dim_Deputado` 690 · M02 20 · M04 550 (429 do PLEN) · M05 15.223 · M07 21 · M08 12 · M09 27 ·
   M01, M06, M11, M12 = universo de 2025 (564).
3. Somas que têm que bater com o refined:
   M06 `sum(vlr_total)` = 239.208.957,97 (total − lideranças) · M07 = M08 = M10 = 240.347.478,45 · M09 = 239.208.957,97.
4. M02: `sum(qtd_votos)` = 175.067 · `sum(qtd_votos_orientados)` = 32.179 · `sum(qtd_votos_fieis)` = 30.770 ·
   `bln_amostra_suficiente` TRUE = 9.
5. M03: soma de `qtd_votacoes` = 8.212 (grupos com 3 ou mais deputados).
6. M04: `bln_resultado_contra_placar` TRUE = 4 · `bln_apertada` TRUE = 7.
7. M07: `sum(pct_total)` entre 99,9 e 100,1 (arredondamento).
8. M10: último `pct_acumulado` = 100,0 · `bln_cnpj_ficticio` TRUE = 5 chaves · `bln_top_80` TRUE = 1.452.
9. M11: `pct_participacao` entre 0 e 100 · `qtd_votos_registrados <= qtd_votacoes_no_periodo`.
10. Nenhum mart por deputado (M01, M05, M06, M11, M12) tem `id_deputado` fora do universo de 2025.
11. M12: `sum(qtd_votos_orientados)` = 129.694 · `sum(qtd_votos_alinhados)` = 86.259.

## Decisões registradas
| # | Decisão | Alternativa descartada |
|---|---|---|
| Universo | Legislatura 57 **e** algum fato em 2025 | Os 648 (suplentes de 2023–24 com zero) |
| M01 | Todos os tipos de evento, menos o teste do painel | Separar por tipo |
| M02 | Fiel = igual; corte de 20% de cobertura | Aceitar `Obstrução` + `Não`; sem corte |
| M03 | Mínimo de 3 deputados; empate entra; abstenção conta | Mínimo de 1 (1.004 grupos com 100% automático) |
| M04 | Todos os órgãos; margem sobre Sim + Não; corte de 5% | Só Plenário |
| M05 | Apresentadas em 2025; tipo como coluna | Todos os anos; todos os tipos somados |
| M08 | Mantém dezembro, com nota | Cortar dezembro |
| M09 | Deputado-mês | Deputado; cadeiras (CSV de fora) |
| M10 | Raiz; fictícios com CNPJ completo e flag | CNPJ completo para todos |
| M11 | Plenário; janela do primeiro ao último voto | Ano inteiro; todos os órgãos |
| M12 | Regras do M02; mínimo de 30 votos | Sem corte |