-- grão: um deputado do refined.deputado (690)
-- Partido e UF: os do último voto em 2025 (regra 6), calculados só aqui; NULL para quem não votou.
-- Universo de 2025 = legislatura 57 E algum fato no ano (voto, presença ou despesa como deputado).
-- Autoria não conta para "exerceu": assinar proposição não é exercer mandato (ex-deputados no Senado assinam).
WITH ultimo_voto AS (
    SELECT
        id_deputado,
        arg_max(cod_partido, ts_voto) AS cod_partido,
        arg_max(cod_uf, ts_voto)      AS cod_uf
    FROM refined.voto
    GROUP BY id_deputado
),
exerceu AS (
    SELECT id_deputado FROM refined.voto
    UNION
    SELECT id_deputado FROM refined.presenca
    UNION
    SELECT id_deputado FROM refined.despesa WHERE tp_beneficiario = 'deputado'
)
SELECT
    d.id_deputado,
    d.des_nome,
    d.bln_legislatura_atual,
    u.cod_partido,
    u.cod_uf,
    d.id_deputado IN (SELECT id_deputado FROM exerceu)                              AS bln_exerceu_2025,
    d.bln_legislatura_atual AND d.id_deputado IN (SELECT id_deputado FROM exerceu)  AS bln_universo_2025
FROM refined.deputado d
LEFT JOIN ultimo_voto u USING (id_deputado)
