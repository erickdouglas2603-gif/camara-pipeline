"""Gera o schema refined a partir do raw: tipo certo, nome padronizado, falso nulo resolvido.

Uso: uv run python -m pipeline.transformacao

Spec: docs/specs/02-transformacao.md (o detalhe coluna a coluna está lá e em
sql/refined/<tabela>.sql). Resumo das regras e dos motivos:

- O refined não corrige fato: não filtra linha, não deduplica, não preenche
  valor. Linha suspeita ganha flag (bln_), não é apagada. Quem filtra é o mart.
- Mesmo grão e mesma contagem da raw em todas as tabelas; se a contagem mudar,
  a carga falha. Exceção: deputado (legislatura 57 + quem aparece em algum
  fato, 690), porque a dimensão precisa cobrir todos os fatos sem carregar o
  histórico desde 1826.
- Conversão falha alto: CAST, nunca TRY_CAST. Os únicos NULL novos são os
  falsos nulos da spec, via NULLIF antes do CAST. Booleanos '1'/'0' por CASE
  pesquisado com error() no ELSE (CAST AS BOOLEAN aceitaria 't', 'yes' etc.).
- Nenhum CPF chega ao refined (deputado, cota, fornecedor pessoa física).
- Organização: um SELECT por arquivo em sql/refined/; este script executa
  CREATE OR REPLACE TABLE refined.<tabela> AS <select> na ordem da spec
  (autoria depende de proposição; presença depende de evento), tudo numa
  transação só.
- Adendo da spec 03: dados/de_para_bancada.csv (criado por nós) vira
  refined.de_para_bancada, lido com as regras da ingestão (tudo texto), antes
  das demais tabelas; 6 conferências próprias.
- Antes de conectar: sem camara.duckdb, manda rodar a ingestão e sai
  (sem conectar(), que criaria o arquivo vazio). Banco travado (ui.py
  aberto): avisa e sai.
- CAST que falha: ROLLBACK, mostra a tabela, sys.exit(1).
- Conferências: números fixos de propósito (valem para o retrato registrado
  no manifesto; retrato novo obriga a revisar a spec). Cada verificação
  atômica conta 1; roda todas, lista as que falharam, ROLLBACK e sys.exit(1).
- Saída: uma linha por tabela (nome, linhas) e "Conferências: N de N OK".
"""

import sys
from pathlib import Path

import duckdb
import pandas as pd

from pipeline.db import CAMINHO_BANCO, conectar, criar_schema, gravar

_RAIZ = Path(__file__).resolve().parent.parent
PASTA_SQL = _RAIZ / "sql" / "refined"
# Adendo da spec 03: de-para criado por nós (não é dado da Câmara), versionado.
ARQUIVO_DE_PARA = _RAIZ / "dados" / "de_para_bancada.csv"
SCHEMA = "refined"

# Ordem da spec. (tabela refined, tabela raw de origem, colunas da chave)
TABELAS = [
    ("deputado", "deputados", ["id_deputado"]),
    ("votacao", "votacoes", ["id_votacao"]),
    ("voto", "votacoesVotos", ["id_votacao", "id_deputado"]),
    ("orientacao", "votacoesOrientacoes", ["id_votacao", "cod_bancada"]),
    ("proposicao", "proposicoes", ["id_proposicao"]),
    ("autoria", "proposicoesAutores", ["id_proposicao", "num_ordem_assinatura"]),
    ("tema", "proposicoesTemas", ["id_proposicao", "cod_tema"]),
    ("evento", "eventos", ["id_evento"]),
    ("presenca", "eventosPresencaDeputados", ["id_evento", "id_deputado"]),
    ("despesa", "ceap", ["id_despesa"]),
]

CONTAGEM_DEPUTADO = 690  # exceção à regra 1, medida e fixada na spec


def _conferencias() -> list[tuple[str, str, str]]:
    """(descrição, SQL do valor obtido, SQL do valor esperado). Cada uma conta 1."""
    c = []
    # 1. Contagem refined = raw (deputado: número fixo da spec).
    for tabela, origem, _ in TABELAS:
        if tabela == "deputado":
            esperado = f"SELECT {CONTAGEM_DEPUTADO}"
        else:
            esperado = f'SELECT count(*) FROM raw."{origem}"'
        c.append(
            (
                f"1. {tabela}: contagem",
                f"SELECT count(*) FROM refined.{tabela}",
                esperado,
            )
        )
    c.append(
        (
            "1. deputado: bln_legislatura_atual TRUE = 648",
            "SELECT count(*) FROM refined.deputado WHERE bln_legislatura_atual",
            "SELECT 648",
        )
    )
    # 1b. Nenhum fato órfão da dimensão deputado.
    for fato in ["voto", "presenca", "autoria", "despesa"]:
        c.append(
            (
                f"1b. {fato}: id_deputado sem deputado",
                (
                    f"SELECT count(*) FROM refined.{fato} f WHERE f.id_deputado IS NOT NULL "
                    "AND NOT EXISTS (SELECT 1 FROM refined.deputado d "
                    "WHERE d.id_deputado = f.id_deputado)"
                ),
                "SELECT 0",
            )
        )
    # 2. Chave sem repetição e sem NULL (duas verificações por tabela).
    for tabela, _, chave in TABELAS:
        cols = ", ".join(chave)
        algum_nulo = " OR ".join(f"{k} IS NULL" for k in chave)
        c.append(
            (
                f"2. {tabela}: chave repetida",
                (
                    f"SELECT count(*) FROM (SELECT {cols} FROM refined.{tabela} "
                    f"GROUP BY {cols} HAVING count(*) > 1)"
                ),
                "SELECT 0",
            )
        )
        c.append(
            (
                f"2. {tabela}: chave com NULL",
                f"SELECT count(*) FROM refined.{tabela} WHERE {algum_nulo}",
                "SELECT 0",
            )
        )
    # 3 a 8. Números fixos da spec.
    c += [
        ("3. votacao: id_proposicao NULL = 7.219",
         "SELECT count(*) FROM refined.votacao WHERE id_proposicao IS NULL", "SELECT 7219"),
        ("3. votacao: bln_aprovada NULL = 107",
         "SELECT count(*) FROM refined.votacao WHERE bln_aprovada IS NULL", "SELECT 107"),
        ("3. votacao: bln_orgao_teste TRUE = 1",
         "SELECT count(*) FROM refined.votacao WHERE bln_orgao_teste", "SELECT 1"),
        ("4. voto: des_voto NULL = 421",
         "SELECT count(*) FROM refined.voto WHERE des_voto IS NULL", "SELECT 421"),
        ("4. voto: des_voto NULL fora da votação 2576389-4",
         ("SELECT count(*) FROM refined.voto "
         "WHERE des_voto IS NULL AND id_votacao <> '2576389-4'"), "SELECT 0"),
        ("5. despesa: lideranca = 937",
         "SELECT count(*) FROM refined.despesa WHERE tp_beneficiario = 'lideranca'", "SELECT 937"),
        ("5. despesa: id_documento NULL = 7.842",
         "SELECT count(*) FROM refined.despesa WHERE id_documento IS NULL", "SELECT 7842"),
        ("5. despesa: sum(vlr_liquido) = 240.347.478,45",
         "SELECT sum(vlr_liquido) FROM refined.despesa",
         "SELECT CAST('240347478.45' AS DECIMAL(38,2))"),
        ("5. despesa: cod_cnpj_fornecedor sem 14 dígitos",
         ("SELECT count(*) FROM refined.despesa WHERE cod_cnpj_fornecedor IS NOT NULL "
         "AND NOT regexp_full_match(cod_cnpj_fornecedor, '[0-9]{14}')"), "SELECT 0"),
        ("5. despesa: PF com cod_cnpj_fornecedor",
         ("SELECT count(*) FROM refined.despesa "
         "WHERE tp_fornecedor = 'PF' AND cod_cnpj_fornecedor IS NOT NULL"), "SELECT 0"),
        ("5. despesa: cod_uf NULL = 937",
         "SELECT count(*) FROM refined.despesa WHERE cod_uf IS NULL", "SELECT 937"),
        ("6. autoria: bln_proposicao_cadastrada FALSE = 56",
         "SELECT count(*) FROM refined.autoria WHERE NOT bln_proposicao_cadastrada", "SELECT 56"),
        ("7. presenca: bln_evento_cadastrado FALSE = 2",
         "SELECT count(*) FROM refined.presenca WHERE NOT bln_evento_cadastrado", "SELECT 2"),
        ("8. tema: proposições distintas = 19.754",
         "SELECT count(DISTINCT id_proposicao) FROM refined.tema", "SELECT 19754"),
        # Adendo da spec 03: de-para partido -> bancada.
        ("9. de_para_bancada: 27 linhas",
         "SELECT count(*) FROM refined.de_para_bancada", "SELECT 27"),
        ("9. de_para_bancada: (cod_partido, cod_bancada_origem) repetido",
         ("SELECT count(*) FROM (SELECT cod_partido, cod_bancada_origem "
          "FROM refined.de_para_bancada GROUP BY ALL HAVING count(*) > 1)"), "SELECT 0"),
        ("9. de_para_bancada: 22 cod_bancada_origem distintos",
         "SELECT count(DISTINCT cod_bancada_origem) FROM refined.de_para_bancada", "SELECT 22"),
        ("9. de_para_bancada: cod_partido de voto sem de-para",
         ("SELECT count(DISTINCT cod_partido) FROM refined.voto WHERE cod_partido NOT IN "
          "(SELECT cod_partido FROM refined.de_para_bancada)"), "SELECT 0"),
        ("9. de_para_bancada: colisões (id_votacao, cod_partido) no JOIN com orientacao",
         ("SELECT count(*) - count(DISTINCT (o.id_votacao, d.cod_partido)) "
          "FROM refined.orientacao o JOIN refined.de_para_bancada d "
          "ON d.cod_bancada_origem = o.cod_bancada"), "SELECT 0"),
        ("9. de_para_bancada: JOIN casa 3.283 orientações",
         ("SELECT count(*) FROM refined.orientacao o JOIN refined.de_para_bancada d "
          "ON d.cod_bancada_origem = o.cod_bancada"), "SELECT 3283"),
    ]  # fmt: skip
    return c


def _ler_de_para() -> pd.DataFrame:
    # Mesmas regras da ingestão (I4): tudo texto, UTF-8 declarado, só o vazio vira nulo.
    return pd.read_csv(
        ARQUIVO_DE_PARA,
        sep=",",
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
        na_values=[""],
    )


class FalhaTabela(Exception):
    def __init__(self, tabela: str, erro: Exception):
        super().__init__(f"{tabela}: {erro}")
        self.tabela = tabela
        self.erro = erro


def _valor(con: duckdb.DuckDBPyConnection, sql: str):
    # fetchall: o DuckDB 2 bloqueia a conexão com resultado não esgotado.
    return con.execute(sql).fetchall()[0][0]


def transformar(
    con: duckdb.DuckDBPyConnection,
) -> tuple[dict[str, int], int, list[str]]:
    """Cria as tabelas e roda as conferências, sem BEGIN/COMMIT (quem chama decide).

    Devolve (contagens, total de conferências, falhas). Levanta FalhaTabela se
    um SELECT falhar (CAST, error() da regra 7 ou do tp_fornecedor).
    """
    criar_schema(con, SCHEMA)
    contagens = {}
    # O de-para vai primeiro: nada no refined depende dele, os marts sim.
    try:
        contagens["de_para_bancada"] = gravar(
            con, _ler_de_para(), SCHEMA, "de_para_bancada"
        )
    except (OSError, ValueError, duckdb.Error) as e:
        raise FalhaTabela("de_para_bancada", e) from e
    for tabela, _, _ in TABELAS:
        select = (
            (PASTA_SQL / f"{tabela}.sql")
            .read_text(encoding="utf-8")
            .strip()
            .rstrip(";")
        )
        try:
            con.execute(f"CREATE OR REPLACE TABLE {SCHEMA}.{tabela} AS\n{select}\n")
        except duckdb.Error as e:
            raise FalhaTabela(tabela, e) from e
        contagens[tabela] = _valor(con, f"SELECT count(*) FROM {SCHEMA}.{tabela}")

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
            'Rode a ingestão primeiro: "uv run python -m pipeline.ingestao".',
            file=sys.stderr,
        )
        sys.exit(1)
    if not ARQUIVO_DE_PARA.is_file():
        print(
            f"ERRO: {ARQUIVO_DE_PARA} não existe (é versionado no repositório).",
            file=sys.stderr,
        )
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
            contagens, total, falhas = transformar(con)
        except FalhaTabela as e:
            con.execute("ROLLBACK")
            print(
                f"ERRO na tabela refined.{e.tabela}; nada foi gravado.\n{e.erro}",
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
