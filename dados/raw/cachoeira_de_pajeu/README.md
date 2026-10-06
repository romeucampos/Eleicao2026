# Boletins de urna brutos — Cachoeira de Pajeú/MG

Esta pasta contém os 30 BUs `.dat` originais das seções principais da zona
0213, município TSE `40533`, nas Eleições 2026. Os arquivos foram baixados do
endpoint oficial de arquivos de urna do TSE e permanecem em formato ASN.1
binário.

- `boletins/0213/<seção>/*.dat`: BU bruto de cada seção;
- `auxiliares/`: arquivos EA18 usados para localizar o BU totalizado;
- `config/`: configuração EA16 de seções;
- `schema/bu.asn1`: schema oficial usado na decodificação;
- `candidatos/`: cadastros oficiais EA20 dos cargos extraídos;
- `manifesto_boletins_raw.csv`: URLs, hashes TSE e SHA-256 local.

O script de download é `scripts/baixar_bu_raw_cachoeira_de_pajeu_2026.py`.
O extrator lê esses `.dat` locais com
`scripts/extrair_votos_cachoeira_de_pajeu_2026.py`.

O mapa de seção para local/distrito fica em
`dados/cachoeira_de_pajeu/secoes_por_local_distrito_bairro.csv`. Ele foi
confirmado com o arquivo oficial de eleitorado por local/seção do TSE para
2026; o código `1112` corresponde à Escola Municipal Castelo Branco II, no
Distrito de Marcela.
