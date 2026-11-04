# Spec 05 — Relatório (dashboard)

## Objetivo
Gerar `docs/relatorio.html`: um arquivo só, que abre em qualquer navegador sem servidor, com os 12 indicadores.
Comando: `python -m pipeline.relatorio`.

## Regra principal: o relatório não calcula nada
O Python **só lê e desenha**. Nada de soma, média, contagem, divisão, agrupamento ou percentil, nem no pandas
nem no Plotly: histograma e boxplot estão proibidos, porque o Plotly calcula faixa e quartil por baixo.
Permitido: ordenar, escolher as N primeiras linhas, filtrar por uma flag que o mart já traz, formatar e
renomear para exibição. Se um gráfico precisa de um número que nenhum mart tem, **o número vai para um mart novo**,
não para o Python.

## Organização
- `pipeline/relatorio.py`:
  - abre o `camara.duckdb` em `read_only=True` (o relatório não escreve no banco). Com o `ui.py` aberto, o DuckDB
    recusa até a conexão só leitura de outro processo (medido: "arquivo já está sendo usado por outro processo").
    É caso normal, não erro: avisar "feche o ui.py" e sair com `sys.exit(1)`, como nos outros scripts;
  - **uma função por gráfico**: `grafico_<nn>(df: pd.DataFrame) -> go.Figure`, sem acesso ao banco
    (recebe o DataFrame pronto). É o que permite testar com dado inventado;
  - uma função `montar_html(secoes) -> str` e o `main()`, que lê os marts, chama as funções e grava o arquivo.
- Plotly em modo autossuficiente: `include_plotlyjs="inline"` uma vez só, no primeiro gráfico (o arquivo funciona offline).
- `docs/relatorio.html` é versionado: dá para publicar no GitHub Pages.
- Dependência: `plotly`.

## Aparência
- Números no padrão brasileiro: `layout.separators = ",."` (decimal com vírgula, milhar com ponto) e `R$` no eixo do dinheiro.
- Uma seção por indicador, na ordem 1 a 12: título, uma frase dizendo o que o gráfico mostra, o gráfico e uma
  nota "Como ler" com as decisões da spec 03 que mudam a leitura (texto fixo, escrito no código).
- No topo: título, "Retrato de dd/mm/aaaa" (o `baixado_em` mais recente de `raw._manifesto`), fonte com link
  (dadosabertos.camara.leg.br) e link para o repositório.
- Cores: uma cor de destaque e cinza. Cor nunca é a única forma de passar informação: o que a cor diz também está no rótulo.

## Mart novo (adendo à spec 03)
O M05 tem grão deputado × tema × tipo. Somar por tema no Python contaria a mesma proposição várias vezes (vários proponentes),
e é cálculo. Por isso entra:

**`marts.agg_Proposicao_Tema` — `05b_proposicao_tema.sql`**. Grão: tema × grupo de tipo de proposição.
Mesmo recorte do M05 (apresentadas em 2025, autor deputado do universo, proponente).
| campo | regra |
|---|---|
| cod_tema, des_tema | |
| cod_tipo_grupo | classificado no SQL: `PL`, `RIC`, `INC` ou `Outros` (todos os demais tipos) |
| qtd_proposicoes | `count(DISTINCT id_proposicao)` no grupo |
| qtd_proposicoes_tema | distintas do tema, todos os grupos; repete nas linhas do tema e serve só para ordenar |
| qtd_deputados | `count(DISTINCT id_deputado)` no grupo |

- Grupos em vez dos 10 tipos: RIC (7.973), PL (6.415) e INC (3.097) concentram o recorte; os outros 7 tipos somam
  menos de 1.000. Com 4 grupos, o gráfico cabe em destaque + cinzas.
- Cada proposição tem um tipo só (medido: 0 com mais de um), então os grupos não se sobrepõem e as 4 barras empilhadas
  de um tema somam exatamente o `qtd_proposicoes_tema`.

Conferências novas: chave (`cod_tema`, `cod_tipo_grupo`) sem repetição e sem NULL · contagem medida e fixada (como o 564):
**122** linhas · em todo tema, `sum(qtd_proposicoes)` dos grupos = `qtd_proposicoes_tema` (0 temas divergentes).
Medido no retrato de 03/11/2026 15:49 (32 temas; a versão por tipo tinha 240 linhas).

## Os gráficos

| # | Mart | Gráfico | Detalhe |
|---|---|---|---|
| 1 | `agg_Presenca_Deputado` | Barras horizontais: os 10 com mais e os 10 com menos eventos | Duas cores para os dois grupos; nome + partido no rótulo. Desempate por `des_nome`. Nota: o corte dos 10 com menos atravessa um empate (6 deputados com 0 eventos e 5 com 1); quem não votou em 2025 aparece como "sem partido" |
| 2 | `agg_Fidelidade_Partido` | Barras horizontais por partido, ordenadas por `pct_fidelidade` | Partidos com amostra insuficiente aparecem no fim, sem barra, com o rótulo "orienta pelo bloco (cobertura X%)" |
| 3 | `agg_Coesao_Partido` | Barras horizontais, 20 partidos ordenados | `qtd_votacoes` no hover; nota sobre o REDE (amostra pequena) |
| 4 | `agg_Votacao_Apertada` | Dispersão: `data_votacao` × `pct_margem` | Plenário e comissões com símbolos diferentes (pela flag `bln_plenario` do M04); as 7 apertadas destacadas; abaixo, tabela das apertadas e das 4 contra o placar (filtro pelas flags) |
| 5 | `agg_Proposicao_Tema` | Barras horizontais por tema, empilhadas pelos 4 grupos de tipo, ordenadas por `qtd_proposicoes_tema` | PL em destaque, RIC/INC/Outros em cinzas, grupo no hover. Nota: proposição com vários temas conta em cada um; só 41% das proposições de 2025 têm tema |
| 6 | `agg_Gasto_Deputado` | Barras horizontais: os 10 maiores `vlr_media_mensal` | Total e meses com despesa no hover |
| 7 | `agg_Gasto_Categoria` | Barras horizontais, 21 subcotas por `vlr_total` | O total negativo (auxílio-moradia) aparece à esquerda do zero, com nota |
| 8 | `agg_Gasto_Mensal` | Colunas por mês de competência | Nota sobre dezembro |
| 9 | `agg_Gasto_UF` | Barras horizontais, 27 UFs por `vlr_medio_deputado_mes` | `qtd_deputados` no hover; nota sobre deputado-mês |
| 10 | `agg_Fornecedor_Pareto` | Linha: `num_posicao` × `pct_acumulado`, com linha horizontal em 80% | Eixo x em escala log; abaixo, tabela dos 15 maiores; fictícios marcados |
| 11 | `agg_Participacao_Deputado` | Barras horizontais: os 10 com menor `pct_participacao` | Período (primeiro e último voto) no hover; nota sobre a janela |
| 12 | `agg_Alinhamento_Governo` | Pontos por partido (um ponto por deputado), só amostra suficiente | Sem boxplot (calcularia quartil); nome no hover |

## Adendo: correção e layout de dashboard
Registrado antes de codar (04/11/2026).

**Bug: rótulos de valor cortados** nos gráficos 1, 6, 7 e 9. Correção: `cliponaxis=False` nos traços com rótulo e margem
direita maior. O `range` do eixo não muda: calcular um range a partir dos valores seria cálculo no Python.
No 7, o rótulo da barra negativa (auxílio-moradia) caía sobre os nomes do eixo: a parcela do total vai no nome da
categoria ("DIVULGAÇÃO… · 42,5%", nome encurtado a 40 caracteres, inteiro no hover), sem rótulo fora da barra.
Achado nos prints: no 1, os dois rankings passam a compartilhar o eixo x (com eixo próprio, 1 evento enchia a barra).

**Layout**
- Cabeçalho escuro com o título e o "Retrato de dd/mm/aaaa"; fonte e repositório continuam linkados.
- Faixa de cartões de destaque logo abaixo, lendo só o `agg_Resumo`.
- 3 abas, com JS pequeno embutido (sem biblioteca):
  **Votações**: 2, 3, 4, 11, 12 · **Atividade**: 1, 5 · **Cota**: 6, 7, 8, 9, 10. Dentro da aba, ordem numérica; a aba
  inicial é Votações. Ao trocar de aba, o JS redimensiona os gráficos (gráfico desenhado em aba escondida nasce sem largura).
- Cada gráfico num cartão (título, frase, gráfico, tabelas do 4 e do 10), em grade de 2 colunas; 1 coluna abaixo de 900 px.
- "Como ler" em `<details>` fechado.
- Barra do Plotly escondida (`displayModeBar: False`).
- Rankings com top 10: gráficos 1, 6 e 11. Os outros mostram o conjunto inteiro.

**Mart novo `marts.agg_Resumo` — `13_resumo.sql`** (adendo à spec 03). Grão: uma linha. Os valores vêm dos outros marts,
no SQL; os cartões só leem este mart.
| campo | origem |
|---|---|
| vlr_total_cota | `sum(vlr_total)` do `agg_Gasto_Categoria` |
| qtd_deputados | `bln_universo_2025` TRUE na `dim_Deputado` |
| qtd_votacoes_nominais | linhas do `agg_Votacao_Apertada` |
| qtd_votacoes_apertadas | `bln_apertada` TRUE no `agg_Votacao_Apertada` |
| qtd_fornecedores | linhas do `agg_Fornecedor_Pareto` |
| qtd_fornecedores_top80 | `bln_top_80` TRUE no `agg_Fornecedor_Pareto` |

Sem chave na lista `MARTS`: no lugar das duas verificações de chave, "exatamente 1 linha". Conferências de valor:
240.347.478,45 · 564 · 550 · 7 · 19.663 · 1.452. Total dos marts: 76 conferências.

## Testes (seguem a spec 04)
- Para cada `grafico_<nn>`: DataFrame inventado com 3 a 5 linhas → a figura tem o número esperado de traços e
  **os valores desenhados são exatamente os da coluna do mart**, na ordem esperada. Esse é o teste da regra principal:
  se alguém colocar uma conta no Python, o valor desenhado deixa de bater com o do DataFrame.
- G2: partido com `bln_amostra_suficiente` FALSE aparece com o rótulo "orienta pelo bloco".
- G12: a figura não contém traço do tipo box ou histogram.
- `montar_html`: o HTML tem 3 abas, 12 cartões de gráfico e o script do Plotly uma vez só.
- Cartões de destaque: o valor desenhado de cada cartão é o do `agg_Resumo`, só formatado (a mesma regra dos gráficos).
- O `main()` sem banco: `SystemExit(1)`, como no O9.
- Cobertura total continua ≥ 60%.

## Conferências da etapa
1. `python -m pipeline.relatorio` gera o arquivo, e ele abre no navegador sem internet.
2. Conferir no olho 3 números do relatório contra a UI do DuckDB (ex.: a coesão do NOVO, o gasto de julho, a posição do 80% no Pareto).
3. `python -m pytest` passa, com cobertura ≥ 60%.