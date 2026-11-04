"""Testes das regras do refined (spec 04, R2 a R10; o R1 está em test_despesa_uf.py)."""

from decimal import Decimal

import duckdb
import pytest
from conftest import inserir, rodar


def test_despesa_hash_com_coalesce(con):
    # ARRANGE: ('a', NULL, 'b') e (NULL, 'a', 'b') — sem o coalesce, concat_ws pularia o NULL
    # e as duas virariam "a|b"
    inserir(
        con,
        "ceap",
        [
            {"txNomeParlamentar": "a", "cpf": None, "txtFornecedor": "b"},
            {"txNomeParlamentar": None, "cpf": "a", "txtFornecedor": "b"},
        ],
    )

    # ACT: roda duas vezes
    rodar(con, "refined", "despesa")
    primeira = sorted(
        r[0] for r in con.execute("SELECT id_despesa FROM refined.despesa").fetchall()
    )
    rodar(con, "refined", "despesa")
    segunda = sorted(
        r[0] for r in con.execute("SELECT id_despesa FROM refined.despesa").fetchall()
    )

    # ASSERT
    assert len(set(primeira)) == 2  # muda: ids diferentes
    assert primeira == segunda  # não muda: a mesma linha gera sempre o mesmo id


def test_despesa_documento_do_fornecedor(con):
    # ARRANGE: um CNPJ pontuado (14 dígitos) e um CPF pontuado (11 dígitos), inventados
    inserir(
        con,
        "ceap",
        [
            {"txtFornecedor": "EMPRESA", "txtCNPJCPF": "12.345.678/0001-90"},
            {"txtFornecedor": "PESSOA", "txtCNPJCPF": "987.654.321-00"},
        ],
    )

    # ACT
    rodar(con, "refined", "despesa")
    linhas = con.execute(
        "SELECT des_fornecedor, tp_fornecedor, cod_cnpj_fornecedor FROM refined.despesa"
    ).fetchall()
    por_nome = {nome: (tp, doc) for nome, tp, doc in linhas}
    tudo_como_texto = con.execute(
        "SELECT string_agg(CAST(COLUMNS(*) AS VARCHAR), '|') FROM refined.despesa"
    ).fetchall()[0]

    # ASSERT
    assert por_nome["EMPRESA"] == ("PJ", "12345678000190")  # muda: só dígitos
    assert por_nome["PESSOA"] == ("PF", None)  # muda: CPF não vira código
    for valor in (
        tudo_como_texto
    ):  # não pode mudar: o CPF não chega ao refined, em formato nenhum
        assert "98765432100" not in (valor or "")
        assert "987.654.321-00" not in (valor or "")


def test_despesa_documento_com_13_digitos_derruba_a_carga(con):
    # ARRANGE
    inserir(con, "ceap", [{"txtCNPJCPF": "1234567890123"}])

    # ACT / ASSERT: o error() do tp_fornecedor derruba o CREATE
    with pytest.raises(duckdb.Error, match="13 dígitos"):
        rodar(con, "refined", "despesa")


def test_despesa_falsos_nulos_e_beneficiario(con):
    # ARRANGE
    inserir(
        con,
        "ceap",
        [
            {
                "txNomeParlamentar": "TELEFONIA",
                "ideDocumento": "0",
                "ideCadastro": "10",
            },
            {"txNomeParlamentar": "NOTA", "ideDocumento": "123", "ideCadastro": "11"},
            {
                "txNomeParlamentar": "LIDERANÇA",
                "ideDocumento": "456",
                "ideCadastro": None,
            },
        ],
    )

    # ACT
    rodar(con, "refined", "despesa")
    linhas = con.execute(
        "SELECT des_nome_parlamentar, id_documento, tp_beneficiario FROM refined.despesa"
    ).fetchall()
    por_nome = {nome: (doc, tp) for nome, doc, tp in linhas}

    # ASSERT
    assert por_nome["TELEFONIA"][0] is None  # muda: '0' -> NULL
    assert por_nome["NOTA"][0] == 123  # não muda
    assert por_nome["LIDERANÇA"][1] == "lideranca"  # muda: sem ideCadastro
    assert por_nome["NOTA"][1] == "deputado"  # não muda


def test_despesa_dinheiro_exato(con):
    # ARRANGE: em DOUBLE, 0.1 + 0.2 = 0.30000000000000004
    inserir(con, "ceap", [{"vlrLiquido": "0.10"}, {"vlrLiquido": "0.20"}])

    # ACT
    rodar(con, "refined", "despesa")
    soma, tipo = con.execute(
        "SELECT sum(vlr_liquido), any_value(typeof(vlr_liquido)) FROM refined.despesa"
    ).fetchall()[0]

    # ASSERT
    assert soma == Decimal("0.30")
    assert tipo == "DECIMAL(14,2)"


def test_votacao_booleano_estrito(con):
    # ARRANGE
    inserir(
        con,
        "votacoes",
        [
            {"id": "1-1", "aprovacao": "1"},
            {"id": "1-2", "aprovacao": "0"},
            {"id": "1-3", "aprovacao": None},
        ],
    )

    # ACT
    rodar(con, "refined", "votacao")
    por_id = dict(
        con.execute("SELECT id_votacao, bln_aprovada FROM refined.votacao").fetchall()
    )

    # ASSERT
    assert por_id == {"1-1": True, "1-2": False, "1-3": None}


def test_votacao_booleano_invalido_derruba_a_carga(con):
    # ARRANGE: 'x' (e 't', 'yes'...) seriam aceitos por CAST AS BOOLEAN; aqui têm que falhar
    inserir(con, "votacoes", [{"id": "1-1", "aprovacao": "x"}])

    # ACT / ASSERT
    with pytest.raises(duckdb.Error, match="fora de 0/1"):
        rodar(con, "refined", "votacao")


def test_votacao_id_e_falsos_nulos(con):
    # ARRANGE
    inserir(
        con,
        "votacoes",
        [
            {
                "id": "2576389-4",
                "siglaOrgao": "TESTECOM",
                "ultimaApresentacaoProposicao_idProposicao": "0",
            },
            {
                "id": "2576390-1",
                "siglaOrgao": "PLEN",
                "ultimaApresentacaoProposicao_idProposicao": "123",
            },
        ],
    )

    # ACT
    rodar(con, "refined", "votacao")
    linhas = con.execute(
        "SELECT id_votacao, id_proposicao, bln_orgao_teste FROM refined.votacao"
    ).fetchall()
    por_id = {i: (prop, teste) for i, prop, teste in linhas}
    tipo_id = con.execute(
        "SELECT any_value(typeof(id_votacao)) FROM refined.votacao"
    ).fetchall()

    # ASSERT
    assert por_id["2576389-4"] == (None, True)  # muda: '0' -> NULL; TESTECOM -> flag
    assert por_id["2576390-1"] == (123, False)  # não muda
    assert tipo_id == [("VARCHAR",)]  # id continua texto, igual ao da raw


def test_deputado_dimensao_cobre_os_fatos(con):
    # ARRANGE: uris com id de 5 e de 6 dígitos
    uri = "https://dadosabertos.camara.leg.br/api/v2/deputados/"
    inserir(
        con,
        "deputados",
        [
            {
                "uri": uri + "12345",
                "nome": "EX COM PRESENCA",
                "idLegislaturaFinal": "50",
            },
            {"uri": uri + "67890", "nome": "EX SEM FATO", "idLegislaturaFinal": "50"},
            {"uri": uri + "123456", "nome": "ATUAL", "idLegislaturaFinal": "57"},
        ],
    )
    inserir(con, "eventosPresencaDeputados", [{"idEvento": "1", "idDeputado": "12345"}])

    # ACT
    rodar(con, "refined", "deputado")
    por_id = dict(
        con.execute(
            "SELECT id_deputado, bln_legislatura_atual FROM refined.deputado"
        ).fetchall()
    )

    # ASSERT
    assert (
        por_id[12345] is False
    )  # muda: legislatura 50 com presença entra, sem ser atual
    assert 67890 not in por_id  # não muda: legislatura 50 sem fato fica fora
    assert por_id[123456] is True  # legislatura 57 entra; id de 6 dígitos inteiro
    assert set(por_id) == {12345, 123456}


def test_evento_realizado(con):
    # ARRANGE
    inserir(
        con,
        "eventos",
        [
            {"id": "1", "situacao": "Encerrada (Termo)"},
            {"id": "2", "situacao": "Cancelada"},
        ],
    )

    # ACT
    rodar(con, "refined", "evento")
    por_id = dict(
        con.execute("SELECT id_evento, bln_realizado FROM refined.evento").fetchall()
    )

    # ASSERT
    assert por_id == {1: True, 2: False}
