"""Testes de orquestração e leitura (spec 04, O1 a O14).

Banco sempre em memória ou num arquivo novo em tmp_path; raw/ e rede substituídos
por monkeypatch. Nada aqui toca o camara.duckdb.
"""

import hashlib
import json

import duckdb
import pandas as pd
import pytest
from conftest import criar_raw, inserir, montar_refined

from pipeline import db, download, ingestao, marts, transformacao

# --- O1 a O4: transformar() e construir() -------------------------------------


def test_transformar_cria_refined_e_devolve_conferencias(con):
    # ARRANGE: raw inventada (um deputado da 57)
    inserir(con, "deputados", [{"uri": "x/1", "idLegislaturaFinal": "57"}])

    # ACT
    contagens, total, falhas = transformacao.transformar(con)
    tabelas = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'refined'"
    ).fetchall()[0][0]

    # ASSERT
    assert tabelas == 11  # 10 do refined + de_para_bancada
    assert len(contagens) == 11
    assert total == 55
    assert falhas and all(
        isinstance(f, str) for f in falhas
    )  # número fixo falha, sem exceção


def test_transformar_booleano_invalido_levanta_falha_tabela(con):
    # ARRANGE
    inserir(con, "votacoes", [{"id": "1-1", "aprovacao": "x"}])

    # ACT / ASSERT
    with pytest.raises(transformacao.FalhaTabela) as erro:
        transformacao.transformar(con)
    assert erro.value.tabela == "votacao"


def test_construir_cria_os_13_marts(con):
    # ARRANGE
    montar_refined(con)

    # ACT
    contagens, total, falhas = marts.construir(con)
    tabelas = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'marts'"
    ).fetchall()[0][0]

    # ASSERT
    assert tabelas == 13
    assert list(contagens) == [t for _, t, _ in marts.MARTS]
    assert total == 64
    assert falhas and all(isinstance(f, str) for f in falhas)  # sem exceção, como lista


def test_conferir_lista_do_repositorio():
    # ARRANGE / ACT
    problemas = marts.conferir_lista()

    # ASSERT
    assert problemas == []


# --- O5 a O8: db, ingestão, download ------------------------------------------


def test_db_gravar_devolve_contagem_do_banco():
    # ARRANGE
    con = duckdb.connect()
    df = pd.DataFrame({"a": ["1", "2", "3"]}, dtype=str)

    # ACT
    db.criar_schema(con, "raw")
    primeira = db.gravar(con, df, "raw", "t")
    segunda = db.gravar(
        con, df, "raw", "t"
    )  # CREATE OR REPLACE: rodar de novo não duplica

    # ASSERT
    assert (primeira, segunda) == (3, 3)


def test_ingestao_ler_preserva_na_e_anula_vazio(tmp_path, monkeypatch):
    # ARRANGE: CSV inventado com BOM, "NA" de liderança e campo vazio
    (tmp_path / "t.csv").write_text(
        '﻿"sgUF";"vlrGlosa"\n"NA";""\n"SP";"1.50"\n', encoding="utf-8"
    )
    monkeypatch.setattr(ingestao, "PASTA_RAW", tmp_path)

    # ACT
    df = ingestao._ler({"arquivo": "t.csv", "sep": ";", "compressao": None})

    # ASSERT
    assert list(df.columns) == ["sgUF", "vlrGlosa"]  # o BOM não gruda no nome da coluna
    assert df["sgUF"].tolist() == [
        "NA",
        "SP",
    ]  # keep_default_na=False: "NA" continua texto
    assert pd.isna(df["vlrGlosa"][0])  # campo vazio vira nulo
    assert df["vlrGlosa"][1] == "1.50"  # e o resto continua texto


def test_ingestao_sha256_bate_com_hashlib(tmp_path):
    # ARRANGE
    arquivo = tmp_path / "x.bin"
    conteudo = b"camara" * 1000
    arquivo.write_bytes(conteudo)

    # ACT
    obtido = ingestao._sha256(arquivo)

    # ASSERT
    assert obtido == hashlib.sha256(conteudo).hexdigest()


def test_download_baixar_tenta_3_vezes_com_espera_de_5_e_10(tmp_path, monkeypatch):
    # ARRANGE: _tentar falha 2 vezes e acerta na 3ª; sleep só registra
    tentativas, esperas = [], []

    def tentar_falso(url, destino):
        tentativas.append(url)
        if len(tentativas) < 3:
            raise download.FalhaDownload("HTTP 503")
        return 3, "abc"

    monkeypatch.setattr(download, "_tentar", tentar_falso)
    monkeypatch.setattr(download.time, "sleep", esperas.append)

    # ACT
    resultado = download._baixar("http://exemplo/arquivo.csv", tmp_path / "arquivo.csv")

    # ASSERT
    assert resultado == (3, "abc")
    assert len(tentativas) == 3
    assert esperas == [5, 10]


# --- O9: main() sem banco -----------------------------------------------------


@pytest.mark.parametrize("modulo", [transformacao, marts])
def test_main_sem_banco_sai_sem_criar_arquivo(modulo, tmp_path, monkeypatch):
    # ARRANGE: o caminho do banco aponta para um arquivo que não existe
    inexistente = tmp_path / "nao_existe.duckdb"
    monkeypatch.setattr(modulo, "CAMINHO_BANCO", inexistente)
    monkeypatch.setattr(db, "CAMINHO_BANCO", inexistente)  # se conectar() fosse chamado

    # ACT
    with pytest.raises(SystemExit) as saida:
        modulo.main()

    # ASSERT
    assert saida.value.code == 1
    assert not inexistente.exists()


# --- O10 e O11: _conferir_arquivos da ingestão --------------------------------


def _raw_em_tmp(tmp_path, monkeypatch, faltando: str | None = None):
    """Monta em tmp_path os 10 arquivos do mapa e um manifesto íntegro."""
    manifesto = []
    for tabela, info in db.ARQUIVOS.items():
        conteudo = f"conteudo de {tabela}".encode()
        manifesto.append(
            {
                "tabela": tabela,
                "arquivo": info["arquivo"],
                "sha256": hashlib.sha256(conteudo).hexdigest(),
            }
        )
        if info["arquivo"] != faltando:
            (tmp_path / info["arquivo"]).write_bytes(conteudo)
    arquivo_manifesto = tmp_path / "_manifesto.json"
    arquivo_manifesto.write_text(json.dumps(manifesto), encoding="utf-8")
    monkeypatch.setattr(ingestao, "PASTA_RAW", tmp_path)
    monkeypatch.setattr(ingestao, "ARQUIVO_MANIFESTO", arquivo_manifesto)


def test_ingestao_conferir_arquivos_com_arquivo_faltando(tmp_path, monkeypatch, capsys):
    # ARRANGE
    _raw_em_tmp(tmp_path, monkeypatch, faltando="deputados.csv")

    # ACT
    with pytest.raises(SystemExit) as saida:
        ingestao._conferir_arquivos()
    erro = capsys.readouterr().err

    # ASSERT
    assert saida.value.code == 1
    assert "deputados.csv" in erro
    assert "pipeline.download" in erro


def test_ingestao_conferir_arquivos_pelo_sha256(tmp_path, monkeypatch, capsys):
    # ARRANGE: tudo íntegro
    _raw_em_tmp(tmp_path, monkeypatch)

    # ACT / ASSERT: íntegro devolve o manifesto
    assert len(ingestao._conferir_arquivos()) == 10

    # ARRANGE: um byte alterado
    alvo = tmp_path / "eventos-2025.csv"
    alvo.write_bytes(b"X" + alvo.read_bytes()[1:])

    # ACT
    with pytest.raises(SystemExit) as saida:
        ingestao._conferir_arquivos()
    erro = capsys.readouterr().err

    # ASSERT
    assert saida.value.code == 1
    assert "eventos-2025.csv" in erro


# --- O12: _tentar do download -------------------------------------------------


class _RespostaFalsa:
    def __init__(self, status: int, blocos: list[bytes]):
        self.status_code = status
        self._blocos = blocos

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, tamanho):
        return iter(self._blocos)


def test_download_tentar_status_e_conteudo(tmp_path, monkeypatch):
    # ARRANGE
    blocos = [b"linha 1\n", b"linha 2\n"]
    respostas = iter([_RespostaFalsa(404, []), _RespostaFalsa(200, blocos)])
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: next(respostas))
    destino = tmp_path / "arquivo.csv"

    # ACT / ASSERT: 404 é falha
    with pytest.raises(download.FalhaDownload, match="404"):
        download._tentar("http://exemplo/arquivo.csv", destino)

    # ACT: 200 grava o conteúdo
    n_bytes, sha = download._tentar("http://exemplo/arquivo.csv", destino)

    # ASSERT
    assert destino.read_bytes() == b"".join(blocos)
    assert n_bytes == len(b"".join(blocos))
    assert sha == hashlib.sha256(b"".join(blocos)).hexdigest()


# --- O13 e O14: main() completo com ROLLBACK ----------------------------------


def _banco_em_tmp(tmp_path, monkeypatch, modulo, com_refined: bool):
    caminho = tmp_path / "camara.duckdb"
    con = duckdb.connect(str(caminho))
    criar_raw(con)
    inserir(con, "deputados", [{"uri": "x/1", "idLegislaturaFinal": "57"}])
    if com_refined:
        montar_refined(con)
    con.close()
    monkeypatch.setattr(modulo, "CAMINHO_BANCO", caminho)
    monkeypatch.setattr(db, "CAMINHO_BANCO", caminho)  # conectar() lê daqui
    return caminho


def _tabelas_no_schema(caminho, schema: str) -> int:
    con = duckdb.connect(str(caminho))
    try:
        return con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = ?",
            [schema],
        ).fetchall()[0][0]
    finally:
        con.close()


def test_transformacao_main_desfaz_tudo_se_conferencia_falha(
    tmp_path, monkeypatch, capsys
):
    # ARRANGE
    caminho = _banco_em_tmp(tmp_path, monkeypatch, transformacao, com_refined=False)

    # ACT
    with pytest.raises(SystemExit) as saida:
        transformacao.main()
    erro = capsys.readouterr().err

    # ASSERT
    assert saida.value.code == 1
    assert "ROLLBACK" in erro
    assert _tabelas_no_schema(caminho, "refined") == 0


def test_marts_main_desfaz_tudo_se_conferencia_falha(tmp_path, monkeypatch, capsys):
    # ARRANGE
    caminho = _banco_em_tmp(tmp_path, monkeypatch, marts, com_refined=True)

    # ACT
    with pytest.raises(SystemExit) as saida:
        marts.main()
    erro = capsys.readouterr().err

    # ASSERT
    assert saida.value.code == 1
    assert "ROLLBACK" in erro
    assert _tabelas_no_schema(caminho, "marts") == 0
