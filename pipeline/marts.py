"""Gera o schema marts a partir do refined: um indicador por tabela, pronto para o dashboard.

Uso: uv run python -m pipeline.marts

Spec: docs/specs/03-marts.md (as regras de cada indicador estão lá e nos
comentários de sql/marts/<nn>_<nome>.sql). Resumo das regras e dos motivos:

- Regra de negócio mora aqui (filtro, recorte, corte de amostra,
  classificação); o dashboard não calcula nada.
- Um SELECT por arquivo em sql/marts/, 1ª linha "-- grão: ...".
- Nomes: dim_<Assunto> e agg_<Assunto>_<Detalhe>; como o nome com maiúscula não
  sai do nome do arquivo, a lista MARTS abaixo diz (arquivo, tabela, chave).
  Antes de executar, confere que a lista segue a numeração dos arquivos e que
  nenhum .sql ficou de fora.
- pct_ de 0 a 100, DECIMAL(5,1). Dinheiro nunca guardado nem somado em DOUBLE;
  divisão com CAST para DECIMAL na mesma expressão (no DuckDB, DECIMAL / x é
  DOUBLE). Divisão por zero vira NULL.
- Grupo pequeno não vira indicador: a linha fica, com valor NULL e
  bln_amostra_suficiente = FALSE.
- Partido de um deputado = o do último voto em 2025, calculado só na
  dim_Deputado. Universo dos indicadores por deputado = bln_universo_2025.
- Execução: CREATE OR REPLACE TABLE marts.<tabela> AS <select>, em ordem
  numérica, numa transação; depois as conferências. Mesmo padrão do
  transformacao.py: banco ausente ou travado -> avisa e sai; SELECT que falha
  ou conferência que falha -> ROLLBACK, lista, sys.exit(1).
- Conferências: números fixos do retrato; cada verificação atômica conta 1.
- Saída: uma linha por tabela e "Conferências: N de N OK".
"""

import sys
from pathlib import Path

import duckdb

from pipeline.db import CAMINHO_BANCO, conectar, criar_schema

PASTA_SQL = Path(__file__).resolve().parent.parent / "sql" / "marts"
SCHEMA = "marts"

# (arquivo, tabela, colunas da chave = o grão). Ordem = numeração dos arquivos.
MARTS = [
    ("00_dim_deputado.sql", "dim_Deputado", ["id_deputado"]),
    ("01_presenca_deputado.sql", "agg_Presenca_Deputado", ["id_deputado"]),
    ("02_fidelidade_partido.sql", "agg_Fidelidade_Partido", ["cod_partido"]),
    ("03_coesao_partido.sql", "agg_Coesao_Partido", ["cod_partido"]),
    ("04_votacao_apertada.sql", "agg_Votacao_Apertada", ["id_votacao"]),
    (
        "05_proposicao_tema_deputado.sql",
        "agg_Proposicao_Tema_Deputado",
        ["id_deputado", "cod_tema", "cod_sigla_tipo"],
    ),
    ("06_gasto_deputado.sql", "agg_Gasto_Deputado", ["id_deputado"]),
    ("07_gasto_categoria.sql", "agg_Gasto_Categoria", ["cod_subcota"]),
    ("08_gasto_mensal.sql", "agg_Gasto_Mensal", ["data_competencia"]),
    ("09_gasto_uf.sql", "agg_Gasto_UF", ["cod_uf"]),
    ("10_fornecedor_pareto.sql", "agg_Fornecedor_Pareto", ["cod_fornecedor"]),
    ("11_participacao_deputado.sql", "agg_Participacao_Deputado", ["id_deputado"]),
    ("12_alinhamento_governo.sql", "agg_Alinhamento_Governo", ["id_deputado"]),
]

UNIVERSO_2025 = 564
POR_DEPUTADO_NO_UNIVERSO = [  # contagem = universo (conferência 2)
    "agg_Presenca_Deputado",
    "agg_Gasto_Deputado",
    "agg_Participacao_Deputado",
    "agg_Alinhamento_Governo",
]
POR_DEPUTADO = POR_DEPUTADO_NO_UNIVERSO + [
    "agg_Proposicao_Tema_Deputado"
]  # conferência 10
TOTAL_COTA = "240347478.45"
TOTAL_DEPUTADOS = "239208957.97"  # total da cota menos as lideranças


class FalhaMart(Exception):
    def __init__(self, tabela: str, erro: Exception):
        super().__init__(f"{tabela}: {erro}")
        self.tabela = tabela
        self.erro = erro


def conferir_lista() -> list[str]:
    """Devolve os problemas entre a lista MARTS e os arquivos de sql/marts/ (vazia = ok)."""
    problemas = []
    na_lista = [arquivo for arquivo, _, _ in MARTS]
    no_disco = sorted(p.name for p in PASTA_SQL.glob("*.sql"))
    for arquivo in sorted(set(no_disco) - set(na_lista)):
        problemas.append(f"{arquivo} está em sql/marts/ mas não na lista MARTS")
    for arquivo in sorted(set(na_lista) - set(no_disco)):
        problemas.append(f"{arquivo} está na lista MARTS mas não em sql/marts/")
    # Ordem numérica pelo prefixo <nn>_, não alfabética (00 < 01 < ... < 10 < 11).
    numeros = [int(arquivo.split("_", 1)[0]) for arquivo in na_lista]
    if numeros != sorted(numeros):
        problemas.append(f"a lista MARTS não segue a numeração dos arquivos: {numeros}")
    return problemas


def _dec(valor: str) -> str:
    return f"SELECT CAST('{valor}' AS DECIMAL(38,2))"


def _conferencias() -> list[tuple[str, str, str]]:
    """(descrição, SQL do valor obtido, SQL do valor esperado). Cada uma conta 1."""
    c = []
    # 1. Chave (o grão) sem repetição e sem NULL.
    for _, tabela, chave in MARTS:
        cols = ", ".join(chave)
        algum_nulo = " OR ".join(f"{k} IS NULL" for k in chave)
        c.append(
            (
                f"1. {tabela}: chave repetida",
                (
                    f"SELECT count(*) FROM (SELECT {cols} FROM marts.{tabela} "
                    f"GROUP BY {cols} HAVING count(*) > 1)"
                ),
                "SELECT 0",
            )
        )
        c.append(
            (
                f"1. {tabela}: chave com NULL",
                f"SELECT count(*) FROM marts.{tabela} WHERE {algum_nulo}",
                "SELECT 0",
            )
        )
    # 2. Contagens.
    for tabela, n in [
        ("dim_Deputado", 690),
        ("agg_Fidelidade_Partido", 20),
        ("agg_Votacao_Apertada", 550),
        ("agg_Proposicao_Tema_Deputado", 15223),
        ("agg_Gasto_Categoria", 21),
        ("agg_Gasto_Mensal", 12),
        ("agg_Gasto_UF", 27),
    ] + [(t, UNIVERSO_2025) for t in POR_DEPUTADO_NO_UNIVERSO]:
        c.append(
            (
                f"2. {tabela}: {n} linhas",
                f"SELECT count(*) FROM marts.{tabela}",
                f"SELECT {n}",
            )
        )
    c += [
        ("2. agg_Votacao_Apertada: 429 do PLEN",
         "SELECT count(*) FROM marts.agg_Votacao_Apertada WHERE cod_orgao = 'PLEN'", "SELECT 429"),
        ("2. dim_Deputado: bln_universo_2025 TRUE = 564",
         "SELECT count(*) FROM marts.dim_Deputado WHERE bln_universo_2025", f"SELECT {UNIVERSO_2025}"),
        # 3. Somas que batem com o refined.
        ("3. agg_Gasto_Deputado: sum(vlr_total) = 239.208.957,97",
         "SELECT sum(vlr_total) FROM marts.agg_Gasto_Deputado", _dec(TOTAL_DEPUTADOS)),
        ("3. agg_Gasto_Categoria: sum(vlr_total) = 240.347.478,45",
         "SELECT sum(vlr_total) FROM marts.agg_Gasto_Categoria", _dec(TOTAL_COTA)),
        ("3. agg_Gasto_Mensal: sum(vlr_total) = 240.347.478,45",
         "SELECT sum(vlr_total) FROM marts.agg_Gasto_Mensal", _dec(TOTAL_COTA)),
        ("3. agg_Fornecedor_Pareto: sum(vlr_total) = 240.347.478,45",
         "SELECT sum(vlr_total) FROM marts.agg_Fornecedor_Pareto", _dec(TOTAL_COTA)),
        ("3. agg_Gasto_UF: sum(vlr_total) = 239.208.957,97",
         "SELECT sum(vlr_total) FROM marts.agg_Gasto_UF", _dec(TOTAL_DEPUTADOS)),
        # 4. M02.
        ("4. agg_Fidelidade_Partido: sum(qtd_votos) = 175.067",
         "SELECT sum(qtd_votos) FROM marts.agg_Fidelidade_Partido", "SELECT 175067"),
        ("4. agg_Fidelidade_Partido: sum(qtd_votos_orientados) = 32.179",
         "SELECT sum(qtd_votos_orientados) FROM marts.agg_Fidelidade_Partido", "SELECT 32179"),
        ("4. agg_Fidelidade_Partido: sum(qtd_votos_fieis) = 30.770",
         "SELECT sum(qtd_votos_fieis) FROM marts.agg_Fidelidade_Partido", "SELECT 30770"),
        ("4. agg_Fidelidade_Partido: bln_amostra_suficiente TRUE = 9",
         "SELECT count(*) FROM marts.agg_Fidelidade_Partido WHERE bln_amostra_suficiente",
         "SELECT 9"),
        # 5. M03.
        ("5. agg_Coesao_Partido: sum(qtd_votacoes) = 8.212",
         "SELECT sum(qtd_votacoes) FROM marts.agg_Coesao_Partido", "SELECT 8212"),
        # 6. M04.
        ("6. agg_Votacao_Apertada: bln_resultado_contra_placar TRUE = 4",
         "SELECT count(*) FROM marts.agg_Votacao_Apertada WHERE bln_resultado_contra_placar",
         "SELECT 4"),
        ("6. agg_Votacao_Apertada: bln_apertada TRUE = 7",
         "SELECT count(*) FROM marts.agg_Votacao_Apertada WHERE bln_apertada", "SELECT 7"),
        # 7. M07.
        ("7. agg_Gasto_Categoria: sum(pct_total) entre 99,9 e 100,1",
         "SELECT sum(pct_total) BETWEEN 99.9 AND 100.1 FROM marts.agg_Gasto_Categoria",
         "SELECT TRUE"),
        # 8. M10.
        ("8. agg_Fornecedor_Pareto: último pct_acumulado = 100,0",
         ("SELECT pct_acumulado FROM marts.agg_Fornecedor_Pareto "
          "WHERE num_posicao = (SELECT max(num_posicao) FROM marts.agg_Fornecedor_Pareto)"),
         "SELECT CAST(100 AS DECIMAL(5,1))"),
        ("8. agg_Fornecedor_Pareto: bln_cnpj_ficticio TRUE = 5",
         "SELECT count(*) FROM marts.agg_Fornecedor_Pareto WHERE bln_cnpj_ficticio", "SELECT 5"),
        ("8. agg_Fornecedor_Pareto: bln_top_80 TRUE = 1.452",
         "SELECT count(*) FROM marts.agg_Fornecedor_Pareto WHERE bln_top_80", "SELECT 1452"),
        # 9. M11.
        ("9. agg_Participacao_Deputado: pct_participacao fora de 0 a 100",
         ("SELECT count(*) FROM marts.agg_Participacao_Deputado "
          "WHERE pct_participacao NOT BETWEEN 0 AND 100"), "SELECT 0"),
        ("9. agg_Participacao_Deputado: registrados > votações no período",
         ("SELECT count(*) FROM marts.agg_Participacao_Deputado "
          "WHERE qtd_votos_registrados > qtd_votacoes_no_periodo"), "SELECT 0"),
    ]  # fmt: skip
    # 10. Nenhum mart por deputado fora do universo.
    for tabela in POR_DEPUTADO:
        c.append(
            (
                f"10. {tabela}: id_deputado fora do universo de 2025",
                (
                    f"SELECT count(*) FROM marts.{tabela} m WHERE NOT EXISTS ("
                    "SELECT 1 FROM marts.dim_Deputado d "
                    "WHERE d.id_deputado = m.id_deputado AND d.bln_universo_2025)"
                ),
                "SELECT 0",
            )
        )
    c += [
        # 11. M12.
        ("11. agg_Alinhamento_Governo: sum(qtd_votos_orientados) = 129.694",
         "SELECT sum(qtd_votos_orientados) FROM marts.agg_Alinhamento_Governo", "SELECT 129694"),
        ("11. agg_Alinhamento_Governo: sum(qtd_votos_alinhados) = 86.259",
         "SELECT sum(qtd_votos_alinhados) FROM marts.agg_Alinhamento_Governo", "SELECT 86259"),
    ]  # fmt: skip
    return c


def _valor(con: duckdb.DuckDBPyConnection, sql: str):
    # fetchall: o DuckDB 2 bloqueia a conexão com resultado não esgotado.
    return con.execute(sql).fetchall()[0][0]


def construir(
    con: duckdb.DuckDBPyConnection,
) -> tuple[dict[str, int], int, list[str]]:
    """Cria os marts e roda as conferências, sem BEGIN/COMMIT (quem chama decide).

    Devolve (contagens, total de conferências, falhas). Levanta FalhaMart se a
    lista MARTS divergir dos arquivos ou se um SELECT falhar.
    """
    problemas = conferir_lista()
    if problemas:
        raise FalhaMart("MARTS", ValueError("; ".join(problemas)))

    criar_schema(con, SCHEMA)
    contagens = {}
    for arquivo, tabela, _ in MARTS:
        select = (PASTA_SQL / arquivo).read_text(encoding="utf-8").strip().rstrip(";")
        try:
            # Aspas: o nome é gravado com as maiúsculas da spec (dim_Deputado).
            con.execute(f'CREATE OR REPLACE TABLE {SCHEMA}."{tabela}" AS\n{select}\n')
        except duckdb.Error as e:
            raise FalhaMart(tabela, e) from e
        contagens[tabela] = _valor(con, f'SELECT count(*) FROM {SCHEMA}."{tabela}"')

    conferencias = _conferencias()
    falhas = []
    for descricao, sql_obtido, sql_esperado in conferencias:
        try:
            obtido, esperado = _valor(con, sql_obtido), _valor(con, sql_esperado)
        except duckdb.Error as e:
            falhas.append(f"{descricao}: erro ao conferir ({e})")
            continue
        if obtido != esperado:
            falhas.append(f"{descricao}: obtido {obtido}, esperado {esperado}")
    return contagens, len(conferencias), falhas


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    if not CAMINHO_BANCO.is_file():
        print(
            f"ERRO: {CAMINHO_BANCO} não existe.\n"
            "Rode a ingestão e a transformação primeiro.",
            file=sys.stderr,
        )
        sys.exit(1)
    problemas = conferir_lista()
    if problemas:
        print("ERRO: lista MARTS e sql/marts/ divergem:", file=sys.stderr)
        for p in problemas:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    try:
        con = conectar()
    except duckdb.IOException as e:
        print(
            f"ERRO: não foi possível abrir {CAMINHO_BANCO} (travado por outro processo?\n"
            f"Feche o ui.py e tente de novo).\n{e}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        con.execute("BEGIN TRANSACTION")
        try:
            contagens, total, falhas = construir(con)
        except FalhaMart as e:
            con.execute("ROLLBACK")
            print(
                f"ERRO em marts.{e.tabela}; nada foi gravado.\n{e.erro}",
                file=sys.stderr,
            )
            sys.exit(1)
        except BaseException:
            con.execute("ROLLBACK")
            raise

        largura = max(len(f"{SCHEMA}.{t}") for t in contagens)
        for tabela, n in contagens.items():
            print(f"{f'{SCHEMA}.{tabela}':<{largura}}  {_milhar(n):>9}")
        print(f"Conferências: {total - len(falhas)} de {total} OK")

        if falhas:
            con.execute("ROLLBACK")
            print("Falharam:", file=sys.stderr)
            for f in falhas:
                print(f"  - {f}", file=sys.stderr)
            print("ROLLBACK: nada foi gravado.", file=sys.stderr)
            sys.exit(1)
        con.execute("COMMIT")
    finally:
        con.close()


if __name__ == "__main__":
    main()
