-- grão: um deputado do universo de 2025
-- Orientação: a linha cod_bancada = 'Governo' da votação. Mesmas regras do M02: entram Sim/Não/Obstrução;
-- ficam fora Liberado, NULL e voto 'Artigo 17'; alinhado = voto igual à orientação.
-- Corte de 30 votos orientados: regra de bolso para não ranquear suplente com 4 votos.
WITH governo AS (
    SELECT id_votacao, des_orientacao
    FROM refined.orientacao
    WHERE cod_bancada = 'Governo'
      AND des_orientacao IN ('Sim', 'Não', 'Obstrução')
),
alinhamento AS (
    SELECT
        v.id_deputado,
        count(*)                                              AS qtd_votos_orientados,
        count(*) FILTER (WHERE v.des_voto = g.des_orientacao) AS qtd_votos_alinhados
    FROM refined.voto v
    JOIN governo g USING (id_votacao)
    WHERE v.des_voto <> 'Artigo 17'
    GROUP BY v.id_deputado
)
SELECT
    d.id_deputado,
    d.des_nome,
    d.cod_partido,
    d.cod_uf,
    coalesce(a.qtd_votos_orientados, 0)       AS qtd_votos_orientados,
    coalesce(a.qtd_votos_alinhados, 0)        AS qtd_votos_alinhados,
    coalesce(a.qtd_votos_orientados, 0) >= 30 AS bln_amostra_suficiente,
    CASE WHEN a.qtd_votos_orientados >= 30
         THEN CAST(100.0 * a.qtd_votos_alinhados / a.qtd_votos_orientados AS DECIMAL(5,1))
    END                                       AS pct_alinhamento
FROM marts.dim_Deputado d
LEFT JOIN alinhamento a USING (id_deputado)
WHERE d.bln_universo_2025
