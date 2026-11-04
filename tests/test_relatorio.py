"""Testes do relatório (spec 05): o Python só lê e desenha.

Cada gráfico recebe um DataFrame inventado de 3 a 5 linhas. O teste da regra principal é
"os valores desenhados são exatamente os da coluna do mart, na ordem esperada": se alguém
colocar uma conta no Python, o valor desenhado deixa de bater com o do DataFrame.
"""

import pandas as pd
import pytest

from pipeline import db, relatorio


def _x(fig, i=0):
    return list(fig.data[i].x)


def _y(fig, i=0):
    return list(fig.data[i].y)


def test_grafico_01_mais_e_menos_presentes():
    # ARRANGE
    df = pd.DataFrame(
        {
            "des_nome": ["ANA", "BIA", "CAIO", "DUDA"],
            "cod_partido": ["PT", None, "PL", "PSD"],
            "qtd_eventos_presente": [10, 0, 30, 0],
        }
    )

    # ACT
    fig = relatorio.grafico_01(df)

    # ASSERT
    assert len(fig.data) == 2
    assert _x(fig, 0) == [30, 10, 0, 0]  # mais: decrescente; empate por nome
    assert _y(fig, 0) == ["CAIO (PL)", "ANA (PT)", "BIA (sem partido)", "DUDA (PSD)"]
    assert _x(fig, 1) == [0, 0, 10, 30]  # menos: crescente; empate por nome
    assert _y(fig, 1)[0] == "BIA (sem partido)"


def test_grafico_02_amostra_insuficiente_orienta_pelo_bloco():
    # ARRANGE
    df = pd.DataFrame(
        {
            "cod_partido": ["PT", "NOVO", "SOLIDARIEDADE"],
            "pct_cobertura": [60.0, 95.0, 4.3],
            "bln_amostra_suficiente": [True, True, False],
            "pct_fidelidade": [97.5, 99.2, None],
        }
    )

    # ACT
    fig = relatorio.grafico_02(df)

    # ASSERT
    assert len(fig.data) == 2
    assert _x(fig, 0) == [99.2, 97.5]  # barras só para a amostra suficiente, ordenadas
    assert _y(fig, 0) == ["NOVO", "PT"]
    assert _y(fig, 1) == ["SOLIDARIEDADE"]
    assert list(fig.data[1].text) == ["orienta pelo bloco (cobertura 4,3%)"]
    assert list(fig.layout.yaxis.categoryarray) == [
        "NOVO",
        "PT",
        "SOLIDARIEDADE",
    ]  # no fim


def test_grafico_03_coesao_ordenada():
    # ARRANGE
    df = pd.DataFrame(
        {
            "cod_partido": ["PT", "REDE", "PL"],
            "qtd_votacoes": [400, 41, 420],
            "pct_coesao_media": [95.1, 93.3, 97.0],
        }
    )

    # ACT
    fig = relatorio.grafico_03(df)

    # ASSERT
    assert len(fig.data) == 1
    assert _x(fig) == [97.0, 95.1, 93.3]
    assert list(fig.data[0].customdata) == [
        420,
        400,
        41,
    ]  # qtd_votacoes no hover, sem conta


def test_grafico_04_plenario_comissao_e_apertadas_pela_flag():
    # ARRANGE
    df = pd.DataFrame(
        {
            "id_votacao": ["A", "B", "C", "D"],
            "data_votacao": pd.to_datetime(
                ["2025-03-01", "2025-04-01", "2025-05-01", "2025-06-01"]
            ),
            "cod_orgao": ["PLEN", "CCJC", "PLEN", "CE"],
            "pct_margem": [40.0, 12.5, 2.4, 3.7],
            "bln_apertada": [False, False, True, True],
            "bln_plenario": [True, False, True, False],
        }
    )

    # ACT
    fig = relatorio.grafico_04(df)

    # ASSERT
    assert len(fig.data) == 3
    assert _y(fig, 0) == [40.0]  # Plenário (não apertada)
    assert _y(fig, 1) == [12.5]  # comissões (não apertada)
    assert _y(fig, 2) == [2.4, 3.7]  # apertadas, em destaque
    assert list(fig.data[2].marker.symbol) == [
        "circle",
        "diamond",
    ]  # símbolo pela bln_plenario


def test_grafico_05_empilhado_pelos_grupos_e_ordenado_pelo_total():
    # ARRANGE
    df = pd.DataFrame(
        {
            "des_tema": ["Saúde", "Saúde", "Educação", "Educação", "Esporte"],
            "cod_tipo_grupo": ["PL", "RIC", "PL", "Outros", "INC"],
            "qtd_proposicoes": [5, 3, 10, 2, 1],
            "qtd_proposicoes_tema": [8, 8, 12, 12, 1],
            "qtd_deputados": [4, 2, 6, 1, 1],
        }
    )

    # ACT
    fig = relatorio.grafico_05(df)

    # ASSERT
    assert [t.name for t in fig.data] == ["PL", "RIC", "INC", "Outros"]
    assert _x(fig, 0) == [10, 5]  # PL: Educação, Saúde
    assert _x(fig, 1) == [3]
    assert _x(fig, 2) == [1]
    assert _x(fig, 3) == [2]
    assert list(fig.layout.yaxis.categoryarray) == ["Educação", "Saúde", "Esporte"]
    assert fig.layout.barmode == "stack"


def test_grafico_06_os_20_maiores_medias():
    # ARRANGE
    df = pd.DataFrame(
        {
            "des_nome": ["ANA", "BIA", "CAIO"],
            "cod_partido": ["PT", "PL", "PSD"],
            "cod_uf": ["SP", "RJ", "MG"],
            "vlr_total": [
                120001.0,
                50000.0,
                0.0,
            ],  # 120001/12 != 10000: recalcular no Python não bate
            "qtd_meses_com_despesa": [12, 2, 0],
            "vlr_media_mensal": [10000.0, 25000.0, None],
        }
    )

    # ACT
    fig = relatorio.grafico_06(df)

    # ASSERT
    assert _x(fig) == [25000.0, 10000.0]  # NULL fora do ranking
    assert [list(c) for c in fig.data[0].customdata] == [[50000.0, 2], [120001.0, 12]]


def test_grafico_07_subcotas_com_negativo():
    # ARRANGE
    df = pd.DataFrame(
        {
            "des_subcota": ["DIVULGAÇÃO", "AUXÍLIO-MORADIA", "TELEFONIA"],
            "qtd_despesas": [100, 50, 30],
            "vlr_total": [1000.0, -200.0, 50.0],
            "pct_total": [117.6, -23.5, 5.9],
        }
    )

    # ACT
    fig = relatorio.grafico_07(df)

    # ASSERT
    assert _x(fig) == [
        1000.0,
        50.0,
        -200.0,
    ]  # o negativo fica no fim, à esquerda do zero


def test_grafico_08_meses_em_portugues():
    # ARRANGE
    df = pd.DataFrame(
        {
            "data_competencia": pd.to_datetime(
                ["2025-02-01", "2025-01-01", "2025-12-01"]
            ),
            "qtd_despesas": [20, 10, 5],
            "vlr_total": [200.0, 100.0, 180.0],
        }
    )

    # ACT
    fig = relatorio.grafico_08(df)

    # ASSERT
    assert _x(fig) == ["jan/2025", "fev/2025", "dez/2025"]
    assert _y(fig) == [100.0, 200.0, 180.0]


def test_grafico_09_uf_por_deputado_mes():
    # ARRANGE
    df = pd.DataFrame(
        {
            "cod_uf": ["SP", "AP", "MG"],
            "qtd_deputados": [78, 14, 56],
            "qtd_deputado_meses": [800, 100, 600],
            "vlr_medio_deputado_mes": [30000.0, 45000.0, 35000.0],
        }
    )

    # ACT
    fig = relatorio.grafico_09(df)

    # ASSERT
    assert _x(fig) == [45000.0, 35000.0, 30000.0]
    assert _y(fig) == ["AP", "MG", "SP"]


def test_grafico_10_pareto_com_quem_cruza_os_80():
    # ARRANGE
    df = pd.DataFrame(
        {
            "num_posicao": [2, 1, 3, 4],
            "des_fornecedor": ["GOL", "TAM", "AZUL", "RAMAL"],
            "pct_acumulado": [70.0, 50.0, 85.0, 100.0],
            "bln_top_80": [True, True, True, False],
        }
    )

    # ACT
    fig = relatorio.grafico_10(df)

    # ASSERT
    assert len(fig.data) == 2
    assert _x(fig, 0) == [1, 2, 3, 4]
    assert _y(fig, 0) == [50.0, 70.0, 85.0, 100.0]
    assert _x(fig, 1) == [3]  # o último com bln_top_80 é o que cruza a linha
    assert fig.layout.xaxis.type == "log"


def test_grafico_11_menor_participacao():
    # ARRANGE
    df = pd.DataFrame(
        {
            "des_nome": ["ANA", "BIA", "CAIO"],
            "cod_partido": ["PT", "PL", None],
            "data_primeiro_voto": pd.to_datetime(["2025-02-04", "2025-08-01", None]),
            "data_ultimo_voto": pd.to_datetime(["2025-12-17", "2025-12-17", None]),
            "qtd_votacoes_no_periodo": [429, 100, 0],
            "qtd_votos_registrados": [400, 20, 0],
            "pct_participacao": [93.2, 20.0, None],
        }
    )

    # ACT
    fig = relatorio.grafico_11(df)

    # ASSERT
    assert _x(fig) == [20.0, 93.2]  # crescente; quem não votou (NULL) fica fora
    assert fig.data[0].customdata[0][0] == "01/08/2025 a 17/12/2025"


def test_grafico_12_pontos_sem_box_nem_histograma():
    # ARRANGE
    df = pd.DataFrame(
        {
            "des_nome": ["ANA", "BIA", "CAIO", "DUDA"],
            "cod_partido": ["PT", "PL", "PT", "PL"],
            "qtd_votos_orientados": [300, 250, 4, 280],
            "bln_amostra_suficiente": [True, True, False, True],
            "pct_alinhamento": [95.0, 20.0, None, 30.0],
        }
    )

    # ACT
    fig = relatorio.grafico_12(df)

    # ASSERT
    assert {t.type for t in fig.data} == {"scatter"}
    assert not [t for t in fig.data if t.type in ("box", "histogram", "violin")]
    assert _x(fig) == ["PL", "PL", "PT"]  # só amostra suficiente, um ponto por deputado
    assert _y(fig) == [20.0, 30.0, 95.0]


def test_montar_html_3_abas_12_cartoes_e_plotly_uma_vez():
    # ARRANGE
    figura = relatorio.grafico_08(
        pd.DataFrame(
            {
                "data_competencia": pd.to_datetime(["2025-01-01"]),
                "qtd_despesas": [1],
                "vlr_total": [1.0],
            }
        )
    )
    secoes = [
        relatorio.Secao(n, f"título {n}", "frase", figura, ["nota"])
        for n in range(1, 13)
    ]

    # ACT
    pagina = relatorio.montar_html(secoes, "03/11/2026", [("rótulo", "1")])

    # ASSERT
    assert pagina.count('<button role="tab"') == 3
    assert pagina.count('<section role="tabpanel"') == 3
    assert pagina.count('<article class="cartao"') == 12
    assert pagina.count("plotly.js v") == 1  # o script do Plotly embutido uma vez só
    assert pagina.count("<details>") == 12  # "Como ler" fechado em cada cartão
    assert '"displayModeBar": false' in pagina
    assert "Retrato de 03/11/2026" in pagina
    assert "dadosabertos.camara.leg.br" in pagina
    # Votações (2, 3, 4, 11, 12) é a aba inicial; as outras começam escondidas
    votacoes = pagina.index('id="painel-votacoes"')
    assert pagina.index('id="indicador-02"') > votacoes
    assert pagina.index('id="indicador-12"') < pagina.index('id="painel-atividade"')
    assert pagina.count(" hidden>") == 2
    # dentro de cada aba, ordem numérica
    posicoes = [
        pagina.index(f'id="indicador-{n:02d}"')
        for n in (2, 3, 4, 11, 12, 1, 5, 6, 7, 8, 9, 10)
    ]
    assert posicoes == sorted(posicoes)


def test_cartoes_resumo_mostram_o_valor_do_mart():
    # ARRANGE: valores inventados, quebrados de propósito (uma conta no Python não bateria)
    df = pd.DataFrame(
        {
            "vlr_total_cota": [1234567.89],
            "qtd_deputados": [512],
            "qtd_votacoes_nominais": [480],
            "qtd_votacoes_apertadas": [9],
            "qtd_fornecedores": [17001],
            "qtd_fornecedores_top80": [1300],
        }
    )

    # ACT
    cartoes = relatorio.cartoes_resumo(df)

    # ASSERT
    assert [valor for _, valor in cartoes] == [
        "R$ 1.234.567,89",
        "512",
        "480",
        "9",
        "17.001",
        "1.300",
    ]


def test_relatorio_main_sem_banco(tmp_path, monkeypatch, capsys):
    # ARRANGE
    inexistente = tmp_path / "nao_existe.duckdb"
    monkeypatch.setattr(relatorio, "CAMINHO_BANCO", inexistente)
    monkeypatch.setattr(db, "CAMINHO_BANCO", inexistente)

    # ACT
    with pytest.raises(SystemExit) as saida:
        relatorio.main()

    # ASSERT
    assert saida.value.code == 1
    assert not inexistente.exists()
    assert "não existe" in capsys.readouterr().err  # e não a mensagem de banco travado
