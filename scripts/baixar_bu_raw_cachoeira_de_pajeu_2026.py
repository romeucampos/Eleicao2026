#!/usr/bin/env python3
"""Baixa e preserva os boletins de urna brutos de Cachoeira de Pajeú/MG.

O script consulta a configuração oficial de seções do TSE, consulta o
auxiliar de cada seção, escolhe o BU com status ``Totalizado`` e salva o
arquivo binário original (ASN.1) sem alterá-lo.

Os arquivos são gravados em ``dados/raw/cachoeira_de_pajeu/`` por padrão.
O manifesto registra a URL de origem e o SHA-256 local de cada arquivo.
Requer somente a biblioteca padrão do Python 3.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "https://resultados.tse.jus.br"
AMBIENTE = "oficial"
UF = "mg"
CODIGO_MUNICIPIO = "40533"  # Cachoeira de Pajeú
NOME_MUNICIPIO = "Cachoeira de Pajeú"
ZONA_ELEITORAL = "0213"
PLEITO = "3220"
USER_AGENT = "consulta-publica-boletins-TSE/1.0"


def requisitar(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()


def salvar_json(url: str, destino: Path, forcar: bool) -> dict:
    if destino.exists() and not forcar:
        bruto = destino.read_bytes()
    else:
        bruto = requisitar(url)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(bruto)
    return json.loads(bruto.decode("utf-8-sig"))


def url_config() -> str:
    nome = f"{UF}-p{int(PLEITO):06d}-cs.json"
    return f"{HOST}/{AMBIENTE}/ele2026/arquivo-urna/{PLEITO}/config/{UF}/{nome}"


def secoes_principais(config: dict):
    for abrangencia in config.get("abr", []):
        if str(abrangencia.get("cd", "")).lower() != UF:
            continue
        for municipio in abrangencia.get("mu", []):
            if str(municipio.get("cd", "")).zfill(5) != CODIGO_MUNICIPIO:
                continue
            for zona in municipio.get("zon", []):
                zona_id = str(zona.get("cd", "0000")).zfill(4)
                for secao in zona.get("sec", []):
                    if secao.get("nsp"):
                        continue
                    yield zona_id, str(secao.get("ns", "0000")).zfill(4)


def url_aux(zona: str, secao: str) -> str:
    nome = f"p{int(PLEITO):06d}-{UF}-m{CODIGO_MUNICIPIO}-z{zona}-s{secao}-aux.json"
    return (
        f"{HOST}/{AMBIENTE}/ele2026/arquivo-urna/{PLEITO}/dados/"
        f"{UF}/{CODIGO_MUNICIPIO}/{zona}/{secao}/{nome}"
    )


def escolher_bu(aux: dict):
    encontrados = []
    for ordem, registro in enumerate(aux.get("hashes", [])):
        arquivos = [
            arquivo for arquivo in registro.get("arq", [])
            if str(arquivo.get("tp", "")).lower() == "bu"
        ]
        if arquivos and str(registro.get("st", "")).strip().casefold() == "totalizado":
            encontrados.append((ordem, registro, arquivos))
    if not encontrados:
        return None
    _, registro, arquivos = encontrados[-1]
    return registro, arquivos[0]


def url_bu(zona: str, secao: str, hash_bu: str, nome: str) -> str:
    return (
        f"{HOST}/{AMBIENTE}/ele2026/arquivo-urna/{PLEITO}/dados/"
        f"{UF}/{CODIGO_MUNICIPIO}/{zona}/{secao}/{hash_bu}/"
        f"{urllib.parse.quote(nome)}"
    )


def gravar_manifesto(destino: Path, linhas: list[dict]) -> None:
    campos = [
        "municipio", "uf", "codigo_municipio", "zona", "secao", "status",
        "hash_tse", "arquivo", "url", "caminho_local", "bytes",
        "sha256_local", "erro",
    ]
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pasta", type=Path,
        default=Path("dados/raw/cachoeira_de_pajeu"),
        help="pasta de destino (padrão: dados/raw/cachoeira_de_pajeu)",
    )
    parser.add_argument("--forcar", action="store_true", help="baixa novamente arquivos existentes")
    parser.add_argument("--pausa", type=float, default=0.25, help="intervalo entre requisições")
    args = parser.parse_args()
    args.pasta.mkdir(parents=True, exist_ok=True)

    config_path = args.pasta / "config" / f"{UF}-p{int(PLEITO):06d}-cs.json"
    print(f"Baixando a configuração de seções de {NOME_MUNICIPIO} (EA16)...")
    try:
        config = salvar_json(url_config(), config_path, args.forcar)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"Falha ao obter a configuração: {exc}", file=sys.stderr)
        return 1

    secoes = list(secoes_principais(config))
    if not secoes:
        print(f"Nenhuma seção principal encontrada para {CODIGO_MUNICIPIO}.", file=sys.stderr)
        return 1

    manifesto = []
    baixados = 0
    for indice, (zona, secao) in enumerate(secoes, 1):
        linha = {
            "municipio": NOME_MUNICIPIO, "uf": UF.upper(),
            "codigo_municipio": CODIGO_MUNICIPIO, "zona": zona,
            "secao": secao, "status": "erro", "hash_tse": "",
            "arquivo": "", "url": "", "caminho_local": "", "bytes": "",
            "sha256_local": "", "erro": "",
        }
        try:
            nome_aux = f"p{int(PLEITO):06d}-{UF}-m{CODIGO_MUNICIPIO}-z{zona}-s{secao}-aux.json"
            aux_path = args.pasta / "auxiliares" / zona / secao / nome_aux
            aux = salvar_json(url_aux(zona, secao), aux_path, args.forcar)
            escolhido = escolher_bu(aux)
            if escolhido is None:
                linha.update(status="sem_BU_totalizado", erro="BU totalizado não encontrado")
                manifesto.append(linha)
                print(f"[{indice}/{len(secoes)}] {zona}/{secao}: sem BU totalizado")
                time.sleep(max(args.pausa, 0))
                continue

            registro, arquivo = escolhido
            hash_bu = str(registro.get("hash", ""))
            nome = str(arquivo["nm"])
            url = url_bu(zona, secao, hash_bu, nome)
            destino = args.pasta / "boletins" / zona / secao / nome
            if destino.exists() and not args.forcar:
                bruto = destino.read_bytes()
            else:
                bruto = requisitar(url)
                if not bruto:
                    raise ValueError("O TSE retornou um arquivo vazio")
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(bruto)

            linha.update(
                status="Totalizado", hash_tse=hash_bu, arquivo=nome, url=url,
                caminho_local=str(destino), bytes=len(bruto),
                sha256_local=hashlib.sha256(bruto).hexdigest(),
            )
            baixados += 1
            print(f"[{indice}/{len(secoes)}] {zona}/{secao}: {nome} ({len(bruto)} bytes)")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                OSError, ValueError, KeyError) as exc:
            linha["erro"] = str(exc)
            print(f"[{indice}/{len(secoes)}] {zona}/{secao}: ERRO {exc}", file=sys.stderr)
        manifesto.append(linha)
        time.sleep(max(args.pausa, 0))

    manifesto_path = args.pasta / "manifesto_boletins_raw.csv"
    gravar_manifesto(manifesto_path, manifesto)
    falhas = sum(linha["status"] != "Totalizado" for linha in manifesto)
    print(f"Boletins totalizados disponíveis: {baixados}/{len(secoes)}")
    print(f"Manifesto: {manifesto_path}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
