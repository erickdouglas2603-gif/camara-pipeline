-- grão: um deputado do universo de 2025
-- Conta eventos distintos realizados com presença; todos os tipos contam igual, menos o teste do painel
-- (teste de equipamento, como o TESTECOM). Presença em evento não cadastrado (2 linhas) não tem
-- bln_realizado e fica fora pelo JOIN.
-- LEFT JOIN a partir da dimensão: quem não tem presença aparece com 0, não some.
-- É contagem, não taxa: o denominador exigiria saber de que órgãos o deputado é membro.
WITH presencas AS (
    SELECT p.id_deputado, count(DISTINCT p.id_evento) AS qtd_eventos_presente
    FROM refined.presenca p
    JOIN refined.evento e USING (id_evento)
    WHERE e.bln_realizado
      AND e.des_tipo_evento IS DISTINCT FROM 'Teste do Painel Eletrônico'
    GROUP BY p.id_deputado
)
SELECT
    d.id_deputado,
    d.des_nome,
    d.cod_partido,
    d.cod_uf,
    coalesce(p.qtd_eventos_presente, 0) AS qtd_eventos_presente
FROM marts.dim_Deputado d
LEFT JOIN presencas p USING (id_deputado)
WHERE d.bln_universo_2025
