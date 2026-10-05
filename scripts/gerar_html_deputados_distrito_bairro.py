#!/usr/bin/env python3
"""Gera o relatório HTML com abas para deputados federal e estadual.

Os CSVs de entrada são produzidos pela extração dos boletins de urna brutos
e pelos scripts de soma por distrito/bairro. O HTML incorpora os dados para
ser aberto localmente, sem servidor.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "dados"
DEFAULT_FEDERAL_SUMMARY = DEFAULT_DIR / "votos_deputado_federal_por_distrito_bairro.csv"
DEFAULT_FEDERAL_CANDIDATES = DEFAULT_DIR / "votos_federal_por_candidato_distrito_bairro.csv"
DEFAULT_ESTADUAL_SUMMARY = DEFAULT_DIR / "votos_deputado_estadual_por_distrito_bairro.csv"
DEFAULT_ESTADUAL_CANDIDATES = DEFAULT_DIR / "votos_estadual_por_candidato_distrito_bairro.csv"
DEFAULT_OUTPUT = ROOT / "relatorio_deputados_federal_estadual_distrito_bairro_atualizado.html"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        header = stream.readline()
        stream.seek(0)
        delimiter = ";" if header.count(";") > header.count(",") else ","
        return list(csv.DictReader(stream, delimiter=delimiter))


def district_name(value: str) -> str:
    return "Sede do município" if value.strip().casefold() == "centro" else value.strip()


def load_dataset(summary_path: Path, candidates_path: Path, cargo: str) -> dict:
    summary = []
    for row in read_csv(summary_path):
        summary.append({
            "distrito": district_name(row["distrito_ou_bairro"]),
            "secoes": int(row["quantidade_secoes"]),
            "aptos": int(row["eleitores_aptos"]),
            "votos": int(row[f"votos_nominais_{cargo}"]),
            "lider": row.get("candidato_mais_votado", ""),
            "lider_numero": row.get("candidato_mais_votado_numero", ""),
            "lider_partido": row.get("partido_mais_votado", ""),
            "lider_votos": int(row.get("votos_do_candidato_mais_votado", "0")),
        })
    summary.sort(key=lambda row: (-row["votos"], row["distrito"].casefold()))

    candidates = []
    for row in read_csv(candidates_path):
        votes = int(row["votos_nominais"])
        if votes <= 0:
            continue
        candidates.append({
            "distrito": district_name(row["distrito_ou_bairro"]),
            "numero": row["numero"],
            "candidato": row["candidato"],
            "partido": row["partido"],
            "votos": votes,
            "secoes": row.get("secoes_com_votos", ""),
        })
    candidates.sort(key=lambda row: (row["distrito"].casefold(), -row["votos"], row["candidato"].casefold()))

    totals = defaultdict(lambda: {"numero": "", "candidato": "", "partido": "", "votos": 0, "distritos": set()})
    for row in candidates:
        key = (row["numero"], row["candidato"], row["partido"])
        item = totals[key]
        item.update(numero=row["numero"], candidato=row["candidato"], partido=row["partido"])
        item["votos"] += row["votos"]
        item["distritos"].add(row["distrito"])
    total_candidates = [
        {**item, "distritos": len(item["distritos"])}
        for item in totals.values()
        if item["votos"] > 0
    ]
    total_candidates.sort(key=lambda row: (-row["votos"], row["candidato"].casefold(), row["numero"]))

    return {
        "cargo": cargo,
        "distritos": summary,
        "candidatos": candidates,
        "totais_candidatos": total_candidates,
        "total_votos": sum(row["votos"] for row in summary),
        "total_secoes": sum(row["secoes"] for row in summary),
        "total_aptos": sum(row["aptos"] for row in summary),
    }


HTML = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Votos nominais de deputados federal e estadual por distrito e bairro em Águas Vermelhas, MG.">
<title>Deputados Federal e Estadual — Águas Vermelhas/MG</title>
<style>
:root{--ink:#18251f;--muted:#63736b;--line:#dce5df;--paper:#fff;--bg:#f3f7f4;--green:#17683d;--green2:#e6f3eb;--shadow:0 8px 28px #193b2910}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}header{background:linear-gradient(120deg,#114c31,#20834b);color:white;padding:34px max(22px,calc((100% - 1160px)/2)) 30px}header .eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.14em;opacity:.8;font-weight:700}h1{font-size:clamp(28px,4vw,42px);line-height:1.1;margin:8px 0}.sub{max-width:790px;color:#e2f1e7;margin:10px 0 0}.wrap{max-width:1160px;margin:0 auto;padding:24px 20px 56px}.tabs{display:flex;gap:8px;margin:0 0 18px}.tab{border:1px solid #c8d6cd;background:#fff;color:var(--green);border-radius:10px;padding:11px 18px;font:700 14px system-ui;cursor:pointer}.tab.active{background:var(--green);border-color:var(--green);color:#fff}.tab:focus{outline:3px solid #17683d2b}.panel[hidden]{display:none}.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.stat,.panel,.district{background:var(--paper);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}.stat{padding:17px 19px}.stat small{display:block;color:var(--muted);font-weight:650}.stat strong{font-size:27px;letter-spacing:-.03em}.tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:24px 0 14px}.tools input{flex:1;min-width:230px;padding:12px 14px;border:1px solid #c8d6cd;border-radius:10px;background:white;font:inherit}.tools input:focus{outline:3px solid #17683d2b;border-color:var(--green)}.hint{color:var(--muted);font-size:13px}.districts{display:grid;gap:14px}.district{overflow:hidden}.dhead{padding:18px 20px;display:flex;align-items:center;gap:18px;cursor:pointer;list-style:none}.dhead::-webkit-details-marker{display:none}.dhead::after{content:'＋';margin-left:auto;color:var(--green);font-size:22px;font-weight:500}.district[open] .dhead::after{content:'−'}.rank{width:38px;height:38px;border-radius:50%;background:var(--green2);color:var(--green);display:grid;place-items:center;font-weight:800;flex:none}.dname{font-size:18px;font-weight:760}.dmeta{color:var(--muted);font-size:13px;margin-top:2px}.dtotal{margin-left:auto;text-align:right;white-space:nowrap}.dtotal strong{font-size:21px;display:block}.dtotal small{color:var(--muted)}.bar{height:6px;background:#edf2ee;margin:0 20px 18px;border-radius:9px;overflow:hidden}.bar span{display:block;background:var(--green);height:100%;border-radius:9px}.inside{padding:0 20px 20px}.inside h3{font-size:14px;margin:0 0 10px;color:#35463d}.tablewrap{overflow:auto;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;min-width:650px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #e8eee9;vertical-align:top}th{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);background:#f7faf8}tbody tr:last-child td{border-bottom:0}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.cand{font-weight:700}.party{display:inline-block;padding:2px 7px;background:#f0f4f1;border-radius:5px;font-size:12px;color:#415449}.share{color:var(--muted)}.sections{font-size:12px;color:var(--muted)}.totais{margin-top:30px;padding:21px}.totais h2{font-size:22px;margin:0}.totais .intro{margin:5px 0 16px;color:var(--muted);font-size:14px}.totalcards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:17px}.totalcard{background:#f6faf7;border:1px solid var(--line);border-radius:10px;padding:12px 14px}.totalcard small{display:block;color:var(--muted)}.totalcard strong{font-size:21px;font-variant-numeric:tabular-nums}.totalrow td{font-weight:800;background:#f3f7f4}.totais h3{font-size:15px;margin:0 0 9px}.notes{margin-top:22px;padding:17px 19px;background:#fff8e9;border:1px solid #f0dfb7;border-radius:12px;color:#59451f;font-size:13px}footer{margin-top:22px;color:var(--muted);font-size:12px}a{color:var(--green)}@media(max-width:680px){.stats,.totalcards{grid-template-columns:1fr}.dhead{gap:10px;padding:15px}.dtotal strong{font-size:18px}.inside{padding:0 12px 15px}.bar{margin-left:15px;margin-right:15px}.dmeta{max-width:220px}.rank{width:32px}}
</style>
</head>
<body>
<header><div class="eyebrow">Eleições 2026 · Águas Vermelhas / MG</div><h1>Deputados por distrito e bairro</h1><p class="sub">Use as abas para consultar deputado federal ou estadual. Os distritos são ordenados pelo total de votos nominais; dentro de cada distrito, os candidatos aparecem do maior para o menor.</p></header>
<main class="wrap">
<nav class="tabs" aria-label="Cargo"><button class="tab active" data-cargo="federal" type="button">Deputado Federal</button><button class="tab" data-cargo="estadual" type="button">Deputado Estadual</button></nav>
<section class="panel" data-panel="federal"></section>
<section class="panel" data-panel="estadual" hidden></section>
<div class="notes"><strong>Como ler:</strong> a ordem usa o total de votos nominais do distrito/bairro; dentro de cada um, os candidatos são ordenados pelos votos recebidos. Candidatos sem voto não aparecem. “Seções com votos” indica as seções em que aquele candidato recebeu voto. Os dados foram extraídos dos boletins de urna brutos e cruzados com o mapa de seções. Votos de legenda, brancos e nulos não estão incluídos.</div>
<footer>Fonte: BUs brutos, CSV por seção e candidato, e mapeamento seção → distrito/bairro deste repositório. Use os arquivos .dat para auditoria.</footer>
</main>
<script>
const DATASETS=__DATASETS__;
const fmt=new Intl.NumberFormat('pt-BR');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label={federal:'Deputado Federal',estadual:'Deputado Estadual'};
const refs={};
function renderCargo(cargo){
 const data=DATASETS[cargo], panel=document.querySelector(`[data-panel="${cargo}"]`);
 const maxVotes=Math.max(...data.distritos.map(d=>d.votos));
 panel.innerHTML=`<section class="stats" aria-label="Resumo da apuração"><div class="stat"><small>Votos nominais somados</small><strong>${fmt.format(data.total_votos)}</strong></div><div class="stat"><small>Distritos / bairros</small><strong>${fmt.format(data.distritos.length)}</strong></div><div class="stat"><small>Seções incluídas · eleitores aptos</small><strong>${fmt.format(data.total_secoes)} <span style="font-size:15px;color:#63736b;font-weight:500">· ${fmt.format(data.total_aptos)} aptos</span></strong></div></section><div class="tools"><input type="search" placeholder="Buscar distrito, candidato, número ou partido…" aria-label="Buscar ${label[cargo]}"><span class="hint"></span></div><section class="districts" aria-live="polite"></section><section class="panel totais" aria-label="Totais consolidados"></section>`;
 refs[cargo]={panel,input:panel.querySelector('input'),hint:panel.querySelector('.hint'),districts:panel.querySelector('.districts'),totais:panel.querySelector('.totais')};
 const render=(query='')=>{
  const q=query.trim().toLocaleLowerCase('pt-BR');
  const matches=data.distritos.map(d=>({...d,lista:data.candidatos.filter(c=>c.distrito===d.distrito)})).filter(d=>!q||d.distrito.toLocaleLowerCase('pt-BR').includes(q)||d.lista.some(c=>[c.candidato,c.numero,c.partido].join(' ').toLocaleLowerCase('pt-BR').includes(q)));
  refs[cargo].hint.textContent=`${matches.length} de ${data.distritos.length} distritos · ${fmt.format(matches.reduce((a,d)=>a+d.lista.length,0))} combinações candidato/distrito com votos`;
  if(!matches.length){refs[cargo].districts.innerHTML='<div class="empty">Nenhum distrito ou candidato encontrado.</div>';return;}
  refs[cargo].districts.innerHTML=matches.map((d,i)=>{
   const cands=d.lista.sort((a,b)=>b.votos-a.votos||a.candidato.localeCompare(b.candidato,'pt-BR'));
   const rows=cands.map((c,j)=>`<tr><td>${j+1}</td><td><span class="cand">${esc(c.candidato)}</span><br><span class="sections">Nº ${esc(c.numero)}</span></td><td><span class="party">${esc(c.partido)}</span></td><td class="num"><strong>${fmt.format(c.votos)}</strong></td><td class="num share">${(100*c.votos/d.votos).toLocaleString('pt-BR',{maximumFractionDigits:1})}%</td><td class="sections">${esc(c.secoes)}</td></tr>`).join('');
   const pct=100*d.votos/maxVotes;
   return `<details class="district" ${q?'open':''}><summary class="dhead"><span class="rank">${i+1}</span><span><span class="dname">${esc(d.distrito)}</span><span class="dmeta"><br>${d.secoes} ${d.secoes===1?'seção':'seções'} · ${fmt.format(d.aptos)} eleitores aptos</span></span><span class="dtotal"><strong>${fmt.format(d.votos)}</strong><small>votos nominais</small></span></summary><div class="bar"><span style="width:${pct.toFixed(2)}%"></span></div><div class="inside"><h3>${cands.length} ${cands.length===1?'candidato com voto':'candidatos com voto'} · maior votação: ${esc(d.lider)} (${fmt.format(d.lider_votos)})</h3><div class="tablewrap"><table><thead><tr><th>Ordem</th><th>Candidato</th><th>Partido</th><th class="num">Votos</th><th class="num">% do distrito</th><th>Seções com votos</th></tr></thead><tbody>${rows}</tbody></table></div></div></details>`;
  }).join('');
 };
 const renderTotals=()=>{
  const ranking=data.totais_candidatos.filter(c=>c.votos>0);
  const body=ranking.map((c,i)=>`<tr><td>${i+1}</td><td><span class="cand">${esc(c.candidato)}</span><br><span class="sections">Nº ${esc(c.numero)}</span></td><td><span class="party">${esc(c.partido)}</span></td><td class="num"><strong>${fmt.format(c.votos)}</strong></td><td class="num share">${(100*c.votos/data.total_votos).toLocaleString('pt-BR',{maximumFractionDigits:1})}%</td><td>${c.distritos} de ${data.distritos.length}</td></tr>`).join('');
  refs[cargo].totais.innerHTML=`<h2>Total consolidado de todos os distritos/bairros</h2><p class="intro">Soma de cada candidato em todos os distritos e bairros, em ordem decrescente. Candidatos sem voto foram ocultados.</p><div class="totalcards"><div class="totalcard"><small>Votos nominais</small><strong>${fmt.format(data.total_votos)}</strong></div><div class="totalcard"><small>Seções · eleitores aptos</small><strong>${fmt.format(data.total_secoes)} · ${fmt.format(data.total_aptos)}</strong></div><div class="totalcard"><small>Candidatos com votos</small><strong>${fmt.format(ranking.length)}</strong></div></div><h3>Ranking municipal de candidatos</h3><div class="tablewrap"><table><thead><tr><th>Ordem</th><th>Candidato</th><th>Partido</th><th class="num">Votos somados</th><th class="num">% do total</th><th>Distritos com voto</th></tr></thead><tbody>${body}<tr class="totalrow"><td colspan="3">Total somado</td><td class="num">${fmt.format(data.total_votos)}</td><td class="num">100%</td><td>${data.distritos.length} distritos/bairros</td></tr></tbody></table></div>`;
 };
 refs[cargo].input.addEventListener('input',e=>render(e.target.value));
 render();renderTotals();
}
Object.keys(DATASETS).forEach(renderCargo);
document.querySelectorAll('.tab').forEach(tab=>tab.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t===tab));document.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==tab.dataset.cargo)}));
</script>
</body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--federal-resumo", type=Path, default=DEFAULT_FEDERAL_SUMMARY)
    parser.add_argument("--federal-candidatos", type=Path, default=DEFAULT_FEDERAL_CANDIDATES)
    parser.add_argument("--estadual-resumo", type=Path, default=DEFAULT_ESTADUAL_SUMMARY)
    parser.add_argument("--estadual-candidatos", type=Path, default=DEFAULT_ESTADUAL_CANDIDATES)
    parser.add_argument("--saida", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    entradas = [args.federal_resumo, args.federal_candidatos, args.estadual_resumo, args.estadual_candidatos]
    faltantes = [str(path) for path in entradas if not path.is_file()]
    if faltantes:
        parser.error("Arquivos não encontrados: " + ", ".join(faltantes))
    datasets = {
        "federal": load_dataset(args.federal_resumo, args.federal_candidatos, "deputado_federal"),
        "estadual": load_dataset(args.estadual_resumo, args.estadual_candidatos, "deputado_estadual"),
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(HTML.replace("__DATASETS__", json.dumps(datasets, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    print(f"HTML: {args.saida}")
    for cargo, data in datasets.items():
        print(f"{cargo}: {data['total_votos']:,} votos, {len(data['distritos'])} distritos, {len(data['totais_candidatos'])} candidatos com voto".replace(",", "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
