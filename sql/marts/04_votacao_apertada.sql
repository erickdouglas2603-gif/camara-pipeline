-- grão: uma votação nominal (550): placar > 0 e fora o órgão de teste
-- Todos os órgãos entram; a margem é proporcional (numa comissão de 10 votos só o empate é apertado).
-- Corte de 5% sobre o pct_margem arredondado (o que o leitor vê).
-- bln_resultado_contra_placar: aprovada com mais Não, ou rejeitada com mais Sim. Empate é FALSE
-- (quem decide é o desempate). CASE explícito porque, com bln_aprovada NULL, a expressão sozinha
-- daria FALSE (NULL AND FALSE = FALSE) em vez de NULL.
WITH nominal AS (
    SELECT
        *,
        CAST(100.0 * abs(qtd_votos_sim - qtd_votos_nao) / NULLIF(qtd_votos_sim + qtd_votos_nao, 0)
             AS DECIMAL(5,1)) AS pct_margem
    FROM refined.votacao
    WHERE qtd_votos_sim + qtd_votos_nao + qtd_votos_outros > 0
      AND NOT bln_orgao_teste
)
SELECT
    id_votacao,
    data_votacao,
    cod_orgao,
    qtd_votos_sim,
    qtd_votos_nao,
    qtd_votos_outros,
    bln_aprovada,
    pct_margem,
    pct_margem < 5 AS bln_apertada,
    CASE
        WHEN bln_aprovada IS NULL THEN NULL
        ELSE (bln_aprovada AND qtd_votos_nao > qtd_votos_sim)
          OR (NOT bln_aprovada AND qtd_votos_sim > qtd_votos_nao)
    END            AS bln_resultado_contra_placar
FROM nominal
