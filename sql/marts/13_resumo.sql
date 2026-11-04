-- grão: uma linha (os números dos cartões de destaque do relatório)
-- Os valores vêm dos outros marts, aqui no SQL: o relatório só lê esta linha e não conta nada.
-- Roda por último (13), depois de todos os marts de que depende.
SELECT
    (SELECT CAST(sum(vlr_total) AS DECIMAL(14,2)) FROM marts.agg_Gasto_Categoria)              AS vlr_total_cota,
    (SELECT count(*) FROM marts.dim_Deputado WHERE bln_universo_2025)                          AS qtd_deputados,
    (SELECT count(*) FROM marts.agg_Votacao_Apertada)                                          AS qtd_votacoes_nominais,
    (SELECT count(*) FROM marts.agg_Votacao_Apertada WHERE bln_apertada)                       AS qtd_votacoes_apertadas,
    (SELECT count(*) FROM marts.agg_Fornecedor_Pareto)                                         AS qtd_fornecedores,
    (SELECT count(*) FROM marts.agg_Fornecedor_Pareto WHERE bln_top_80)                        AS qtd_fornecedores_top80
