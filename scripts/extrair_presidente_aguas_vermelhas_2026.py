#!/usr/bin/env python3
"""Baixa os BUs do 2º turno e extrai Presidente nos dois turnos de 2026.

O 1º turno usa os BUs já preservados em ``dados/raw/boletins``. O 2º turno
usa o pleito 3221 e é preservado separadamente em ``dados/raw/boletins/2o_turno``.
Os votos nominais são gravados em um CSV único, com a coluna ``turno``.
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
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = "https://resultados.tse.jus.br"
AMBIENTE = "oficial"
UF = "mg"
MUNICIPIO = "40193"
ZONA = "0213"
SCHEMA = ROOT / "dados" / "raw" / "spec" / "bu.asn1"
TSE_BU_ZIP = "https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/formato-arquivos-de-bu-rdv-e-assinatura-digital"
ROUNDS = {
    "1": {"eleicao": "6257", "pleito": "3220", "label": "1º turno", "raw_root": ROOT / "dados" / "raw" / "boletins"},
    "2": {"eleicao": "6258", "pleito": "3221", "label": "2º turno", "raw_root": ROOT / "dados" / "raw" / "boletins" / "2o_turno"},
}
USER_AGENT = "consulta-publica-boletins-TSE/1.0"


def get_bytes(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()


def save_bytes(url: str, path: Path, force: bool = False) -> bytes:
    if path.exists() and not force:
        return path.read_bytes()
    raw = get_bytes(url)
    if not raw:
        raise ValueError(f"Arquivo vazio: {url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def save_json(url: str, path: Path, force: bool = False) -> dict:
    raw = save_bytes(url, path, force)
    return json.loads(raw.decode("utf-8-sig"))


def config_url(pleito: str) -> str:
    return f"{HOST}/{AMBIENTE}/ele2026/arquivo-urna/{pleito}/config/{UF}/{UF}-p{int(pleito):06d}-cs.json"


def aux_url(pleito: str, section: str) -> str:
    name = f"p{int(pleito):06d}-{UF}-m{MUNICIPIO}-z{ZONA}-s{section}-aux.json"
    return f"{HOST}/{AMBIENTE}/ele2026/arquivo-urna/{pleito}/dados/{UF}/{MUNICIPIO}/{ZONA}/{section}/{name}"


def candidate_url(election: str) -> str:
    name = f"{UF}{MUNICIPIO}-c0001-e{int(election):06d}-u.json"
    return f"{HOST}/{AMBIENTE}/ele2026/{election}/dados/{UF}/{name}"


def sections(config: dict) -> list[str]:
    result = []
    for scope in config.get("abr", []):
        if str(scope.get("cd", "")).casefold() != UF:
            continue
        for municipality in scope.get("mu", []):
            if str(municipality.get("cd", "")).zfill(5) != MUNICIPIO:
                continue
            for zone in municipality.get("zon", []):
                for section in zone.get("sec", []):
                    if not section.get("nsp"):
                        result.append(str(section.get("ns", "0000")).zfill(4))
    return sorted(set(result))


def choose_bu(aux: dict) -> tuple[dict, dict] | None:
    candidates = []
    for item in aux.get("hashes", []):
        files = [f for f in item.get("arq", []) if str(f.get("tp", "")).casefold() == "bu"]
        if files and str(item.get("st", "")).strip().casefold() == "totalizado":
            candidates.append((item, files[0]))
    return candidates[-1] if candidates else None


def bu_url(pleito: str, section: str, hash_bu: str, filename: str) -> str:
    return (
        f"{HOST}/{AMBIENTE}/ele2026/arquivo-urna/{pleito}/dados/{UF}/{MUNICIPIO}/{ZONA}/{section}/"
        f"{hash_bu}/{urllib.parse.quote(filename)}"
    )


def map_candidates(data: dict) -> dict[tuple[int, int], dict[str, str]]:
    result = {}
    for cargo in data.get("carg", []):
        if int(cargo.get("cd", 0)) != 1:
            continue
        for group in cargo.get("agr", []):
            for party in group.get("par", []):
                party_number = int(party.get("n", 0))
                party_name = str(party.get("sg", f"código {party_number}")).strip()
                for candidate in party.get("cand", []):
                    number = int(candidate["n"])
                    civil = str(candidate.get("nm", "")).strip()
                    urna = str(candidate.get("nmu") or civil).strip()
                    result[(party_number, number)] = {"candidato": urna, "partido": party_name}
    return result


def decode_rows(raw: bytes, codec, election: str, turn: str, section: str, hash_bu: str, candidates: dict) -> list[dict]:
    envelope = codec.decode("EntidadeEnvelopeGenerico", raw)
    bu = codec.decode("EntidadeBoletimUrna", envelope["conteudo"])
    ident = bu["identificacaoSecao"]
    if (str(ident["municipioZona"]["municipio"]).zfill(5), str(ident["municipioZona"]["zona"]).zfill(4), str(ident["secao"]).zfill(4)) != (MUNICIPIO, ZONA, section):
        raise ValueError(f"Identificação divergente na seção {section}")
    rows = []
    for election_data in bu.get("resultadosVotacaoPorEleicao", []):
        if str(election_data.get("idEleicao")) != election:
            continue
        for result in election_data.get("resultadosVotacao", []):
            for cargo in result.get("totaisVotosCargo", []):
                code = cargo.get("codigoCargo")
                code = int(code[-1]) if isinstance(code, tuple) else int(code)
                if code != 1:
                    continue
                for vote in cargo.get("votosVotaveis", []):
                    vote_type = vote.get("tipoVoto")
                    vote_type = int(vote_type[-1]) if isinstance(vote_type, tuple) else int(vote_type)
                    if vote_type != 1:
                        continue
                    target = vote.get("identificacaoVotavel")
                    if not target or int(vote["quantidadeVotos"]) <= 0:
                        continue
                    party_number = int(target["partido"])
                    number = int(target["codigo"])
                    meta = candidates.get((party_number, number), {"candidato": f"Nº {number}", "partido": f"código {party_number}"})
                    rows.append({
                        "municipio": "Águas Vermelhas", "uf": "MG", "zona": ZONA, "secao": section,
                        "turno": turn, "turno_label": ROUNDS[turn]["label"], "eleicao": election,
                        "cargo": "Presidente", "codigo_cargo": 1, "numero": number,
                        "candidato": meta["candidato"], "partido": meta["partido"], "partido_numero": party_number,
                        "votos": int(vote["quantidadeVotos"]), "hash_bu": hash_bu,
                        "status_bu": "Totalizado", "data_emissao_bu": bu.get("dataHoraEmissao", ""),
                    })
    return rows


def download_second_round(force: bool, workers: int) -> tuple[dict, list[str]]:
    spec = ROUNDS["2"]
    root = spec["raw_root"]
    config_path = ROOT / "dados" / "raw" / "config" / f"{UF}-p{int(spec['pleito']):06d}-cs.json"
    config = save_json(config_url(spec["pleito"]), config_path, force)
    sections_list = sections(config)
    manifest = []

    def one(section: str):
        aux_path = root / "auxiliares" / ZONA / section / f"p{int(spec['pleito']):06d}-{UF}-m{MUNICIPIO}-z{ZONA}-s{section}-aux.json"
        aux = save_json(aux_url(spec["pleito"], section), aux_path, force)
        chosen = choose_bu(aux)
        if not chosen:
            raise ValueError("BU com status Totalizado não encontrado")
        info, file_info = chosen
        filename = str(file_info["nm"])
        path = root / ZONA / section / filename
        raw = save_bytes(bu_url(spec["pleito"], section, str(info["hash"]), filename), path, force)
        return {"turno": "2", "zona": ZONA, "secao": section, "status": "Totalizado", "hash_tse": str(info["hash"]), "arquivo": filename, "bytes": len(raw), "sha256_local": hashlib.sha256(raw).hexdigest(), "url": bu_url(spec["pleito"], section, str(info["hash"]), filename), "erro": ""}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, section): section for section in sections_list}
        for future in as_completed(futures):
            section = futures[future]
            try:
                item = future.result()
                print(f"2º turno: seção {section} baixada ({item['bytes']} bytes)")
            except Exception as exc:  # noqa: BLE001 - preserva todos os erros no manifesto
                item = {"turno": "2", "zona": ZONA, "secao": section, "status": "erro", "hash_tse": "", "arquivo": "", "bytes": "", "sha256_local": "", "url": "", "erro": str(exc)}
                print(f"2º turno: seção {section}: ERRO {exc}", file=sys.stderr)
            manifest.append(item)
    manifest.sort(key=lambda item: item["secao"])
    manifest_path = root / "manifesto_boletins_raw.csv"
    fields = ["turno", "zona", "secao", "status", "hash_tse", "arquivo", "bytes", "sha256_local", "url", "erro"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest)
    return config, sections_list


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forcar", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    try:
        import asn1tools
    except ImportError:
        print("Instale com: python3 -m pip install -r scripts/requirements_boletins_tse.txt", file=sys.stderr)
        return 2
    if not SCHEMA.is_file():
        print(f"Schema não encontrado: {SCHEMA}", file=sys.stderr)
        return 2
    first_files = sorted(ROUNDS["1"]["raw_root"].glob(f"{ZONA}/*/*.dat"))
    if not first_files:
        print("Nenhum BU do 1º turno encontrado em dados/raw/boletins.", file=sys.stderr)
        return 2
    print("Baixando candidatos dos dois turnos e os BUs do 2º turno...")
    candidate_maps = {}
    for turn, spec in ROUNDS.items():
        path = ROOT / "dados" / "raw" / "candidatos" / f"{UF}{MUNICIPIO}-c0001-e{int(spec['eleicao']):06d}-u.json"
        data = save_json(candidate_url(spec["eleicao"]), path, args.forcar)
        candidate_maps[turn] = map_candidates(data)
    _, second_sections = download_second_round(args.forcar, max(1, args.workers))
    if len(first_files) != 31 or len(second_sections) != 31:
        print(f"Aviso: BUs principais encontrados: 1º turno={len(first_files)}, 2º turno={len(second_sections)}", file=sys.stderr)
    codec = asn1tools.compile_files([str(SCHEMA)], codec="ber", numeric_enums=True)
    all_rows = []
    for turn, spec in ROUNDS.items():
        files = first_files if turn == "1" else sorted(spec["raw_root"].glob(f"{ZONA}/*/*.dat"))
        for path in files:
            section = path.parent.name
            raw = path.read_bytes()
            all_rows.extend(decode_rows(raw, codec, spec["eleicao"], turn, section, "", candidate_maps[turn]))
    output = ROOT / "dados" / "presidente_por_secao_e_candidato_2026.csv"
    fields = ["municipio", "uf", "zona", "secao", "turno", "turno_label", "eleicao", "cargo", "codigo_cargo", "numero", "candidato", "partido", "partido_numero", "votos", "hash_bu", "status_bu", "data_emissao_bu"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(all_rows, key=lambda row: (row["turno"], row["secao"], -row["votos"], row["numero"])))
    print(f"CSV: {output}")
    for turn, label in (("1", "Presidente 1º turno"), ("2", "Presidente 2º turno")):
        print(f"{label}: {sum(row['votos'] for row in all_rows if row['turno'] == turn):,} votos nominais".replace(",", "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
