-- Exceção à regra 1: legislatura 57 + quem aparece em algum fato (a dimensão cobre todos os fatos).
WITH ids_em_fatos AS (
    SELECT CAST(deputado_id AS BIGINT) AS id FROM raw.votacoesVotos
    UNION
    SELECT CAST(idDeputado AS BIGINT) FROM raw.eventosPresencaDeputados
    UNION
    SELECT CAST(idDeputadoAutor AS BIGINT) FROM raw.proposicoesAutores WHERE idDeputadoAutor IS NOT NULL
    UNION
    SELECT CAST(ideCadastro AS BIGINT) FROM raw.ceap WHERE ideCadastro IS NOT NULL
)
SELECT
    CAST(split_part(uri, '/', -1) AS BIGINT)   AS id_deputado,
    nome                                       AS des_nome,
    nomeCivil                                  AS des_nome_civil,
    CAST(idLegislaturaInicial AS INTEGER)      AS num_legislatura_inicial,
    CAST(idLegislaturaFinal AS INTEGER)        AS num_legislatura_final,
    siglaSexo                                  AS cod_sexo,
    CAST(dataNascimento AS DATE)               AS data_nascimento,
    CAST(dataFalecimento AS DATE)              AS data_falecimento,
    ufNascimento                               AS cod_uf_nascimento,
    municipioNascimento                        AS des_municipio_nascimento,
    urlRedeSocial                              AS des_url_rede_social,
    urlWebsite                                 AS des_url_website,
    CAST(idLegislaturaFinal AS INTEGER) >= 57  AS bln_legislatura_atual
FROM raw.deputados
WHERE CAST(idLegislaturaFinal AS INTEGER) >= 57
   OR CAST(split_part(uri, '/', -1) AS BIGINT) IN (SELECT id FROM ids_em_fatos)
