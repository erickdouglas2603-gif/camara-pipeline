# Câmara dos Deputados em 2025: pipeline de dados

Pipeline em Python e DuckDB que baixa os dados abertos da Câmara dos Deputados de 2025, trata em três camadas
e entrega 12 indicadores sobre votações, atividade parlamentar e cota parlamentar.

**[Abrir o dashboard](https://erickdouglas2603-gif.github.io/camara-pipeline/docs/relatorio.html)**

Projeto final da Aula 4 da Formação em Engenharia de Dados.

## Arquitetura

```
dadosabertos.camara.leg.br
        │  download.py   10 arquivos, sha256 no manifesto
        ▼
raw        10 tabelas, 827.153 linhas, tudo texto, espelho do arquivo
        │  transformacao.py + sql/refined/   55 conferências
        ▼
refined    tipo certo, nome padronizado, falso nulo resolvido, sem CPF
        │  marts.py + sql/marts/             76 conferências
        ▼
marts      1 dimensão + 12 indicadores + 2 de apoio
        │  relatorio.py (só lê e desenha)
        ▼
docs/relatorio.html
```

- **Cada etapa só confirma se todas as conferências passarem.** Se uma falhar, a transação volta atrás e o banco fica como estava.
- **As regras de negócio moram no SQL.** O Python orquestra, e o dashboard não calcula nada.
- **Cada etapa começou por uma spec** (`docs/specs/`), escrita antes do código.

## Fonte

| | |
|---|---|
| Origem | [Portal de Dados Abertos da Câmara dos Deputados](https://dadosabertos.camara.leg.br) e arquivo da cota parlamentar (`camara.leg.br/cotas`) |
| Recorte | ano de 2025 |
| Retrato | baixado em 03/11/2026 (data e sha256 de cada arquivo em `raw/_manifesto.json`) |
| Licença | Dados públicos, divulgados pela Câmara dos Deputados no Portal de Dados Abertos para livre consulta. O portal não informa uma licença específica (verificado em 04/11/2026). |
| Tabelas | votações, votos, orientações, deputados, proposições, autores, temas, eventos, presenças e despesas da cota |

Ligações usadas (mais de duas tabelas relacionadas por chave): voto → votação → orientação; voto, despesa,
presença e autoria → deputado; autoria e tema → proposição; presença → evento.

## Grão das tabelas

### Refined
| Tabela | Uma linha é | Chave |
|---|---|---|
| `deputado` | um deputado da legislatura 57 ou que aparece em algum fato (690) | `id_deputado` |
| `votacao` | uma votação, nominal ou simbólica | `id_votacao` |
| `voto` | o voto de um deputado numa votação | `id_votacao`, `id_deputado` |
| `orientacao` | a orientação de uma bancada numa votação | `id_votacao`, `cod_bancada` |
| `proposicao` | uma proposição | `id_proposicao` |
| `autoria` | um autor de uma proposição | `id_proposicao`, `num_ordem_assinatura` |
| `tema` | um tema de uma proposição | `id_proposicao`, `cod_tema` |
| `evento` | um evento (sessão, reunião, audiência) | `id_evento` |
| `presenca` | a presença de um deputado num evento | `id_evento`, `id_deputado` |
| `despesa` | uma linha de despesa da cota | `id_despesa` (hash das colunas: não há chave natural) |
| `de_para_bancada` | uma grafia de bancada que vale para um partido (`dados/de_para_bancada.csv`) | `cod_partido`, `cod_bancada_origem` |

### Marts
| Mart | Indicador | Uma linha é |
|---|---|---|
| `dim_Deputado` | — | um deputado, com o universo de 2025 marcado (564) |
| `agg_Presenca_Deputado` | 1 · Presença em eventos | um deputado |
| `agg_Fidelidade_Partido` | 2 · Fidelidade à orientação | um partido |
| `agg_Coesao_Partido` | 3 · Coesão partidária | um partido |
| `agg_Votacao_Apertada` | 4 · Votações apertadas | uma votação nominal |
| `agg_Proposicao_Tema_Deputado` | 5 · Proposições por tema | deputado × tema × tipo |
| `agg_Proposicao_Tema` | 5 (gráfico) | tema × grupo de tipo |
| `agg_Gasto_Deputado` | 6 · Gasto por deputado | um deputado |
| `agg_Gasto_Categoria` | 7 · Gasto por categoria | uma subcota |
| `agg_Gasto_Mensal` | 8 · Gasto por mês | um mês de competência |
| `agg_Gasto_UF` | 9 · Gasto por UF | uma UF |
| `agg_Fornecedor_Pareto` | 10 · Concentração em fornecedores | um fornecedor |
| `agg_Participacao_Deputado` | 11 · Participação nas votações | um deputado |
| `agg_Alinhamento_Governo` | 12 · Alinhamento ao Governo | um deputado |
| `agg_Resumo` | cartões do dashboard | uma linha só |

As colunas de cada tabela e a regra de cada coluna estão nas specs 02 e 03.

## Como rodar

Requisitos: Python 3.11+ e [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # instala as dependências
uv run python -m pipeline.download       # baixa os 10 arquivos para raw/
uv run python -m pipeline.ingestao       # raw/ → schema raw
uv run python -m pipeline.transformacao  # raw → refined (55 conferências)
uv run python -m pipeline.marts          # refined → marts (76 conferências)
uv run python -m pipeline.relatorio      # marts → docs/relatorio.html
```

Para explorar o banco no navegador: `uv run python ui.py` (interface do DuckDB em `localhost:4213`).
Com a interface aberta, o banco fica travado para os scripts: feche antes de rodar o pipeline.

### Testes

```bash
uv run python -m pytest                       # suíte completa, exige cobertura ≥ 60%
uv run python -m pytest --no-cov -k fidelidade  # um teste isolado
```

- **49 testes, com cobertura de cerca de 75% do Python.**
- **Todos usam dado inventado e banco em memória.** A suíte passa sem o `camara.duckdb`.
- **Cada teste de regra verifica o caso que muda e o caso que não pode mudar.** Também passou pela prova de quebra: a regra foi removida, o teste falhou, e a regra foi restaurada.
- **O número de cobertura mede só o Python.** As regras de negócio estão no SQL e são protegidas pelos testes de regra (R e M da spec 04), um por regra.
- **Os `main()` do download e da ingestão não são testados**, porque dependem de rede e de arquivos reais.

## Principais achados

- **O centrão orienta pelo bloco, não pelo partido.** 11 dos 20 partidos têm orientação própria em menos de 5% dos votos. Para eles, a fidelidade fica sem valor.
- **Os partidos ideológicos votam mais unidos.** NOVO, PCdoB, PSOL e PT têm coesão acima de 98%; MDB, PRD, UNIÃO e CIDADANIA, cerca de 80%.
- **A Câmara quase nunca decide no detalhe.** Só 7 das 550 votações nominais tiveram margem menor que 5%. Outras 4 tiveram resultado contrário ao placar, como um 0 × 10 aprovado. Os dados mostram, mas não explicam: pode ser quórum qualificado ou votação em que o "Não" aprova.
- **O gasto da cota é concentrado.** 1.452 dos 19.663 fornecedores (7%) recebem 80% dos R$ 240,3 milhões. Só a TAM fica com 7,2%. Divulgação da atividade parlamentar é a maior categoria, com 42,5%.
- **O alinhamento ao Governo** é de 66,5% dos votos orientados.

## Decisões e limitações

As decisões de cada camada, com a alternativa descartada e o motivo, estão nas specs:

| Spec | Assunto |
|---|---|
| [01-ingestao](docs/specs/01-ingestao.md) | download tudo ou nada, sha256, leitura sem inferir tipo |
| [02-transformacao](docs/specs/02-transformacao.md) | tipos, falsos nulos, chave da despesa, sem CPF, dimensão que cobre os fatos |
| [03-marts](docs/specs/03-marts.md) | regra e corte de amostra de cada indicador |
| [04-testes](docs/specs/04-testes.md) | princípios e lista de testes |
| [05-relatorio](docs/specs/05-relatorio.md) | dashboard sem cálculo |

Limitações principais:
- **Presença é contagem, não taxa.** Os dados não dizem de que órgãos cada deputado é membro.
- **Ausência não tem linha.** Dá para medir participação, não falta.
- **O partido nas despesas é a última filiação do ano**, não o partido na data da despesa.
- **A composição dos blocos parlamentares não está nos dados**, e por isso a fidelidade só vale para 9 partidos.
- **O pipeline é um retrato.** As conferências têm números fixos, então um download novo faz a carga falhar de propósito, até a spec ser revisada.
- **A chave da despesa (hash) é estável dentro de um retrato.** Se a Câmara corrigir uma linha, o id dela muda.

As fichas da exploração (formato, grão, chave, nulos e valores estranhos de cada arquivo) estão em
[docs/fichas.md](docs/fichas.md), e a lista de indicadores, com o que os dados não sustentam, em
[docs/indicadores.md](docs/indicadores.md).

## Uso de IA

O projeto foi feito com IA em dois papéis: um tutor (Claude), que conduziu a exploração e redigiu as specs
a partir das minhas decisões, e o Claude Code, que gerou o código a partir das specs, listando dúvidas e
suposições antes de codar. As decisões, a execução e a conferência dos resultados foram minhas.

A IA errou, e os erros estão registrados com a forma como foram descobertos em [docs/uso-de-ia.md](docs/uso-de-ia.md).
Alguns exemplos: afirmou um separador de arquivo que não existia, escreveu regras que tratavam o NULL errado,
e chegou a escrever no dashboard uma explicação que não estava nos dados. A maior parte dos erros foi pega na etapa
de dúvidas antes do código ou por uma consulta que conferiu a afirmação.

## Melhorias futuras

- **Composição dos blocos parlamentares**, pela API da Câmara, para calcular a fidelidade dos 11 partidos que orientam pelo bloco.
- **Membros de cada órgão** (`orgaosDeputados`), para transformar presença em taxa.
- **População por UF (IBGE)**, para gasto per capita.
- **Base de CNPJ (Receita Federal)**, para o perfil dos fornecedores.
- **Dashboard:**
  - o valor do primeiro cartão estoura a borda;
  - os rótulos do eixo do gráfico 12 aparecem cortados.

## Estrutura

```
pipeline/   download, ingestao, transformacao, marts, relatorio, db
sql/        refined/ (um SELECT por tabela) e marts/ (um por indicador, grão na 1ª linha)
dados/      de_para_bancada.csv (referência criada no projeto)
tests/      pytest com dado inventado
docs/       specs, fichas, indicadores, uso de IA e o dashboard
```
