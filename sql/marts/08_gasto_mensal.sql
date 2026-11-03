-- grão: um mês de competência (12)
-- Dezembro fica: tem menos linhas, mas o valor é igual ao dos meses vizinhos; cortar faria o M08 não
-- bater com o M07. Notas emitidas até mar/2026 entram por competência; um retrato novo pode mudar dezembro.
-- Lideranças entram (total da cota).
SELECT
    data_competencia,
    count(*)                                AS qtd_despesas,
    CAST(sum(vlr_liquido) AS DECIMAL(14,2)) AS vlr_total
FROM refined.despesa
GROUP BY data_competencia
