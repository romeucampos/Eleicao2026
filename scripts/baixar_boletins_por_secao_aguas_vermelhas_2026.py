#!/usr/bin/env python3
"""Baixa e soma os BUs seção a seção de Águas Vermelhas/MG nas Eleições 2026.

Baixa a configuração oficial de seções (EA16), consulta os auxiliares (EA18),
baixa o BU totalizado de cada seção principal e extrai votos nominais para
Governador, Senador, Deputado Federal e Deputado Estadual.

Dependência: pip install -r requirements_boletins_tse.txt
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path

HOST = "https://resultados.tse.jus.br"
AMBIENTE = "oficial"
ELEICAO = "6259"            # Estadual: governador, senador e deputados
CODIGO_MUNICIPIO = "40193"  # Águas Vermelhas/MG
UF = "mg"
PLEITO = "3220"
CARGOS = {
    3: "Governador",
    5: "Senador",
    6: "Deputado Federal",
    7: "Deputado Estadual",
}
TSE_BU_ZIP = "https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/formato-arquivos-de-bu-rdv-e-assinatura-digital"
USER_AGENT = "consulta-publica-resultados-TSE/1.0"


def get_bytes(url: str, timeout=45) -> bytes:
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


def digito(valor):
    if isinstance(valor, tuple):
        return int(valor[-1])
    return int(valor)


def mapear_candidatos(data: dict) -> tuple[dict, dict]:
    """(cargo, partido, número) -> nome, usando os EA20 municipais do TSE."""
    nomes = {}
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
                        nome = candidato["nm"]
                    except (KeyError, TypeError, ValueError):
                        continue
                    nomes[(codigo_cargo, cod_partido, numero)] = nome
    return nomes, partidos


def carregar_schema(destino: Path, force: bool) -> Path:
    schema = destino / "spec" / "bu.asn1"
    if schema.exists() and not force:
        return schema
    raw = get_bytes(TSE_BU_ZIP)
    schema.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        schema.write_bytes(zf.read("spec/bu.asn1"))
    return schema


def baixar_config_secoes(destino: Path, force: bool) -> dict:
    # O diretório de arquivos de urna segue a configuração oficial EA11.
    url = f"{HOST}/{AMBIENTE}/ele2026/arquivo-urna/{PLEITO}/config/{UF}/{UF}-p{int(PLEITO):06d}-cs.json"
    return save_json(url, destino / "config" / f"{UF}-p{int(PLEITO):06d}-cs.json", force)


def secoes_principais(config: dict):
    for abrangencia in config.get("abr", []):
        if abrangencia.get("cd") != UF:
            continue
        for municipio in abrangencia.get("mu", []):
            if municipio.get("cd") != CODIGO_MUNICIPIO:
                continue
            for zona in municipio.get("zon", []):
                for secao in zona.get("sec", []):
                    # Se nsp estiver presente, esta seção foi agregada a outra;
                    # o BU da seção principal já contém seus votos.
                    if secao.get("nsp"):
                        continue
                    yield zona.get("cd", "0000").zfill(4), secao.get("ns", "0000").zfill(4), secao


def aux_url(zona: str, secao: str) -> str:
    nome = f"p{int(PLEITO):06d}-{UF}-m{CODIGO_MUNICIPIO}-z{zona}-s{secao}-aux.json"
    return f"{HOST}/{AMBIENTE}/ele2026/arquivo-urna/{PLEITO}/dados/{UF}/{CODIGO_MUNICIPIO}/{zona}/{secao}/{nome}"


def escolher_bu(aux: dict):
    # Prefere o registro efetivamente totalizado; ignora reenvios rejeitados.
    elegiveis = []
    for h in aux.get("hashes", []):
        arquivos = [a for a in h.get("arq", []) if a.get("tp", "").lower() == "bu"]
        if not arquivos:
            continue
        status = h.get("st", "").strip().casefold()
        prioridade = 2 if status == "totalizado" else (1 if status == "recebido" else 0)
        elegiveis.append((prioridade, h, arquivos))
    if not elegiveis:
        return None
    _, h, arquivos = max(elegiveis, key=lambda x: x[0])
    if h.get("st", "").strip().casefold() != "totalizado":
        return None
    return h, arquivos[0]


def ler_bu(raw: bytes, codec):
    envelope = codec.decode("EntidadeEnvelopeGenerico", raw)
    return codec.decode("EntidadeBoletimUrna", envelope["conteudo"])


def extrair_votos(bu: dict, nomes: dict, partidos: dict, zona: str, secao: str, hash_bu: str):
    rows = []
    idmun = bu["identificacaoSecao"]["municipioZona"]["municipio"]
    idzona = bu["identificacaoSecao"]["municipioZona"]["zona"]
    idsecao = bu["identificacaoSecao"]["secao"]
    if (str(idmun).zfill(5), str(idzona).zfill(4), str(idsecao).zfill(4)) != (CODIGO_MUNICIPIO, zona, secao):
        raise ValueError("A identificação da seção no BU não corresponde ao arquivo solicitado")
    for eleicao in bu.get("resultadosVotacaoPorEleicao", []):
        if str(eleicao.get("idEleicao")) != ELEICAO:
            continue
        for resultado in eleicao.get("resultadosVotacao", []):
            for cargo in resultado.get("totaisVotosCargo", []):
                codigo_cargo = digito(cargo["codigoCargo"])
                if codigo_cargo not in CARGOS:
                    continue
                for voto in cargo.get("votosVotaveis", []):
                    if digito(voto["tipoVoto"]) != 1:  # nominal
                        continue
                    votavel = voto.get("identificacaoVotavel")
                    if not votavel:
                        continue
                    numero = int(votavel["codigo"])
                    cod_partido = int(votavel["partido"])
                    qtd = int(voto["quantidadeVotos"])
                    if qtd <= 0:
                        continue
                    rows.append({
                        "municipio": "Águas Vermelhas", "uf": "MG", "zona": zona,
                        "secao": secao, "eleicao": ELEICAO, "cargo": CARGOS[codigo_cargo],
                        "codigo_cargo": codigo_cargo, "numero": numero,
                        "candidato": nomes.get((codigo_cargo, cod_partido, numero), f"Nº {numero} (não consta no EA20 municipal)"),
                        "partido": partidos.get(cod_partido, f"código {cod_partido}"),
                        "partido_numero": cod_partido, "votos": qtd,
                        "data_emissao_bu": bu.get("dataHoraEmissao", ""),
                        "hash_bu": hash_bu, "status_bu": "Totalizado",
                    })
    return rows


def gravar_csv(path: Path, rows: list[dict], campos: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", type=Path, default=Path("dados_aguas_vermelhas_por_secao_2026"))
    parser.add_argument("--forcar", action="store_true", help="baixa novamente os arquivos já presentes")
    parser.add_argument("--pausa", type=float, default=0.25, help="segundos entre arquivos distintos (padrão: 0,25)")
    args = parser.parse_args()
    args.pasta.mkdir(parents=True, exist_ok=True)

    try:
        import asn1tools
    except ImportError:
        print("Falta a dependência ASN.1. Instale com: python3 -m pip install -r requirements_boletins_tse.txt", file=sys.stderr)
        return 2

    print("Baixando índice de seções, schema oficial e resultados para nomes dos candidatos...")
    config = baixar_config_secoes(args.pasta, args.forcar)
    schema = carregar_schema(args.pasta, args.forcar)
    codec = asn1tools.compile_files([str(schema)], codec="ber", numeric_enums=True)
    nomes = {}
    partidos = {}
    for codigo in CARGOS:
        filename = f"{UF}{CODIGO_MUNICIPIO}-c{codigo:04d}-e{int(ELEICAO):06d}-u.json"
        url = f"{HOST}/{AMBIENTE}/ele2026/{ELEICAO}/dados/{UF}/{filename}"
        data = save_json(url, args.pasta / "candidatos" / filename, args.forcar)
        nomes_cargo, partidos_cargo = mapear_candidatos(data)
        nomes.update(nomes_cargo)
        partidos.update(partidos_cargo)
        time.sleep(max(args.pausa, 0))

    sections = list(secoes_principais(config))
    if not sections:
        print(f"Nenhuma seção principal encontrada para o código municipal {CODIGO_MUNICIPIO}.", file=sys.stderr)
        return 1
    print(f"Seções principais no índice: {len(sections)}")

    all_rows = []
    erros = []
    for index, (zona, secao, meta) in enumerate(sections, 1):
        try:
            aux_path = args.pasta / "auxiliares" / zona / secao / f"p{int(PLEITO):06d}-{UF}-m{CODIGO_MUNICIPIO}-z{zona}-s{secao}-aux.json"
            aux = save_json(aux_url(zona, secao), aux_path, args.forcar)
            escolhido = escolher_bu(aux)
            if not escolhido:
                print(f"[{index}/{len(sections)}] zona {zona}, seção {secao}: BU totalizado ainda não encontrado")
                time.sleep(max(args.pausa, 0))
                continue
            h, arq = escolhido
            filename = arq["nm"]
            url_bu = f"{HOST}/{AMBIENTE}/ele2026/arquivo-urna/{PLEITO}/dados/{UF}/{CODIGO_MUNICIPIO}/{zona}/{secao}/{h['hash']}/{filename}"
            bu_path = args.pasta / "boletins" / zona / secao / filename
            if bu_path.exists() and not args.forcar:
                raw = bu_path.read_bytes()
            else:
                raw = get_bytes(url_bu)
                bu_path.parent.mkdir(parents=True, exist_ok=True)
                bu_path.write_bytes(raw)
            bu = ler_bu(raw, codec)
            rows = extrair_votos(bu, nomes, partidos, zona, secao, h.get("hash", ""))
            all_rows.extend(rows)
            print(f"[{index}/{len(sections)}] zona {zona}, seção {secao}: BU baixado, {len(rows)} votos nominais dos cargos-alvo")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, KeyError) as exc:
            erros.append((zona, secao, str(exc)))
            print(f"[{index}/{len(sections)}] zona {zona}, seção {secao}: ERRO {exc}", file=sys.stderr)
        time.sleep(max(args.pausa, 0))

    campos = ["municipio", "uf", "zona", "secao", "eleicao", "cargo", "codigo_cargo", "numero", "candidato", "partido", "partido_numero", "votos", "data_emissao_bu", "hash_bu", "status_bu"]
    por_secao = args.pasta / "votos_por_secao_e_candidato.csv"
    gravar_csv(por_secao, sorted(all_rows, key=lambda r: (r["codigo_cargo"], r["zona"], r["secao"], -r["votos"])), campos)
    somas = defaultdict(int)
    metadados = {}
    for row in all_rows:
        k = (row["cargo"], row["numero"], row["candidato"], row["partido"], row["partido_numero"])
        somas[k] += row["votos"]
        metadados[k] = {"cargo": row["cargo"], "numero": row["numero"], "candidato": row["candidato"], "partido": row["partido"], "partido_numero": row["partido_numero"]}
    ranking = [{**metadados[k], "votos": v} for k, v in somas.items()]
    ranking.sort(key=lambda r: (r["cargo"], -r["votos"], r["candidato"]))
    resumo = args.pasta / "votos_somados_por_candidato.csv"
    gravar_csv(resumo, ranking, ["cargo", "numero", "candidato", "partido", "partido_numero", "votos"])
    print(f"CSV por seção: {por_secao}")
    print(f"CSV somado por candidato: {resumo}")
    print(f"BUs processados: {len({(r['zona'], r['secao']) for r in all_rows})} de {len(sections)} seções principais")
    for cargo in CARGOS.values():
        print(f"{cargo}: {sum(r['votos'] for r in all_rows if r['cargo'] == cargo):,} votos nominais".replace(",", "."))
    if erros:
        print(f"Ocorreram {len(erros)} erros; consulte os arquivos e mensagens acima.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
