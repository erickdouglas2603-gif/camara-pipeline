CONTEXTO
Estou construindo um pipeline de dados em Python sobre os dados abertos da
Câmara dos Deputados (ano de 2025). Trabalho com spec-driven development: a
spec abaixo é a fonte da verdade e o código é consequência dela. Não acrescente
requisito que não esteja escrito aqui. Se algo estiver ambíguo, pergunte antes
de escrever código.

STACK
- Python 3.11 ou superior, dependências com uv (duckdb, pandas, requests já instalados)
- DuckDB, arquivo camara.duckdb na raiz do projeto
- Nenhum orquestrador. Scripts executáveis pela linha de comando.

O QUE JÁ EXISTE
pyproject.toml, .gitignore (ignora raw/, explorar/, *.duckdb), docs/fichas.md,
docs/indicadores.md. Nenhum código ainda. A pasta raw/ ainda não existe.

ARTEFATOS A PRODUZIR, nesta ordem
0. pipeline/__init__.py vazio
1. pipeline/db.py
2. pipeline/download.py     -> uv run python -m pipeline.download
3. pipeline/ingestao.py     -> uv run python -m pipeline.ingestao
4. ui.py                    -> uv run python ui.py
download.py e ingestao.py importam apenas pipeline.db; nenhum importa o outro.
ui.py importa de pipeline.db apenas a constante CAMINHO_BANCO, e não importa
download.py nem ingestao.py.
Motivo: download e ingestão são independentes. A ingestão roda sem internet,
sempre sobre o mesmo retrato que está em raw/.

MAPA DOS ARQUIVOS (fonte da verdade para download.py e ingestao.py)
  tabela                    arquivo em raw/                       sep  compressão  URL
  ceap                      Ano-2025.csv.zip                      ;    zip         https://www.camara.leg.br/cotas/Ano-2025.csv.zip
  votacoes                  votacoes-2025.csv                     ;    nenhuma     http://dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-2025.csv
  votacoesVotos             votacoesVotos-2025.csv                ;    nenhuma     http://dadosabertos.camara.leg.br/arquivos/votacoesVotos/csv/votacoesVotos-2025.csv
  votacoesOrientacoes       votacoesOrientacoes-2025.csv          ;    nenhuma     http://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/csv/votacoesOrientacoes-2025.csv
  proposicoes               proposicoes-2025.csv                  ;    nenhuma     http://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-2025.csv
  proposicoesAutores        proposicoesAutores-2025.csv           ;    nenhuma     http://dadosabertos.camara.leg.br/arquivos/proposicoesAutores/csv/proposicoesAutores-2025.csv
  proposicoesTemas          proposicoesTemas-2025.csv             ;    nenhuma     http://dadosabertos.camara.leg.br/arquivos/proposicoesTemas/csv/proposicoesTemas-2025.csv
  deputados                 deputados.csv                         ;    nenhuma     http://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv
  eventos                   eventos-2025.csv                      ;    nenhuma     http://dadosabertos.camara.leg.br/arquivos/eventos/csv/eventos-2025.csv
  eventosPresencaDeputados  eventosPresencaDeputados-2025.csv     ;    nenhuma     http://dadosabertos.camara.leg.br/arquivos/eventosPresencaDeputados/csv/eventosPresencaDeputados-2025.csv
O separador é escrito arquivo por arquivo, mesmo sendo igual em todos.
Motivo: se a fonte mudar um arquivo, a spec diz qual era o esperado.
Este mapa fica num único lugar do código (a constante ARQUIVOS em
pipeline/db.py) e os dois scripts leem dele.
Motivo: nome de arquivo, separador e URL não podem divergir entre download e
ingestão.

SPEC DO pipeline/db.py
Expõe exatamente: PASTA_RAW, ARQUIVO_MANIFESTO (raw/_manifesto.json),
CAMINHO_BANCO (camara.duckdb na raiz), ARQUIVOS (o mapa), conectar(),
criar_schema(con, nome), gravar(con, df, schema, tabela).
D1. Caminhos resolvidos a partir da localização do próprio db.py (a pasta
    acima de pipeline/), nunca do diretório corrente.
    Motivo: rodar de outra pasta não pode criar um camara.duckdb vazio no
    lugar errado.
D2. db.py não lê arquivo, não baixa nada, não imprime nada, não converte tipo.
    Motivo: as etapas seguintes importam este arquivo; regra escondida aqui
    vale para todas sem aparecer em nenhuma spec.
D3. gravar(): CREATE OR REPLACE TABLE schema.tabela a partir do DataFrame, sem
    alterar nada; não deixa view ou tabela temporária para trás; devolve o
    count(*) lido do banco, não do DataFrame.
    Motivo: a contagem na tela tem que ser a do que foi gravado.
D4. conectar() devolve a conexão aberta, criando o arquivo se faltar; quem
    chama é quem fecha. Sem conexão global.
Critérios: importar pipeline.db não cria arquivo nenhum; gravar() com 3
linhas devolve 3, e rodar duas vezes continua devolvendo 3.

SPEC DO pipeline/download.py
B1. Baixa os 10 arquivos do mapa para raw/, com os nomes do mapa, sem
    descompactar e sem alterar o conteúdo.
B2. Tudo ou nada:
    - se raw/_tmp/ existir no início (execução interrompida), apaga antes de
      começar;
    - baixa primeiro para raw/_tmp/;
    - para no primeiro arquivo que esgotar as tentativas, sem tentar os
      seguintes; nesse caso apaga raw/_tmp/, não toca em raw/ e sys.exit(1);
    - só se os 10 baixarem, move todos para raw/ substituindo os anteriores,
      e só então grava o manifesto.
    Motivo: raw/ nunca fica com metade dos arquivos de um dia e metade de
    outro. Uma queda durante a etapa de mover não é tratada aqui: quem
    detecta é a ingestão (I7, sha256).
B3. Cada arquivo: até 3 tentativas no total, com espera de 5 e 10 segundos
    entre elas. timeout=120 do requests (inatividade de conexão e leitura, não
    duração total). Resposta diferente de 200 conta como falha.
B4. Manifesto raw/_manifesto.json, uma entrada por arquivo: tabela, arquivo,
    url, baixado_em (ISO 8601 com fuso America/Sao_Paulo), bytes, sha256.
    Motivo: os arquivos da Câmara mudam todo dia; o manifesto diz de quando é
    o retrato.
B5. Saída: uma linha por arquivo com nome e tamanho em MB; a última linha diz
    "Retrato de dd/mm/aaaa HH:MM" (horário de Brasília), com o maior
    baixado_em do manifesto. stdout reconfigurado para utf-8.

SPEC DO pipeline/ingestao.py
I1. ESCOPO: lê só raw/ (nunca a internet) e grava no schema raw, uma tabela
    por linha do mapa, com o nome da coluna "tabela".
I2. PROIBIÇÕES (a regra central): nenhuma conversão de tipo, nenhuma linha
    descartada ou deduplicada, nenhum nome de coluna alterado, nenhum valor
    corrigido. Em especial: ideDocumento = 0 continua 0; sgUF = 'NA' continua
    'NA'; vlrGlosa vazio continua nulo.
    Motivo: a fronteira entre o dado que chegou e o dado decidido é a
    passagem para refined.
I3. REEXECUÇÃO: CREATE OR REPLACE. Rodar dez vezes = rodar uma.
I4. LEITURA, com pandas:
    - encoding="utf-8-sig" declarado (aceita BOM), nunca adivinhado
    - separador e compressão do mapa, nunca inferidos
    - dtype=str: toda coluna como texto
    - keep_default_na=False e na_values=[""]: SÓ o campo vazio vira nulo.
      Motivo: com o padrão do pandas, o texto "NA" (sgUF das lideranças)
      viraria nulo em silêncio, e isso é uma correção proibida pelo I2.
    - campos entre aspas com quebra de linha dentro (descricao das votações)
      são um registro só.
I5. MANIFESTO: lê raw/_manifesto.json e grava a tabela raw._manifesto, com as
    mesmas colunas, todas VARCHAR (inclusive bytes).
    Motivo: a data do retrato precisa estar no banco para aparecer no
    dashboard; e raw não tem tipo, nem no manifesto.
I6. SAÍDA: uma linha por tabela (as 10 do mapa), nome qualificado e contagem
    vinda do banco, milhar com ponto; uma linha com o total das 10;
    raw._manifesto fica fora da contagem e do total; última linha
    "Retrato de dd/mm/aaaa HH:MM" (horário de Brasília), com o maior
    baixado_em do manifesto. stdout em utf-8.
I7. ERRO, antes de abrir o banco:
    - confere que os 10 arquivos e o manifesto existem. Faltando qualquer um:
      lista os que faltam, diz em que pasta procurou, manda rodar
      "uv run python -m pipeline.download" e sys.exit(1);
    - confere o sha256 de cada arquivo contra o manifesto. Divergência: lista
      os arquivos, manda rodar o download de novo e sys.exit(1).
      Motivo: detecta raw/ misturado por um download interrompido.
I8. TRANSAÇÃO: as 10 tabelas e o raw._manifesto são gravados numa transação
    só (BEGIN/COMMIT, ROLLBACK em qualquer erro, inclusive erro de leitura de
    um arquivo no meio).
    Motivo: ou as 11 tabelas trocam juntas, ou nenhuma troca; o schema raw
    nunca fica com tabelas de retratos diferentes.

SPEC DO ui.py
U1. Abre o banco em CAMINHO_BANCO, INSTALL ui; LOAD ui; CALL start_ui().
U2. Fica de pé até Ctrl+C, imprime a URL e "Ctrl+C para encerrar", e sai sem
    traceback.
U3. Usa CAMINHO_BANCO de pipeline.db, nunca conectar() (que cria o arquivo
    quando falta). Se o banco não existir, diz para rodar a ingestão e
    sys.exit(1).
    Motivo: um banco vazio aberto no navegador parece ingestão quebrada.
U4. stdout reconfigurado para utf-8.

CRITÉRIOS DE ACEITE
- Rodar a ingestão duas vezes seguidas imprime exatamente a mesma coisa.
- SELECT * FROM raw.ceap devolve todas as colunas como VARCHAR.
- SELECT count(*) FROM raw.ceap WHERE sgUF = 'NA' devolve mais que zero.
- SELECT count(*) FROM raw.ceap WHERE ideDocumento = '0' devolve mais que zero.
- Renomear um arquivo de raw/ faz a ingestão parar antes de gravar qualquer
  tabela.
- Alterar um byte de um arquivo de raw/ faz a ingestão parar pelo sha256.
- A ingestão funciona sem internet.
- ui.py Com camara.duckdb renomeado, ui.py para sem criar arquivo novo.
- Referência (retrato de 31/10/2026, medido na exploração com DuckDB): ceap
  209.081 · votacoesVotos 175.067 · votacoes 13.827 · votacoesOrientacoes
  4.947 · proposicoes 107.587 · proposicoesAutores 154.579 · proposicoesTemas
  40.909 · deputados 7.889 · eventos 3.225 · eventosPresencaDeputados 110.042.
  Com um download novo os números podem ser maiores (os arquivos crescem com
  lançamentos atrasados); devem ficar na mesma ordem de grandeza, nunca menores
  de forma brusca.

ENTREGA, para cada arquivo
1. A spec como docstring no topo, com o motivo de cada regra.
2. O código, comentado só onde a decisão não é óbvia.
3. Uma lista final do que você assumiu e que não estava na spec.