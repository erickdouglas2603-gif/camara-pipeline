"""Infraestrutura dos testes (spec 04): raw inventada em banco em memória, SQL de verdade.

Nenhum teste lê o camara.duckdb, a pasta raw/ ou a internet. A única leitura de
fora é dados/de_para_bancada.csv (dado de referência versionado), feita pelo
transformar() de verdade.
"""

import duckdb
import pytest

from pipeline import marts, transformacao

# Colunas das 10 tabelas da raw, na ordem real, copiadas uma vez do
# information_schema do banco real (retrato de 03/11/2026). Na raw tudo é VARCHAR.
COLUNAS_RAW = {
    "ceap": [
        "txNomeParlamentar", "cpf", "ideCadastro", "nuCarteiraParlamentar", "nuLegislatura",
        "sgUF", "sgPartido", "codLegislatura", "numSubCota", "txtDescricao",
        "numEspecificacaoSubCota", "txtDescricaoEspecificacao", "txtFornecedor", "txtCNPJCPF",
        "txtNumero", "indTipoDocumento", "datEmissao", "vlrDocumento", "vlrGlosa", "vlrLiquido",
        "numMes", "numAno", "numParcela", "txtPassageiro", "txtTrecho", "numLote",
        "numRessarcimento", "datPagamentoRestituicao", "vlrRestituicao", "nuDeputadoId",
        "ideDocumento", "urlDocumento",
    ],
    "votacoes": [
        "id", "uri", "data", "dataHoraRegistro", "idOrgao", "uriOrgao", "siglaOrgao", "idEvento",
        "uriEvento", "aprovacao", "votosSim", "votosNao", "votosOutros", "descricao",
        "ultimaAberturaVotacao_dataHoraRegistro", "ultimaAberturaVotacao_descricao",
        "ultimaApresentacaoProposicao_dataHoraRegistro", "ultimaApresentacaoProposicao_descricao",
        "ultimaApresentacaoProposicao_idProposicao", "ultimaApresentacaoProposicao_uriProposicao",
    ],
    "votacoesVotos": [
        "idVotacao", "uriVotacao", "dataHoraVoto", "voto", "deputado_id", "deputado_uri",
        "deputado_nome", "deputado_siglaPartido", "deputado_uriPartido", "deputado_siglaUf",
        "deputado_idLegislatura", "deputado_urlFoto",
    ],
    "votacoesOrientacoes": [
        "idVotacao", "uriVotacao", "siglaOrgao", "descricao", "siglaBancada", "uriBancada",
        "orientacao",
    ],
    "proposicoes": [
        "id", "uri", "siglaTipo", "numero", "ano", "codTipo", "descricaoTipo", "ementa",
        "ementaDetalhada", "keywords", "dataApresentacao", "uriOrgaoNumerador", "uriPropAnterior",
        "uriPropPrincipal", "uriPropPosterior", "urlInteiroTeor", "urnFinal",
        "ultimoStatus_dataHora", "ultimoStatus_sequencia", "ultimoStatus_uriRelator",
        "ultimoStatus_idOrgao", "ultimoStatus_siglaOrgao", "ultimoStatus_uriOrgao",
        "ultimoStatus_regime", "ultimoStatus_descricaoTramitacao", "ultimoStatus_idTipoTramitacao",
        "ultimoStatus_descricaoSituacao", "ultimoStatus_idSituacao", "ultimoStatus_despacho",
        "ultimoStatus_apreciacao", "ultimoStatus_url",
    ],
    "proposicoesAutores": [
        "idProposicao", "uriProposicao", "idDeputadoAutor", "uriAutor", "codTipoAutor",
        "tipoAutor", "nomeAutor", "siglaPartidoAutor", "uriPartidoAutor", "siglaUFAutor",
        "ordemAssinatura", "proponente",
    ],
    "proposicoesTemas": [
        "uriProposicao", "siglaTipo", "numero", "ano", "codTema", "tema", "relevancia",
    ],
    "deputados": [
        "uri", "nome", "idLegislaturaInicial", "idLegislaturaFinal", "nomeCivil", "cpf",
        "siglaSexo", "urlRedeSocial", "urlWebsite", "dataNascimento", "dataFalecimento",
        "ufNascimento", "municipioNascimento",
    ],
    "eventos": [
        "id", "uri", "urlDocumentoPauta", "dataHoraInicio", "dataHoraFim", "situacao",
        "descricao", "descricaoTipo", "localExterno", "localCamara.nome", "localCamara.predio",
        "localCamara.sala", "localCamara.andar",
    ],
    "eventosPresencaDeputados": [
        "idEvento", "uriEvento", "dataHoraInicio", "idDeputado", "uriDeputado",
    ],
}  # fmt: skip


def criar_raw(con: duckdb.DuckDBPyConnection) -> None:
    """Schema raw com as 10 tabelas vazias, todas as colunas VARCHAR, na ordem real."""
    con.execute("CREATE SCHEMA raw")
    for tabela, colunas in COLUNAS_RAW.items():
        definicao = ", ".join(f'"{c}" VARCHAR' for c in colunas)
        con.execute(f'CREATE TABLE raw."{tabela}" ({definicao})')


def inserir(con: duckdb.DuckDBPyConnection, tabela: str, linhas: list[dict]) -> None:
    """Insere linhas na raw; coluna que a linha não informa entra NULL."""
    colunas = COLUNAS_RAW[tabela]
    desconhecidas = {c for linha in linhas for c in linha} - set(colunas)
    # Um nome de coluna digitado errado viraria NULL em silêncio e o teste passaria pelo motivo errado.
    assert not desconhecidas, (
        f"colunas que não existem em raw.{tabela}: {desconhecidas}"
    )
    marcadores = ", ".join("?" for _ in colunas)
    for linha in linhas:
        con.execute(
            f'INSERT INTO raw."{tabela}" VALUES ({marcadores})',
            [linha.get(c) for c in colunas],
        )


def rodar(con: duckdb.DuckDBPyConnection, camada: str, nome: str) -> None:
    """Lê o .sql do projeto e cria a tabela <camada>.<nome>.

    refined: nome = tabela = arquivo (despesa -> sql/refined/despesa.sql).
    marts: nome = tabela; o arquivo vem da lista MARTS (dim_Deputado -> 00_dim_deputado.sql).
    """
    if camada == "refined":
        arquivo = transformacao.PASTA_SQL / f"{nome}.sql"
    elif camada == "marts":
        arquivo = marts.PASTA_SQL / next(a for a, t, _ in marts.MARTS if t == nome)
    else:
        raise ValueError(f"camada desconhecida: {camada}")
    select = arquivo.read_text(encoding="utf-8").strip().rstrip(";")
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {camada}")
    con.execute(f'CREATE OR REPLACE TABLE {camada}."{nome}" AS\n{select}\n')


def montar_refined(con: duckdb.DuckDBPyConnection) -> None:
    """Raw inventada -> refined de verdade (com o de-para), ignorando as conferências.

    Com dado inventado, as conferências de número fixo falham; aqui só importa o refined
    existir como a transformação o criaria.
    """
    transformacao.transformar(con)


@pytest.fixture
def con():
    conexao = duckdb.connect()  # sem caminho = memória; o camara.duckdb nem é tocado
    criar_raw(conexao)
    yield conexao
    conexao.close()
