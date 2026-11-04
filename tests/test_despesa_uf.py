import duckdb

from pipeline.transformacao import PASTA_SQL

# As 32 colunas da raw.ceap, na ordem da raw. Na raw tudo é texto.
COLUNAS = [
    "txNomeParlamentar", "cpf", "ideCadastro", "nuCarteiraParlamentar", "nuLegislatura",
    "sgUF", "sgPartido", "codLegislatura", "numSubCota", "txtDescricao",
    "numEspecificacaoSubCota", "txtDescricaoEspecificacao", "txtFornecedor", "txtCNPJCPF",
    "txtNumero", "indTipoDocumento", "datEmissao", "vlrDocumento", "vlrGlosa", "vlrLiquido",
    "numMes", "numAno", "numParcela", "txtPassageiro", "txtTrecho", "numLote",
    "numRessarcimento", "datPagamentoRestituicao", "vlrRestituicao", "nuDeputadoId",
    "ideDocumento", "urlDocumento",
]


def montar_raw(linhas: list[dict]) -> duckdb.DuckDBPyConnection:
    """Banco em memória com uma raw.ceap feita só das linhas inventadas."""
    con = duckdb.connect()  # sem caminho = memória; o camara.duckdb nem é tocado
    con.execute("CREATE SCHEMA raw")
    colunas_sql = ", ".join(f'"{c}" VARCHAR' for c in COLUNAS)
    con.execute(f"CREATE TABLE raw.ceap ({colunas_sql})")
    marcadores = ", ".join("?" for _ in COLUNAS)
    for linha in linhas:
        # coluna que a linha não informa entra como NULL
        con.execute(f"INSERT INTO raw.ceap VALUES ({marcadores})",
                    [linha.get(c) for c in COLUNAS])
    return con


def test_uf_na_vira_nulo():
    # ARRANGE: as 3 linhas inventadas
    linhas = [
        {"txNomeParlamentar": "Deputado Teste SP", "sgUF": "SP", "ideCadastro": "1"},
        {"txNomeParlamentar": "LIDERANÇA TESTE", "sgUF": "NA", "ideCadastro": None},
        {"txNomeParlamentar": "Deputado Teste Sem UF", "sgUF": None, "ideCadastro": "2"},
    ]
    con = montar_raw(linhas)

    # ACT: roda o SQL de verdade do projeto
    sql = (PASTA_SQL / "despesa.sql").read_text(encoding="utf-8")
    con.execute(f"CREATE TABLE resultado AS {sql}")
    uf_por_nome = dict(con.execute(
        "SELECT des_nome_parlamentar, cod_uf FROM resultado").fetchall())

    # ASSERT
    assert uf_por_nome["Deputado Teste SP"] == "SP"
    assert uf_por_nome["LIDERANÇA TESTE"] == None
    assert uf_por_nome["Deputado Teste Sem UF"] == None