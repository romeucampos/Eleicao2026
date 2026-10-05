#!/usr/bin/env python3
"""Baixa resultados nominais do TSE para Águas Vermelhas/MG (Eleições 2026).

Salva os JSON oficiais e um CSV combinado dos votos por candidato para
Deputado Federal e Deputado Estadual. Requer somente Python 3 (sem pacotes).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://resultados.tse.jus.br/oficial/ele2026/6259/dados/mg"
MUNICIPIO = "40193"
CARGOS = (("0006", "Deputado Federal"), ("0007", "Deputado Estadual"))


def baixar(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; consulta-publica-TSE/1.0)"})
    with urlopen(req, timeout=40) as response:
        if response.status != 200:
            raise RuntimeError(f"Resposta HTTP {response.status}: {url}")
        return response.read()


def textos(v):
    if v is None:
        return ""
    return str(v).strip()


def localizar_candidatos(data):
    """Varre o JSON do TSE e encontra os registros nominais de candidatos."""
    encontrados = []
    vistos = set()

    def walk(obj, partido_pai=""):
        if isinstance(obj, dict):
            partido = textos(obj.get("sg", obj.get("partido", obj.get("sgPartido", partido_pai))))
            # O EA20 usa normalmente n/nm/vap; aliases deixam o parser resiliente.
            numero = next((obj[k] for k in ("n", "nr", "numero", "num") if k in obj), None)
            nome = next((obj[k] for k in ("nm", "nome", "nomeCandidato") if k in obj), None)
            votos = next((obj[k] for k in ("vap", "votos", "qtVotos", "qtvotos") if k in obj), None)
            if numero is not None and nome is not None and votos is not None:
                chave = (textos(numero), textos(nome), partido)
                if chave not in vistos:
                    vistos.add(chave)
                    encontrados.append({
                        "numero": textos(numero),
                        "candidato": textos(nome),
                        "partido": partido,
                        "votos": textos(votos),
                        "situacao": textos(obj.get("st", obj.get("situacao", ""))),
                        "vagas_partido": textos(obj.get("vag", "")),
                    })
            for value in obj.values():
                walk(value, partido)
        elif isinstance(obj, list):
            for value in obj:
                walk(value, partido_pai)

    walk(data)
    return encontrados


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", type=Path, default=Path("dados_aguas_vermelhas_2026"),
                        help="Pasta de saída (padrão: ./dados_aguas_vermelhas_2026)")
    parser.add_argument("--sobrescrever", action="store_true",
                        help="Baixa de novo mesmo se o JSON já existir")
    args = parser.parse_args()
    args.pasta.mkdir(parents=True, exist_ok=True)

    linhas = []
    erros = []
    for codigo, cargo in CARGOS:
        filename = f"mg{MUNICIPIO}-c{codigo}-e006259-u.json"
        destino = args.pasta / filename
        url = f"{BASE}/{filename}"
        try:
            if destino.exists() and not args.sobrescrever:
                raw = destino.read_bytes()
                print(f"Usando arquivo já baixado: {destino}")
            else:
                raw = baixar(url)
                destino.write_bytes(raw)
                print(f"Baixado: {destino} ({len(raw):,} bytes)")
            data = json.loads(raw.decode("utf-8-sig"))
            candidatos = localizar_candidatos(data)
            if not candidatos:
                raise ValueError("JSON válido, mas não localizei registros de candidatos/votos no formato esperado")
            for c in candidatos:
                linhas.append({"municipio": "Águas Vermelhas", "uf": "MG", "cargo": cargo, **c})
            print(f"  {len(candidatos)} candidatos encontrados para {cargo}")
        except (HTTPError, URLError, TimeoutError, RuntimeError, UnicodeError,
                json.JSONDecodeError, ValueError, OSError) as exc:
            erros.append(f"{cargo}: {exc}")
            print(f"Falha ao obter {cargo}: {exc}", file=sys.stderr)
        time.sleep(0.3)  # acesso moderado ao servidor público

    if linhas:
        csv_path = args.pasta / "votos_nominais_aguas_vermelhas_2026.csv"
        campos = ("municipio", "uf", "cargo", "numero", "candidato", "partido", "votos", "situacao", "vagas_partido")
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(linhas)
        print(f"CSV consolidado: {csv_path}")
    if erros:
        print("\nUm ou mais cargos não foram baixados; consulte as mensagens acima.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
