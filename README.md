# Eleição 2026 — Águas Vermelhas/MG

Scripts e resultados para consultar boletins de urna por seção e somar votos nominais de presidente, governador, senador e deputados federal e estadual.

## Conteúdo

- `scripts/baixar_bu_raw_aguas_vermelhas_2026.py`: baixa e guarda os BUs brutos completos em `.dat`, sem decodificá-los; gera manifesto com a URL de origem e o SHA-256 local.
- `scripts/baixar_boletins_por_secao_aguas_vermelhas_2026.py`: baixa os BUs e extrai votos nominais positivos de governador, senador, deputado federal e deputado estadual.
- `scripts/somar_deputado_federal_por_distrito_bairro.py`: agrupa a extração nominal federal dos BUs por distrito/bairro e por candidato.
- `scripts/somar_deputado_estadual_por_distrito_bairro.py`: agrupa a extração nominal estadual dos BUs por distrito/bairro e por candidato.
- `scripts/somar_governador_por_distrito_bairro.py`: agrupa a extração nominal de governador dos BUs por distrito/bairro e por candidato.
- `scripts/extrair_presidente_aguas_vermelhas_2026.py`: preserva os BUs do 2º turno e extrai Presidente nos dois turnos.
- `scripts/somar_presidente_aguas_vermelhas_2026.py`: agrega Presidente do 1º e do 2º turno por distrito/bairro e candidato.
- `scripts/gerar_html_deputados_distrito_bairro.py`: gera o relatório HTML com abas para deputado federal e estadual.
- `scripts/gerar_html_aguas_vermelhas_2026.py`: gera o relatório HTML com abas para os quatro cargos e os dois turnos de Presidente.
- `scripts/baixar_votos_aguas_vermelhas_2026.py`: baixa os resultados nominais usados em outra etapa de análise.
- `dados/raw/boletins/0213/<seção>/`: 31 BUs `.dat` originais, também disponíveis no ZIP.
- `dados/`: CSVs, ZIPs dos dados e planilha.
- `docs/REFERENCIAS_E_LINKS.md`: URLs dos endpoints, referências oficiais e descrição dos arquivos.
- `docs/`: relatório de seções e quantidade de eleitores.

A soma por distrito/bairro gera `dados/votos_deputado_federal_por_distrito_bairro.csv` e `dados/votos_federal_por_candidato_distrito_bairro.csv`. A mesma soma para deputado estadual gera `dados/votos_deputado_estadual_por_distrito_bairro.csv` e `dados/votos_estadual_por_candidato_distrito_bairro.csv`.

Para governador, os arquivos gerados são `dados/votos_governador_por_distrito_bairro.csv` e `dados/votos_governador_por_candidato_distrito_bairro.csv`.

O relatório `relatorio_aguas_vermelhas_2026_mobile_first.html` é gerado a partir dos CSVs derivados dos BUs brutos e traz seis abas: deputado federal, deputado estadual, senador, governador, Presidente no 1º turno e Presidente no 2º turno. A sede do município e os demais distritos são ordenados por votos, candidatos sem voto são ocultados, e cada aba mostra percentuais e o total consolidado do cargo/turno.

## Baixar novamente os boletins brutos

O script dedicado usa somente a biblioteca padrão do Python 3:

```bash
python3 scripts/baixar_bu_raw_aguas_vermelhas_2026.py
```

Por padrão, grava em `dados_raw_aguas_vermelhas_2026/`, incluindo configuração EA16, auxiliares EA18, arquivos `.dat` e `manifesto_boletins_raw.csv`. Use `--pasta CAMINHO` para escolher outro destino ou `--forcar` para baixar novamente arquivos existentes.

Para decodificar e gerar as planilhas de votos, consulte as instruções em [`docs/LEIA-ME-boletins-por-secao.txt`](docs/LEIA-ME-boletins-por-secao.txt).

## Escopo dos CSVs atuais

Os arquivos `votos_por_secao_e_candidato.csv` e `votos_somados_por_candidato.csv` contêm votos nominais positivos para governador, senador, deputado federal e estadual. O arquivo `presidente_por_secao_e_candidato_2026.csv` separa os votos de Presidente pelos turnos `1` e `2`. Candidatos com zero voto e votos de legenda, branco e nulo não aparecem nesses CSVs. Os `.dat` são os boletins completos publicados para as seções, com status totalizado.

### Presidente nos dois turnos

Os BUs presidenciais do 1º turno estão em `dados/raw/boletins/` e os do 2º turno em `dados/raw/boletins/2o_turno/`. Os cadastros oficiais de candidatos são `mg40193-c0001-e006257-u.json` e `mg40193-c0001-e006258-u.json`; os códigos de eleição são `6257` (1º turno) e `6258` (2º turno), e os pleitos de arquivos de urna são `3220` e `3221`.

Para reproduzir a atualização:

```bash
python3 -m pip install -r scripts/requirements_boletins_tse.txt
python3 scripts/extrair_presidente_aguas_vermelhas_2026.py
python3 scripts/somar_presidente_aguas_vermelhas_2026.py
python3 scripts/gerar_html_aguas_vermelhas_2026.py
```

Na extração validada, foram processadas 31 seções em cada turno. Os totais nominais conferidos com o cadastro municipal oficial foram 7.149 no 1º turno e 7.422 no 2º turno.

Confira status, hash e fontes na documentação antes de reutilizar os dados. Os resultados processados são transformação dos arquivos oficiais e não substituem a conferência do BU original.


## Aba de senador (branch `senador-tab`)

A branch separada acrescenta a extração do cargo **Senador** aos mesmos boletins de urna brutos. O parser `baixar_boletins_por_secao_aguas_vermelhas_2026.py` agora usa os códigos 5 (senador), 6 (deputado federal) e 7 (deputado estadual). O novo agregador é `scripts/somar_senador_por_distrito_bairro.py`.

Os resultados derivados da extração dos BUs brutos são:
- `dados/votos_senador_por_distrito_bairro.csv`;
- `dados/votos_senador_por_candidato_distrito_bairro.csv`.

O relatório `relatorio_deputados_federal_estadual_senador_mobile_first.html` tem uma terceira aba para senador, com distritos/bairros em ordem decrescente de votos, candidatos com voto e ranking consolidado. O Centro é exibido como “Sede do município”; o partido fica na penúltima coluna.
