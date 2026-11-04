from conftest import inserir, rodar


def test_despesa_uf_na_vira_nulo(con):
    # ARRANGE: as 3 linhas inventadas
    inserir(
        con,
        "ceap",
        [
            {
                "txNomeParlamentar": "Deputado Teste SP",
                "sgUF": "SP",
                "ideCadastro": "1",
            },
            {"txNomeParlamentar": "LIDERANÇA TESTE", "sgUF": "NA", "ideCadastro": None},
            {
                "txNomeParlamentar": "Deputado Teste Sem UF",
                "sgUF": None,
                "ideCadastro": "2",
            },
        ],
    )

    # ACT: roda o SQL de verdade do projeto
    rodar(con, "refined", "despesa")
    uf_por_nome = dict(
        con.execute(
            "SELECT des_nome_parlamentar, cod_uf FROM refined.despesa"
        ).fetchall()
    )

    # ASSERT
    assert uf_por_nome["LIDERANÇA TESTE"] is None  # muda: 'NA' -> NULL
    assert uf_por_nome["Deputado Teste SP"] == "SP"  # não muda
    assert uf_por_nome["Deputado Teste Sem UF"] is None  # NULL da raw continua NULL
