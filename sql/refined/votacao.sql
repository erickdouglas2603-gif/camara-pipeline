SELECT
    id                                                                 AS id_votacao,
    CAST(data AS DATE)                                                 AS data_votacao,
    CAST(dataHoraRegistro AS TIMESTAMP)                                AS ts_registro,
    CAST(idOrgao AS BIGINT)                                            AS id_orgao,
    siglaOrgao                                                         AS cod_orgao,
    CAST(idEvento AS BIGINT)                                           AS id_evento,
    CASE
        WHEN aprovacao IS NULL THEN NULL
        WHEN aprovacao = '1' THEN TRUE
        WHEN aprovacao = '0' THEN FALSE
        ELSE error('votacao.aprovacao fora de 0/1: ' || aprovacao)
    END                                                                AS bln_aprovada,
    CAST(votosSim AS INTEGER)                                          AS qtd_votos_sim,
    CAST(votosNao AS INTEGER)                                          AS qtd_votos_nao,
    CAST(votosOutros AS INTEGER)                                       AS qtd_votos_outros,
    descricao                                                          AS des_votacao,
    CAST(ultimaAberturaVotacao_dataHoraRegistro AS TIMESTAMP)          AS ts_ultima_abertura,
    ultimaAberturaVotacao_descricao                                    AS des_ultima_abertura,
    CAST(ultimaApresentacaoProposicao_dataHoraRegistro AS TIMESTAMP)   AS ts_ultima_apresentacao,
    ultimaApresentacaoProposicao_descricao                             AS des_ultima_apresentacao,
    CAST(NULLIF(ultimaApresentacaoProposicao_idProposicao, '0') AS BIGINT) AS id_proposicao,
    siglaOrgao = 'TESTECOM'                                            AS bln_orgao_teste
FROM raw.votacoes
