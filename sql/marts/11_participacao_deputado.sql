-- grão: um deputado do universo de 2025
-- Base: só as nominais do Plenário (429): deputado só vota em comissão de que é membro, e a composição
-- das comissões não está nos dados.
-- Janela do primeiro ao último voto no Plenário: não cobra do suplente as votações de antes da posse.
-- Limitação: quem saiu e voltou fica com a janela inteira.
-- Registrados: qualquer valor, inclusive 'Artigo 17' e o voto secreto (NULL).
-- Quem não votou no Plenário: datas e pct NULL, contagens 0.
WITH plenario AS (
    SELECT id_votacao, data_votacao
    FROM refined.votacao
    WHERE cod_orgao = 'PLEN'
      AND qtd_votos_sim + qtd_votos_nao + qtd_votos_outros > 0
      AND NOT bln_orgao_teste
),
janela AS (
    SELECT
        v.id_deputado,
        min(p.data_votacao) AS data_primeiro_voto,
        max(p.data_votacao) AS data_ultimo_voto,
        count(*)            AS qtd_votos_registrados
    FROM refined.voto v
    JOIN plenario p USING (id_votacao)
    GROUP BY v.id_deputado
),
periodo AS (
    SELECT j.id_deputado, count(*) AS qtd_votacoes_no_periodo
    FROM janela j
    JOIN plenario p ON p.data_votacao BETWEEN j.data_primeiro_voto AND j.data_ultimo_voto
    GROUP BY j.id_deputado
)
SELECT
    d.id_deputado,
    d.des_nome,
    d.cod_partido,
    d.cod_uf,
    j.data_primeiro_voto,
    j.data_ultimo_voto,
    coalesce(p.qtd_votacoes_no_periodo, 0) AS qtd_votacoes_no_periodo,
    coalesce(j.qtd_votos_registrados, 0)   AS qtd_votos_registrados,
    CAST(100.0 * j.qtd_votos_registrados / NULLIF(p.qtd_votacoes_no_periodo, 0) AS DECIMAL(5,1)) AS pct_participacao
FROM marts.dim_Deputado d
LEFT JOIN janela j USING (id_deputado)
LEFT JOIN periodo p USING (id_deputado)
WHERE d.bln_universo_2025
