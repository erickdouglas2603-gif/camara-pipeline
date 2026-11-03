-- grão: uma subcota (21)
-- Lideranças entram: o indicador é sobre o total da cota. Auxílio-moradia entra com total negativo.
-- cod_subcota e des_subcota são 1 para 1 (provado), então agrupar pelos dois não muda o grão.
WITH total AS (
    SELECT sum(vlr_liquido) AS vlr FROM refined.despesa
)
SELECT
    cod_subcota,
    des_subcota,
    count(*)                                                                     AS qtd_despesas,
    CAST(sum(vlr_liquido) AS DECIMAL(14,2))                                      AS vlr_total,
    CAST(100 * sum(vlr_liquido) / NULLIF((SELECT vlr FROM total), 0) AS DECIMAL(5,1)) AS pct_total
FROM refined.despesa
GROUP BY cod_subcota, des_subcota
