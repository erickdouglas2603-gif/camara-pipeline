"""Carrega os arquivos de raw/ no schema raw do DuckDB, sem decidir nada.

Uso: uv run python -m pipeline.ingestao

Spec: docs/specs/01-ingestao.md, seção "SPEC DO pipeline/ingestao.py".
Importa apenas pipeline.db; não importa download.py.
Motivo: download e ingestão são independentes. A ingestão roda sem internet,
sempre sobre o mesmo retrato que está em raw/.

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
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from pipeline.db import (
    ARQUIVO_MANIFESTO,
    ARQUIVOS,
    PASTA_RAW,
    conectar,
    criar_schema,
    gravar,
)

FUSO = ZoneInfo("America/Sao_Paulo")
SCHEMA = "raw"
COLUNAS_MANIFESTO = ["tabela", "arquivo", "url", "baixado_em", "bytes", "sha256"]
COMANDO_DOWNLOAD = "uv run python -m pipeline.download"


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _conferir_arquivos() -> list[dict]:
    """I7: existência e sha256, tudo antes de abrir o banco. Devolve o manifesto."""
    esperados = [PASTA_RAW / info["arquivo"] for info in ARQUIVOS.values()]
    esperados.append(ARQUIVO_MANIFESTO)
    faltando = [p.name for p in esperados if not p.is_file()]
    if faltando:
        print(f"ERRO: faltam arquivos em {PASTA_RAW}:", file=sys.stderr)
        for nome in faltando:
            print(f"  - {nome}", file=sys.stderr)
        print(f'Rode "{COMANDO_DOWNLOAD}".', file=sys.stderr)
        sys.exit(1)

    manifesto = json.loads(ARQUIVO_MANIFESTO.read_text(encoding="utf-8"))
    sha_por_arquivo = {e["arquivo"]: e["sha256"] for e in manifesto}
    # Arquivo sem entrada no manifesto também é divergência: não há como
    # saber de que retrato ele é.
    divergentes = [
        info["arquivo"]
        for info in ARQUIVOS.values()
        if sha_por_arquivo.get(info["arquivo"]) != _sha256(PASTA_RAW / info["arquivo"])
    ]
    if divergentes:
        print(f"ERRO: sha256 diferente do manifesto em {PASTA_RAW}:", file=sys.stderr)
        for nome in divergentes:
            print(f"  - {nome}", file=sys.stderr)
        print(
            f'raw/ está inconsistente. Rode "{COMANDO_DOWNLOAD}" de novo.',
            file=sys.stderr,
        )
        sys.exit(1)
    return manifesto


def _ler(info: dict) -> pd.DataFrame:
    """I4. O parser C do pandas já trata quebra de linha dentro de aspas."""
    return pd.read_csv(
        PASTA_RAW / info["arquivo"],
        sep=info["sep"],
        compression=info["compressao"],
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
        na_values=[""],
    )


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _retrato(manifesto: list[dict]) -> str:
    maior = max(datetime.fromisoformat(e["baixado_em"]) for e in manifesto)
    return maior.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    manifesto = _conferir_arquivos()

    contagens = {}
    con = conectar()
    try:
        con.execute("BEGIN TRANSACTION")
        try:
            criar_schema(con, SCHEMA)
            for tabela, info in ARQUIVOS.items():
                contagens[tabela] = gravar(con, _ler(info), SCHEMA, tabela)
            # I5: dtype=str no construtor deixa bytes como texto, igual ao CSV.
            df_manifesto = pd.DataFrame(manifesto, columns=COLUNAS_MANIFESTO, dtype=str)
            gravar(con, df_manifesto, SCHEMA, "_manifesto")
            con.execute("COMMIT")
        except BaseException:
            # BaseException: Ctrl+C no meio também desfaz tudo (I8).
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()

    # Saída só depois do COMMIT: o que aparece na tela é o que ficou no banco.
    largura = max(len(f"{SCHEMA}.{t}") for t in contagens)
    for tabela, n in contagens.items():
        print(f"{SCHEMA}.{tabela:<{largura - len(SCHEMA) - 1}}  {_milhar(n):>9}")
    print(f"{'total':<{largura}}  {_milhar(sum(contagens.values())):>9}")
    print(f"Retrato de {_retrato(manifesto)}")


if __name__ == "__main__":
    main()
