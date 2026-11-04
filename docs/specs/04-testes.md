# Spec 04 — Testes (pytest)

## Objetivo
Provar com `pytest` que as regras do pipeline fazem o que as specs dizem, com cobertura de pelo menos 60%
do código Python em `pipeline/`.

## Princípios (valem para todos os testes)
1. **Dado inventado, banco em memória.** `duckdb.connect()` sem caminho. Nenhum teste lê o `camara.duckdb`,
   a pasta `raw/` ou a internet. Exceção: `dados/de_para_bancada.csv`, que é dado de referência versionado.
2. **O SQL testado é o de verdade**: o teste lê `sql/refined/*.sql` e `sql/marts/*.sql`, nunca uma cópia.
3. **Arrange, Act, Assert**, com comentário marcando as três partes.
4. **O caso que muda e o caso que não pode mudar.** Toda regra é testada com a linha que ela transforma
   e com uma linha que ela tem que deixar intacta (ex.: `'NA'` vira NULL **e** `'SP'` continua `'SP'`).
5. **Um teste, uma regra.** O nome diz qual: `test_<tabela>_<regra>`. Quando o teste falha, o nome já explica o quê.
6. **Todo teste tem que conseguir falhar.** Antes de dar o teste por pronto, remover a regra do SQL ou do código,
   ver o teste falhar e desfazer. As provas feitas vão para a descrição do PR.
7. O teste existente `tests/test_despesa_uf.py` é o modelo e continua passando (pode passar a usar o `conftest.py`).

## Infraestrutura
- Dependência de desenvolvimento: `pytest-cov`.
- `tests/conftest.py`:
  - fixture `con`: conexão em memória com o schema `raw` e as 10 tabelas da raw criadas **vazias**, todas as colunas
    VARCHAR e na ordem real (a lista de colunas fica escrita no conftest, copiada uma vez do `information_schema`
    do banco real);
  - `inserir(con, tabela, linhas: list[dict])`: coluna que a linha não informa entra NULL;
  - `rodar(con, camada, nome)`: lê o `.sql` do projeto e cria a tabela no schema da camada.
- Os testes de marts montam a raw inventada e passam pelo refined de verdade (raw → refined → marts), para
  que um mart nunca seja testado em cima de um refined que não existiria.
- Comando: `python -m pytest`. O `pyproject.toml` tem, em `[tool.pytest.ini_options]`,
  `addopts = "--cov=pipeline --cov-report=term-missing --cov-fail-under=60"`: a cobertura é medida e cobrada
  em toda execução, e abaixo de 60% o pytest falha. (`--cov-fail-under` sozinho não faz nada sem `--cov`.)
- Teste isolado roda com `--no-cov` (ex.: `python -m pytest --no-cov -k despesa`): sem ele, rodar um teste só
  falha por cobertura, porque o resto de `pipeline/` não foi executado.

## Testes

### Refined
| # | Teste | Muda | Não pode mudar |
|---|---|---|---|
| R1 | `despesa`: UF `'NA'` vira NULL (já existe) | `'NA'` → NULL | `'SP'` → `'SP'`; NULL na raw continua NULL (o campo vazio do CSV já chega NULL da ingestão) |
| R2 | `despesa`: hash com coalesce | `('a', NULL, 'b')` e `(NULL, 'a', 'b')` geram ids diferentes | a mesma linha gera sempre o mesmo id |
| R3 | `despesa`: documento do fornecedor | 14 dígitos pontuados → `PJ` com CNPJ só dígitos; 11 dígitos → `PF` com `cod_cnpj_fornecedor` NULL | nenhuma coluna do resultado contém o CPF inventado |
| R4 | `despesa`: documento com 13 dígitos | a carga falha (`error()`) | — |
| R5 | `despesa`: falsos nulos e beneficiário | `ideDocumento '0'` → NULL; sem `ideCadastro` → `lideranca` | `ideDocumento '123'` → 123; com `ideCadastro` → `deputado` |
| R6 | `despesa`: dinheiro exato | `'0.10'` + `'0.20'` somam exatamente `0.30` (DECIMAL) | — |
| R7 | `votacao`: booleano estrito | `'1'` → TRUE, `'0'` → FALSE, NULL → NULL | `'x'` derruba a carga |
| R8 | `votacao`: id e falsos nulos | `idProposicao '0'` → NULL; `TESTECOM` → `bln_orgao_teste` | id `"2576389-4"` continua texto igual |
| R9 | `deputado`: dimensão cobre os fatos | legislatura 50 **com** presença entra, com `bln_legislatura_atual` FALSE | legislatura 50 **sem** fato não entra; legislatura 57 entra; ids de 5 e de 6 dígitos extraídos da uri |
| R10 | `evento`: realizado | `Encerrada (Termo)` → TRUE | `Cancelada` → FALSE |

### Marts
| # | Teste | Muda | Não pode mudar |
|---|---|---|---|
| M1 | `dim_Deputado`: universo | legislatura 57 com despesa → no universo | legislatura 57 sem nenhum fato → fora |
| M2 | `agg_Fidelidade_Partido`: regra de fiel | `Obstrução` + `Não` é infiel; PCdoB casa com `Fdr PT-PCdoB-PV` | `Liberado`, NULL e `Artigo 17` ficam fora da conta |
| M3 | `agg_Fidelidade_Partido`: corte de 20% | cobertura abaixo de 20 → `pct_fidelidade` NULL e `bln_amostra_suficiente` FALSE | o partido continua no mart |
| M4 | `agg_Coesao_Partido`: grupos | empate 2 × 2 dá 50% | grupo com 2 deputados fica fora |
| M5 | `agg_Votacao_Apertada`: contra o placar | aprovada com mais Não → TRUE; `bln_aprovada` NULL → NULL | empate aprovado → FALSE; empate rejeitado → FALSE |
| M6 | `agg_Fornecedor_Pareto`: chave | 2 filiais da mesma raiz viram 1 fornecedor | 2 CNPJs `00000000...` continuam 2 fornecedores, com `bln_cnpj_ficticio` |
| M7 | `agg_Participacao_Deputado`: janela | suplente que votou só no fim do ano tem denominador só do período | votação de comissão não entra no denominador |

### Orquestração e leitura
| # | Teste | O que prova |
|---|---|---|
| O1 | `transformar(con)` com raw inventada | cria as 11 tabelas do refined e devolve as conferências; com dado inventado as conferências de número fixo falham e voltam como lista de mensagens, sem exceção |
| O2 | `transformar(con)` com um booleano inválido | levanta `FalhaTabela` com o nome da tabela |
| O3 | `construir(con)` depois do `transformar` | cria os 15 marts (13 da spec 03 + `agg_Proposicao_Tema` e `agg_Resumo` da spec 05) |
| O4 | `marts.conferir_lista()` | devolve lista vazia para o repositório como está |
| O5 | `db.criar_schema` e `db.gravar` | grava um DataFrame e devolve o número de linhas |
| O6 | `ingestao._ler` com um CSV inventado em `tmp_path` | `'NA'` continua `'NA'` (é o `keep_default_na=False`) e campo vazio vira NULL |
| O7 | `ingestao._sha256` | o hash de um arquivo inventado bate com o `hashlib` |
| O8 | `download._baixar` com `_tentar` falhando 2 vezes | tenta 3 vezes e chama a espera com 5 e 10 s (`time.sleep` substituído por monkeypatch, sem esperar de verdade) |
| O9 | `main()` da transformação e dos marts sem banco | `CAMINHO_BANCO` apontado para um arquivo inexistente em `tmp_path` → `SystemExit(1)`, e nenhum arquivo criado |
| O10 | `ingestao._conferir_arquivos` com um arquivo faltando (`PASTA_RAW` e `ARQUIVO_MANIFESTO` em `tmp_path`) | `SystemExit(1)` e a mensagem cita o arquivo que falta e manda rodar o download |
| O11 | `ingestao._conferir_arquivos` com um byte alterado | `SystemExit(1)` pelo sha256, citando o arquivo divergente; com tudo íntegro, devolve o manifesto |
| O12 | `download._tentar` com `requests.get` substituído | resposta 404 → `FalhaDownload`; resposta 200 → grava o conteúdo e devolve bytes e sha256 iguais aos do `hashlib` |
| O13 | `main()` da transformação com banco em `tmp_path` e raw inventada | as conferências de número fixo falham → ROLLBACK, `SystemExit(1)`, e o schema `refined` não fica no banco |
| O14 | `main()` dos marts com banco em `tmp_path` (raw e refined montados) | conferências falham → ROLLBACK, `SystemExit(1)`, e o schema `marts` não fica com tabela nenhuma |

O10 a O14 entraram depois da primeira leitura: só com O1 a O9 a cobertura estimada ficava em 50–55%, abaixo da meta.

## Conferências da etapa
1. `python -m pytest` passa sem nenhum teste pulado.
2. Cobertura de `pipeline/` ≥ 60%.
3. Nenhum teste toca `camara.duckdb`, `raw/` ou rede (conferir: renomear o `camara.duckdb` e rodar a suíte; tem que passar).
4. A prova de quebra (princípio 6) está feita e registrada no PR para R1, R3, M2 e M5.

## Limitação a registrar no README
A cobertura mede só o Python. As regras de negócio estão no SQL, que o `coverage` não enxerga: elas são protegidas
pelos testes R e M, um por regra, e não pelo número de cobertura.