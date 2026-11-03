### votacoesVotos-2025
- Fonte e data: dadosabertos.camara.leg.br/arquivos/votacoesVotos, baixado em 31/10/2026
- Formato: utf-8 / separador simples / cabeçalho na 1ª linha
- Linhas: 175.067
- Grão: o voto de um deputado numa votação
- Chave: (idVotacao, deputado_id) — provada, linhas = chaves
- Cópias exatas: não testado ainda
- Liga com: votacoes por idVotacao; deputados por deputado_id
- Nulos que significam algo: 421 em `voto`, todos da votação 2576389-4 (secreta, eleição CNJ): votou, voto sigiloso
- Categorias: Sim 101.406 · Não 72.098 · Artigo 17 420 (presidente da Câmara) · Obstrução 375 · Abstenção 347
- Valores estranhos: idVotacao é texto ("2576389-4"), não número
- Datas: dataHoraVoto = hora do registro do voto, não da votação; fev a dez/2025
- Atributos que mudam: partido (14 deputados com 2+ partidos no ano); nome (2 ids com grafias diferentes)
- Perguntas em aberto:
  - Ausente não tem linha: de onde sai presença?
  - 551 deputados > 513 cadeiras: suplentes. Como tratar?
  - Artigo 17: confirmar no regimento

  ### votacoes-2025

- Fonte e data: dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-2025.csv, baixado em 31/10/2026
- Formato: utf-8 / separador simples / cabeçalho na 1ª linha
- Linhas: 13.827
- Grão: uma votação, de qualquer órgão (Plenário ou comissão), nominal ou simbólica
- Chave: id — provada (13.827 linhas = 13.827 distintos)
- Cópias exatas: nenhuma (decorre da chave única)
- Liga com:
  - votacoesVotos por id = idVotacao (1:N)
    - votos sem votação: 0 → JOIN comum a partir dos votos é seguro
    - votações sem voto: 13.277 → só 550 são nominais; JOIN comum a partir das votações perde 96%
  - proposicoes por ultimaApresentacaoProposicao_idProposicao (ver nulos: 52% com 0)
  - orgaos por idOrgao — tabela ainda não baixada
  - eventos por idEvento — tabela ainda não baixada
- Nulos que significam algo:
  - ultimaApresentacaoProposicao_idProposicao: 7.219 de 13.827 (52%) com 0, nenhum NULL real → 0 é "sem proposição" disfarçado
  - aprovacao: 107 vazias, todas no PLEN → significado desconhecido
- Categorias:
  - aprovacao: 1 (aprovada) / 0 (rejeitada) / vazio (107)
  - siglaOrgao: ~95 órgãos; PLEN é o maior (1.705 + 229 + 107); há órgãos com nome de proposição (PL233823, PEC01825) = comissões especiais

- Valores estranhos:
  - id é texto ("2576389-4"), não número → nunca converter para inteiro
  - órgão TESTECOM: 1 votação, rejeitada → cara de registro de teste
- Atributos que mudam: nenhum (não testado)
- Perguntas em aberto:
    - id_proposicao = 0, como tratar?
- Conferência: votosSim + votosNao + votosOutros = votos registrados nas 550 nominais (0 divergências; placar sem nulos, 0 de 13.827)
    
- Datas:
  - data = dia em que a votação aconteceu; 04/02 a 23/12/2025 (ano legislativo, sem recesso)
  - dataHoraRegistro = quando foi lançada no sistema; até 01/07/2026
  - 490 votações registradas em outro dia: 217 com 1 dia de atraso; 61 com mais de 60 dias (máx. 203)
  - atrasos em grupos (36 com 90 dias, 12 com 84, 11 com 203) → lançamentos em lote
  - nenhum registro antes da votação
  - → o mês da votação é o de `data`

 ### Deputados-2025

### deputados
- Fonte e data: dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv, baixado em 31/10/2026
- Formato: utf-8 / separador simples / cabeçalho na 1ª linha
- Linhas: 7.889
- Grão: uma pessoa que já exerceu mandato de deputado, de toda a história da Câmara
  - legislaturas de 1 a 57 (consulta 2)
  - ativos na legislatura 57: 648 (consulta 2)
- Chave: id extraído da `uri` (tudo depois da última "/") — provada (7.889 linhas = 7.889 ids, 0 não numéricos)
  - NÃO cortar por tamanho fixo: há ids de 5 e de 6 dígitos (ex.: 74646)
  - o id extraído é TEXTO; converter para número antes de ligar com os votos (lá é BIGINT)
- Cópias exatas: nenhuma (decorre da chave única)
- Liga com:
  - votacoesVotos por id = deputado_id (1:N)
    - deputados dos votos sem cadastro: 0 (NOT IN, válido porque o try_cast não gerou nulo)
    - deputados do cadastro sem voto em 2025: 7.338 (7.889 − 551) → histórico, esperado
- Atributos que mudam:
  - partido NÃO está no cadastro: a pessoa tem um partido em cada momento.
    O partido vem dos eventos (votos, autorias, despesas) e vale para a data do evento.
  -   - nome: os ids 230764 e 215043 têm duas grafias nos votos; no cadastro, uma só
    ("Ivan Junior", "Josivaldo JP") → o nome para exibição vem do cadastro (coluna `nome`,
    nome parlamentar), nunca dos votos; agrupar sempre por id
- Nulos que significam algo:
  - dataFalecimento nula = está vivo (informação, não falta)
  - % sem data de nascimento: 12.2 no total, 0 entre os ativos da 57 (consulta 7)
  - % sem sexo: 0 no total, 0 entre os ativos da 57 (consulta 7)
  - falecidos entre os ativos da 57: 2 (consulta 7)
- Dado pessoal:
  - cpf: vazio em 7889 no total, 648 entre os ativos da 57 (consulta 6)
  - decisão: CPF não vai para os marts (dado pessoal, nenhum indicador precisa, repositório público)
  - reavaliar ao explorar despesas: se for a única chave de ligação, usar só no refined para o JOIN
- Perguntas em aberto:
  - o refined leva os 7.889 ou só quem tem idLegislaturaFinal >= 57?
  - cpf é necessário para ligar com as despesas?

  ### Ano-2025 (despesas da cota — CEAP)
- Fonte e data: camara.leg.br/cotas/Ano-2025.csv.zip, baixado em 31/10/2026
  - dicionário: dadosabertos.camara.leg.br/howtouse/2023-12-26-dados-ceap.html
- Formato: utf-8 / separador ";" (diferente dos outros 6) / aspas " / decimal: ponto
- Linhas: 209.081
- Organização do arquivo: por ano de COMPETÊNCIA (numAno sempre 2025);
  notas emitidas de 18/02/2024 a 31/03/2026
- Grão: um lançamento na cota (valor × documento × categoria × competência)
- Chave: NÃO existe chave natural → [decidir] chave substituta no refined
  - ideDocumento repete: 10.318 docs com 2 a 6 linhas (99,2% PASSAGEM AÉREA)
  - 21 docs em 2 categorias (nota com itens de rubricas diferentes), todos de 1 deputado
  - ideDocumento = 0 → falso nulo: 7.841 linhas, 100% TELEFONIA da Câmara
  - 1 linha com ideDocumento nulo (Arthur Lira, MISSÃO OFICIAL, +61.932,80 / −61.932,80)
  - nenhuma cópia exata; conferência 201.239 + 7.841 + 1 = 209.081 ✓
- Liga com:
  - deputados por ideCadastro (N:1): 0 órfãos (NOT EXISTS)
  - ideCadastro ↔ nuDeputadoId: 1 para 1 (562) → nuDeputadoId redundante p/ pessoas
  - votos: 549 nos dois · 13 só gastaram · 2 só votaram → FULL JOIN ou partir do cadastro
- Beneficiário que não é pessoa: 937 linhas sem ideCadastro = 12 lideranças, ~R$ 1,14 mi, sgUF='NA'
- Atributos que mudam: sgPartido = última filiação NO ANO, não a da data da despesa
- Valores:
  - O GASTO = vlrLiquido (o que sai da cota). Total 2025: R$ 240.347.478,45
  - DOUBLE gera falso erro: "líquido ≠ documento − glosa" dá 2.548 em DOUBLE, 279 em DECIMAL
    → no refined, DECIMAL
  - vlrGlosa nula em 835 linhas (= as 835 com documento positivo e líquido negativo)
  - não fecham, já com coalesce e DECIMAL: 1.114 = 279 + 835
  - negativos: 7.197 em vlrDocumento (compensação de passagem); 8.032 em vlrLiquido
    → negativos ENTRAM na soma (são devolução/compensação)
  - restituição: 51 linhas, R$ 180.356,68; todas com vlrLiquido = 0
- Datas:
  - mês do gasto = numMes/numAno (competência; sempre preenchido)
  - datEmissao nula em 8.675 = 7.841 telefonia + 834 auxílio-moradia
  - 17.230 linhas com mês da nota ≠ mês da competência
- Categorias: 21 códigos (numSubCota), cada um com 1 descrição
  - top 3: DIVULGAÇÃO (R$ 102 mi, 42%), LOCAÇÃO DE VEÍCULOS (R$ 41,9 mi), ESCRITÓRIO (R$ 33,5 mi)
  - 4 categorias de passagem aérea: SIGEPA, REEMBOLSO, RPA, MISSÃO OFICIAL
  - COMPLEMENTAÇÃO DO AUXÍLIO-MORADIA: total NEGATIVO (−R$ 1,8 mi), 834 linhas sem emissão
  - indTipoDocumento 4 e 5 = NF-e (dicionário) → unificar no refined
- Fornecedores:
  - 0 sem CNPJ/CPF; 0 CNPJs falsos (00.000.000/0000-0X) em 2025
  - [pendente] contradição: tamanho estranho = 0, mas LIMIT mostrou CNPJ de 13 dígitos
  - texto livre: txtTrecho com variação ("BSB /CGH" × "BSB/CGH")
- Dado pessoal:
  - cpf do deputado preenchido em 208.144 linhas (todas exceto lideranças) → NÃO vai pro refined
    (ideCadastro já liga; dado pessoal sem necessidade)
  - txtPassageiro em 37.770 linhas: nome de terceiros → NÃO vai pros marts
- Falsos nulos: ideDocumento = 0 · sgUF = 'NA' · vlrGlosa nula
- Perguntas em aberto:
  - chave substituta: hash das colunas ou sequencial?
  - lideranças: coluna tipo_beneficiario ou fora dos marts por deputado?
  - auxílio-moradia negativo: é desconto/ajuste? fica nos totais?
  - ausência de despesa ≠ não gastou (lançamento atrasado; mandato curto)
  - [pendente] os 13 que gastaram sem votar
- Fornecedores:
  - txtCNPJCPF com pontuação inconsistente (ex.: 085.324.290/0013-1, 14 dígitos, mal formatado)
    → no refined: só dígitos; 0 com tamanho fora de 11 (CPF) ou 14 (CNPJ)
- Os 13 que gastaram sem votar: quase todos só jan–fev (1ª votação nominal: 11/02)
  → suplentes que saíram no início do ano + licenciados (resíduos de centavos, provável ramal)
- sgPartido tem 'S.PART.' (sem partido) → valor de domínio, não é partido

### proposicoes-2025
- Linhas: 107.587 · Grão: uma proposição (inclui emendas, pareceres, requerimentos: 82 tipos)
- Chave: id — provada (107.587 = 107.587)
  - (siglaTipo, numero, ano) NÃO é chave: 36.099 combinações → nunca ligar pelo "nome"
- Datas: dataApresentacao de 17/03/2003 a 16/09/2026; 59.259 (55%) com ano ≠ 2025
  - [investigar] por que um arquivo "2025" tem proposições de outros anos
- ultimoStatus_* = estado ATUAL da tramitação (retrato do dia do download, muda todo dia)
- Nulos: 2.723 sem ementa
- Liga com:
  - votacoes por ultimaApresentacaoProposicao_idProposicao (desconsiderando o 0):
    5.264 citadas, 544 (10%) fora do arquivo → LEFT JOIN, ou ingerir vários anos
  - proposicoesAutores por id = idProposicao (1:N)
- Perguntas em aberto: recorte de anos das proposições; o que o "ano" do arquivo significa

### proposicoesAutores-2025
- Linhas: 154.579 · Grão: um signatário de uma proposição
- Chave: (idProposicao, ordemAssinatura) — provada (154.579 = 154.579)
  - (idProposicao, idDeputadoAutor) NÃO é chave: 153.230 (autores não deputados têm id nulo)
- Autor não é sempre deputado: 15.162 linhas (~10%) sem idDeputadoAutor
  - 24 tipos de autor: Deputado(a), Senador(a), Executivo, comissões, Judiciário, MPU, DPU, Sociedade Civil...
- proponente: 0 | 1 (só o 1º signatário escreve a justificativa — dicionário, art. 102)
- siglaPartidoAutor = partido NO MOMENTO da assinatura
- Liga com:
  - proposicoes: 107.637 proposições aqui × 107.587 lá → 56 linhas de autoria sem proposição
  - deputados por idDeputadoAutor: 0 órfãos
- Pergunta em aberto: "autoria" no mart conta todo signatário ou só o proponente?

### votacoesOrientacoes-2025
- Linhas: 4.947 · Grão: a orientação de uma bancada numa votação
- Chave: (idVotacao, siglaBancada) — provada (4.947 = 4.947)
- 540 votações; 31 bancadas (partidos + blocos + Governo/Maioria/Minoria/Oposição)
- Órgãos: 13 (PLEN + comissões) → CONTRADIZ o dicionário ("só Plenário")
- Domínio: Sim | Não | Liberado | Obstrução | nulo (1.205 linhas, 24%)
  - [investigar] o que é orientação nula: bancada não orientou?
- Liga com:
  - votacoes: 0 votações inexistentes
  - votos: todas as 540 têm voto nominal; mas há 550 votações nominais
    → 10 votações nominais SEM orientação
- Habilita o indicador: "o deputado seguiu a orientação da bancada?"
  (cuidado: siglaBancada pode ser bloco, não partido → casar com o partido do voto exige regra)

### eventos
- Fonte e data: dadosabertos.camara.leg.br/arquivos/eventos, baixado em 31/10/2026
- Formato: utf-8 / separador `;` / cabeçalho na 1ª linha
- Linhas: 3.225
- Grão: um evento da Câmara (sessão, reunião de comissão, audiência)
- Chave: id — provada (linhas = distintos)
- Cópias exatas: nenhuma (decorre da chave única)
- Liga com:
  - eventosPresencaDeputados por id = idEvento (1:N); 2 presenças apontam para evento que não está aqui
  - votacoes por id = idEvento
- Categorias: situacao = Cancelada | Encerrada | Encerrada (Termo) | Encerrada (Final)
  → evento realizado = situacao começa com "Encerrada"
- Datas: dataHoraInicio / dataHoraFim
- Perguntas em aberto: diferença entre Encerrada, (Termo) e (Final) — tratadas igual

### eventosPresencaDeputados
- Fonte e data: dadosabertos.camara.leg.br/arquivos/eventosPresencaDeputados, baixado em 31/10/2026
- Formato: utf-8 / separador `;` / cabeçalho na 1ª linha
- Linhas: 110.042
- Grão: a presença de um deputado num evento
- Chave: (idEvento, idDeputado) — provada
- Cópias exatas: nenhuma (decorre da chave única)
- Liga com:
  - eventos por idEvento: 2 presenças sem evento cadastrado (flag no refined, não apaga)
  - deputados por idDeputado: 567 deputados; 9 fora da legislatura 57 (ex-deputados em eventos de 2025,
    provavelmente convidados de audiências)
- Valores estranhos: 116 presenças em eventos não encerrados (cancelados)
- Atenção: ausente não tem linha → dá para medir presença, não falta (taxa de faltas está em "não dá")

### proposicoesTemas
- Fonte e data: dadosabertos.camara.leg.br/arquivos/proposicoesTemas, baixado em 31/10/2026
- Formato: utf-8 / separador `;` / cabeçalho na 1ª linha
- Linhas: 40.909
- Grão: um tema de uma proposição
- Chave: (uriProposicao, codTema) — provada; id da proposição extraído da uri
- Cópias exatas: nenhuma (decorre da chave única)
- Liga com: proposicoes por id extraído de uriProposicao
- Cobertura: 19.754 proposições com tema (18% das 107.587) → indicador por tema cobre só esse recorte
- Categorias: 32 temas; até 12 temas por proposição; relevancia = 0 | 1 | 2
- Atenção: proposição com vários temas conta uma vez em cada tema → a soma por tema é maior que o total de proposições

### Correções nas fichas existentes
- votacoesVotos, votacoes, deputados: "separador simples" → "separador `;`"
- Ano-2025 (cota): remover "diferente dos outros"; "Cópias exatas: 0 (DISTINCT * = 209.081)"