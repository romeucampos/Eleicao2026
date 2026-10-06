#!/usr/bin/env python3
"""Soma votos nominais de governador por distrito/bairro e candidato.

Cruza o CSV nominal extraído dos BUs com o mapa de seções de Águas Vermelhas
e gera um resumo por distrito/bairro e um detalhamento por candidato.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOTES = ROOT / "dados" / "votos_por_secao_e_candidato.csv"
DEFAULT_SECTIONS = ROOT / "dados" / "secoes_por_local_distrito_aguas_vermelhas.csv"
DEFAULT_SUMMARY = ROOT / "dados" / "votos_governador_por_distrito_bairro.csv"
DEFAULT_CANDIDATES = ROOT / "dados" / "votos_governador_por_candidato_distrito_bairro.csv"


def ler_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(4096)
        stream.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        return list(csv.DictReader(stream, delimiter=delimiter))


def escrever_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def carregar_secoes(path: Path):
    rows = ler_csv(path)
    required = {"secao", "local_votacao", "distrito_ou_bairro", "eleitores_aptos"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"O CSV de seções precisa conter: {sorted(required)}")

    sections: dict[str, dict] = {}
    districts: dict[str, dict] = {}
    for row in rows:
        section = str(row["secao"]).strip().zfill(4)
        district = str(row["distrito_ou_bairro"]).strip()
        if not district:
            raise ValueError(f"Distrito/bairro vazio na seção {section}")
        if section in sections:
            raise ValueError(f"Seção duplicada no mapa: {section}")
        key = district.casefold()
        aptos = int(row["eleitores_aptos"])
        sections[section] = {"district": district, "key": key}
        group = districts.setdefault(key, {"district": district, "sections": set(), "locations": set(), "aptos": 0})
        group["sections"].add(section)
        group["locations"].add(str(row["local_votacao"]).strip())
        group["aptos"] += aptos
    return sections, districts


def somar(votes_path: Path, sections_path: Path):
    sections, districts = carregar_secoes(sections_path)
    district_totals: dict[str, int] = defaultdict(int)
    candidate_totals: dict[tuple, int] = defaultdict(int)
    candidate_sections: dict[tuple, set[str]] = defaultdict(set)
    unknown_sections = set()

    for row in ler_csv(votes_path):
        if str(row.get("cargo", "")).strip().casefold() != "governador":
            continue
        section = str(row.get("secao", "")).strip().zfill(4)
        if section not in sections:
            unknown_sections.add(section)
            continue
        try:
            votes = int(row.get("votos", "0"))
        except ValueError as exc:
            raise ValueError(f"Número de votos inválido na seção {section}") from exc
        if votes < 0:
            raise ValueError(f"Votos negativos encontrados na seção {section}")

        district_key = sections[section]["key"]
        district_totals[district_key] += votes
        candidate = (
            district_key,
            str(row.get("numero", "")).strip(),
            str(row.get("candidato", "")).strip(),
            str(row.get("partido", "")).strip(),
        )
        candidate_totals[candidate] += votes
        if votes > 0:
            candidate_sections[candidate].add(section)

    if unknown_sections:
        raise ValueError("Seções sem correspondência no mapa: " + ", ".join(sorted(unknown_sections)))

    summary = []
    for key, group in sorted(districts.items(), key=lambda item: item[1]["district"].casefold()):
        candidates = [
            (number, name, party, votes)
            for (district, number, name, party), votes in candidate_totals.items()
            if district == key and votes > 0
        ]
        candidates.sort(key=lambda item: (-item[3], item[1].casefold(), item[0]))
        leader = candidates[0] if candidates else ("", "", "", 0)
        summary.append({
            "distrito_ou_bairro": group["district"],
            "quantidade_secoes": len(group["sections"]),
            "secoes": ", ".join(sorted(group["sections"])),
            "locais_votacao": " | ".join(sorted(group["locations"], key=str.casefold)),
            "eleitores_aptos": group["aptos"],
            "votos_nominais_governador": district_totals[key],
            "candidato_mais_votado_numero": leader[0],
            "candidato_mais_votado": leader[1],
            "partido_mais_votado": leader[2],
            "votos_do_candidato_mais_votado": leader[3],
        })

    details = []
    for (key, number, name, party), votes in candidate_totals.items():
        if votes <= 0:
            continue
        details.append({
            "distrito_ou_bairro": districts[key]["district"],
            "numero": number,
            "candidato": name,
            "partido": party,
            "votos_nominais": votes,
            "secoes_com_votos": ", ".join(sorted(candidate_sections[(key, number, name, party)])),
        })
    details.sort(key=lambda row: (row["distrito_ou_bairro"].casefold(), -row["votos_nominais"], row["candidato"].casefold()))
    return summary, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--votos", type=Path, default=DEFAULT_VOTES)
    parser.add_argument("--secoes", type=Path, default=DEFAULT_SECTIONS)
    parser.add_argument("--saida", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--saida-candidatos", type=Path, default=DEFAULT_CANDIDATES)
    args = parser.parse_args()
    for path in (args.votos, args.secoes):
        if not path.is_file():
            print(f"Arquivo de entrada não encontrado: {path}", file=sys.stderr)
            return 2
    try:
        summary, details = somar(args.votos, args.secoes)
        escrever_csv(args.saida, list(summary[0]) if summary else [
            "distrito_ou_bairro", "quantidade_secoes", "secoes", "locais_votacao",
            "eleitores_aptos", "votos_nominais_governador", "candidato_mais_votado_numero",
            "candidato_mais_votado", "partido_mais_votado", "votos_do_candidato_mais_votado",
        ], summary)
        escrever_csv(args.saida_candidatos, list(details[0]) if details else [
            "distrito_ou_bairro", "numero", "candidato", "partido", "votos_nominais", "secoes_com_votos",
        ], details)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Erro ao somar: {exc}", file=sys.stderr)
        return 1
    total = sum(int(row["votos_nominais_governador"]) for row in summary)
    print(f"Distritos/bairros: {len(summary)}")
    print(f"Votos nominais de governador: {total:,}".replace(",", "."))
    print(f"Resumo: {args.saida}")
    print(f"Por candidato: {args.saida_candidatos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
