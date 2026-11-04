"""Testes das regras dos marts (spec 04, M1 a M7).

Cada teste monta a raw inventada e passa pelo refined de verdade (raw -> refined ->
marts): um mart nunca é testado em cima de um refined que não existiria.
"""

from decimal import Decimal

from conftest import inserir, montar_refined, rodar

URI_DEP = "https://dadosabertos.camara.leg.br/api/v2/deputados/"


def _deputados(con, ids_legislatura: dict[str, str]) -> None:
    inserir(
        con,
        "deputados",
        [
            {"uri": URI_DEP + i, "nome": f"DEP {i}", "idLegislaturaFinal": leg}
            for i, leg in ids_legislatura.items()
        ],
    )


def _votacoes(con, votacoes: list[dict]) -> None:
    # Nominal = placar > 0; o padrão é PLEN, 2025-03-01, 1 x 0, aprovada.
    padrao = {
        "siglaOrgao": "PLEN",
        "data": "2025-03-01",
        "votosSim": "1",
        "votosNao": "0",
        "votosOutros": "0",
        "aprovacao": "1",
    }
    inserir(con, "votacoes", [padrao | v for v in votacoes])


def test_dim_deputado_universo(con):
    # ARRANGE: dois deputados da 57; só um tem fato em 2025 (uma despesa)
    _deputados(con, {"1001": "57", "1002": "57"})
    inserir(con, "ceap", [{"ideCadastro": "1001", "vlrLiquido": "10.00"}])
    montar_refined(con)

    # ACT
    rodar(con, "marts", "dim_Deputado")
    por_id = dict(
        con.execute(
            "SELECT id_deputado, bln_universo_2025 FROM marts.dim_Deputado"
        ).fetchall()
    )

    # ASSERT
    assert por_id[1001] is True  # muda: 57 com despesa entra no universo
    assert por_id[1002] is False  # não muda: 57 sem nenhum fato fica fora


def test_fidelidade_partido_regra_de_fiel(con):
    # ARRANGE: PCdoB orienta pela federação "Fdr PT-PCdoB-PV" (de-para de verdade)
    bancada = "Fdr PT-PCdoB-PV"
    _votacoes(con, [{"id": f"V{n}"} for n in range(1, 6)])
    inserir(
        con,
        "votacoesOrientacoes",
        [
            {"idVotacao": "V1", "siglaBancada": bancada, "orientacao": "Obstrução"},
            {"idVotacao": "V2", "siglaBancada": bancada, "orientacao": "Sim"},
            {"idVotacao": "V3", "siglaBancada": bancada, "orientacao": "Liberado"},
            {"idVotacao": "V4", "siglaBancada": bancada, "orientacao": None},
            {"idVotacao": "V5", "siglaBancada": bancada, "orientacao": "Sim"},
        ],
    )
    voto = {"deputado_id": "2001", "deputado_siglaPartido": "PCdoB"}
    inserir(
        con,
        "votacoesVotos",
        [
            voto | {"idVotacao": "V1", "voto": "Não"},  # Obstrução + Não: infiel
            voto | {"idVotacao": "V2", "voto": "Sim"},  # fiel
            voto | {"idVotacao": "V3", "voto": "Sim"},  # Liberado: fora
            voto | {"idVotacao": "V4", "voto": "Sim"},  # orientação NULL: fora
            voto | {"idVotacao": "V5", "voto": "Artigo 17"},  # presidente: fora
        ],
    )
    montar_refined(con)

    # ACT
    rodar(con, "marts", "agg_Fidelidade_Partido")
    votos, orientados, fieis = con.execute(
        "SELECT qtd_votos, qtd_votos_orientados, qtd_votos_fieis "
        "FROM marts.agg_Fidelidade_Partido WHERE cod_partido = 'PCdoB'"
    ).fetchall()[0]

    # ASSERT
    assert votos == 5
    assert (
        orientados == 2
    )  # só V1 e V2: PCdoB casou com a federação; Liberado/NULL/Artigo 17 fora
    assert fieis == 1  # Obstrução + Não não é fiel


def test_fidelidade_partido_corte_de_20(con):
    # ARRANGE: 10 votos do PL, só 1 em votação com orientação (cobertura 10%)
    _votacoes(con, [{"id": f"V{n}"} for n in range(10)])
    inserir(
        con,
        "votacoesOrientacoes",
        [{"idVotacao": "V0", "siglaBancada": "PL", "orientacao": "Sim"}],
    )
    inserir(
        con,
        "votacoesVotos",
        [
            {
                "idVotacao": f"V{n}",
                "deputado_id": "3001",
                "deputado_siglaPartido": "PL",
                "voto": "Sim",
            }
            for n in range(10)
        ],
    )
    montar_refined(con)

    # ACT
    rodar(con, "marts", "agg_Fidelidade_Partido")
    linhas = con.execute(
        "SELECT pct_cobertura, bln_amostra_suficiente, pct_fidelidade "
        "FROM marts.agg_Fidelidade_Partido WHERE cod_partido = 'PL'"
    ).fetchall()

    # ASSERT
    assert len(linhas) == 1  # não muda: o partido continua no mart
    assert linhas[0] == (Decimal("10.0"), False, None)  # muda: sem valor, com o motivo


def test_coesao_partido_grupos(con):
    # ARRANGE: V1 com 4 deputados do PT (2 Sim x 2 Não); V2 com só 2 deputados do PT
    _votacoes(con, [{"id": "V1"}, {"id": "V2"}])
    pt = {"deputado_siglaPartido": "PT"}
    inserir(
        con,
        "votacoesVotos",
        [
            pt | {"idVotacao": "V1", "deputado_id": "1", "voto": "Sim"},
            pt | {"idVotacao": "V1", "deputado_id": "2", "voto": "Sim"},
            pt | {"idVotacao": "V1", "deputado_id": "3", "voto": "Não"},
            pt | {"idVotacao": "V1", "deputado_id": "4", "voto": "Não"},
            pt | {"idVotacao": "V2", "deputado_id": "1", "voto": "Sim"},
            pt | {"idVotacao": "V2", "deputado_id": "2", "voto": "Sim"},
        ],
    )
    montar_refined(con)

    # ACT
    rodar(con, "marts", "agg_Coesao_Partido")
    linha = con.execute(
        "SELECT qtd_votacoes, pct_coesao_media FROM marts.agg_Coesao_Partido "
        "WHERE cod_partido = 'PT'"
    ).fetchall()

    # ASSERT: só V1 conta (V2 tem 2 deputados), e o empate 2 x 2 dá 50%
    assert linha == [(1, Decimal("50.0"))]


def test_votacao_apertada_contra_o_placar(con):
    # ARRANGE
    _votacoes(
        con,
        [
            {
                "id": "A",
                "votosSim": "10",
                "votosNao": "20",
                "aprovacao": "1",
            },  # aprovada com mais Não
            {
                "id": "N",
                "votosSim": "5",
                "votosNao": "3",
                "aprovacao": None,
            },  # resultado desconhecido
            {
                "id": "EA",
                "votosSim": "10",
                "votosNao": "10",
                "aprovacao": "1",
            },  # empate aprovado
            {
                "id": "ER",
                "votosSim": "10",
                "votosNao": "10",
                "aprovacao": "0",
            },  # empate rejeitado
        ],
    )
    montar_refined(con)

    # ACT
    rodar(con, "marts", "agg_Votacao_Apertada")
    por_id = dict(
        con.execute(
            "SELECT id_votacao, bln_resultado_contra_placar FROM marts.agg_Votacao_Apertada"
        ).fetchall()
    )

    # ASSERT
    assert por_id["A"] is True  # muda
    assert por_id["N"] is None  # muda: sem resultado, sem flag
    assert por_id["EA"] is False  # não muda: empate quem decide é o desempate
    assert por_id["ER"] is False


def test_fornecedor_pareto_chave(con):
    # ARRANGE: 2 filiais da mesma raiz e 2 CNPJs fictícios "00000000..."
    inserir(
        con,
        "ceap",
        [
            {
                "txtFornecedor": "EMPRESA",
                "txtCNPJCPF": "11.222.333/0001-01",
                "vlrLiquido": "100",
            },
            {
                "txtFornecedor": "EMPRESA",
                "txtCNPJCPF": "11.222.333/0002-02",
                "vlrLiquido": "50",
            },
            {
                "txtFornecedor": "CELULAR",
                "txtCNPJCPF": "00.000.000/0000-01",
                "vlrLiquido": "30",
            },
            {
                "txtFornecedor": "RAMAL",
                "txtCNPJCPF": "00.000.000/0000-06",
                "vlrLiquido": "20",
            },
        ],
    )
    montar_refined(con)

    # ACT
    rodar(con, "marts", "agg_Fornecedor_Pareto")
    por_chave = {
        chave: (ficticio, valor)
        for chave, ficticio, valor in con.execute(
            "SELECT cod_fornecedor, bln_cnpj_ficticio, vlr_total FROM marts.agg_Fornecedor_Pareto"
        ).fetchall()
    }

    # ASSERT
    assert por_chave["11222333"] == (
        False,
        Decimal("150.00"),
    )  # muda: 2 filiais, 1 fornecedor
    assert por_chave["00000000000001"] == (
        True,
        Decimal("30.00"),
    )  # não muda: fictício completo
    assert por_chave["00000000000006"] == (True, Decimal("20.00"))
    assert len(por_chave) == 3


def test_participacao_deputado_janela(con):
    # ARRANGE: 4 nominais do Plenário no ano e 1 de comissão no fim do ano
    _votacoes(
        con,
        [
            {"id": "P1", "data": "2025-02-10"},
            {"id": "P2", "data": "2025-06-10"},
            {"id": "P3", "data": "2025-11-10"},
            {"id": "C1", "data": "2025-11-20", "siglaOrgao": "CCJC"},
            {"id": "P4", "data": "2025-12-10"},
        ],
    )
    _deputados(
        con, {"4001": "57", "4002": "57"}
    )  # 4001 titular; 4002 suplente de novembro
    voto = {"voto": "Sim", "deputado_siglaPartido": "PT"}
    inserir(
        con,
        "votacoesVotos",
        [
            voto | {"idVotacao": p, "deputado_id": "4001"}
            for p in ["P1", "P2", "P3", "P4"]
        ]
        + [voto | {"idVotacao": v, "deputado_id": "4002"} for v in ["P3", "C1", "P4"]],
    )
    montar_refined(con)
    rodar(con, "marts", "dim_Deputado")

    # ACT
    rodar(con, "marts", "agg_Participacao_Deputado")
    por_id = {
        i: (periodo, registrados)
        for i, periodo, registrados in con.execute(
            "SELECT id_deputado, qtd_votacoes_no_periodo, qtd_votos_registrados "
            "FROM marts.agg_Participacao_Deputado"
        ).fetchall()
    }

    # ASSERT
    assert por_id[4002] == (2, 2)  # muda: só P3 e P4 (da posse em diante); C1 não entra
    assert por_id[4001] == (4, 4)  # não muda: o titular tem o ano inteiro de Plenário
