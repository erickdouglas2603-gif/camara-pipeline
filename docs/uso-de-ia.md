# Uso de IA no projeto

## Como a IA foi usada
- **Tutor (Claude, chat):** conduziu a exploração, propôs consultas e indicadores, revisou decisões e
  redigiu as specs a partir das decisões tomadas por mim.
- **Implementação (Claude Code):** gerou o código a partir das specs em `docs/specs/`. Antes de codar,
  listou dúvidas e suposições, que voltaram para a spec como linhas novas.
- **Eu:** tomei as decisões (grão, chaves, tratamento de nulos, escopo), rodei os comandos e
  conferi os resultados contra os números da exploração.

Regra de trabalho: nenhuma afirmação da IA sobre os dados vale sem uma consulta que a prove.

## Onde a IA errou

| # | Etapa | O que a IA afirmou ou fez | Como foi descoberto | Correção |
|---|---|---|---|---|
| 1 | Exploração | Disse que o arquivo da cota usava um separador diferente dos outros. | `sniff_csv` nos 10 arquivos: todos usam `;`. | Fichas corrigidas: separador `;` em todos. |
| 2 | Exploração | Assumiu decimal com vírgula na cota, por ser arquivo brasileiro. | `DESCRIBE` e leitura dos valores: o decimal é ponto. | Conversão direta para `DECIMAL(14,2)`. |
| 3 | Exploração | Tratou `sgPartido` da cota como o partido no momento da despesa. | Leitura do dicionário de dados: é a última filiação do ano. | Partido no momento do evento vem dos votos; "gasto por partido no momento" foi para a lista do que não dá para fazer. |
| 4 | Exploração | Consulta com `LIMIT 3` para mostrar três documentos repetidos mostrou o mesmo documento três vezes (faltou `DISTINCT` na CTE). | O resultado estranho (0, 0, 0) denunciou o erro de grão. | `DISTINCT` na CTE. O erro revelou o `ideDocumento = 0` (7.841 linhas de telefonia). |
| 5 | Exploração | Afirmou que um CNPJ (`085.324.290/0013-1`) tinha 13 dígitos. | Contagem de dígitos com `regexp_replace`: são 14; só a pontuação está fora do padrão. | Documento normalizado para só dígitos no refined. |
| 6 | Exploração | Comparou valores como `DOUBLE` para checar se documento − glosa = líquido. | 2.548 linhas "não fechavam" em DOUBLE contra 279 em DECIMAL: erro de ponto flutuante. | Dinheiro sempre `DECIMAL(14,2)` (regra da spec 02). |
| 7 | Spec 01 | Três erros de redação na spec da ingestão (esperas, frase e critério truncados). | Perguntas do Claude Code antes de codar. | Spec corrigida antes do código. |
| 8 | Spec 02 | O Claude Code baseou suposições numa versão antiga da spec (7.889 deputados, CPF sem máscara). | Comparação das suposições com as decisões já tomadas. | A versão nova foi salva no repo antes de codar. Lição: commitar a spec antes de pedir o código. |
| 9 | Spec 02 | O Claude Code propôs `CASE x WHEN NULL THEN ...`, que nunca casa (NULL = NULL não é verdadeiro). | Revisão da suposição pelo tutor. | Regra 7 da spec: `CASE WHEN x IS NULL ...`. |
| 10 | Spec 02 | A primeira versão da spec filtrava a dimensão `deputado` pela legislatura 57 sem checar órfãos. | Consulta de órfãos: 9 deputados na presença e 33 na autoria ficariam sem cadastro. | Opção A: dimensão = legislatura 57 + quem aparece em algum fato (690). |
| 11 | Git | O tutor mandou acrescentar linhas ao `.gitignore` com `Add-Content` sem checar se o arquivo terminava com quebra de linha. `raw/` e `__pycache__/` grudaram em `raw/__pycache__/`, e a pasta `raw/` deixou de ser ignorada. | Revisão do repositório no GitHub. Nenhum dado chegou a ser versionado. | `.gitignore` reescrito com `Set-Content`; conferência com `git check-ignore raw`. |
| 12 | Marts | Esperou 26 grafias no de-para partido → bancada. São 22: as federações se repetem para cada partido. | A consulta de controle positivo devolveu 22, e a conta das 3.283 orientações casadas fechou exatamente. | Conferência da transformação: 22 grafias distintas. |
| 13 | Marts | Consulta de cobertura com `GROUP BY ALL` numa coluna que misturava agregado e não agregado. | Binder Error do DuckDB. | `GROUP BY` explícito. |
| 14 | Spec 03 | A regra "nunca dividir dinheiro em DOUBLE" era impossível: no DuckDB, divisão de DECIMAL sempre devolve DOUBLE. | Teste do Claude Code no DuckDB 2.0. | Regra reescrita: nunca guardar nem somar em DOUBLE; divisão com CAST para DECIMAL na mesma expressão. |
| 15 | Spec 03 | Escreveu "26 eventos" do Teste do Painel Eletrônico. São 73 do tipo (69 realizados); 26 é o número com presença. | Medição do Claude Code. | Texto da spec corrigido. |
| 16 | Spec 03 | Não restringiu o M05 (proposições por tema) ao universo de 2025: entrariam 31 ex-deputados, hoje em outra casa, como produção de 2025. | Pergunta do Claude Code antes de codar. | M05 com JOIN na `dim_Deputado`. |
| 17 | Spec 03 | Três números medidos (votações apertadas, top 80% de fornecedores, votos orientados pelo Governo) ficaram fora das conferências, e a contagem do M05 também. | Perguntas do Claude Code e revisão do resultado. | Viraram conferências (64 nos marts). |
| 18 | Spec 03 | A regra `bln_resultado_contra_placar` dava FALSE onde devia dar NULL e tratava os dois empates de jeitos diferentes: o 17 × 17 aprovado contava como "contra o placar"; o 6 × 6 rejeitado, não. | O NULL foi apontado pelo Claude Code; o empate apareceu na leitura do resultado do M04. | Empate é FALSE (quem decide é o desempate); conferência de 5 para 4. |

## Onde a IA acertou

| # | O que aconteceu | Como foi descoberto |
|---|---|---|
| 1 | No DuckDB 2.0, `fetchone()` sem ler o resultado inteiro trava a conexão. | O Claude Code achou em teste com dado sintético e trocou por `fetchall()`. |
| 2 | `CAST(x AS BOOLEAN)` aceita `'t'`, `'yes'` etc., então não é estrito. | O Claude Code propôs CASE com `error()` no ELSE. |
| 3 | `des_tipo_evento <> 'Teste...'` descartaria eventos de tipo NULL. | O Claude Code usou `IS DISTINCT FROM` no M01. |
| 4 | No M02 e no M03, o partido tem que ser o do momento do voto, não o da dimensão. | Suposição do Claude Code sobre uma regra ambígua da spec 03. |
| 5 | Somar valores negativos (auxílio-moradia) faz o percentual acumulado do Pareto passar de 100% e voltar. | Suposição do Claude Code no M10. |

## Onde eu errei e a IA percebeu

| # | O que aconteceu | Como foi descoberto |
|---|---|---|
| 1 | O commit `e9e3eab` dizia que as fichas de eventos, presença e temas estavam feitas, mas elas não estavam no arquivo. | O Claude Code procurou o "número da ficha" e não achou. |
| 2 | O commit `25f6bc2` dizia "ignorar `__pycache__`", mas não alterou o `.gitignore`. | O Claude Code avisou; `Get-Content .gitignore` confirmou. |
| 3 | Um `git add .` foi colado por engano dentro do `docs/indicadores.md`. | Revisão do repositório pelo tutor. |

## Lições
- **Mensagem de commit não garante conteúdo.** Conferir com `git show --stat` antes do push.
- **A armadilha do NULL apareceu cinco vezes** (`NOT IN`, `CASE WHEN NULL`, `<>` com NULL, `AND`/`OR` com NULL, `concat_ws` pulando NULL). Toda regra com comparação precisa dizer o que acontece com o NULL.
- **Um zero pode provar ou esconder.** Toda consulta que espera "0 linhas" precisa de um controle positivo, provando que o JOIN casou o que devia.
- **A pergunta antes de codar é a etapa que mais pega erro.** Dos 18 erros da tabela, 6 foram achados nas dúvidas e suposições do Claude Code, antes de existir código.