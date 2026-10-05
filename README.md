# Eleição 2026 — Águas Vermelhas/MG

Scripts e resultados para consultar boletins de urna por seção e somar votos nominais de deputados federal e estadual.

## Conteúdo

- `scripts/`: scripts Python de download e extração.
- `dados/`: CSVs resultantes, mapa de seções por local/distrito e cópia compactada dos boletins originais.
- `documentos/`: relatório de seções e quantidade de eleitores.

## Escopo dos CSVs atuais

Os arquivos `votos_por_secao_e_candidato.csv` e `votos_somados_por_candidato.csv` contêm votos nominais positivos para os cargos de deputado federal e estadual. Candidatos com zero voto e votos de legenda, branco e nulo não aparecem nesses CSVs. Os boletins `.dat` arquivados são os arquivos completos baixados do TSE para as 31 seções principais, com status totalizado.

## Executar

Instale a dependência com `python3 -m pip install -r scripts/requirements_boletins_tse.txt` e execute `python3 scripts/baixar_boletins_por_secao_aguas_vermelhas_2026.py`.

Os dados eleitorais devem ser conferidos diretamente com os boletins oficiais do TSE antes de reutilização.