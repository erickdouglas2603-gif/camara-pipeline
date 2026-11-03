"""Abre o camara.duckdb na interface web do DuckDB.

Uso: uv run python ui.py

Spec: docs/specs/01-ingestao.md, seção "SPEC DO ui.py".
Importa de pipeline.db apenas a constante CAMINHO_BANCO; não importa
download.py nem ingestao.py.
Motivo: o caminho do banco fica num lugar só.

U1. Abre o banco em CAMINHO_BANCO, INSTALL ui; LOAD ui; CALL start_ui().
U2. Fica de pé até Ctrl+C, imprime a URL e "Ctrl+C para encerrar", e sai sem
    traceback.
U3. Usa CAMINHO_BANCO de pipeline.db, nunca conectar() (que cria o arquivo
    quando falta). Se o banco não existir, diz para rodar a ingestão e
    sys.exit(1).
    Motivo: um banco vazio aberto no navegador parece ingestão quebrada.
U4. stdout reconfigurado para utf-8.
"""

import sys
import time

import duckdb

from pipeline.db import CAMINHO_BANCO

PORTA_PADRAO = "4213"  # porta padrão da extensão ui do DuckDB


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    # U3: checar antes de conectar, porque duckdb.connect cria o arquivo.
    if not CAMINHO_BANCO.is_file():
        print(
            f"ERRO: {CAMINHO_BANCO} não existe.\n"
            'Rode "uv run python -m pipeline.ingestao" primeiro.',
            file=sys.stderr,
        )
        sys.exit(1)

    con = duckdb.connect(str(CAMINHO_BANCO))
    try:
        con.execute("INSTALL ui")
        con.execute("LOAD ui")
        # fetchall esgota os resultados: o DuckDB 2 bloqueia a conexão com
        # resultado pendente.
        con.execute("CALL start_ui()").fetchall()
        try:
            linhas = con.execute("SELECT current_setting('ui_local_port')").fetchall()
            porta = linhas[0][0]
        except duckdb.Error:
            porta = PORTA_PADRAO
        print(f"DuckDB UI em http://localhost:{porta}/")
        print("Ctrl+C para encerrar")
        # O servidor da UI roda em thread da extensão; o processo só precisa
        # continuar vivo com a conexão aberta.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass  # U2: sair sem traceback
    finally:
        con.close()


if __name__ == "__main__":
    main()
