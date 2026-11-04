"""Gera docs/relatorio.html: um arquivo só, offline, com os 12 indicadores.

Uso: uv run python -m pipeline.relatorio

Spec: docs/specs/05-relatorio.md. Resumo das regras e dos motivos:

- Regra principal: o relatório não calcula nada. O Python só lê e desenha:
  nada de soma, média, contagem, divisão, agrupamento ou percentil, nem no
  pandas nem no Plotly (histograma e boxplot proibidos: calculam faixa e
  quartil por baixo). Permitido: ordenar, escolher as N primeiras linhas,
  filtrar por uma flag que o mart já traz, formatar e renomear. Número que
  nenhum mart tem vai para um mart novo, não para cá (por isso existem o
  agg_Proposicao_Tema e o agg_Resumo dos cartões).
- Uma função por gráfico, grafico_<nn>(df) -> go.Figure, sem acesso ao banco:
  recebe o DataFrame pronto, o que permite testar com dado inventado.
- Banco aberto em read_only=True (o relatório não escreve). Com o ui.py
  aberto, o DuckDB recusa até a conexão só leitura de outro processo: é caso
  normal, avisa "feche o ui.py" e sai.
- Plotly embutido uma vez só (include_plotlyjs="inline" no primeiro gráfico):
  o arquivo abre sem internet e pode ir para o GitHub Pages.
- Layout de dashboard (adendo): cabeçalho escuro, cartões de destaque lidos
  do agg_Resumo, 3 abas (Votações, Atividade, Cota) com JS pequeno embutido,
  um cartão por gráfico em grade de 2 colunas, "Como ler" em <details>,
  barra do Plotly escondida, rankings com top 10 (gráficos 1, 6 e 11).
- Rótulo de valor não é cortado: cliponaxis=False e margem direita maior; o
  range do eixo não é calculado a partir dos valores (seria cálculo).
- Números no padrão brasileiro (separators ",."), R$ no eixo do dinheiro.
- Cores: um destaque e cinzas; o que a cor diz também está no rótulo.
"""

import html
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pipeline.db import CAMINHO_BANCO

ARQUIVO_RELATORIO = Path(__file__).resolve().parent.parent / "docs" / "relatorio.html"
URL_FONTE = "https://dadosabertos.camara.leg.br"
URL_REPOSITORIO = "https://github.com/erickdouglas2603-gif/camara-pipeline"

DESTAQUE = "#1f5fa8"
CINZA = "#8a9099"
CINZAS = ["#4d535c", "#8a9099", "#c3c7cd"]
GRUPOS_TIPO = ["PL", "RIC", "INC", "Outros"]  # ordem do empilhamento (gráfico 5)
TOP = 10  # rankings dos gráficos 1, 6 e 11
MARGEM_ROTULO = 90  # px à direita para o rótulo de valor da barra mais longa

# Um mart por gráfico, na ordem 1 a 12; o resumo alimenta os cartões de destaque.
MARTS_DOS_GRAFICOS = {
    1: "agg_Presenca_Deputado",
    2: "agg_Fidelidade_Partido",
    3: "agg_Coesao_Partido",
    4: "agg_Votacao_Apertada",
    5: "agg_Proposicao_Tema",
    6: "agg_Gasto_Deputado",
    7: "agg_Gasto_Categoria",
    8: "agg_Gasto_Mensal",
    9: "agg_Gasto_UF",
    10: "agg_Fornecedor_Pareto",
    11: "agg_Participacao_Deputado",
    12: "agg_Alinhamento_Governo",
}
MART_RESUMO = "agg_Resumo"

# (id, nome, gráficos) na ordem da página; a primeira aba é a inicial.
ABAS = [
    ("votacoes", "Votações", [2, 3, 4, 11, 12]),
    ("atividade", "Atividade", [1, 5]),
    ("cota", "Cota", [6, 7, 8, 9, 10]),
]

# (campo do agg_Resumo, rótulo, é dinheiro?)
CARTOES_RESUMO = [
    ("vlr_total_cota", "gasto total da cota em 2025", True),
    ("qtd_deputados", "deputados no universo de 2025", False),
    ("qtd_votacoes_nominais", "votações nominais", False),
    ("qtd_votacoes_apertadas", "votações apertadas (margem < 5%)", False),
    ("qtd_fornecedores", "fornecedores pagos pela cota", False),
    ("qtd_fornecedores_top80", "fornecedores somam 80% do gasto", False),
]

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]  # fmt: skip


# --- formatação (permitida: só muda a aparência do número) ---------------------


def _num(valor, casas: int = 0) -> str:
    """1234567.8 -> '1.234.567,8' (padrão brasileiro)."""
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def _data(valor) -> str:
    return "" if pd.isna(valor) else pd.Timestamp(valor).strftime("%d/%m/%Y")


def _rotulo_deputado(df: pd.DataFrame) -> pd.Series:
    partido = df["cod_partido"].fillna("sem partido")
    return df["des_nome"] + " (" + partido + ")"


def _layout(fig: go.Figure, altura: int = 500, direita: int = 30, **extra) -> go.Figure:
    fig.update_layout(
        separators=",.",
        template="simple_white",
        height=altura,
        margin={"l": 10, "r": direita, "t": 40, "b": 40},
        font={"family": "system-ui, -apple-system, Segoe UI, sans-serif", "size": 12},
        legend={"orientation": "h", "y": 1.1, "x": 0},
        **extra,
    )
    return fig


# --- os 12 gráficos -------------------------------------------------------------


def grafico_01(df: pd.DataFrame) -> go.Figure:
    """Presença: os 10 com mais e os 10 com menos eventos (desempate por nome)."""
    mais = df.sort_values(
        ["qtd_eventos_presente", "des_nome"], ascending=[False, True]
    ).head(TOP)
    menos = df.sort_values(
        ["qtd_eventos_presente", "des_nome"], ascending=[True, True]
    ).head(TOP)
    titulos = [f"Os {TOP} com mais eventos", f"Os {TOP} com menos eventos"]
    # Um embaixo do outro: lado a lado, os nomes não cabem num cartão de meia largura.
    # Eixo x compartilhado: com eixo próprio, a barra de 1 evento ocupava a largura toda.
    fig = make_subplots(
        rows=2, cols=1, subplot_titles=titulos, vertical_spacing=0.1, shared_xaxes=True
    )
    for linha, (parte, cor, nome) in enumerate(
        [(mais, DESTAQUE, titulos[0]), (menos, CINZA, titulos[1])], start=1
    ):
        fig.add_trace(
            go.Bar(
                x=parte["qtd_eventos_presente"],
                y=_rotulo_deputado(parte),
                orientation="h",
                marker_color=cor,
                name=nome,
                text=parte["qtd_eventos_presente"],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="%{y}: %{x} eventos<extra></extra>",
            ),
            row=linha,
            col=1,
        )
        fig.update_yaxes(autorange="reversed", row=linha, col=1)
    return _layout(fig, altura=640, direita=MARGEM_ROTULO, showlegend=False)


def grafico_02(df: pd.DataFrame) -> go.Figure:
    """Fidelidade: partidos com amostra suficiente em barras; os demais no fim, sem barra."""
    suficientes = df[
        df["bln_amostra_suficiente"] == True
    ].sort_values(  # NULL fica fora
        ["pct_fidelidade", "cod_partido"], ascending=[False, True]
    )
    insuficientes = df[df["bln_amostra_suficiente"] != True].sort_values(
        ["pct_cobertura", "cod_partido"], ascending=[False, True]
    )
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=suficientes["pct_fidelidade"],
            y=suficientes["cod_partido"],
            orientation="h",
            marker_color=DESTAQUE,
            name="fidelidade (% dos votos orientados)",
            text=[f"{_num(v, 1)}%" for v in suficientes["pct_fidelidade"]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:.1f}% de fidelidade<extra></extra>",
        )
    )
    rotulos = [
        f"orienta pelo bloco (cobertura {_num(v, 1)}%)"
        for v in insuficientes["pct_cobertura"]
    ]
    fig.add_trace(
        go.Scatter(
            x=[0] * len(insuficientes),
            y=insuficientes["cod_partido"],
            mode="text",
            text=rotulos,
            textposition="middle right",
            textfont={"color": CINZAS[0]},
            cliponaxis=False,
            name="amostra insuficiente",
            hovertemplate="%{y}: %{text}<extra></extra>",
        )
    )
    fig.update_yaxes(
        autorange="reversed",
        categoryorder="array",
        categoryarray=list(suficientes["cod_partido"])
        + list(insuficientes["cod_partido"]),
    )
    fig.update_xaxes(range=[0, 105], ticksuffix="%")
    return _layout(fig, altura=600, direita=MARGEM_ROTULO, showlegend=False)


def grafico_03(df: pd.DataFrame) -> go.Figure:
    """Coesão média por partido, ordenada."""
    ordenado = df.sort_values(
        ["pct_coesao_media", "cod_partido"], ascending=[False, True]
    )
    fig = go.Figure(
        go.Bar(
            x=ordenado["pct_coesao_media"],
            y=ordenado["cod_partido"],
            orientation="h",
            marker_color=DESTAQUE,
            customdata=ordenado["qtd_votacoes"],
            text=[f"{_num(v, 1)}%" for v in ordenado["pct_coesao_media"]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: coesão %{x:.1f}% em %{customdata} votações<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(range=[0, 105], ticksuffix="%")
    return _layout(fig, altura=600, direita=MARGEM_ROTULO, showlegend=False)


def grafico_04(df: pd.DataFrame) -> go.Figure:
    """Margem das votações nominais no tempo; Plenário x comissões pela flag; apertadas em destaque."""
    apertada = df["bln_apertada"] == True  # NULL não é apertada
    plenario = df["bln_plenario"] == True
    fig = go.Figure()
    for filtro, nome, simbolo in [
        (plenario & ~apertada, "Plenário", "circle"),
        (~plenario & ~apertada, "Comissões", "diamond"),
    ]:
        parte = df[filtro].sort_values(["data_votacao", "id_votacao"])
        fig.add_trace(
            go.Scatter(
                x=parte["data_votacao"],
                y=parte["pct_margem"],
                mode="markers",
                name=nome,
                marker={"symbol": simbolo, "color": CINZA, "size": 7, "opacity": 0.7},
                customdata=parte[["id_votacao", "cod_orgao"]],
                hovertemplate="%{customdata[0]} (%{customdata[1]})<br>"
                "%{x|%d/%m/%Y}: margem %{y:.1f}%<extra></extra>",
            )
        )
    destaque = df[apertada].sort_values(["data_votacao", "id_votacao"])
    fig.add_trace(
        go.Scatter(
            x=destaque["data_votacao"],
            y=destaque["pct_margem"],
            mode="markers",
            name="apertada (margem < 5%)",
            marker={
                "symbol": [
                    "circle" if p else "diamond" for p in destaque["bln_plenario"]
                ],
                "color": DESTAQUE,
                "size": 11,
                "line": {"width": 1, "color": "white"},
            },
            customdata=destaque[["id_votacao", "cod_orgao"]],
            hovertemplate="apertada: %{customdata[0]} (%{customdata[1]})<br>"
            "%{x|%d/%m/%Y}: margem %{y:.1f}%<extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="%d/%m/%Y")
    fig.update_yaxes(
        title_text="margem entre Sim e Não", ticksuffix="%", rangemode="tozero"
    )
    return _layout(fig, altura=440)


def grafico_05(df: pd.DataFrame) -> go.Figure:
    """Proposições por tema, empilhadas pelos 4 grupos de tipo, ordenadas pelo total do tema."""
    ordenado = df.sort_values(
        ["qtd_proposicoes_tema", "des_tema"], ascending=[False, True]
    )
    temas = list(ordenado["des_tema"].drop_duplicates())  # só a ordem de exibição
    cores = dict(zip(GRUPOS_TIPO, [DESTAQUE, *CINZAS], strict=True))
    fig = go.Figure()
    for grupo in GRUPOS_TIPO:
        parte = ordenado[ordenado["cod_tipo_grupo"] == grupo]
        fig.add_trace(
            go.Bar(
                x=parte["qtd_proposicoes"],
                y=parte["des_tema"],
                orientation="h",
                name=grupo,
                marker_color=cores[grupo],
                customdata=parte[["qtd_proposicoes_tema", "qtd_deputados"]],
                hovertemplate=f"%{{y}} · {grupo}: %{{x}} proposições de %{{customdata[1]}} "
                "deputados<br>total do tema: %{customdata[0]}<extra></extra>",
            )
        )
    fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=temas)
    fig.update_xaxes(tickformat=",d")
    # Em barra horizontal empilhada o Plotly inverte a legenda; "normal" mantém PL, RIC, INC, Outros.
    return _layout(fig, altura=860, barmode="stack", legend_traceorder="normal")


def grafico_06(df: pd.DataFrame) -> go.Figure:
    """Os 10 maiores gastos médios mensais."""
    top = (
        df[df["vlr_media_mensal"].notna()]
        .sort_values(["vlr_media_mensal", "des_nome"], ascending=[False, True])
        .head(TOP)
    )
    fig = go.Figure(
        go.Bar(
            x=top["vlr_media_mensal"],
            y=_rotulo_deputado(top) + " " + top["cod_uf"].fillna(""),
            orientation="h",
            marker_color=DESTAQUE,
            customdata=top[["vlr_total", "qtd_meses_com_despesa"]],
            text=[f"R$ {_num(v, 0)}" for v in top["vlr_media_mensal"]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>média mensal R$ %{x:,.2f}<br>total R$ %{customdata[0]:,.2f} "
            "em %{customdata[1]} meses<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickprefix="R$ ", tickformat=",.0f")
    return _layout(fig, altura=440, direita=MARGEM_ROTULO, showlegend=False)


def _curto(texto: str, limite: int = 40) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def grafico_07(df: pd.DataFrame) -> go.Figure:
    """Gasto total por subcota (o negativo fica à esquerda do zero)."""
    ordenado = df.sort_values(["vlr_total", "des_subcota"], ascending=[False, True])
    # A parcela do total vai no nome da categoria, não fora da barra: o rótulo da barra
    # negativa (auxílio-moradia) cairia em cima dos nomes do eixo. Nome inteiro no hover.
    rotulos = [
        f"{_curto(nome)} · {_num(pct, 1)}%"
        for nome, pct in zip(
            ordenado["des_subcota"], ordenado["pct_total"], strict=True
        )
    ]
    fig = go.Figure(
        go.Bar(
            x=ordenado["vlr_total"],
            y=rotulos,
            orientation="h",
            marker_color=DESTAQUE,
            customdata=ordenado[["des_subcota", "pct_total", "qtd_despesas"]],
            hovertemplate="%{customdata[0]}<br>R$ %{x:,.2f} (%{customdata[1]:.1f}% do total)<br>"
            "%{customdata[2]} despesas<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickprefix="R$ ", tickformat=",.0f", nticks=4)
    return _layout(fig, altura=680, showlegend=False)


def grafico_08(df: pd.DataFrame) -> go.Figure:
    """Gasto por mês de competência."""
    ordenado = df.sort_values("data_competencia")
    rotulos = [
        f"{MESES[pd.Timestamp(d).month - 1]}/{pd.Timestamp(d).year}"
        for d in ordenado["data_competencia"]
    ]
    fig = go.Figure(
        go.Bar(
            x=rotulos,
            y=ordenado["vlr_total"],
            marker_color=DESTAQUE,
            customdata=ordenado["qtd_despesas"],
            hovertemplate="%{x}: R$ %{y:,.2f} em %{customdata} despesas<extra></extra>",
        )
    )
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    return _layout(fig, altura=400, showlegend=False)


def grafico_09(df: pd.DataFrame) -> go.Figure:
    """Gasto médio por deputado-mês, por UF."""
    ordenado = df.sort_values(
        ["vlr_medio_deputado_mes", "cod_uf"], ascending=[False, True]
    )
    fig = go.Figure(
        go.Bar(
            x=ordenado["vlr_medio_deputado_mes"],
            y=ordenado["cod_uf"],
            orientation="h",
            marker_color=DESTAQUE,
            customdata=ordenado[["qtd_deputados", "qtd_deputado_meses"]],
            text=[f"R$ {_num(v, 0)}" for v in ordenado["vlr_medio_deputado_mes"]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: R$ %{x:,.2f} por deputado-mês<br>%{customdata[0]} deputados, "
            "%{customdata[1]} deputado-meses<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickprefix="R$ ", tickformat=",.0f")
    return _layout(fig, altura=680, direita=MARGEM_ROTULO, showlegend=False)


def grafico_10(df: pd.DataFrame) -> go.Figure:
    """Pareto dos fornecedores: posição (escala log) x % acumulado, com a linha dos 80%."""
    ordenado = df.sort_values("num_posicao")
    cruza = ordenado[ordenado["bln_top_80"] == True].tail(1)  # o último dentro dos 80%
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ordenado["num_posicao"],
            y=ordenado["pct_acumulado"],
            mode="lines",
            name="% acumulado do gasto",
            line={"color": DESTAQUE, "width": 2},
            customdata=ordenado["des_fornecedor"],
            hovertemplate="%{x}º %{customdata}<br>acumulado %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cruza["num_posicao"],
            y=cruza["pct_acumulado"],
            mode="markers+text",
            name="fornecedor que cruza os 80%",
            marker={"color": CINZAS[0], "size": 10},
            text=[f"{_num(p)} fornecedores" for p in cruza["num_posicao"]],
            textposition="bottom right",
            hovertemplate="%{x}º fornecedor: acumulado %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_hline(
        y=80, line_dash="dash", line_color=CINZA, annotation_text="80% do gasto"
    )
    # dtick=1: só as potências de 10 (1, 10, 100...), sem os ticks intermediários 2 e 5.
    fig.update_xaxes(
        type="log",
        dtick=1,
        tickformat=",d",
        title_text="posição do fornecedor (escala log)",
    )
    fig.update_yaxes(ticksuffix="%", range=[0, 105])
    return _layout(fig, altura=420)


def grafico_11(df: pd.DataFrame) -> go.Figure:
    """Os 10 com menor participação nas nominais do Plenário (na janela de cada um)."""
    baixo = (
        df[df["pct_participacao"].notna()]
        .sort_values(["pct_participacao", "des_nome"], ascending=[True, True])
        .head(TOP)
    )
    periodo = [
        f"{_data(a)} a {_data(b)}"
        for a, b in zip(
            baixo["data_primeiro_voto"], baixo["data_ultimo_voto"], strict=True
        )
    ]
    fig = go.Figure(
        go.Bar(
            x=baixo["pct_participacao"],
            y=_rotulo_deputado(baixo),
            orientation="h",
            marker_color=DESTAQUE,
            customdata=list(
                zip(
                    periodo,
                    baixo["qtd_votos_registrados"],
                    baixo["qtd_votacoes_no_periodo"],
                    strict=True,
                )
            ),
            text=[f"{_num(v, 1)}%" for v in baixo["pct_participacao"]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:.1f}%<br>%{customdata[1]} de %{customdata[2]} votações<br>"
            "período: %{customdata[0]}<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(range=[0, 105], ticksuffix="%")
    return _layout(fig, altura=440, direita=MARGEM_ROTULO, showlegend=False)


def grafico_12(df: pd.DataFrame) -> go.Figure:
    """Alinhamento ao Governo: um ponto por deputado, agrupado por partido (sem boxplot)."""
    pontos = df[df["bln_amostra_suficiente"] == True].sort_values(
        ["cod_partido", "pct_alinhamento", "des_nome"]
    )
    fig = go.Figure(
        go.Scatter(
            x=pontos["cod_partido"],
            y=pontos["pct_alinhamento"],
            mode="markers",
            marker={"color": DESTAQUE, "size": 7, "opacity": 0.55},
            customdata=pontos[["des_nome", "qtd_votos_orientados"]],
            hovertemplate="%{customdata[0]} (%{x})<br>%{y:.1f}% alinhado em "
            "%{customdata[1]} votos orientados<extra></extra>",
        )
    )
    fig.update_yaxes(
        range=[0, 105],
        ticksuffix="%",
        title_text="votos iguais à orientação do Governo",
    )
    fig.update_xaxes(tickangle=-45)
    return _layout(fig, altura=480, showlegend=False)


# --- cartões de destaque (só leem o agg_Resumo) --------------------------------


def cartoes_resumo(df: pd.DataFrame) -> list[tuple[str, str]]:
    """(rótulo, valor formatado) de cada cartão; o valor é o do mart, só formatado."""
    linha = df.iloc[0]
    return [
        (rotulo, f"R$ {_num(linha[campo], 2)}" if dinheiro else _num(linha[campo]))
        for campo, rotulo, dinheiro in CARTOES_RESUMO
    ]


# --- tabelas abaixo dos gráficos (só seleção e formatação) ---------------------


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> str:
    th = "".join(f"<th>{html.escape(c)}</th>" for c in cabecalho)
    corpo = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in linha) + "</tr>"
        for linha in linhas
    )
    return (
        '<div class="rolagem"><table class="tabela">'
        f"<thead><tr>{th}</tr></thead><tbody>{corpo}</tbody></table></div>"
    )


def _linhas_votacao(df: pd.DataFrame) -> list[list[str]]:
    resultado = {True: "aprovada", False: "rejeitada"}
    return [
        [
            r.id_votacao,
            _data(r.data_votacao),
            r.cod_orgao,
            _num(r.qtd_votos_sim),
            _num(r.qtd_votos_nao),
            "" if pd.isna(r.pct_margem) else f"{_num(r.pct_margem, 1)}%",
            resultado.get(r.bln_aprovada, "sem resultado"),
        ]
        for r in df.sort_values(["data_votacao", "id_votacao"]).itertuples()
    ]


def tabelas_04(df: pd.DataFrame) -> str:
    cab = ["votação", "data", "órgão", "Sim", "Não", "margem", "resultado"]
    apertadas = df[df["bln_apertada"] == True]
    contra = df[df["bln_resultado_contra_placar"] == True]
    return (
        "<h4>Votações apertadas (margem menor que 5%)</h4>"
        + _tabela(cab, _linhas_votacao(apertadas))
        + "<h4>Resultado contra o placar</h4>"
        + _tabela(cab, _linhas_votacao(contra))
    )


def tabela_10(df: pd.DataFrame) -> str:
    top = df.sort_values("num_posicao").head(15)
    linhas = [
        [
            f"{r.num_posicao}º",
            r.des_fornecedor + (" (CNPJ fictício)" if r.bln_cnpj_ficticio else ""),
            r.tp_fornecedor,
            f"R$ {_num(r.vlr_total, 2)}",
            f"{_num(r.pct_acumulado, 1)}%",
        ]
        for r in top.itertuples()
    ]
    return "<h4>Os 15 maiores fornecedores</h4>" + _tabela(
        ["posição", "fornecedor", "tipo", "total", "acumulado"], linhas
    )


# --- página ---------------------------------------------------------------------


@dataclass
class Secao:
    numero: int
    titulo: str
    frase: str
    figura: go.Figure
    como_ler: list[str]
    extra_html: str = ""


_CSS = f"""
  :root {{ --fundo: #eef1f4; --cartao: #ffffff; --texto: #1d2329; --suave: #4d535c;
          --borda: #dfe3e8; --topo: #14202c; --destaque: {DESTAQUE}; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--texto);
         background: var(--fundo); line-height: 1.45; }}
  header {{ background: var(--topo); color: #fff; padding: 24px 16px 20px; }}
  .conteudo {{ max-width: 1280px; margin: 0 auto; padding: 0 16px; }}
  header .conteudo {{ padding: 0; }}
  h1 {{ margin: 0 0 6px; font-size: 26px; }}
  .meta {{ margin: 0; color: #c9d2dc; font-size: 14px; }}
  .meta a {{ color: #9cc3f0; }}
  .retrato {{ display: inline-block; background: rgba(255,255,255,.12); border-radius: 4px;
              padding: 2px 8px; margin-right: 8px; color: #fff; }}
  .resumo {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;
             margin: 20px auto 8px; }}
  .kpi {{ background: var(--cartao); border: 1px solid var(--borda); border-top: 3px solid var(--destaque);
          border-radius: 6px; padding: 12px 14px; }}
  .kpi .valor {{ font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums;
                 white-space: nowrap; }}
  .kpi .rotulo {{ color: var(--suave); font-size: 13px; }}
  [role="tablist"] {{ display: flex; gap: 4px; border-bottom: 2px solid var(--borda); margin: 16px 0; }}
  [role="tab"] {{ font: inherit; font-weight: 600; background: none; border: 0; padding: 10px 18px;
                 color: var(--suave); cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px; }}
  [role="tab"][aria-selected="true"] {{ color: var(--destaque); border-bottom-color: var(--destaque); }}
  [role="tab"]:focus-visible {{ outline: 2px solid var(--destaque); outline-offset: 2px; }}
  .grade {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding-bottom: 48px; }}
  @media (max-width: 900px) {{ .grade {{ grid-template-columns: minmax(0, 1fr); }} }}
  .cartao {{ background: var(--cartao); border: 1px solid var(--borda); border-radius: 6px; padding: 16px;
             min-width: 0; }}
  .cartao h2 {{ font-size: 17px; margin: 0 0 4px; }}
  .frase {{ color: var(--suave); margin: 0 0 8px; font-size: 14px; }}
  h4 {{ margin: 12px 0 4px; font-size: 14px; }}
  details {{ margin-top: 10px; background: #f5f7f9; border-left: 3px solid var(--destaque); padding: 6px 12px;
             font-size: 14px; }}
  summary {{ cursor: pointer; font-weight: 600; }}
  details ul {{ margin: 6px 0; padding-left: 18px; }}
  .rolagem {{ overflow-x: auto; }}
  .tabela {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  .tabela th, .tabela td {{ border-bottom: 1px solid var(--borda); padding: 4px 6px; text-align: left;
                            vertical-align: top; }}
  .tabela td:not(:nth-child(2)) {{ white-space: nowrap; }}
"""

# Abas: troca o painel visível e redimensiona os gráficos dele (gráfico desenhado em
# painel escondido nasce sem largura).
_JS = """
document.querySelectorAll('[role="tab"]').forEach(function (aba) {
  aba.addEventListener('click', function () {
    document.querySelectorAll('[role="tab"]').forEach(function (a) {
      a.setAttribute('aria-selected', a === aba ? 'true' : 'false');
      document.getElementById(a.getAttribute('aria-controls')).hidden = a !== aba;
    });
    var painel = document.getElementById(aba.getAttribute('aria-controls'));
    painel.querySelectorAll('.js-plotly-plot').forEach(function (g) { Plotly.Plots.resize(g); });
  });
});
"""


def _cartao(s: Secao, incluir_plotly: bool) -> str:
    grafico = s.figura.to_html(
        full_html=False,
        include_plotlyjs="inline" if incluir_plotly else False,
        config={"displayModeBar": False, "responsive": True},
    )
    itens = "".join(f"<li>{html.escape(t)}</li>" for t in s.como_ler)
    return (
        f'<article class="cartao" id="indicador-{s.numero:02d}">'
        f"<h2>{s.numero}. {html.escape(s.titulo)}</h2>"
        f'<p class="frase">{html.escape(s.frase)}</p>'
        f"{grafico}{s.extra_html}"
        f"<details><summary>Como ler</summary><ul>{itens}</ul></details>"
        "</article>"
    )


def montar_html(
    secoes: list[Secao], retrato: str = "", resumo: list[tuple[str, str]] | None = None
) -> str:
    """Página com cabeçalho, cartões de destaque e 3 abas; o Plotly vai embutido uma vez."""
    por_numero = {s.numero: s for s in secoes}
    abas, paineis = [], []
    primeiro = True
    for i, (id_aba, nome, numeros) in enumerate(ABAS):
        cartoes = []
        for n in numeros:
            if n in por_numero:
                cartoes.append(_cartao(por_numero[n], incluir_plotly=primeiro))
                primeiro = False
        abas.append(
            f'<button role="tab" id="aba-{id_aba}" aria-controls="painel-{id_aba}" '
            f'aria-selected="{"true" if i == 0 else "false"}">{html.escape(nome)}</button>'
        )
        paineis.append(
            f'<section role="tabpanel" id="painel-{id_aba}" aria-labelledby="aba-{id_aba}"'
            f'{"" if i == 0 else " hidden"}><div class="grade">{"".join(cartoes)}</div></section>'
        )
    kpis = "".join(
        f'<div class="kpi"><div class="valor">{html.escape(valor)}</div>'
        f'<div class="rotulo">{html.escape(rotulo)}</div></div>'
        for rotulo, valor in (resumo or [])
    )
    linha_retrato = (
        f'<span class="retrato">Retrato de {html.escape(retrato)}</span>'
        if retrato
        else ""
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Câmara dos Deputados 2025</title>
<style>{_CSS}</style>
</head>
<body>
<header><div class="conteudo">
<h1>Câmara dos Deputados em 2025: 12 indicadores</h1>
<p class="meta">{linha_retrato}Fonte: <a href="{URL_FONTE}">dadosabertos.camara.leg.br</a> ·
<a href="{URL_REPOSITORIO}">código e specs no GitHub</a></p>
</div></header>
<main class="conteudo">
<div class="resumo">{kpis}</div>
<div role="tablist" aria-label="Grupos de indicadores">{"".join(abas)}</div>
{"".join(paineis)}
</main>
<script>{_JS}</script>
</body>
</html>
"""


def _filtrado(df: pd.DataFrame, flag: str) -> pd.DataFrame:
    return df[df[flag] == True]  # NULL fica fora


def montar_secoes(marts: dict[int, pd.DataFrame]) -> list[Secao]:
    """Textos fixos das 12 seções. Números citados saem do mart (formatados), nunca de conta."""
    m = marts
    rede = m[3][m[3]["cod_partido"] == "REDE"]
    votacoes_rede = _num(rede["qtd_votacoes"].iloc[0]) if len(rede) else "poucas"
    n_bloco = len(m[2][m[2]["bln_amostra_suficiente"] != True])
    n_apertadas = len(_filtrado(m[4], "bln_apertada"))
    n_contra = len(_filtrado(m[4], "bln_resultado_contra_placar"))
    cruza = _filtrado(m[10], "bln_top_80").sort_values("num_posicao").tail(1)
    n_top80 = _num(cruza["num_posicao"].iloc[0]) if len(cruza) else "?"
    return [
        Secao(1, "Presença em eventos", f"Eventos realizados com presença registrada: os {TOP} "
              f"deputados com mais e os {TOP} com menos.", grafico_01(m[1]), [
              ("É contagem, não taxa: para virar taxa seria preciso saber de que órgãos cada deputado é "
              "membro, e isso não está nos dados."),
              "Contam todos os tipos de evento realizados, menos o teste do painel eletrônico.",
              (f"O corte dos {TOP} com menos atravessa um empate (vários deputados com 0 ou 1 evento); "
              "dentro do empate, a ordem é alfabética."),
              "\"sem partido\" é quem não votou em 2025: o partido vem do último voto do ano."]),
        Secao(2, "Fidelidade à orientação do partido", "Dos votos em que a bancada orientou Sim, Não "
              "ou Obstrução, quantos seguiram a orientação.", grafico_02(m[2]), [
              ("Fiel é votar exatamente o que a bancada orientou. Votar Não quando a orientação é "
              "Obstrução conta como infiel: a obstrução tira o deputado do quórum, e o Não conta para ele."),
              "Fora da conta: orientação Liberado, bancada sem orientação e o voto Artigo 17 (presidente).",
              (f"{n_bloco} partidos orientam pelo bloco (federação) e ficam sem valor: cobertura abaixo de "
              "20% dos votos, porque a composição do bloco não está nos dados.")]),
        Secao(3, "Coesão dos partidos", "Em cada votação, a parcela da bancada que votou na opção mais "
              "votada; média das votações do ano.", grafico_03(m[3]), [
              "Só entram votações com 3 ou mais deputados do partido: com 1 a coesão é 100% por definição.",
              "Empate conta: 5 × 5 dá 50%. A abstenção é uma posição.",
              f"O REDE tem só {votacoes_rede} votações válidas: amostra pequena, coesão menos estável."]),
        Secao(4, "Votações apertadas", "Margem entre Sim e Não de cada votação nominal do ano, no "
              "Plenário e nas comissões.", grafico_04(m[4]), [
              "Margem = diferença entre Sim e Não sobre Sim + Não. Apertada: menor que 5%.",
              "A margem é proporcional: numa comissão de 10 votos, só o empate é apertado.",
              (f"{n_apertadas} votações apertadas e {n_contra} com resultado contra o placar (quórum "
              "qualificado ou desempate), listadas abaixo. Empate não conta como contra o placar.")],
              tabelas_04(m[4])),
        Secao(5, "Proposições por tema", "Proposições apresentadas em 2025 por deputados, por tema, "
              "separadas pelo tipo.", grafico_05(m[5]), [
              "Proposição com vários temas conta em cada um: a soma dos temas é maior que o total.",
              "Só 41% das proposições de 2025 têm tema; emenda e requerimento quase nunca têm.",
              "RIC é requerimento de informação; INC, indicação; Outros reúne os demais tipos."]),
        Secao(6, "Gasto médio mensal por deputado", f"Os {TOP} maiores gastos médios por mês com "
              "despesa na cota parlamentar.", grafico_06(m[6]), [
              "A média é por mês com despesa: compara de forma justa o mandato inteiro e a suplência curta.",
              "Lideranças ficam fora (não são deputados)."]),
        Secao(7, "Gasto por categoria", "Total da cota em 2025 por subcota; o rótulo é a parcela do "
              "total.", grafico_07(m[7]), [
              "Inclui as lideranças: é o total da cota.",
              ("A complementação do auxílio-moradia aparece à esquerda do zero: o total da categoria "
              "em 2025 é negativo, e entra assim na soma da cota.")]),
        Secao(8, "Gasto por mês", "Total da cota por mês de competência.", grafico_08(m[8]), [
              ("Dezembro tem menos lançamentos, mas valor parecido com os vizinhos; os dados não mostram "
              "que esteja incompleto."),
              ("Notas emitidas até março de 2026 entram no mês de competência: um retrato novo pode mudar "
              "dezembro.")]),
        Secao(9, "Gasto por UF", "Gasto médio por deputado-mês em cada UF.", grafico_09(m[9]), [
              "Divide por deputado-mês, não por deputado: a UF que teve troca de mandato não é punida.",
              "Lideranças ficam fora (não têm UF)."]),
        Secao(10, "Concentração em fornecedores", "Parcela acumulada do gasto à medida que se somam os "
              "fornecedores, do maior para o menor.", grafico_10(m[10]), [
              f"{n_top80} fornecedores somam 80% do gasto da cota.",
              ("Empresa com várias filiais conta uma vez (raiz do CNPJ). CNPJs começados com 00000000 são "
              "códigos internos e ficam separados, marcados como fictícios."),
              "Pessoa física é agrupada pelo nome (o CPF não entra no projeto)."], tabela_10(m[10])),
        Secao(11, "Participação nas votações do Plenário", f"Os {TOP} deputados com menor participação "
              "nas votações nominais do Plenário.", grafico_11(m[11]), [
              "Só o Plenário: em comissão, o deputado só vota se for membro.",
              ("O denominador vai do primeiro ao último voto do deputado: o suplente não é cobrado pelas "
              "votações de antes da posse. Quem saiu e voltou fica com a janela inteira.")]),
        Secao(12, "Alinhamento ao Governo", "Um ponto por deputado: parcela dos votos iguais à "
              "orientação do Governo, por partido.", grafico_12(m[12]), [
              "Mesmas regras da fidelidade: só Sim, Não e Obstrução orientados; fica fora o Artigo 17.",
              "Só deputados com 30 ou mais votos orientados (para não ranquear suplente com 4 votos).",
              "Sem boxplot de propósito: o gráfico mostra os pontos, não quartis calculados."]),
    ]  # fmt: skip


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    if not CAMINHO_BANCO.is_file():
        print(
            f"ERRO: {CAMINHO_BANCO} não existe.\n"
            "Rode a ingestão, a transformação e os marts primeiro.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        con = duckdb.connect(str(CAMINHO_BANCO), read_only=True)
    except duckdb.IOException as e:
        print(
            f"ERRO: {CAMINHO_BANCO} está travado por outro processo. Feche o ui.py e tente de novo.\n{e}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        marts = {
            n: con.execute(f'SELECT * FROM marts."{tabela}"').df()
            for n, tabela in MARTS_DOS_GRAFICOS.items()
        }
        resumo = con.execute(f'SELECT * FROM marts."{MART_RESUMO}"').df()
        baixado_em = con.execute(
            "SELECT baixado_em FROM raw._manifesto ORDER BY baixado_em DESC LIMIT 1"
        ).fetchall()[0][0]
    except duckdb.CatalogException as e:
        print(
            f"ERRO: falta tabela no banco. Rode os marts primeiro.\n{e}",
            file=sys.stderr,
        )
        sys.exit(1)
    finally:
        con.close()

    retrato = datetime.fromisoformat(baixado_em).strftime("%d/%m/%Y")
    pagina = montar_html(montar_secoes(marts), retrato, cartoes_resumo(resumo))
    ARQUIVO_RELATORIO.write_text(pagina, encoding="utf-8")
    print(f"{ARQUIVO_RELATORIO} ({_num(ARQUIVO_RELATORIO.stat().st_size)} bytes)")
    print(f"Retrato de {retrato}")


if __name__ == "__main__":
    main()
