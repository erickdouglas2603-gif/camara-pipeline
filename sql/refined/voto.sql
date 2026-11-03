SELECT
    idVotacao                                AS id_votacao,
    CAST(deputado_id AS BIGINT)              AS id_deputado,
    CAST(dataHoraVoto AS TIMESTAMP)          AS ts_voto,
    voto                                     AS des_voto,
    deputado_nome                            AS des_nome_deputado,
    deputado_siglaPartido                    AS cod_partido,
    deputado_siglaUf                         AS cod_uf,
    CAST(deputado_idLegislatura AS INTEGER)  AS num_legislatura,
    deputado_urlFoto                         AS des_url_foto
FROM raw.votacoesVotos
