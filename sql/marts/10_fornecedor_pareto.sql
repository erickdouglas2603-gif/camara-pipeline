-- grão: um fornecedor (cod_fornecedor)
-- Chave: PJ pela raiz do CNPJ (8 dígitos), para a empresa com filiais não virar vários fornecedores pequenos;
-- CNPJ que começa com 00000000 fica completo e com flag (códigos internos, não uma empresa "00000000");
-- PF pelo nome (não há CPF no refined).
-- des_fornecedor: o nome mais frequente da chave; empate, o menor em ordem alfabética.
-- bln_top_80 usa a soma exata (não o pct arredondado) e inclui o fornecedor que cruza a linha dos 80%.
-- Um fornecedor tem total negativo e fica no fim: o acumulado passa de 100 e volta a 100,0 na última posição.
-- Lideranças entram (concentração do gasto total).
WITH base AS (
    SELECT
        *,
        CASE
            WHEN tp_fornecedor = 'PJ' AND cod_cnpj_fornecedor LIKE '00000000%' THEN cod_cnpj_fornecedor
            WHEN tp_fornecedor = 'PJ' THEN left(cod_cnpj_fornecedor, 8)
            ELSE des_fornecedor
        END AS cod_fornecedor,
        coalesce(tp_fornecedor = 'PJ' AND cod_cnpj_fornecedor LIKE '00000000%', FALSE) AS bln_cnpj_ficticio
    FROM refined.despesa
),
nome AS (
    SELECT cod_fornecedor, des_fornecedor
    FROM base
    GROUP BY cod_fornecedor, des_fornecedor
    QUALIFY row_number() OVER (PARTITION BY cod_fornecedor ORDER BY count(*) DESC, des_fornecedor) = 1
),
fornecedor AS (
    SELECT
        cod_fornecedor,
        any_value(tp_fornecedor)  AS tp_fornecedor,
        bool_or(bln_cnpj_ficticio) AS bln_cnpj_ficticio,
        count(*)                  AS qtd_despesas,
        sum(vlr_liquido)          AS vlr_total
    FROM base
    GROUP BY cod_fornecedor
),
ordenado AS (
    SELECT
        f.*,
        n.des_fornecedor,
        row_number() OVER (ORDER BY f.vlr_total DESC, f.cod_fornecedor) AS num_posicao,
        sum(f.vlr_total) OVER (ORDER BY f.vlr_total DESC, f.cod_fornecedor
                               ROWS UNBOUNDED PRECEDING)                AS vlr_acumulado,
        sum(f.vlr_total) OVER ()                                        AS vlr_geral
    FROM fornecedor f
    JOIN nome n USING (cod_fornecedor)
)
SELECT
    cod_fornecedor,
    tp_fornecedor,
    bln_cnpj_ficticio,
    des_fornecedor,
    qtd_despesas,
    CAST(vlr_total AS DECIMAL(14,2))                                       AS vlr_total,
    num_posicao,
    CAST(100 * vlr_acumulado / NULLIF(vlr_geral, 0) AS DECIMAL(5,1))       AS pct_acumulado,
    vlr_acumulado - vlr_total < 0.8 * vlr_geral                            AS bln_top_80
FROM ordenado
