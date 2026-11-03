-- grão: um deputado do universo de 2025
-- Lideranças fora (não são deputados). Quem não teve despesa aparece com total 0 e média NULL.
-- A média mensal é a comparação justa entre mandato inteiro e suplência curta.
-- Divisão de dinheiro com CAST para DECIMAL na mesma expressão (regra 3).
WITH gasto AS (
    SELECT
        id_deputado,
        sum(vlr_liquido)                 AS vlr_total,
        count(DISTINCT data_competencia) AS qtd_meses
    FROM refined.despesa
    WHERE tp_beneficiario = 'deputado'
    GROUP BY id_deputado
)
SELECT
    d.id_deputado,
    d.des_nome,
    d.cod_partido,
    d.cod_uf,
    CAST(coalesce(g.vlr_total, 0) AS DECIMAL(14,2))                   AS vlr_total,
    coalesce(g.qtd_meses, 0)                                         AS qtd_meses_com_despesa,
    CAST(g.vlr_total / NULLIF(g.qtd_meses, 0) AS DECIMAL(14,2))       AS vlr_media_mensal
FROM marts.dim_Deputado d
LEFT JOIN gasto g USING (id_deputado)
WHERE d.bln_universo_2025
