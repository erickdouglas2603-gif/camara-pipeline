SELECT
    CAST(split_part(uriProposicao, '/', -1) AS BIGINT)  AS id_proposicao,
    siglaTipo                                           AS cod_sigla_tipo,
    CAST(numero AS INTEGER)                             AS num_proposicao,
    CAST(ano AS INTEGER)                                AS num_ano,
    CAST(codTema AS INTEGER)                            AS cod_tema,
    tema                                                AS des_tema,
    CAST(relevancia AS INTEGER)                         AS num_relevancia
FROM raw.proposicoesTemas
