# Links, endpoints e referências

Este documento descreve as fontes oficiais usadas pelos scripts e os arquivos gerados para Águas Vermelhas/MG. Os URLs de download são endpoints de dados do TSE; a estrutura e os identificadores podem mudar entre pleitos.

## Fontes oficiais do TSE

| Referência | Link | Uso |
|---|---|---|
| Eleições 2026 | <https://www.tse.jus.br/eleicoes/eleicoes-2026> | Página oficial com informações, documentos e acesso aos resultados. |
| Portal Resultados do TSE | <https://resultados.tse.jus.br/oficial/app/index.html> | Consulta interativa de resultados e boletins por seção. |
| Divulgação de resultados 2026 | <https://www.tse.jus.br/eleicoes/eleicoes-2026-content/divulgacao-dos-resultados-das-eleicoes-2026> | Página do TSE que encaminha ao portal de resultados. |
| Formato BU, RDV e assinatura digital | <https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/formato-arquivos-de-bu-rdv-e-assinatura-digital> | Pacote oficial ZIP com especificações e leiautes; o script de soma usa o schema ASN.1 do BU. |
| EA11 — configuração de eleições | <https://www.tse.jus.br/eleicoes/arquivos/tse-ea11-arquivo-de-configuracao-de-eleicoes> | Descreve arquivos de configuração do pleito. |
| EA16 — configuração de seções | <https://www.tse.jus.br/eleicoes/arquivos/tse-ea16-arquivo-de-configuracao-de-secoes-eleitorais> | Descreve o índice de zonas e seções usado para enumerar as seções. |
| EA18 — auxiliar de seção | <https://www.tse.jus.br/eleicoes/arquivos/tse-ea18-arquivo-auxiliar-de-secao> | Descreve os auxiliares que identificam hashes, status e arquivos BU disponíveis por seção. |
| EA20 — resultado unificado | <https://www.tse.jus.br/eleicoes/arquivos/tse-ea20-arquivo-de-resultado-unificado> | Referência do arquivo unificado usado para obter dados de candidatos no script de extração. |
| Resolução TSE nº 23.751/2026 | <https://www.tse.jus.br/legislacao/compilada/res/2026/resolucao-no-23-751-de-26-de-fevereiro-de-2026> | Art. 210 descreve conteúdo do BU, incluindo votação por candidatura, legenda, votos brancos e nulos. |

## Endpoints usados

Constantes da coleta deste município:

- Ambiente: `oficial`
- UF: `mg`
- Código do município: `40193` (Águas Vermelhas)
- Identificador do pleito de arquivos de urna: `3220`
- Identificador da eleição para os dados de candidatos: `6259`
- Zona do material incluído neste repositório: `0213`

### Índice de seções — EA16

```text
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/config/mg/mg-p003220-cs.json
```

O JSON lista as seções do estado. O script filtra o município `40193` e ignora seções agregadas com `nsp`, porque seus votos constam no BU da seção principal.

### Auxiliar de uma seção — EA18

```text
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/mg/40193/0213/0070/p003220-mg-m40193-z0213-s0070-aux.json
```

Troque `0213` pela zona e `0070` pela seção. O auxiliar é consultado para localizar o BU disponível e seu status. A coleta escolhe um registro com status `Totalizado` e tipo de arquivo `BU`.

### Boletim bruto — BU `.dat`

```text
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/mg/40193/0213/0070/<hash>/<arquivo-bu>.dat
```

O segmento `<hash>` vem do auxiliar EA18; `<arquivo-bu>` é o nome indicado no mesmo registro. O arquivo `.dat` é salvo sem decodificação. O script `baixar_bu_raw_aguas_vermelhas_2026.py` não precisa da biblioteca ASN.1.

### Configuração de candidatos — EA20

```text
https://resultados.tse.jus.br/oficial/ele2026/6259/dados/mg/mg40193-c0005-e006259-u.json
https://resultados.tse.jus.br/oficial/ele2026/6259/dados/mg/mg40193-c0006-e006259-u.json
https://resultados.tse.jus.br/oficial/ele2026/6259/dados/mg/mg40193-c0007-e006259-u.json
```

Os códigos `0005`, `0006` e `0007` identificam senador, deputado federal e estadual. Esses JSONs são consultados pelo script de soma para associar número, partido e nome de urna ao resultado.

## Arquivos no repositório

- [`../scripts/baixar_bu_raw_aguas_vermelhas_2026.py`](../scripts/baixar_bu_raw_aguas_vermelhas_2026.py): baixa e preserva BUs completos em `.dat`, além de gravar um manifesto com hash SHA-256 local.
- [`../scripts/baixar_boletins_por_secao_aguas_vermelhas_2026.py`](../scripts/baixar_boletins_por_secao_aguas_vermelhas_2026.py): baixa os BUs e extrai votos nominais positivos dos cargos-alvo.
- [`../scripts/somar_deputado_federal_por_distrito_bairro.py`](../scripts/somar_deputado_federal_por_distrito_bairro.py): junta a extração federal por seção ao mapa de locais/distritos e gera totais por distrito/bairro e por candidato.
- [`../scripts/somar_senador_por_distrito_bairro.py`](../scripts/somar_senador_por_distrito_bairro.py): faz a mesma agregação para senador.
- [`../dados/votos_senador_por_distrito_bairro.csv`](../dados/votos_senador_por_distrito_bairro.csv) e [`../dados/votos_senador_por_candidato_distrito_bairro.csv`](../dados/votos_senador_por_candidato_distrito_bairro.csv): totais e detalhamento do senador por distrito/bairro.
- [`../dados/raw/boletins/0213/`](../dados/raw/boletins/0213/): arquivos BU brutos `.dat` por seção.
- [`../dados/boletins_aguas_vermelhas_2026.zip`](../dados/boletins_aguas_vermelhas_2026.zip): pacote dos BUs, auxiliares, schema e materiais usados na coleta.
- [`../dados/votos_por_secao_e_candidato.csv`](../dados/votos_por_secao_e_candidato.csv) e [`../dados/votos_somados_por_candidato.csv`](../dados/votos_somados_por_candidato.csv): resultados processados; incluem votos nominais positivos, não os votos brancos, nulos, de legenda ou candidatos com zero voto.
- [`../dados/votos_deputado_federal_por_distrito_bairro.csv`](../dados/votos_deputado_federal_por_distrito_bairro.csv) e [`../dados/votos_federal_por_candidato_distrito_bairro.csv`](../dados/votos_federal_por_candidato_distrito_bairro.csv): agregação federal por distrito/bairro e detalhamento por candidato.
- [`../dados/secoes_por_local_distrito_aguas_vermelhas.csv`](../dados/secoes_por_local_distrito_aguas_vermelhas.csv): relação de seções por local/distrito extraída do PDF fornecido.
- [`../docs/SECOES-QUANTIDADE-ELEITORES-AGUAS-VERMELHAS.pdf`](../docs/SECOES-QUANTIDADE-ELEITORES-AGUAS-VERMELHAS.pdf): cópia do PDF de origem da relação de locais e aptos.

## Referências técnicas dos dados

- **EA16:** configuração que fornece a relação de municípios, zonas e seções.
- **EA18:** auxiliar por seção que indica status, hash e arquivos disponíveis.
- **BU:** arquivo de resultado emitido para uma seção; os originais `.dat` são preservados para permitir reprocessamento.
- **EA20:** dados unificados de resultados e candidaturas usados para nomes/siglas na saída CSV.
- **Schema ASN.1:** leiaute do TSE para interpretar o arquivo bruto BU; está incluído no pacote ZIP de formato publicado pelo Tribunal.

Confira sempre o status e o hash informados pelo auxiliar do TSE. Resultados agregados deste projeto são uma transformação dos arquivos oficiais, não substituem a consulta ao BU original.
