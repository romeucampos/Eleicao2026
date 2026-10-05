#!/usr/bin/env python3
"""Soma votos nominais estaduais por distrito/bairro e por candidato.

Usa o CSV por seção produzido pelo processamento dos boletins de urna brutos
e cruza cada seção com ``secoes_por_local_distrito_aguas_vermelhas.csv``.
Agrega locais de votação que pertencem ao mesmo distrito/bairro (por exemplo,
os dois locais do Centro).

Gera dois CSVs: total de votos por distrito/bairro e detalhamento por
candidato dentro de cada distrito/bairro. As entradas contêm votos nominais
positivos; votos de legenda, brancos, nulos e candidaturas com zero voto não
estão representados no CSV de origem.
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
DEFAULT_SUMMARY = ROOT / "dados" / "votos_deputado_estadual_por_distrito_bairro.csv"
DEFAULT_CANDIDATES = ROOT / "dados" / "votos_estadual_por_candidato_distrito_bairro.csv"


def ler_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        amostra = f.read(4096)
        f.seek(0)
        delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
        return list(csv.DictReader(f, delimiter=delimitador))


def escrever_csv(path: Path, campos: list[str], linhas: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(linhas)


def carregar_secoes(path: Path):
    rows = ler_csv(path)
    necessarios = {"secao", "local_votacao", "distrito_ou_bairro", "eleitores_aptos"}
    if not rows or not necessarios.issubset(rows[0]):
        raise ValueError(f"O CSV de seções precisa conter estas colunas: {sorted(necessarios)}")

    secoes: dict[str, dict] = {}
    distritos: dict[str, dict] = {}
    for row in rows:
        secao = str(row["secao"]).strip().zfill(4)
        distrito = str(row["distrito_ou_bairro"]).strip()
        if not distrito:
            raise ValueError(f"Distrito/bairro vazio na seção {secao}")
        chave = distrito.casefold()
        if secao in secoes:
            raise ValueError(f"Seção duplicada no CSV de mapeamento: {secao}")
        secoes[secao] = {
            "distrito": distrito,
            "chave_distrito": chave,
            "local": str(row["local_votacao"]).strip(),
            "aptos": int(row["eleitores_aptos"]),
        }
        grupo = distritos.setdefault(chave, {
            "distrito": distrito, "secoes": set(), "locais": set(), "aptos": 0,
        })
        grupo["secoes"].add(secao)
        grupo["locais"].add(str(row["local_votacao"]).strip())
        grupo["aptos"] += int(row["eleitores_aptos"])
    return secoes, distritos


def somar(votos_path: Path, secoes_path: Path):
    secoes, grupos = carregar_secoes(secoes_path)
    totais: dict[str, int] = defaultdict(int)
    votos_candidato: dict[tuple, int] = defaultdict(int)
    secoes_com_votos: dict[tuple, set[str]] = defaultdict(set)
    desconhecidas = set()

    for row in ler_csv(votos_path):
        if str(row.get("cargo", "")).strip().casefold() != "deputado estadual".casefold():
            continue
        secao = str(row.get("secao", "")).strip().zfill(4)
        if secao not in secoes:
            desconhecidas.add(secao)
            continue
        info = secoes[secao]
        try:
            votos = int(row.get("votos", "0"))
        except ValueError as exc:
            raise ValueError(f"Número de votos inválido na seção {secao}: {row.get('votos')!r}") from exc
        if votos < 0:
            raise ValueError(f"Votos negativos encontrados na seção {secao}")

        chave = info["chave_distrito"]
        totais[chave] += votos
        candidato = (
            chave,
            str(row.get("numero", "")).strip(),
            str(row.get("candidato", "")).strip(),
            str(row.get("partido", "")).strip(),
        )
        votos_candidato[candidato] += votos
        if votos > 0:
            secoes_com_votos[candidato].add(secao)

    if desconhecidas:
        raise ValueError("Há seções de votos sem correspondência no mapa: " + ", ".join(sorted(desconhecidas)))

    por_distrito = []
    for chave, grupo in sorted(grupos.items(), key=lambda item: item[1]["distrito"].casefold()):
        candidatos = [
            (numero, nome, partido, votos)
            for (dist, numero, nome, partido), votos in votos_candidato.items()
            if dist == chave and votos > 0
        ]
        candidatos.sort(key=lambda x: (-x[3], x[1].casefold(), x[0]))
        lider = candidatos[0] if candidatos else ("", "", "", 0)
        por_distrito.append({
            "distrito_ou_bairro": grupo["distrito"],
            "quantidade_secoes": len(grupo["secoes"]),
            "secoes": ", ".join(sorted(grupo["secoes"])),
            "locais_votacao": " | ".join(sorted(grupo["locais"], key=str.casefold)),
            "eleitores_aptos": grupo["aptos"],
            "votos_nominais_deputado_estadual": totais[chave],
            "candidato_mais_votado_numero": lider[0],
            "candidato_mais_votado": lider[1],
            "partido_mais_votado": lider[2],
            "votos_do_candidato_mais_votado": lider[3],
        })

    por_candidato = []
    for (chave, numero, nome, partido), votos in votos_candidato.items():
        if votos <= 0:
            continue
        grupo = grupos[chave]
        por_candidato.append({
            "distrito_ou_bairro": grupo["distrito"],
            "numero": numero,
            "candidato": nome,
            "partido": partido,
            "votos_nominais": votos,
            "secoes_com_votos": ", ".join(sorted(secoes_com_votos[(chave, numero, nome, partido)])),
        })
    por_candidato.sort(key=lambda row: (row["distrito_ou_bairro"].casefold(), -row["votos_nominais"], row["candidato"].casefold()))
    return por_distrito, por_candidato


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--votos", type=Path, default=DEFAULT_VOTES, help="CSV por seção e candidato gerado dos BUs")
    parser.add_argument("--secoes", type=Path, default=DEFAULT_SECTIONS, help="CSV seção -> local/distrito/bairro")
    parser.add_argument("--saida", type=Path, default=DEFAULT_SUMMARY, help="CSV com total por distrito/bairro")
    parser.add_argument("--saida-candidatos", type=Path, default=DEFAULT_CANDIDATES, help="CSV com detalhe por candidato e distrito/bairro")
    args = parser.parse_args()

    for entrada in (args.votos, args.secoes):
        if not entrada.is_file():
            print(f"Arquivo de entrada não encontrado: {entrada}", file=sys.stderr)
            return 2

    try:
        resumo, candidatos = somar(args.votos, args.secoes)
        escrever_csv(args.saida, list(resumo[0]) if resumo else [
            "distrito_ou_bairro", "quantidade_secoes", "secoes", "locais_votacao",
            "eleitores_aptos", "votos_nominais_deputado_estadual",
            "candidato_mais_votado_numero", "candidato_mais_votado", "partido_mais_votado",
            "votos_do_candidato_mais_votado",
        ], resumo)
        escrever_csv(args.saida_candidatos, list(candidatos[0]) if candidatos else [
            "distrito_ou_bairro", "numero", "candidato", "partido", "votos_nominais", "secoes_com_votos",
        ], candidatos)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Erro ao somar: {exc}", file=sys.stderr)
        return 1

    total = sum(int(row["votos_nominais_deputado_estadual"]) for row in resumo)
    print(f"Distritos/bairros: {len(resumo)}")
    print(f"Votos nominais estaduais: {total:,}".replace(",", "."))
    print(f"Resumo: {args.saida}")
    print(f"Por candidato: {args.saida_candidatos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
