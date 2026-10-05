# Eleição 2026 — Águas Vermelhas/MG

Scripts e resultados para consultar boletins de urna por seção e somar votos nominais de deputados federal e estadual.

## Conteúdo

- `scripts/baixar_bu_raw_aguas_vermelhas_2026.py`: baixa e guarda os BUs brutos completos em `.dat`, sem decodificá-los; gera manifesto com a URL de origem e o SHA-256 local.
- `scripts/baixar_boletins_por_secao_aguas_vermelhas_2026.py`: baixa os BUs e extrai votos nominais positivos de deputado federal e estadual.
- `scripts/baixar_votos_aguas_vermelhas_2026.py`: baixa os resultados nominais usados em outra etapa de análise.
- `dados/raw/boletins/0213/<seção>/`: 31 BUs `.dat` originais, também disponíveis no ZIP.
- `dados/`: CSVs, ZIPs dos dados e planilha.
- `docs/REFERENCIAS_E_LINKS.md`: URLs dos endpoints, referências oficiais e descrição dos arquivos.
- `docs/`: relatório de seções e quantidade de eleitores.

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
