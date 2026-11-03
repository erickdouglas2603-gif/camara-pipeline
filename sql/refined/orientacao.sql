SELECT
    idVotacao     AS id_votacao,
    siglaOrgao    AS cod_orgao,
    descricao     AS des_votacao,
    siglaBancada  AS cod_bancada,
    orientacao    AS des_orientacao
FROM raw.votacoesOrientacoes
