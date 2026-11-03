"""Baixa os 10 arquivos brutos da Câmara para raw/ e grava o manifesto.

Uso: uv run python -m pipeline.download

Spec: docs/specs/01-ingestao.md, seção "SPEC DO pipeline/download.py".
Importa apenas pipeline.db; não importa ingestao.py.
Motivo: download e ingestão são independentes. A ingestão roda sem internet,
sempre sobre o mesmo retrato que está em raw/.

B1. Baixa os 10 arquivos do mapa (ARQUIVOS em pipeline.db) para raw/, com os
    nomes do mapa, sem descompactar e sem alterar o conteúdo.
B2. Tudo ou nada:
    - se raw/_tmp/ existir no início (execução interrompida), apaga antes de
      começar;
    - baixa primeiro para raw/_tmp/;
    - para no primeiro arquivo que esgotar as tentativas, sem tentar os
      seguintes; nesse caso apaga raw/_tmp/, não toca em raw/ e sys.exit(1);
    - só se os 10 baixarem, move todos para raw/ substituindo os anteriores,
      e só então grava o manifesto.
    Motivo: raw/ nunca fica com metade dos arquivos de um dia e metade de
    outro. Uma queda durante a etapa de mover não é tratada aqui: quem
    detecta é a ingestão (I7, sha256).
B3. Cada arquivo: até 3 tentativas no total, com espera de 5 e 10 segundos
    entre elas. timeout=120 do requests (inatividade de conexão e leitura, não
    duração total). Resposta diferente de 200 conta como falha.
B4. Manifesto raw/_manifesto.json, uma entrada por arquivo: tabela, arquivo,
    url, baixado_em (ISO 8601 com fuso America/Sao_Paulo), bytes, sha256.
    Motivo: os arquivos da Câmara mudam todo dia; o manifesto diz de quando é
    o retrato.
B5. Saída: uma linha por arquivo com nome e tamanho em MB; a última linha diz
    "Retrato de dd/mm/aaaa HH:MM" (horário de Brasília), com o maior
    baixado_em do manifesto. stdout reconfigurado para utf-8.
"""

import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from pipeline.db import ARQUIVO_MANIFESTO, ARQUIVOS, PASTA_RAW

FUSO = ZoneInfo("America/Sao_Paulo")
PASTA_TMP = PASTA_RAW / "_tmp"
ESPERAS = (5, 10)  # B3: 3 tentativas => 2 esperas entre elas
TIMEOUT = 120
BLOCO = 1024 * 1024


class FalhaDownload(Exception):
    pass


def _tentar(url: str, destino: Path) -> tuple[int, str]:
    """Uma tentativa. Devolve (bytes, sha256) do que foi gravado em disco."""
    with requests.get(url, stream=True, timeout=TIMEOUT) as resp:
        # Redirecionamentos (http -> https) são seguidos; vale o status final.
        if resp.status_code != 200:
            raise FalhaDownload(f"HTTP {resp.status_code}")
        h = hashlib.sha256()
        total = 0
        with open(destino, "wb") as f:
            # iter_content desfaz só a codificação de transporte (gzip do
            # HTTP); o arquivo gravado é o mesmo publicado pela Câmara (B1).
            for bloco in resp.iter_content(BLOCO):
                f.write(bloco)
                h.update(bloco)
                total += len(bloco)
    return total, h.hexdigest()


def _baixar(url: str, destino: Path) -> tuple[int, str]:
    """B3: até 3 tentativas, esperando 5 s e 10 s entre elas."""
    ultimo_erro = ""
    for tentativa in range(len(ESPERAS) + 1):
        try:
            return _tentar(url, destino)
        except (requests.RequestException, OSError, FalhaDownload) as e:
            ultimo_erro = f"{type(e).__name__}: {e}"
            destino.unlink(missing_ok=True)
            if tentativa < len(ESPERAS):
                print(
                    f"  tentativa {tentativa + 1} falhou ({ultimo_erro}); "
                    f"nova tentativa em {ESPERAS[tentativa]} s",
                    file=sys.stderr,
                )
                time.sleep(ESPERAS[tentativa])
    raise FalhaDownload(ultimo_erro)


def _retrato(manifesto: list[dict]) -> str:
    maior = max(datetime.fromisoformat(e["baixado_em"]) for e in manifesto)
    return maior.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


def _mb(n: int) -> str:
    # MB decimal (10^6 bytes), vírgula decimal, como no resto da saída em pt-BR.
    return f"{n / 1_000_000:.1f}".replace(".", ",")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    if PASTA_TMP.exists():
        shutil.rmtree(PASTA_TMP)
    PASTA_TMP.mkdir(parents=True)

    manifesto = []
    for tabela, info in ARQUIVOS.items():
        destino = PASTA_TMP / info["arquivo"]
        try:
            n_bytes, sha = _baixar(info["url"], destino)
        except FalhaDownload as e:
            print(
                f"ERRO: {info['arquivo']} falhou após 3 tentativas ({e}).\n"
                f"Nada foi alterado em {PASTA_RAW}.",
                file=sys.stderr,
            )
            shutil.rmtree(PASTA_TMP, ignore_errors=True)
            sys.exit(1)
        manifesto.append(
            {
                "tabela": tabela,
                "arquivo": info["arquivo"],
                "url": info["url"],
                "baixado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
                "bytes": n_bytes,
                "sha256": sha,
            }
        )
        print(f"{info['arquivo']:<36} {_mb(n_bytes):>8} MB")

    for e in manifesto:
        os.replace(PASTA_TMP / e["arquivo"], PASTA_RAW / e["arquivo"])

    # Grava o manifesto num arquivo ao lado e troca de uma vez, para nunca
    # existir um _manifesto.json pela metade.
    tmp_manifesto = ARQUIVO_MANIFESTO.with_suffix(".json.tmp")
    tmp_manifesto.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp_manifesto, ARQUIVO_MANIFESTO)
    PASTA_TMP.rmdir()

    print(f"Retrato de {_retrato(manifesto)}")


if __name__ == "__main__":
    main()
