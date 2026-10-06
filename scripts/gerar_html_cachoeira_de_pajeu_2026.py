#!/usr/bin/env python3
"""Gera um relatório HTML mobile-first de Cachoeira de Pajeú/MG."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "dados" / "cachoeira_de_pajeu"
OUTPUT = ROOT / "relatorio_cachoeira_de_pajeu_2026_mobile_first.html"
DATASETS = {
    "senador": ("Senador", BASE / "votos_senador_por_distrito_bairro.csv", BASE / "votos_senador_por_candidato_distrito_bairro.csv", "votos_nominais_senador"),
    "federal": ("Deputado Federal", BASE / "votos_deputado_federal_por_distrito_bairro.csv", BASE / "votos_federal_por_candidato_distrito_bairro.csv", "votos_nominais_deputado_federal"),
    "estadual": ("Deputado Estadual", BASE / "votos_deputado_estadual_por_distrito_bairro.csv", BASE / "votos_estadual_por_candidato_distrito_bairro.csv", "votos_nominais_deputado_estadual"),
}


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(4096)
        stream.seek(0)
        return list(csv.DictReader(stream, delimiter=";" if sample.count(";") > sample.count(",") else ","))


def district_name(value: str) -> str:
    return "Sede do município" if value.strip().casefold() == "centro" else value.strip()


def load_dataset(key: str, spec):
    cargo, summary_path, candidates_path, total_field = spec
    districts = []
    for row in read_csv(summary_path):
        districts.append({
            "distrito": district_name(row["distrito_ou_bairro"]),
            "secoes": int(row["quantidade_secoes"]),
            "aptos": int(row.get("eleitores_aptos") or 0),
            "votos": int(row[total_field]),
            "lider": row.get("candidato_mais_votado", ""),
            "lider_votos": int(row.get("votos_do_candidato_mais_votado") or 0),
        })
    districts.sort(key=lambda row: (-row["votos"], row["distrito"].casefold()))

    candidates = []
    for row in read_csv(candidates_path):
        votes = int(row.get("votos_nominais") or 0)
        if votes <= 0:
            continue
        candidates.append({
            "distrito": district_name(row["distrito_ou_bairro"]),
            "numero": row["numero"], "candidato": row["candidato"],
            "partido": row["partido"], "votos": votes,
            "secoes": row.get("secoes_com_votos", ""),
        })
    candidates.sort(key=lambda row: (row["distrito"].casefold(), -row["votos"], row["candidato"].casefold()))

    totals = defaultdict(lambda: {"numero": "", "candidato": "", "partido": "", "votos": 0, "distritos": set()})
    for row in candidates:
        item = totals[(row["numero"], row["candidato"], row["partido"])]
        item.update(numero=row["numero"], candidato=row["candidato"], partido=row["partido"])
        item["votos"] += row["votos"]
        item["distritos"].add(row["distrito"])
    ranking = [{**item, "distritos": len(item["distritos"])} for item in totals.values()]
    ranking.sort(key=lambda row: (-row["votos"], row["candidato"].casefold(), row["numero"]))
    return {"cargo": cargo, "distritos": districts, "candidatos": candidates,
            "ranking": ranking, "total_votos": sum(r["votos"] for r in districts),
            "total_secoes": sum(r["secoes"] for r in districts),
            "total_aptos": sum(r["aptos"] for r in districts), "key": key}


HTML = r'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Votos nominais de senador e deputados por distrito em Cachoeira de Pajeú/MG.">
<title>Votos por distrito — Cachoeira de Pajeú/MG</title>
<style>
:root{--ink:#17231d;--muted:#65736c;--line:#dce6df;--paper:#fff;--bg:#f3f7f4;--green:#17683d;--tint:#e6f3eb;--shadow:0 8px 26px #173b2810}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}header{background:linear-gradient(120deg,#114c31,#20834b);color:#fff;padding:24px 18px 22px}header h1{font-size:clamp(25px,7vw,40px);line-height:1.08;margin:4px 0}.eyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;opacity:.82;font-weight:700}.wrap{max-width:1100px;margin:auto;padding:16px 12px 42px}.tabs{position:sticky;top:0;z-index:2;display:flex;gap:6px;overflow:auto;padding:8px 0;background:var(--bg)}.tab{flex:0 0 auto;border:1px solid #c8d6cd;background:#fff;color:var(--green);border-radius:10px;padding:12px 14px;font-weight:750;cursor:pointer}.tab.active{background:var(--green);border-color:var(--green);color:#fff}.panel[hidden]{display:none}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.stat,.district,.totals{background:var(--paper);border:1px solid var(--line);border-radius:13px;box-shadow:var(--shadow)}.stat{padding:13px}.stat small{display:block;color:var(--muted);font-size:12px}.stat strong{font-size:23px}.tools{margin:16px 0 11px}.tools input{width:100%;padding:13px;border:1px solid #c8d6cd;border-radius:10px;font:inherit}.hint{display:block;color:var(--muted);font-size:12px;margin-top:7px}.districts{display:grid;gap:10px}.district{overflow:hidden}.dhead{display:flex;align-items:center;gap:9px;padding:14px;cursor:pointer;list-style:none}.dhead::-webkit-details-marker{display:none}.dhead:after{content:'＋';margin-left:auto;color:var(--green);font-size:21px}.district[open] .dhead:after{content:'−'}.rank{width:29px;height:29px;border-radius:50%;background:var(--tint);color:var(--green);display:grid;place-items:center;font-weight:800;flex:none}.dname{font-weight:800}.dmeta{display:block;color:var(--muted);font-size:12px}.dtotal{margin-left:auto;text-align:right;white-space:nowrap}.dtotal strong{display:block;font-size:19px}.dtotal small{color:var(--muted);font-size:11px}.inside{padding:0 10px 13px}.tablewrap{overflow:auto;border:1px solid var(--line);border-radius:9px}table{border-collapse:collapse;width:100%;min-width:610px}th,td{padding:9px 10px;text-align:left;border-bottom:1px solid #e8eee9;vertical-align:top}th{background:#f7faf8;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.06em}tbody tr:last-child td{border-bottom:0}.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.cand{font-weight:750}.party{color:var(--muted);font-size:12px}.sections{color:var(--muted);font-size:11px}.totals{margin-top:18px;padding:15px}.totals h2{font-size:19px;margin:0}.totalcards{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.totalcard{background:#f6faf7;border:1px solid var(--line);border-radius:9px;padding:10px}.totalcard small{display:block;color:var(--muted);font-size:11px}.totalcard strong{font-size:19px}.totalrow td{font-weight:800;background:#f3f7f4}footer{color:var(--muted);font-size:12px;margin-top:18px}@media(max-width:650px){.stats,.totalcards{grid-template-columns:1fr}.stat strong{font-size:21px}.inside{padding-left:8px;padding-right:8px}}
</style></head><body>
<header><div class="eyebrow">Eleições 2026 · Cachoeira de Pajeú / MG</div><h1>Votos por distrito e candidato</h1></header>
<main class="wrap"><nav class="tabs" aria-label="Cargo"><button class="tab active" data-cargo="senador">Senador</button><button class="tab" data-cargo="federal">Deputado Federal</button><button class="tab" data-cargo="estadual">Deputado Estadual</button></nav>
<section data-panel="senador"></section><section data-panel="federal" hidden></section><section data-panel="estadual" hidden></section><footer>Dados extraídos dos BUs brutos do TSE. Feito por Romeu Campos.</footer></main>
<script>const DATA=__DATA__;const fmt=new Intl.NumberFormat('pt-BR');const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const refs={};
function render(key){const d=DATA[key],p=document.querySelector(`[data-panel="${key}"]`);p.innerHTML=`<section class="stats"><div class="stat"><small>Votos nominais</small><strong>${fmt.format(d.total_votos)}</strong></div><div class="stat"><small>Distritos/bairros</small><strong>${d.distritos.length}</strong></div><div class="stat"><small>Seções · eleitores aptos</small><strong>${d.total_secoes} · ${fmt.format(d.total_aptos)}</strong></div></section><div class="tools"><input type="search" placeholder="Buscar distrito, candidato, número ou partido…"><span class="hint"></span></div><section class="districts"></section><section class="totals"></section>`;refs[key]={p,input:p.querySelector('input'),hint:p.querySelector('.hint'),districts:p.querySelector('.districts'),totals:p.querySelector('.totals')};const draw=q=>{q=q.trim().toLocaleLowerCase('pt-BR');const ds=d.distritos.map(x=>({...x,lista:d.candidatos.filter(c=>c.distrito===x.distrito)})).filter(x=>!q||x.distrito.toLocaleLowerCase('pt-BR').includes(q)||x.lista.some(c=>[c.candidato,c.numero,c.partido].join(' ').toLocaleLowerCase('pt-BR').includes(q)));refs[key].hint.textContent=`${ds.length} de ${d.distritos.length} distritos · ${fmt.format(ds.reduce((a,x)=>a+x.lista.length,0))} combinações com voto`;refs[key].districts.innerHTML=ds.map((x,i)=>`<details class="district" ${q?'open':''}><summary class="dhead"><span class="rank">${i+1}</span><span><span class="dname">${esc(x.distrito)}</span><span class="dmeta">${x.secoes} ${x.secoes===1?'seção':'seções'} · ${fmt.format(x.aptos)} aptos</span></span><span class="dtotal"><strong>${fmt.format(x.votos)}</strong><small>votos</small></span></summary><div class="inside"><div class="tablewrap"><table><thead><tr><th>Ordem</th><th>Candidato</th><th class="num">Votos</th><th>Partido</th><th>Seções</th></tr></thead><tbody>${x.lista.sort((a,b)=>b.votos-a.votos||a.candidato.localeCompare(b.candidato,'pt-BR')).map((c,j)=>`<tr><td>${j+1}</td><td><span class="cand">${esc(c.candidato)}</span><br><span class="sections">Nº ${esc(c.numero)}</span></td><td class="num"><strong>${fmt.format(c.votos)}</strong></td><td><span class="party">${esc(c.partido)}</span></td><td class="sections">${esc(c.secoes)}</td></tr>`).join('')}</tbody></table></div></div></details>`).join('')||'<p>Nenhum resultado encontrado.</p>'};const body=d.ranking.map((c,i)=>`<tr><td>${i+1}</td><td><span class="cand">${esc(c.candidato)}</span><br><span class="sections">Nº ${esc(c.numero)}</span></td><td class="num"><strong>${fmt.format(c.votos)}</strong></td><td><span class="party">${esc(c.partido)}</span></td><td>${c.distritos} de ${d.distritos.length}</td></tr>`).join('');refs[key].totals.innerHTML=`<h2>Total consolidado</h2><div class="totalcards"><div class="totalcard"><small>Votos nominais</small><strong>${fmt.format(d.total_votos)}</strong></div><div class="totalcard"><small>Seções · aptos</small><strong>${d.total_secoes} · ${fmt.format(d.total_aptos)}</strong></div><div class="totalcard"><small>Candidatos com voto</small><strong>${d.ranking.length}</strong></div></div><div class="tablewrap"><table><thead><tr><th>Ordem</th><th>Candidato</th><th class="num">Votos</th><th>Partido</th><th>Distritos</th></tr></thead><tbody>${body}<tr class="totalrow"><td colspan="2">Total</td><td class="num">${fmt.format(d.total_votos)}</td><td></td><td>${d.distritos.length}</td></tr></tbody></table></div>`;refs[key].input.oninput=e=>draw(e.target.value);draw('')}
Object.keys(DATA).forEach(render);document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==b.dataset.cargo)});</script></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=OUTPUT)
    args = parser.parse_args()
    datasets = {key: load_dataset(key, spec) for key, spec in DATASETS.items()}
    args.saida.write_text(HTML.replace("__DATA__", json.dumps(datasets, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    print(f"HTML: {args.saida}")
    for key, data in datasets.items():
        print(f"{data['cargo']}: {data['total_votos']:,} votos, {len(data['distritos'])} distritos, {data['total_aptos']:,} aptos".replace(",", "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
