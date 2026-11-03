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
| 3 | Exploração | Tratou `sgPartido` da cota como o partido no momento da despesa. | Leitura do dicionário de dados: é a última filiação do ano. | Partido no momento do evento vem dos votos e das autorias; indicador "gasto por partido no momento" foi para a lista do que não dá para fazer. |
| 4 | Exploração | Consulta com `LIMIT 3` para mostrar três documentos repetidos mostrou o mesmo documento três vezes (faltou `DISTINCT` na CTE). | O resultado estranho (0, 0, 0) denunciou o erro de grão. | `DISTINCT` na CTE. O erro revelou o `ideDocumento = 0` (7.841 linhas de telefonia). |
| 5 | Exploração | Afirmou que um CNPJ (`085.324.290/0013-1`) tinha 13 dígitos. | Contagem de dígitos com `regexp_replace`: são 14; só a pontuação está fora do padrão. | Documento normalizado para só dígitos no refined. |
| 6 | Exploração | Comparou valores como `DOUBLE` para checar se documento − glosa = líquido. | 2.548 linhas "não fechavam" em DOUBLE contra 279 em DECIMAL: erro de ponto flutuante. | Dinheiro sempre `DECIMAL(14,2)` (regra da spec 02). |
| 7 | Spec 01 | Três erros de redação na spec da ingestão (esperas, frase e critério truncados). | Perguntas do Claude Code antes de codar. | Spec corrigida antes do código. |
| 8 | Spec 02 | O Claude Code baseou suposições numa versão antiga da spec (7.889 deputados, CPF sem máscara). | Comparação das suposições com as decisões já tomadas. | A versão nova foi salva no repo antes de codar. Lição: commitar a spec antes de pedir o código. |
| 9 | Spec 02 | O Claude Code propôs `CASE x WHEN NULL THEN ...`, que nunca casa (NULL = NULL não é verdadeiro). | Revisão da suposição pelo tutor. | Regra 7 da spec: `CASE WHEN x IS NULL ...`. |
| 10 | Spec 02 | A primeira versão da spec filtrava a dimensão `deputado` pela legislatura 57 sem checar órfãos. | Consulta de órfãos: 9 deputados na presença e 33 na autoria ficariam sem cadastro. | Opção A: dimensão = legislatura 57 + quem aparece em algum fato (690). |

## Onde a IA acertou e eu errei
| # | O que aconteceu | Como foi descoberto |
|---|---|---|
| 1 | O commit `e9e3eab` dizia que as fichas de eventos, presença e temas estavam feitas, mas elas não estavam no arquivo. | O Claude Code procurou o "número da ficha" e não achou. |
| 2 | O commit `25f6bc2` dizia "ignorar `__pycache__`", mas não alterou o `.gitignore`. | O Claude Code avisou; `Get-Content .gitignore` confirmou. |
| 3 | No DuckDB 2.0, `fetchone()` sem ler o resultado inteiro trava a conexão. | O Claude Code achou em teste com dado sintético e trocou por `fetchall()`. |

Lição: mensagem de commit não garante conteúdo. Conferir com `git show --stat` antes do push.
