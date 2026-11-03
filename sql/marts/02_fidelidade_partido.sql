-- grão: um partido que aparece nos votos (20)
-- Partido = o do voto (no momento do voto), ligado à orientação pelo de-para partido -> bancada.
-- Orientado: orientação Sim/Não/Obstrução e voto diferente de 'Artigo 17' (presidente).
-- Fora: Liberado (não há o que seguir) e orientação NULL (a bancada não orientou).
-- Voto secreto (NULL) não é orientado: NULL <> 'Artigo 17' não é verdadeiro.
-- Fiel = voto igual à orientação, sem exceção (Obstrução + Não é infiel; Abstenção é infiel).
-- Corte de 20% de cobertura, no valor arredondado que o leitor vê: o buraco natural entre 4,3% e 22,5%.
WITH orientacao_partido AS (
    SELECT o.id_votacao, dp.cod_partido, o.des_orientacao
    FROM refined.orientacao o
    JOIN refined.de_para_bancada dp ON dp.cod_bancada_origem = o.cod_bancada
),
votos AS (
    SELECT
        v.cod_partido,
        v.des_voto,
        o.des_orientacao,
        o.des_orientacao IN ('Sim', 'Não', 'Obstrução') AND v.des_voto <> 'Artigo 17' AS bln_orientado
    FROM refined.voto v
    LEFT JOIN orientacao_partido o
           ON o.id_votacao = v.id_votacao
          AND o.cod_partido = v.cod_partido
),
partido AS (
    SELECT
        cod_partido,
        count(*)                                                          AS qtd_votos,
        count(*) FILTER (WHERE bln_orientado)                             AS qtd_votos_orientados,
        count(*) FILTER (WHERE bln_orientado AND des_voto = des_orientacao) AS qtd_votos_fieis
    FROM votos
    GROUP BY cod_partido
),
cobertura AS (
    SELECT
        *,
        CAST(100.0 * qtd_votos_orientados / NULLIF(qtd_votos, 0) AS DECIMAL(5,1)) AS pct_cobertura
    FROM partido
)
SELECT
    cod_partido,
    qtd_votos,
    qtd_votos_orientados,
    qtd_votos_fieis,
    pct_cobertura,
    pct_cobertura >= 20 AS bln_amostra_suficiente,
    CASE WHEN pct_cobertura >= 20
         THEN CAST(100.0 * qtd_votos_fieis / NULLIF(qtd_votos_orientados, 0) AS DECIMAL(5,1))
    END                 AS pct_fidelidade
FROM cobertura
