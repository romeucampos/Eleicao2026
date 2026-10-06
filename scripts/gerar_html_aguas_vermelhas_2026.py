#!/usr/bin/env python3
"""Gera o relatório mobile-first de Águas Vermelhas com quatro cargos."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "dados"

SPECS = {
    "federal": (
        "Deputado Federal", "6", BASE / "votos_deputado_federal_por_distrito_bairro.csv",
        BASE / "votos_federal_por_candidato_distrito_bairro.csv", "votos_nominais_deputado_federal",
    ),
    "estadual": (
        "Deputado Estadual", "7", BASE / "votos_deputado_estadual_por_distrito_bairro.csv",
        BASE / "votos_estadual_por_candidato_distrito_bairro.csv", "votos_nominais_deputado_estadual",
    ),
    "senador": (
        "Senador", "5", BASE / "votos_senador_por_distrito_bairro.csv",
        BASE / "votos_senador_por_candidato_distrito_bairro.csv", "votos_nominais_senador",
    ),
    "governador": (
        "Governador", "3", BASE / "votos_governador_por_distrito_bairro.csv",
        BASE / "votos_governador_por_candidato_distrito_bairro.csv", "votos_nominais_governador",
    ),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        sample = stream.readline()
        stream.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        return list(csv.DictReader(stream, delimiter=delimiter))


def district_name(value: str) -> str:
    return "Sede do município" if value.strip().casefold() == "centro" else value.strip()


def load_urna_names() -> dict[tuple[str, str, str], str]:
    """Lê os nomes de urna dos cadastros oficiais EA20 preservados no repositório."""
    names = {}
    for path in sorted((BASE / "raw" / "candidatos").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for cargo in data.get("carg", []):
            cargo_code = str(cargo.get("cd", "")).strip()
            for agrupamento in cargo.get("agr", []):
                for partido in agrupamento.get("par", []):
                    for candidato in partido.get("cand", []):
                        numero = str(candidato.get("n", "")).strip()
                        nome = str(candidato.get("nm", "")).strip()
                        nome_urna = str(candidato.get("nmu") or nome).strip()
                        if cargo_code and numero and nome:
                            names[(cargo_code, numero, nome)] = nome_urna
    return names


def load_dataset(key: str, urna_names: dict[tuple[str, str, str], str]) -> dict:
    label, cargo_code, summary_path, candidates_path, total_field = SPECS[key]
    summary = []
    for row in read_csv(summary_path):
        leader = row.get("candidato_mais_votado", "")
        leader_number = row.get("candidato_mais_votado_numero", "")
        leader_urna = urna_names.get((cargo_code, leader_number, leader), leader)
        summary.append({
            "distrito": district_name(row["distrito_ou_bairro"]),
            "secoes": int(row["quantidade_secoes"]),
            "aptos": int(row["eleitores_aptos"]),
            "votos": int(row[total_field]),
            "lider": leader_urna,
            "lider_urna": leader_urna,
            "lider_votos": int(row.get("votos_do_candidato_mais_votado", "0")),
        })
    summary.sort(key=lambda row: (-row["votos"], row["distrito"].casefold()))

    candidates = []
    for row in read_csv(candidates_path):
        votes = int(row["votos_nominais"])
        if votes <= 0:
            continue
        candidate = row["candidato"]
        candidate_number = row["numero"]
        candidate_urna = urna_names.get((cargo_code, candidate_number, candidate), candidate)
        candidates.append({
            "distrito": district_name(row["distrito_ou_bairro"]),
            "numero": candidate_number, "candidato": candidate_urna,
            "nome_urna": candidate_urna,
            "partido": row["partido"],
            "votos": votes, "secoes": row.get("secoes_com_votos", ""),
        })
    candidates.sort(key=lambda row: (row["distrito"].casefold(), -row["votos"], row["candidato"].casefold()))

    totals = defaultdict(lambda: {"numero": "", "candidato": "", "nome_urna": "", "partido": "", "votos": 0, "distritos": set()})
    for row in candidates:
        item = totals[(row["numero"], row["candidato"], row["nome_urna"], row["partido"])]
        item.update(numero=row["numero"], candidato=row["candidato"], nome_urna=row["nome_urna"], partido=row["partido"])
        item["votos"] += row["votos"]
        item["distritos"].add(row["distrito"])
    ranking = [{**item, "distritos": len(item["distritos"])} for item in totals.values() if item["votos"] > 0]
    ranking.sort(key=lambda row: (-row["votos"], row["candidato"].casefold(), row["numero"]))
    return {
        "cargo": label, "distritos": summary, "candidatos": candidates, "ranking": ranking,
        "total_votos": sum(row["votos"] for row in summary),
        "total_secoes": sum(row["secoes"] for row in summary),
        "total_aptos": sum(row["aptos"] for row in summary), "key": key,
    }


HTML = r'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Votos nominais de governador, senador e deputados por distrito e bairro em Águas Vermelhas, MG.">
<title>Resultados por cargo — Águas Vermelhas/MG</title>
<style>
:root{--ink:#18251f;--muted:#63736b;--line:#dce5df;--paper:#fff;--bg:#f3f7f4;--green:#17683d;--green2:#e6f3eb;--shadow:0 8px 28px #193b2910}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}header{background:linear-gradient(120deg,#114c31,#20834b);color:#fff;padding:26px max(16px,calc((100% - 1160px)/2)) 24px}header .eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.14em;opacity:.8;font-weight:700}h1{font-size:clamp(28px,8vw,42px);line-height:1.1;margin:8px 0}.sub{max-width:820px;color:#e2f1e7;margin:10px 0 0}.wrap{max-width:1160px;margin:0 auto;padding:12px 12px 50px}.tabs{display:flex;gap:8px;position:sticky;top:0;z-index:10;margin:0 -12px 12px;padding:8px 12px;background:#f3f7f4eb;backdrop-filter:blur(10px)}.tab{flex:1;border:1px solid #c8d6cd;background:#fff;color:var(--green);border-radius:10px;padding:12px 8px;min-height:48px;font:700 14px system-ui;cursor:pointer}.tab.active{background:var(--green);border-color:var(--green);color:#fff}.panel[hidden]{display:none}.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.stat,.district,.totals{background:var(--paper);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}.stat{padding:15px}.stat small{display:block;color:var(--muted);font-weight:650}.stat strong{font-size:25px}.tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:22px 0 14px}.tools input{flex:1;min-width:230px;padding:12px 14px;border:1px solid #c8d6cd;border-radius:10px;background:#fff;font:inherit}.hint{color:var(--muted);font-size:13px}.districts{display:grid;gap:12px}.district{overflow:hidden}.dhead{padding:16px;display:flex;align-items:center;gap:12px;cursor:pointer;list-style:none}.dhead::-webkit-details-marker{display:none}.dhead::after{content:'＋';margin-left:auto;color:var(--green);font-size:22px}.district[open] .dhead::after{content:'−'}.rank{width:34px;height:34px;border-radius:50%;background:var(--green2);color:var(--green);display:grid;place-items:center;font-weight:800;flex:none}.dname{font-weight:760}.dmeta{display:block;color:var(--muted);font-size:13px}.dtotal{margin-left:auto;text-align:right;white-space:nowrap}.dtotal strong{font-size:20px;display:block}.dtotal small{color:var(--muted)}.bar{height:6px;background:#edf2ee;margin:0 16px 16px;border-radius:9px;overflow:hidden}.bar span{display:block;background:var(--green);height:100%;border-radius:9px}.inside{padding:0 12px 15px}.inside h3{font-size:14px;margin:0 0 10px;color:#35463d}.tablewrap{overflow:auto;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;min-width:700px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #e8eee9;vertical-align:top}th{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);background:#f7faf8}tbody tr:last-child td{border-bottom:0}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.cand{font-weight:700}.party{display:inline-block;padding:2px 7px;background:#f0f4f1;border-radius:5px;font-size:12px;color:#415449}.share,.sections{font-size:12px;color:var(--muted)}.totals{margin-top:24px;padding:17px}.totals h2{font-size:21px;margin:0 0 12px}.totalcards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:15px}.totalcard{background:#f6faf7;border:1px solid var(--line);border-radius:10px;padding:11px 13px}.totalcard small{display:block;color:var(--muted)}.totalcard strong{font-size:20px}.totalrow td{font-weight:800;background:#f3f7f4}.notes{margin-top:18px;padding:15px;background:#fff8e9;border:1px solid #f0dfb7;border-radius:12px;color:#59451f;font-size:13px}footer{margin-top:18px;color:var(--muted);font-size:12px}@media(max-width:680px){.stats,.totalcards{grid-template-columns:repeat(2,minmax(0,1fr))}.stat:last-child{grid-column:1/-1}.tab{font-size:13px}.dhead{gap:8px}.dmeta{max-width:210px}.dtotal strong{font-size:18px}}
</style></head><body>
<header><div class="eyebrow">Eleições 2026 · Águas Vermelhas / MG</div><h1>Votos por distrito e candidato</h1><p class="sub">Consulte governador, senador, deputado federal e deputado estadual. Os distritos são ordenados pelos votos nominais; percentuais são calculados dentro do distrito e no total municipal.</p></header>
<main class="wrap"><nav class="tabs" aria-label="Cargo"><button class="tab active" data-cargo="federal" type="button">Deputado Federal</button><button class="tab" data-cargo="estadual" type="button">Deputado Estadual</button><button class="tab" data-cargo="senador" type="button">Senador</button><button class="tab" data-cargo="governador" type="button">Governador</button></nav>
<section class="panel" data-panel="federal"></section><section class="panel" data-panel="estadual" hidden></section><section class="panel" data-panel="senador" hidden></section><section class="panel" data-panel="governador" hidden></section>
<div class="notes"><strong>Como ler:</strong> candidatos sem voto são ocultados. “Seções” mostra onde o candidato recebeu voto. Votos de legenda, brancos e nulos não estão incluídos. Os resultados foram extraídos dos BUs brutos do TSE.</div><footer>Fonte: boletins de urna, dados oficiais de candidatos e mapa de seções deste repositório. Os arquivos .dat permitem auditoria.<br><br>GitHub: <a href="https://github.com/romeucampos">@romeucampos</a> · Projeto: <a href="https://github.com/romeucampos/Eleicao2026">Eleicao2026</a> · <a href="https://github.com/romeucampos/Eleicao2026/tree/main/dados">Dados</a><br>Feito por Romeu Campos.</footer></main>
<script>
const DATA=__DATASETS__,fmt=new Intl.NumberFormat('pt-BR');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const refs={};
function render(key){const d=DATA[key],panel=document.querySelector(`[data-panel="${key}"]`),max=Math.max(...d.distritos.map(x=>x.votos),1);panel.innerHTML=`<section class="stats"><div class="stat"><small>Votos nominais</small><strong>${fmt.format(d.total_votos)}</strong></div><div class="stat"><small>Distritos / bairros</small><strong>${d.distritos.length}</strong></div><div class="stat"><small>Seções · aptos</small><strong>${d.total_secoes} · ${fmt.format(d.total_aptos)}</strong></div></section><div class="tools"><input type="search" aria-label="Buscar candidato ou distrito" placeholder="Buscar distrito, candidato, número ou partido…"><span class="hint"></span></div><section class="districts"></section><section class="totals"></section>`;refs[key]={input:panel.querySelector('input'),hint:panel.querySelector('.hint'),districts:panel.querySelector('.districts'),totals:panel.querySelector('.totals')};const draw=q=>{q=q.trim().toLocaleLowerCase('pt-BR');const ds=d.distritos.map(x=>({...x,lista:d.candidatos.filter(c=>c.distrito===x.distrito)})).filter(x=>!q||x.distrito.toLocaleLowerCase('pt-BR').includes(q)||x.lista.some(c=>[c.candidato,c.numero,c.partido].join(' ').toLocaleLowerCase('pt-BR').includes(q)));refs[key].hint.textContent=`${ds.length} de ${d.distritos.length} distritos · ${fmt.format(ds.reduce((a,x)=>a+x.lista.length,0))} combinações com voto`;refs[key].districts.innerHTML=ds.map((x,i)=>{const rows=x.lista.sort((a,b)=>b.votos-a.votos||a.candidato.localeCompare(b.candidato,'pt-BR')).map((c,j)=>`<tr><td>${j+1}</td><td><span class="cand">${esc(c.candidato)}</span><br><span class="sections">Nº ${esc(c.numero)}</span></td><td><span class="party">${esc(c.partido)}</span></td><td class="num"><strong>${fmt.format(c.votos)}</strong></td><td class="num share">${(100*c.votos/x.votos).toLocaleString('pt-BR',{maximumFractionDigits:1})}%</td><td class="sections">${esc(c.secoes)}</td></tr>`).join('');return `<details class="district" ${q?'open':''}><summary class="dhead"><span class="rank">${i+1}</span><span><span class="dname">${esc(x.distrito)}</span><span class="dmeta">${x.secoes} ${x.secoes===1?'seção':'seções'} · ${fmt.format(x.aptos)} aptos</span></span><span class="dtotal"><strong>${fmt.format(x.votos)}</strong><small>votos</small></span></summary><div class="bar"><span style="width:${(100*x.votos/max).toFixed(2)}%"></span></div><div class="inside"><h3>Maior votação: ${esc(x.lider)} (${fmt.format(x.lider_votos)})</h3><div class="tablewrap"><table><thead><tr><th>Ordem</th><th>Candidato</th><th>Partido</th><th class="num">Votos</th><th class="num">% do distrito</th><th>Seções</th></tr></thead><tbody>${rows}</tbody></table></div></div></details>`}).join('')||'<p>Nenhum resultado encontrado.</p>';};const body=d.ranking.map((c,i)=>`<tr><td>${i+1}</td><td><span class="cand">${esc(c.candidato)}</span><br><span class="sections">Nº ${esc(c.numero)}</span></td><td><span class="party">${esc(c.partido)}</span></td><td class="num"><strong>${fmt.format(c.votos)}</strong></td><td class="num share">${(100*c.votos/d.total_votos).toLocaleString('pt-BR',{maximumFractionDigits:1})}%</td><td>${c.distritos} de ${d.distritos.length}</td></tr>`).join('');refs[key].totals.innerHTML=`<h2>Total consolidado</h2><div class="totalcards"><div class="totalcard"><small>Votos nominais</small><strong>${fmt.format(d.total_votos)}</strong></div><div class="totalcard"><small>Seções · aptos</small><strong>${d.total_secoes} · ${fmt.format(d.total_aptos)}</strong></div><div class="totalcard"><small>Candidatos com voto</small><strong>${d.ranking.length}</strong></div></div><div class="tablewrap"><table><thead><tr><th>Ordem</th><th>Candidato</th><th>Partido</th><th class="num">Votos</th><th class="num">% do total</th><th>Distritos</th></tr></thead><tbody>${body}<tr class="totalrow"><td colspan="3">Total</td><td class="num">${fmt.format(d.total_votos)}</td><td class="num">100%</td><td>${d.distritos.length}</td></tr></tbody></table></div>`;refs[key].input.oninput=e=>draw(e.target.value);draw('')}
Object.keys(DATA).forEach(render);document.querySelectorAll('.tab').forEach(tab=>tab.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===tab));document.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==tab.dataset.cargo)});
function reorderPartyColumns(){document.querySelectorAll('table').forEach(table=>{const rows=[...table.rows];if(!rows.length)return;const header=[...rows[0].children];const partyIndex=header.findIndex(cell=>cell.textContent.trim()==='Partido');const target=header.length-2;if(partyIndex<0||partyIndex===target)return;rows.forEach(row=>{if(row.classList.contains('totalrow')){const cells=[...row.children],label=cells[0],votes=cells[1],percent=cells[2],districts=cells[3],party=document.createElement('td');label.colSpan=2;party.textContent='';row.replaceChildren(label,votes,percent,party,districts);return}const cells=[...row.children],party=cells.splice(partyIndex,1)[0];cells.splice(target,0,party);row.replaceChildren(...cells)})})}
reorderPartyColumns();document.addEventListener('input',event=>{if(event.target.matches('.tools input'))setTimeout(reorderPartyColumns,0)});
</script></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=ROOT / "relatorio_aguas_vermelhas_2026_mobile_first.html")
    args = parser.parse_args()
    missing = [str(path) for _, _, summary, candidates, _ in SPECS.values() for path in (summary, candidates) if not path.is_file()]
    if missing:
        parser.error("Arquivos não encontrados: " + ", ".join(missing))
    urna_names = load_urna_names()
    datasets = {key: load_dataset(key, urna_names) for key in ("federal", "estadual", "senador", "governador")}
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(HTML.replace("__DATASETS__", json.dumps(datasets, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    print(f"HTML: {args.saida}")
    for key, data in datasets.items():
        print(f"{data['cargo']}: {data['total_votos']:,} votos, {len(data['distritos'])} distritos, {len(data['ranking'])} candidatos".replace(",", "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
