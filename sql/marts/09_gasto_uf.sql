-- grão: uma UF (27)
-- Divide por deputado-mês, não por deputado: a UF com troca de mandato não é punida
-- (SP tem 78 deputados com despesa para 70 cadeiras).
-- UF = a da despesa (cod_uf da cota); nenhum deputado tem despesa em mais de uma UF.
-- Lideranças fora (não têm UF). Divisão de dinheiro com CAST na mesma expressão (regra 3).
WITH deputado_uf AS (
    SELECT
        cod_uf,
        id_deputado,
        count(DISTINCT data_competencia) AS qtd_meses,
        sum(vlr_liquido)                 AS vlr_total
    FROM refined.despesa
    WHERE tp_beneficiario = 'deputado'
    GROUP BY cod_uf, id_deputado
)
SELECT
    cod_uf,
    count(*)                                                         AS qtd_deputados,
    CAST(sum(qtd_meses) AS BIGINT)                                   AS qtd_deputado_meses,
    CAST(sum(vlr_total) AS DECIMAL(14,2))                            AS vlr_total,
    CAST(sum(vlr_total) / NULLIF(sum(qtd_meses), 0) AS DECIMAL(14,2)) AS vlr_medio_deputado_mes
FROM deputado_uf
GROUP BY cod_uf
