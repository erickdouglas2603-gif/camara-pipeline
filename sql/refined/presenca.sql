SELECT
    CAST(p.idEvento AS BIGINT)            AS id_evento,
    CAST(p.idDeputado AS BIGINT)          AS id_deputado,
    CAST(p.dataHoraInicio AS TIMESTAMP)   AS ts_inicio_evento,
    EXISTS (
        SELECT 1 FROM refined.evento e
        WHERE e.id_evento = CAST(p.idEvento AS BIGINT)
    )                                     AS bln_evento_cadastrado
FROM raw.eventosPresencaDeputados p
