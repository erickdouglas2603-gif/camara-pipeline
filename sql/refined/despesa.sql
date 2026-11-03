WITH base AS (
    SELECT
        *,
        -- Chave: as 32 colunas da raw, na ordem da raw, com coalesce (concat_ws pula NULL).
        md5(concat_ws('|',
            coalesce(txNomeParlamentar, '<NULL>'), coalesce(cpf, '<NULL>'),
            coalesce(ideCadastro, '<NULL>'), coalesce(nuCarteiraParlamentar, '<NULL>'),
            coalesce(nuLegislatura, '<NULL>'), coalesce(sgUF, '<NULL>'),
            coalesce(sgPartido, '<NULL>'), coalesce(codLegislatura, '<NULL>'),
            coalesce(numSubCota, '<NULL>'), coalesce(txtDescricao, '<NULL>'),
            coalesce(numEspecificacaoSubCota, '<NULL>'), coalesce(txtDescricaoEspecificacao, '<NULL>'),
            coalesce(txtFornecedor, '<NULL>'), coalesce(txtCNPJCPF, '<NULL>'),
            coalesce(txtNumero, '<NULL>'), coalesce(indTipoDocumento, '<NULL>'),
            coalesce(datEmissao, '<NULL>'), coalesce(vlrDocumento, '<NULL>'),
            coalesce(vlrGlosa, '<NULL>'), coalesce(vlrLiquido, '<NULL>'),
            coalesce(numMes, '<NULL>'), coalesce(numAno, '<NULL>'),
            coalesce(numParcela, '<NULL>'), coalesce(txtPassageiro, '<NULL>'),
            coalesce(txtTrecho, '<NULL>'), coalesce(numLote, '<NULL>'),
            coalesce(numRessarcimento, '<NULL>'), coalesce(datPagamentoRestituicao, '<NULL>'),
            coalesce(vlrRestituicao, '<NULL>'), coalesce(nuDeputadoId, '<NULL>'),
            coalesce(ideDocumento, '<NULL>'), coalesce(urlDocumento, '<NULL>')
        )) AS _hash,
        -- Só dígitos; vazio vira NULL. O documento cru não sai deste CTE (CPF não chega ao refined).
        NULLIF(regexp_replace(txtCNPJCPF, '[^0-9]', '', 'g'), '') AS _doc
    FROM raw.ceap
)
SELECT
    _hash                                         AS id_despesa,
    CAST(ideCadastro AS BIGINT)                   AS id_deputado,
    CAST(nuDeputadoId AS BIGINT)                  AS cod_deputado_cota,
    CASE WHEN ideCadastro IS NULL THEN 'lideranca' ELSE 'deputado' END AS tp_beneficiario,
    txNomeParlamentar                             AS des_nome_parlamentar,
    CAST(nuCarteiraParlamentar AS INTEGER)        AS num_carteira_parlamentar,
    CAST(nuLegislatura AS INTEGER)                AS num_legislatura,
    CAST(codLegislatura AS INTEGER)               AS cod_legislatura,
    NULLIF(sgUF, 'NA')                            AS cod_uf,
    sgPartido                                     AS cod_partido,
    CAST(numSubCota AS INTEGER)                   AS cod_subcota,
    txtDescricao                                  AS des_subcota,
    CAST(numEspecificacaoSubCota AS INTEGER)      AS cod_especificacao_subcota,
    txtDescricaoEspecificacao                     AS des_especificacao_subcota,
    txtFornecedor                                 AS des_fornecedor,
    CASE WHEN length(_doc) = 14 THEN _doc END     AS cod_cnpj_fornecedor,
    CASE
        WHEN _doc IS NULL THEN NULL
        WHEN length(_doc) = 14 THEN 'PJ'
        WHEN length(_doc) = 11 THEN 'PF'
        ELSE error('despesa.txtCNPJCPF com ' || length(_doc) || ' dígitos (esperado 11 ou 14)')
    END                                           AS tp_fornecedor,
    txtNumero                                     AS cod_documento_fiscal,
    indTipoDocumento                              AS tp_documento,
    CAST(datEmissao AS TIMESTAMP)                 AS ts_emissao,
    CAST(vlrDocumento AS DECIMAL(14,2))           AS vlr_documento,
    CAST(vlrGlosa AS DECIMAL(14,2))               AS vlr_glosa,
    CAST(vlrLiquido AS DECIMAL(14,2))             AS vlr_liquido,
    CAST(vlrRestituicao AS DECIMAL(14,2))         AS vlr_restituicao,
    CAST(numMes AS INTEGER)                       AS num_mes,
    CAST(numAno AS INTEGER)                       AS num_ano,
    make_date(CAST(numAno AS INTEGER), CAST(numMes AS INTEGER), 1) AS data_competencia,
    CAST(numParcela AS INTEGER)                   AS num_parcela,
    txtTrecho                                     AS des_trecho,
    CAST(numLote AS BIGINT)                       AS num_lote,
    CAST(numRessarcimento AS BIGINT)              AS num_ressarcimento,
    CAST(datPagamentoRestituicao AS TIMESTAMP)    AS ts_pagamento_restituicao,
    CAST(NULLIF(ideDocumento, '0') AS BIGINT)     AS id_documento,
    urlDocumento                                  AS des_url_documento
FROM base
