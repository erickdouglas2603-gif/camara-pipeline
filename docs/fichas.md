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

  ### Ano-2025
- Fonte e data: dadosabertos.camara.leg.br/arquivos/deputados/csv//Ano-2025.csv, baixado em 31/10/2026
-- Formato: utf-8 / separador ";" (diferente dos outros 6 arquivos)
    -valores lidos como DOUBLE; no refined, DECIMAL (dinheiro não fica em ponto flutuante)
- Linhas: 209.081
- - Grão: um lançamento na cota (valor × documento × categoria × data)
- Chave: NÃO existe chave natural
  - ideDocumento repete: 10.318 documentos com 2 a 6 linhas (99,2% passagem aérea: remarcação/compensação)
  - 21 documentos aparecem em 2 categorias (nota com itens de rubricas diferentes); todos de 1 deputado só
  - ideDocumento = 0 → falso nulo: 7.841 linhas, 100% TELEFONIA contratada pela Câmara, sem data de emissão
  - 1 linha com ideDocumento nulo: Arthur Lira, PASSAGEM AÉREA - MISSÃO OFICIAL, vlrDocumento +61.932,80 e vlrLiquido −61.932,80
  - nenhuma cópia exata (209.081 = 209.081)
  - conferência: as partes somam o todo (189.081 docs + doc 0 + 1 nulo; 201.239 + 7.841 + 1 = 209.081 linhas)
- Pergunta em aberto: criar chave substituta no refined? (hash ou sequencial)
- Regra pra marts: contagem de documentos NÃO soma entre categorias; documento 0 fica fora de qualquer contagem de documentos
- Valores estranhos: soma em DOUBLE deu 822726.939999997 → DECIMAL no refined