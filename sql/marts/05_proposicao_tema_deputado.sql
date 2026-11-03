-- grão: deputado x tema x tipo de proposição
-- Recorte: apresentadas em 2025 (autoria, não tramitação), autor deputado, proponente, e autor no universo
-- de 2025 (o JOIN com a dimensão tira 31 ex-deputados hoje em outra casa).
-- Proposição com vários proponentes conta para cada um, e com vários temas conta em cada tema:
-- a soma do mart é maior que o total de proposições, por construção.
-- O tipo fica como coluna para o dashboard filtrar. Só 18% das proposições têm tema.
SELECT
    d.id_deputado,
    d.des_nome,
    t.cod_tema,
    t.des_tema,
    p.cod_sigla_tipo,
    count(DISTINCT p.id_proposicao) AS qtd_proposicoes
FROM refined.autoria a
JOIN refined.proposicao p USING (id_proposicao)
JOIN refined.tema t USING (id_proposicao)
JOIN marts.dim_Deputado d
  ON d.id_deputado = a.id_deputado
 AND d.bln_universo_2025
WHERE p.num_ano = 2025
  AND a.bln_proponente
GROUP BY ALL
