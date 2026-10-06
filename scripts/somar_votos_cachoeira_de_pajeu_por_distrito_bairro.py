#!/usr/bin/env python3
"""Soma votos nominais de Cachoeira de Pajeú por distrito/bairro.

O script aceita senador, deputado federal ou deputado estadual e gera dois
CSVs: o total por distrito/bairro e o detalhe por candidato. A associação
seção -> local/distrito fica em dados/cachoeira_de_pajeu/.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "dados" / "cachoeira_de_pajeu"
DEFAULT_VOTES = BASE / "votos_por_secao_e_candidato.csv"
DEFAULT_SECTIONS = BASE / "secoes_por_local_distrito_bairro.csv"
CARGOS = {
    "senador": ("Senador", "votos_senador_por_distrito_bairro.csv", "votos_senador_por_candidato_distrito_bairro.csv", "votos_nominais_senador"),
    "federal": ("Deputado Federal", "votos_deputado_federal_por_distrito_bairro.csv", "votos_federal_por_candidato_distrito_bairro.csv", "votos_nominais_deputado_federal"),
    "estadual": ("Deputado Estadual", "votos_deputado_estadual_por_distrito_bairro.csv", "votos_estadual_por_candidato_distrito_bairro.csv", "votos_nominais_deputado_estadual"),
}


def ler_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(4096)
        stream.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        return list(csv.DictReader(stream, delimiter=delimiter))


def escrever_csv(path: Path, campos: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=campos, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def carregar_mapa(path: Path):
    rows = ler_csv(path)
    obrigatorias = {"secao", "local_votacao", "codigo_local", "distrito_ou_bairro"}
    if not rows or not obrigatorias.issubset(rows[0]):
        raise ValueError(f"O mapa precisa conter: {sorted(obrigatorias)}")
    mapa = {}
    grupos = {}
    for row in rows:
        secao = str(row["secao"]).strip().zfill(4)
        if secao in mapa:
            raise ValueError(f"Seção duplicada no mapa: {secao}")
        distrito = str(row["distrito_ou_bairro"]).strip()
        chave = distrito.casefold()
        mapa[secao] = {"distrito": distrito, "chave": chave,
                       "local": str(row["local_votacao"]).strip(),
                       "codigo_local": str(row["codigo_local"]).strip(),
                       "aptos_federal": str(row.get("eleitores_aptos", "")).strip(),
                       "aptos_estadual": str(row.get("eleitores_aptos_estadual", row.get("eleitores_aptos", ""))).strip()}
        grupo = grupos.setdefault(chave, {"distrito": distrito, "secoes": set(), "locais": set(), "aptos_federal": [], "aptos_estadual": []})
        grupo["secoes"].add(secao)
        grupo["locais"].add(mapa[secao]["local"])
        for campo in ("aptos_federal", "aptos_estadual"):
            if mapa[secao][campo]:
                grupo[campo].append(int(mapa[secao][campo]))
    return mapa, grupos


def somar(votos_path: Path, mapa_path: Path, cargo: str):
    mapa, grupos = carregar_mapa(mapa_path)
    nome_cargo = CARGOS[cargo][0]
    totais = defaultdict(int)
    candidatos = defaultdict(int)
    secoes_com_votos = defaultdict(set)
    desconhecidas = set()
    for row in ler_csv(votos_path):
        if str(row.get("cargo", "")).strip().casefold() != nome_cargo.casefold():
            continue
        secao = str(row.get("secao", "")).strip().zfill(4)
        if secao not in mapa:
            desconhecidas.add(secao)
            continue
        try:
            votos = int(row.get("votos", "0"))
        except ValueError as exc:
            raise ValueError(f"Votos inválidos na seção {secao}") from exc
        if votos < 0:
            raise ValueError(f"Votos negativos na seção {secao}")
        info = mapa[secao]
        chave_distrito = info["chave"]
        totais[chave_distrito] += votos
        chave = (chave_distrito, str(row.get("numero", "")).strip(),
                 str(row.get("candidato", "")).strip(), str(row.get("partido", "")).strip())
        candidatos[chave] += votos
        if votos > 0:
            secoes_com_votos[chave].add(secao)
    if desconhecidas:
        raise ValueError("Seções sem mapeamento: " + ", ".join(sorted(desconhecidas)))

    resumo = []
    for chave, grupo in grupos.items():
        ranking = [(numero, nome, partido, valor) for (dist, numero, nome, partido), valor in candidatos.items() if dist == chave and valor > 0]
        ranking.sort(key=lambda row: (-row[3], row[1].casefold(), row[0]))
        lider = ranking[0] if ranking else ("", "", "", 0)
        resumo.append({
            "distrito_ou_bairro": grupo["distrito"],
            "quantidade_secoes": len(grupo["secoes"]),
            "secoes": ", ".join(sorted(grupo["secoes"])),
            "locais_votacao": " | ".join(sorted(grupo["locais"], key=str.casefold)),
            "eleitores_aptos": sum(grupo["aptos_estadual"] if cargo == "estadual" else grupo["aptos_federal"]),
            CARGOS[cargo][3]: totais[chave],
            "candidato_mais_votado_numero": lider[0],
            "candidato_mais_votado": lider[1],
            "partido_mais_votado": lider[2],
            "votos_do_candidato_mais_votado": lider[3],
        })
    resumo.sort(key=lambda row: (-int(row[CARGOS[cargo][3]]), row["distrito_ou_bairro"].casefold()))
    detalhe = []
    for (chave, numero, nome, partido), votos in candidatos.items():
        if votos <= 0:
            continue
        detalhe.append({
            "distrito_ou_bairro": grupos[chave]["distrito"], "numero": numero,
            "candidato": nome, "partido": partido, "votos_nominais": votos,
            "secoes_com_votos": ", ".join(sorted(secoes_com_votos[(chave, numero, nome, partido)])),
        })
    detalhe.sort(key=lambda row: (row["distrito_ou_bairro"].casefold(), -int(row["votos_nominais"]), row["candidato"].casefold()))
    return resumo, detalhe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cargo", choices=sorted(CARGOS), default="senador")
    parser.add_argument("--votos", type=Path, default=DEFAULT_VOTES)
    parser.add_argument("--secoes", type=Path, default=DEFAULT_SECTIONS)
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--saida-candidatos", type=Path)
    args = parser.parse_args()
    if not args.votos.is_file() or not args.secoes.is_file():
        print("CSV de votos ou mapa de seções não encontrado", file=sys.stderr)
        return 2
    nome, resumo_nome, detalhe_nome, campo_total = CARGOS[args.cargo]
    args.saida = args.saida or BASE / resumo_nome
    args.saida_candidatos = args.saida_candidatos or BASE / detalhe_nome
    try:
        resumo, detalhe = somar(args.votos, args.secoes, args.cargo)
        escrever_csv(args.saida, list(resumo[0]) if resumo else ["distrito_ou_bairro", "quantidade_secoes", "secoes", "locais_votacao", "eleitores_aptos", campo_total], resumo)
        escrever_csv(args.saida_candidatos, list(detalhe[0]) if detalhe else ["distrito_ou_bairro", "numero", "candidato", "partido", "votos_nominais", "secoes_com_votos"], detalhe)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Erro ao somar: {exc}", file=sys.stderr)
        return 1
    print(f"Cargo: {nome}")
    print(f"Distritos/bairros: {len(resumo)}")
    print(f"Votos nominais: {sum(int(row[campo_total]) for row in resumo):,}".replace(",", "."))
    print(f"Resumo: {args.saida}")
    print(f"Por candidato: {args.saida_candidatos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
