#!/usr/bin/env python3
"""Extrai votos nominais dos BUs brutos de Cachoeira de Pajeú/MG.

Lê somente os arquivos ``.dat`` preservados por
``baixar_bu_raw_cachoeira_de_pajeu_2026.py`` e usa o schema ASN.1 oficial do
TSE. Os cargos incluídos são senador, deputado federal e deputado estadual.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
import zipfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path

HOST = "https://resultados.tse.jus.br"
AMBIENTE = "oficial"
UF = "mg"
CODIGO_MUNICIPIO = "40533"
NOME_MUNICIPIO = "Cachoeira de Pajeú"
PLEITO = "3220"
ELEICAO = "6259"
CARGOS = {5: "Senador", 6: "Deputado Federal", 7: "Deputado Estadual"}
SCHEMA_URL = "https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/formato-arquivos-de-bu-rdv-e-assinatura-digital"
USER_AGENT = "consulta-publica-resultados-TSE/1.0"


def get_bytes(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()


def save_json(url: str, path: Path, force: bool) -> dict:
    if path.exists() and not force:
        raw = path.read_bytes()
    else:
        raw = get_bytes(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return json.loads(raw.decode("utf-8-sig"))


def digito(value) -> int:
    return int(value[-1] if isinstance(value, tuple) else value)


def mapear_candidatos(data: dict):
    nomes = {}
    nomes_completos = {}
    partidos = {}
    for cargo in data.get("carg", []):
        codigo_cargo = int(cargo.get("cd", 0))
        for agrupamento in cargo.get("agr", []):
            for partido in agrupamento.get("par", []):
                try:
                    cod_partido = int(partido.get("n", 0))
                except (TypeError, ValueError):
                    cod_partido = 0
                if cod_partido:
                    partidos[cod_partido] = partido.get("sg", f"código {cod_partido}")
                for candidato in partido.get("cand", []):
                    try:
                        numero = int(candidato["n"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    nome_completo = candidato.get("nm", f"Nº {numero}")
                    nome_urna = candidato.get("nmu") or nome_completo
                    nomes[(codigo_cargo, cod_partido, numero)] = nome_urna
                    nomes_completos[(codigo_cargo, cod_partido, numero)] = nome_completo
    return nomes, nomes_completos, partidos


def carregar_schema(pasta: Path, force: bool) -> Path:
    schema = pasta / "schema" / "bu.asn1"
    if schema.exists() and not force:
        return schema
    raw = get_bytes(SCHEMA_URL)
    schema.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        schema.write_bytes(archive.read("spec/bu.asn1"))
    return schema


def ler_bu(raw: bytes, codec):
    envelope = codec.decode("EntidadeEnvelopeGenerico", raw)
    return codec.decode("EntidadeBoletimUrna", envelope["conteudo"])


def extrair(bu: dict, nomes: dict, nomes_completos: dict, partidos: dict,
            zona: str, secao: str, hash_bu: str):
    identificacao = bu["identificacaoSecao"]
    idmun = identificacao["municipioZona"]["municipio"]
    idzona = identificacao["municipioZona"]["zona"]
    idsecao = identificacao["secao"]
    esperado = (CODIGO_MUNICIPIO, zona, secao)
    recebido = (str(idmun).zfill(5), str(idzona).zfill(4), str(idsecao).zfill(4))
    if recebido != esperado:
        raise ValueError(f"Identificação divergente: esperado {esperado}, recebido {recebido}")

    rows = []
    for eleicao in bu.get("resultadosVotacaoPorEleicao", []):
        if str(eleicao.get("idEleicao")) != ELEICAO:
            continue
        for resultado in eleicao.get("resultadosVotacao", []):
            for cargo in resultado.get("totaisVotosCargo", []):
                codigo_cargo = digito(cargo["codigoCargo"])
                if codigo_cargo not in CARGOS:
                    continue
                for voto in cargo.get("votosVotaveis", []):
                    if digito(voto["tipoVoto"]) != 1:
                        continue
                    votavel = voto.get("identificacaoVotavel")
                    if not votavel:
                        continue
                    numero = int(votavel["codigo"])
                    cod_partido = int(votavel["partido"])
                    quantidade = int(voto["quantidadeVotos"])
                    if quantidade <= 0:
                        continue
                    chave = (codigo_cargo, cod_partido, numero)
                    rows.append({
                        "municipio": NOME_MUNICIPIO, "uf": "MG", "zona": zona,
                        "secao": secao, "eleicao": ELEICAO,
                        "cargo": CARGOS[codigo_cargo], "codigo_cargo": codigo_cargo,
                        "numero": numero, "candidato": nomes.get(chave, f"Nº {numero}"),
                        "nome_completo": nomes_completos.get(chave, ""),
                        "partido": partidos.get(cod_partido, f"código {cod_partido}"),
                        "partido_numero": cod_partido, "votos": quantidade,
                        "data_emissao_bu": bu.get("dataHoraEmissao", ""),
                        "hash_bu": hash_bu, "status_bu": "Totalizado",
                    })
    return rows


def gravar_csv(path: Path, rows: list[dict], campos: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", type=Path, default=Path("dados/raw/cachoeira_de_pajeu"),
                        help="pasta dos BUs brutos e auxiliares")
    parser.add_argument("--saida", type=Path,
                        default=Path("dados/cachoeira_de_pajeu/votos_por_secao_e_candidato.csv"))
    parser.add_argument("--forcar", action="store_true", help="baixa novamente schema e candidatos")
    args = parser.parse_args()

    try:
        import asn1tools
    except ImportError:
        print("Instale a dependência: python3 -m pip install -r scripts/requirements_boletins_tse.txt", file=sys.stderr)
        return 2

    try:
        schema = carregar_schema(args.pasta, args.forcar)
        codec = asn1tools.compile_files([str(schema)], codec="ber", numeric_enums=True)
        nomes = {}
        nomes_completos = {}
        partidos = {}
        for codigo in CARGOS:
            filename = f"{UF}{CODIGO_MUNICIPIO}-c{codigo:04d}-e{int(ELEICAO):06d}-u.json"
            url = f"{HOST}/{AMBIENTE}/ele2026/{ELEICAO}/dados/{UF}/{filename}"
            data = save_json(url, args.pasta / "candidatos" / filename, args.forcar)
            n, nc, p = mapear_candidatos(data)
            nomes.update(n)
            nomes_completos.update(nc)
            partidos.update(p)

        rows = []
        erros = []
        boletins = sorted((args.pasta / "boletins").glob("*/*/*-bu.dat"))
        if not boletins:
            raise FileNotFoundError(f"Nenhum .dat encontrado em {args.pasta / 'boletins'}")
        for path in boletins:
            partes = path.parts
            zona, secao = partes[-3], partes[-2]
            aux_path = args.pasta / "auxiliares" / zona / secao / f"p{int(PLEITO):06d}-{UF}-m{CODIGO_MUNICIPIO}-z{zona}-s{secao}-aux.json"
            try:
                aux = json.loads(aux_path.read_text(encoding="utf-8-sig"))
                totalizados = [h for h in aux.get("hashes", []) if str(h.get("st", "")).casefold() == "totalizado"]
                hash_bu = totalizados[-1].get("hash", "") if totalizados else ""
                rows.extend(extrair(ler_bu(path.read_bytes(), codec), nomes, nomes_completos, partidos, zona, secao, hash_bu))
                print(f"{zona}/{secao}: {len(rows)} registros acumulados")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                erros.append(f"{zona}/{secao}: {exc}")
                print(f"{zona}/{secao}: ERRO {exc}", file=sys.stderr)

        campos = ["municipio", "uf", "zona", "secao", "eleicao", "cargo", "codigo_cargo",
                  "numero", "candidato", "nome_completo", "partido", "partido_numero",
                  "votos", "data_emissao_bu", "hash_bu", "status_bu"]
        gravar_csv(args.saida, sorted(rows, key=lambda r: (r["codigo_cargo"], r["zona"], r["secao"], -r["votos"])), campos)
        print(f"CSV por seção: {args.saida}")
        print(f"BUs processados: {len(boletins) - len(erros)}/{len(boletins)}")
        for cargo in CARGOS.values():
            total = sum(r["votos"] for r in rows if r["cargo"] == cargo)
            print(f"{cargo}: {total:,} votos nominais".replace(",", "."))
        if erros:
            print("Erros:\n" + "\n".join(erros), file=sys.stderr)
            return 1
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as exc:
        print(f"Falha na extração: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
