# Eleição 2026 — Águas Vermelhas/MG

Scripts e resultados para consultar boletins de urna por seção e somar votos nominais de deputados federal e estadual.

## Conteúdo

- `scripts/baixar_bu_raw_aguas_vermelhas_2026.py`: baixa e guarda os BUs brutos completos em `.dat`, sem decodificá-los; gera manifesto com a URL de origem e o SHA-256 local.
- `scripts/baixar_boletins_por_secao_aguas_vermelhas_2026.py`: baixa os BUs e extrai votos nominais positivos de deputado federal e estadual.
- `scripts/somar_deputado_federal_por_distrito_bairro.py`: agrupa a extração nominal federal dos BUs por distrito/bairro e por candidato.
- `scripts/somar_deputado_estadual_por_distrito_bairro.py`: agrupa a extração nominal estadual dos BUs por distrito/bairro e por candidato.
- `scripts/gerar_html_deputados_distrito_bairro.py`: gera o relatório HTML com abas para deputado federal e estadual.
- `scripts/baixar_votos_aguas_vermelhas_2026.py`: baixa os resultados nominais usados em outra etapa de análise.
- `dados/raw/boletins/0213/<seção>/`: 31 BUs `.dat` originais, também disponíveis no ZIP.
- `dados/`: CSVs, ZIPs dos dados e planilha.
- `docs/REFERENCIAS_E_LINKS.md`: URLs dos endpoints, referências oficiais e descrição dos arquivos.
- `docs/`: relatório de seções e quantidade de eleitores.

A soma por distrito/bairro gera `dados/votos_deputado_federal_por_distrito_bairro.csv` e `dados/votos_federal_por_candidato_distrito_bairro.csv`. A mesma soma para deputado estadual gera `dados/votos_deputado_estadual_por_distrito_bairro.csv` e `dados/votos_estadual_por_candidato_distrito_bairro.csv`.

O relatório com as duas abas é `relatorio_deputados_federal_estadual_distrito_bairro_atualizado.html`. Ele é gerado a partir dos CSVs derivados dos BUs brutos e traz a sede do município, os distritos ordenados por votos, candidatos sem voto ocultos e o total consolidado de cada cargo.

## Baixar novamente os boletins brutos

O script dedicado usa somente a biblioteca padrão do Python 3:

```bash
python3 scripts/baixar_bu_raw_aguas_vermelhas_2026.py
```

Por padrão, grava em `dados_raw_aguas_vermelhas_2026/`, incluindo configuração EA16, auxiliares EA18, arquivos `.dat` e `manifesto_boletins_raw.csv`. Use `--pasta CAMINHO` para escolher outro destino ou `--forcar` para baixar novamente arquivos existentes.

Para decodificar e gerar as planilhas de votos, consulte as instruções em [`docs/LEIA-ME-boletins-por-secao.txt`](docs/LEIA-ME-boletins-por-secao.txt).

## Escopo dos CSVs atuais

Os arquivos `votos_por_secao_e_candidato.csv` e `votos_somados_por_candidato.csv` contêm votos nominais positivos para deputado federal e estadual. Candidatos com zero voto e votos de legenda, branco e nulo não aparecem nesses CSVs. Os `.dat` são os boletins completos publicados para as seções, com status totalizado.

Confira status, hash e fontes na documentação antes de reutilizar os dados. Os resultados processados são transformação dos arquivos oficiais e não substituem a conferência do BU original.


## Aba de senador (branch `senador-tab`)

A branch separada acrescenta a extração do cargo **Senador** aos mesmos boletins de urna brutos. O parser `baixar_boletins_por_secao_aguas_vermelhas_2026.py` agora usa os códigos 5 (senador), 6 (deputado federal) e 7 (deputado estadual). O novo agregador é `scripts/somar_senador_por_distrito_bairro.py`.

Os resultados derivados da extração dos BUs brutos são:
- `dados/votos_senador_por_distrito_bairro.csv`;
- `dados/votos_senador_por_candidato_distrito_bairro.csv`.

O relatório `relatorio_deputados_federal_estadual_senador_mobile_first.html` tem uma terceira aba para senador, com distritos/bairros em ordem decrescente de votos, candidatos com voto e ranking consolidado. O Centro é exibido como “Sede do município”; o partido fica na penúltima coluna.
