SELECT
    CAST(a.idProposicao AS BIGINT)       AS id_proposicao,
    CAST(a.idDeputadoAutor AS BIGINT)    AS id_deputado,
    CAST(a.codTipoAutor AS INTEGER)      AS cod_tipo_autor,
    a.tipoAutor                          AS des_tipo_autor,
    a.nomeAutor                          AS des_nome_autor,
    a.siglaPartidoAutor                  AS cod_partido,
    a.siglaUFAutor                       AS cod_uf,
    CAST(a.ordemAssinatura AS INTEGER)   AS num_ordem_assinatura,
    CASE
        WHEN a.proponente IS NULL THEN NULL
        WHEN a.proponente = '1' THEN TRUE
        WHEN a.proponente = '0' THEN FALSE
        ELSE error('autoria.proponente fora de 0/1: ' || a.proponente)
    END                                  AS bln_proponente,
    EXISTS (
        SELECT 1 FROM refined.proposicao p
        WHERE p.id_proposicao = CAST(a.idProposicao AS BIGINT)
    )                                    AS bln_proposicao_cadastrada
FROM raw.proposicoesAutores a
