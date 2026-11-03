# Indicadores — Câmara dos Deputados, 2025

Recorte: ano de 2025 (votações, votos e orientações por data da votação;
despesas por competência; proposições conforme o arquivo do ano).
Formato: indicador — tabelas (colunas) — o que mede. `?` = depende de decisão em aberto.

## Atividade parlamentar

1. Participação em votações nominais — votacoesVotos (idVotacao, deputado_id) + deputados (uri, nome) — votos registrados sobre as 550 votações nominais do ano; ? suplentes ficam com taxa baixa por mandato curto (o cadastro não tem datas de exercício)

2. Fidelidade à orientação da bancada — votacoesVotos (idVotacao, deputado_id, voto, deputado_siglaPartido) + votacoesOrientacoes (idVotacao, siglaBancada, orientacao) — % de votos iguais à orientação da bancada do deputado; ? siglaBancada pode ser bloco, não partido: exige regra de casamento; "Liberado" e orientação nula ficam fora

3. Coesão partidária — votacoesVotos (idVotacao, voto, deputado_siglaPartido) — % de deputados de cada partido que votaram com a maioria do próprio partido, por votação; usa o partido NO MOMENTO do voto

4. Votações apertadas — votacoes (id, votosSim, votosNao, aprovacao, siglaOrgao) — diferença entre Sim e Não nas votações nominais; quantas foram decididas por menos de 5% dos votos

5. Proposições apresentadas como proponente — proposicoesAutores (idProposicao, idDeputadoAutor, proponente = 1) + proposicoes (id, siglaTipo) + deputados (nome) — conta só o primeiro signatário; ? decidir se emendas e requerimentos entram (82 tipos)

## Cota parlamentar

6. Gasto da cota por deputado — Ano-2025 (vlrLiquido, ideCadastro, numAno) + deputados (nome) — soma do líquido por competência 2025, sem lideranças; ? mandato curto aparece com gasto baixo

7. Gasto por categoria — Ano-2025 (numSubCota, txtDescricao, vlrLiquido) — quanto cada rubrica pesa no total de R$ 240,3 mi; auxílio-moradia entra com total negativo

8. Evolução mensal do gasto — Ano-2025 (numMes, numAno, vlrLiquido) — gasto por mês de COMPETÊNCIA, não de emissão da nota

9. Gasto médio por deputado, por UF — Ano-2025 (sgUF, ideCadastro, vlrLiquido) — soma da UF dividida pelos deputados da UF que tiveram despesa; sgUF = 'NA' (lideranças) fora

10. Concentração de fornecedores — Ano-2025 (txtCNPJCPF só dígitos, txtFornecedor, vlrLiquido) — quantos fornecedores somam 80% do gasto (Pareto); CNPJ normalizado para não contar o mesmo fornecedor duas vezes

## Indicadores que o dado NÃO sustenta

- ❌ "Gasto por projeto aprovado" (eficiência do deputado) — a cota paga escritório, combustível
  e passagem, não aprovação de projeto; a razão sugere uma causa que não existe. Além disso,
  proposições de 2025 quase não viraram lei em um ano, e o crédito entre vários signatários
  não tem regra. Mostrar gasto (6) e proposições (5) lado a lado, sem dividir.
- ❌ "Gasto por partido no momento da despesa" — no Ano-2025, sgPartido é a última filiação
  do ano (dicionário), não a da data da despesa.
- ❌ "Taxa de faltas" — ausente não tem linha em votacoesVotos; só dá para contar
  participação, não ausência justificada ou não.
- ❌ "Como cada deputado votou na eleição do CNJ" — votação secreta (2576389-4):
  o voto individual é nulo por regra.