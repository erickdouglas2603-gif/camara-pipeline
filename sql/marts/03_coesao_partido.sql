-- grão: um partido com pelo menos um grupo válido
-- Grupo = (votação, partido do voto), contando Sim, Não, Obstrução e Abstenção (a abstenção é uma posição).
-- Coesão do grupo = votos na opção mais votada / total do grupo; o empate entra (5 x 5 dá 50%).
-- Só grupos com 3 ou mais deputados: com 1 a coesão é 100% por definição (1.004 grupos); com 2, só 50% ou 100%.
-- Coesão do partido = média simples das coesões dos grupos (cada votação pesa igual), arredondada no fim.
WITH opcao AS (
    SELECT id_votacao, cod_partido, des_voto, count(*) AS qtd
    FROM refined.voto
    WHERE des_voto IN ('Sim', 'Não', 'Obstrução', 'Abstenção')
    GROUP BY ALL
),
grupo AS (
    SELECT id_votacao, cod_partido, max(qtd) AS qtd_maior, sum(qtd) AS qtd_total
    FROM opcao
    GROUP BY id_votacao, cod_partido
    HAVING sum(qtd) >= 3
)
SELECT
    cod_partido,
    count(*)                                                AS qtd_votacoes,
    CAST(avg(100.0 * qtd_maior / qtd_total) AS DECIMAL(5,1)) AS pct_coesao_media
FROM grupo
GROUP BY cod_partido
