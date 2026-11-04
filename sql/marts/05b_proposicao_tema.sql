-- grão: tema x grupo de tipo de proposição (PL, RIC, INC, Outros)
-- Mesmo recorte do M05: apresentadas em 2025, proponente, autor deputado do universo de 2025.
-- Existe para o gráfico 5: somar o M05 por tema no Python contaria a mesma proposição uma vez por proponente.
-- Grupos: RIC, PL e INC concentram o recorte; os outros 7 tipos somam menos de 1.000 e viram 'Outros'.
-- Cada proposição tem um tipo só, então os grupos não se sobrepõem: as 4 barras de um tema somam
-- exatamente qtd_proposicoes_tema, que repete nas linhas do tema e serve só para ordenar.
WITH recorte AS (
    SELECT
        t.cod_tema,
        t.des_tema,
        p.id_proposicao,
        a.id_deputado,
        CASE WHEN p.cod_sigla_tipo IN ('PL', 'RIC', 'INC') THEN p.cod_sigla_tipo ELSE 'Outros' END
            AS cod_tipo_grupo
    FROM refined.autoria a
    JOIN refined.proposicao p USING (id_proposicao)
    JOIN refined.tema t USING (id_proposicao)
    JOIN marts.dim_Deputado d
      ON d.id_deputado = a.id_deputado
     AND d.bln_universo_2025
    WHERE p.num_ano = 2025
      AND a.bln_proponente
),
tema AS (
    SELECT cod_tema, count(DISTINCT id_proposicao) AS qtd_proposicoes_tema
    FROM recorte
    GROUP BY cod_tema
)
SELECT
    r.cod_tema,
    r.des_tema,
    r.cod_tipo_grupo,
    count(DISTINCT r.id_proposicao) AS qtd_proposicoes,
    any_value(t.qtd_proposicoes_tema) AS qtd_proposicoes_tema,
    count(DISTINCT r.id_deputado)   AS qtd_deputados
FROM recorte r
JOIN tema t USING (cod_tema)
GROUP BY r.cod_tema, r.des_tema, r.cod_tipo_grupo
