#!/usr/bin/env python3
"""Agrega os votos de Presidente do 1º e do 2º turno por distrito/bairro."""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOTES = ROOT / "dados" / "presidente_por_secao_e_candidato_2026.csv"
DEFAULT_SECTIONS = ROOT / "dados" / "secoes_por_local_distrito_aguas_vermelhas.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(4096)
        stream.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        return list(csv.DictReader(stream, delimiter=delimiter))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def aggregate(votes: list[dict[str, str]], section_rows: list[dict[str, str]], turn: str):
    sections = {}
    districts = {}
    for row in section_rows:
        section = str(row["secao"]).strip().zfill(4)
        district = str(row["distrito_ou_bairro"]).strip()
        key = district.casefold()
        sections[section] = key
        group = districts.setdefault(key, {"district": district, "sections": set(), "locations": set(), "aptos": 0})
        group["sections"].add(section)
        group["locations"].add(str(row["local_votacao"]).strip())
        group["aptos"] += int(row["eleitores_aptos"])
    district_totals = defaultdict(int)
    candidate_totals = defaultdict(int)
    candidate_sections = defaultdict(set)
    for row in votes:
        if row.get("turno") != turn or row.get("cargo", "").casefold() != "presidente":
            continue
        section = str(row.get("secao", "")).zfill(4)
        if section not in sections:
            raise ValueError(f"Seção sem correspondência no mapa: {section}")
        key = sections[section]
        votes_count = int(row.get("votos", 0))
        if votes_count < 0:
            raise ValueError(f"Votos negativos na seção {section}")
        candidate = (key, row["numero"].strip(), row["candidato"].strip(), row["partido"].strip())
        district_totals[key] += votes_count
        candidate_totals[candidate] += votes_count
        if votes_count:
            candidate_sections[candidate].add(section)
    summary = []
    for key, group in sorted(districts.items(), key=lambda item: item[1]["district"].casefold()):
        candidates = [(number, name, party, count) for (district, number, name, party), count in candidate_totals.items() if district == key and count > 0]
        candidates.sort(key=lambda item: (-item[3], item[1].casefold(), item[0]))
        leader = candidates[0] if candidates else ("", "", "", 0)
        summary.append({
            "distrito_ou_bairro": group["district"], "quantidade_secoes": len(group["sections"]),
            "secoes": ", ".join(sorted(group["sections"])), "locais_votacao": " | ".join(sorted(group["locations"], key=str.casefold)),
            "eleitores_aptos": group["aptos"], "votos_nominais_presidente": district_totals[key],
            "candidato_mais_votado_numero": leader[0], "candidato_mais_votado": leader[1],
            "partido_mais_votado": leader[2], "votos_do_candidato_mais_votado": leader[3],
        })
    details = []
    for (key, number, name, party), count in candidate_totals.items():
        if count > 0:
            details.append({"distrito_ou_bairro": districts[key]["district"], "numero": number, "candidato": name, "partido": party, "votos_nominais": count, "secoes_com_votos": ", ".join(sorted(candidate_sections[(key, number, name, party)]))})
    details.sort(key=lambda row: (row["distrito_ou_bairro"].casefold(), -row["votos_nominais"], row["candidato"].casefold()))
    return summary, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--votos", type=Path, default=DEFAULT_VOTES)
    parser.add_argument("--secoes", type=Path, default=DEFAULT_SECTIONS)
    args = parser.parse_args()
    if not args.votos.is_file() or not args.secoes.is_file():
        print("CSV de votos ou mapa de seções não encontrado.", file=sys.stderr)
        return 2
    votes, section_rows = read_csv(args.votos), read_csv(args.secoes)
    fields_summary = ["distrito_ou_bairro", "quantidade_secoes", "secoes", "locais_votacao", "eleitores_aptos", "votos_nominais_presidente", "candidato_mais_votado_numero", "candidato_mais_votado", "partido_mais_votado", "votos_do_candidato_mais_votado"]
    fields_details = ["distrito_ou_bairro", "numero", "candidato", "partido", "votos_nominais", "secoes_com_votos"]
    for turn in ("1", "2"):
        summary, details = aggregate(votes, section_rows, turn)
        write_csv(ROOT / "dados" / f"votos_presidente_{turn}_turno_por_distrito_bairro.csv", fields_summary, summary)
        write_csv(ROOT / "dados" / f"votos_presidente_{turn}_turno_por_candidato_distrito_bairro.csv", fields_details, details)
        print(f"Presidente {turn}º turno: {sum(row['votos_nominais_presidente'] for row in summary):,} votos; {len(details)} combinações candidato/distrito".replace(",", "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
