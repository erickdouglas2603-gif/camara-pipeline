SELECT
    CAST(id AS BIGINT)                  AS id_evento,
    CAST(dataHoraInicio AS TIMESTAMP)   AS ts_inicio,
    CAST(dataHoraFim AS TIMESTAMP)      AS ts_fim,
    situacao                            AS des_situacao,
    descricao                           AS des_evento,
    descricaoTipo                       AS des_tipo_evento,
    localExterno                        AS des_local_externo,
    "localCamara.nome"                  AS des_local_nome,
    "localCamara.predio"                AS des_local_predio,
    "localCamara.sala"                  AS des_local_sala,
    "localCamara.andar"                 AS des_local_andar,
    urlDocumentoPauta                   AS des_url_pauta,
    situacao LIKE 'Encerrada%'          AS bln_realizado
FROM raw.eventos
