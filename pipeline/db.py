"""Constantes e acesso ao DuckDB compartilhados pelo pipeline.

Spec: docs/specs/01-ingestao.md, seção "SPEC DO pipeline/db.py".

Expõe exatamente: PASTA_RAW, ARQUIVO_MANIFESTO (raw/_manifesto.json),
CAMINHO_BANCO (camara.duckdb na raiz), ARQUIVOS (o mapa), conectar(),
criar_schema(con, nome), gravar(con, df, schema, tabela).

MAPA DOS ARQUIVOS (ARQUIVOS)
    Fica só aqui; download.py e ingestao.py leem desta constante.
    Motivo: nome de arquivo, separador e URL não podem divergir entre download
    e ingestão.
    O separador é escrito arquivo por arquivo, mesmo sendo igual em todos.
    Motivo: se a fonte mudar um arquivo, a spec diz qual era o esperado.

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
"""

from pathlib import Path

import duckdb
import pandas as pd

# D1: raiz do projeto = pasta acima de pipeline/.
_RAIZ = Path(__file__).resolve().parent.parent

PASTA_RAW = _RAIZ / "raw"
ARQUIVO_MANIFESTO = PASTA_RAW / "_manifesto.json"
CAMINHO_BANCO = _RAIZ / "camara.duckdb"

# Chave = nome da tabela no schema raw. compressao: "zip" ou None ("nenhuma").
ARQUIVOS = {
    "ceap": {
        "arquivo": "Ano-2025.csv.zip",
        "sep": ";",
        "compressao": "zip",
        "url": "https://www.camara.leg.br/cotas/Ano-2025.csv.zip",
    },
    "votacoes": {
        "arquivo": "votacoes-2025.csv",
        "sep": ";",
        "compressao": None,
        "url": "http://dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-2025.csv",
    },
    "votacoesVotos": {
        "arquivo": "votacoesVotos-2025.csv",
        "sep": ";",
        "compressao": None,
        "url": "http://dadosabertos.camara.leg.br/arquivos/votacoesVotos/csv/votacoesVotos-2025.csv",
    },
    "votacoesOrientacoes": {
        "arquivo": "votacoesOrientacoes-2025.csv",
        "sep": ";",
        "compressao": None,
        "url": "http://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/csv/votacoesOrientacoes-2025.csv",
    },
    "proposicoes": {
        "arquivo": "proposicoes-2025.csv",
        "sep": ";",
        "compressao": None,
        "url": "http://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-2025.csv",
    },
    "proposicoesAutores": {
        "arquivo": "proposicoesAutores-2025.csv",
        "sep": ";",
        "compressao": None,
        "url": "http://dadosabertos.camara.leg.br/arquivos/proposicoesAutores/csv/proposicoesAutores-2025.csv",
    },
    "proposicoesTemas": {
        "arquivo": "proposicoesTemas-2025.csv",
        "sep": ";",
        "compressao": None,
        "url": "http://dadosabertos.camara.leg.br/arquivos/proposicoesTemas/csv/proposicoesTemas-2025.csv",
    },
    "deputados": {
        "arquivo": "deputados.csv",
        "sep": ";",
        "compressao": None,
        "url": "http://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv",
    },
    "eventos": {
        "arquivo": "eventos-2025.csv",
        "sep": ";",
        "compressao": None,
        "url": "http://dadosabertos.camara.leg.br/arquivos/eventos/csv/eventos-2025.csv",
    },
    "eventosPresencaDeputados": {
        "arquivo": "eventosPresencaDeputados-2025.csv",
        "sep": ";",
        "compressao": None,
        "url": "http://dadosabertos.camara.leg.br/arquivos/eventosPresencaDeputados/csv/eventosPresencaDeputados-2025.csv",
    },
}


def _ident(nome: str) -> str:
    # Aspas duplas: preserva o nome exatamente (ex.: "_manifesto", camelCase).
    return '"' + nome.replace('"', '""') + '"'


def conectar() -> duckdb.DuckDBPyConnection:
    """D4: devolve a conexão aberta (cria o arquivo se faltar). Quem chama fecha."""
    return duckdb.connect(str(CAMINHO_BANCO))


def criar_schema(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {_ident(nome)}")


def gravar(
    con: duckdb.DuckDBPyConnection, df: pd.DataFrame, schema: str, tabela: str
) -> int:
    """D3: CREATE OR REPLACE TABLE schema.tabela com o df, sem alterar nada.

    Devolve o count(*) lido do banco.
    """
    destino = f"{_ident(schema)}.{_ident(tabela)}"
    # View registrada só durante o CREATE; o finally garante que não fica
    # para trás nem quando o CREATE falha (D3).
    visao = f"_gravar_{tabela}"
    con.register(visao, df)
    try:
        con.execute(
            f"CREATE OR REPLACE TABLE {destino} AS SELECT * FROM {_ident(visao)}"
        )
    finally:
        con.unregister(visao)
    # fetchall, não fetchone: o DuckDB 2 considera um resultado não esgotado
    # como pendente e bloqueia o próximo uso da conexão.
    return con.execute(f"SELECT count(*) FROM {destino}").fetchall()[0][0]
