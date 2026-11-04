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
  - abre o `camara.duckdb` em `read_only=True` (o `ui.py` aberto trava a escrita, não a leitura em modo só leitura;
    se travar mesmo assim, avisar e sair, como nos outros scripts);
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

**`marts.agg_Proposicao_Tema` — `05b_proposicao_tema.sql`**. Grão: tema × tipo de proposição.
Mesmo recorte do M05 (apresentadas em 2025, autor deputado do universo, proponente).
| campo | regra |
|---|---|
| cod_tema, des_tema, cod_sigla_tipo | |
| qtd_proposicoes | `count(DISTINCT id_proposicao)` |
| qtd_deputados | `count(DISTINCT id_deputado)` |

Conferências novas: chave (`cod_tema`, `cod_sigla_tipo`) sem repetição; contagem medida e fixada (como o 564).

## Os gráficos

| # | Mart | Gráfico | Detalhe |
|---|---|---|---|
| 1 | `agg_Presenca_Deputado` | Barras horizontais: os 15 com mais e os 15 com menos eventos | Duas cores para os dois grupos; nome + partido no rótulo |
| 2 | `agg_Fidelidade_Partido` | Barras horizontais por partido, ordenadas por `pct_fidelidade` | Partidos com amostra insuficiente aparecem no fim, sem barra, com o rótulo "orienta pelo bloco (cobertura X%)" |
| 3 | `agg_Coesao_Partido` | Barras horizontais, 20 partidos ordenados | `qtd_votacoes` no hover; nota sobre o REDE (amostra pequena) |
| 4 | `agg_Votacao_Apertada` | Dispersão: `data_votacao` × `pct_margem` | Plenário e comissões com símbolos diferentes; as 7 apertadas destacadas; abaixo, tabela das apertadas e das 4 contra o placar (filtro pelas flags) |
| 5 | `agg_Proposicao_Tema` | Barras horizontais por tema, empilhadas por tipo | Nota: proposição com vários temas conta em cada um; só 18% têm tema |
| 6 | `agg_Gasto_Deputado` | Barras horizontais: os 20 maiores `vlr_media_mensal` | Total e meses com despesa no hover |
| 7 | `agg_Gasto_Categoria` | Barras horizontais, 21 subcotas por `vlr_total` | O total negativo (auxílio-moradia) aparece à esquerda do zero, com nota |
| 8 | `agg_Gasto_Mensal` | Colunas por mês de competência | Nota sobre dezembro |
| 9 | `agg_Gasto_UF` | Barras horizontais, 27 UFs por `vlr_medio_deputado_mes` | `qtd_deputados` no hover; nota sobre deputado-mês |
| 10 | `agg_Fornecedor_Pareto` | Linha: `num_posicao` × `pct_acumulado`, com linha horizontal em 80% | Eixo x em escala log; abaixo, tabela dos 15 maiores; fictícios marcados |
| 11 | `agg_Participacao_Deputado` | Barras horizontais: os 20 com menor `pct_participacao` | Período (primeiro e último voto) no hover; nota sobre a janela |
| 12 | `agg_Alinhamento_Governo` | Pontos por partido (um ponto por deputado), só amostra suficiente | Sem boxplot (calcularia quartil); nome no hover |

## Testes (seguem a spec 04)
- Para cada `grafico_<nn>`: DataFrame inventado com 3 a 5 linhas → a figura tem o número esperado de traços e
  **os valores desenhados são exatamente os da coluna do mart**, na ordem esperada. Esse é o teste da regra principal:
  se alguém colocar uma conta no Python, o valor desenhado deixa de bater com o do DataFrame.
- G2: partido com `bln_amostra_suficiente` FALSE aparece com o rótulo "orienta pelo bloco".
- G12: a figura não contém traço do tipo box ou histogram.
- `montar_html`: o HTML tem 12 seções e o script do Plotly uma vez só.
- O `main()` sem banco: `SystemExit(1)`, como no O9.
- Cobertura total continua ≥ 60%.

## Conferências da etapa
1. `python -m pipeline.relatorio` gera o arquivo, e ele abre no navegador sem internet.
2. Conferir no olho 3 números do relatório contra a UI do DuckDB (ex.: a coesão do NOVO, o gasto de julho, a posição do 80% no Pareto).
3. `python -m pytest` passa, com cobertura ≥ 60%.