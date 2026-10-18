# -*- coding: utf-8 -*-
"""
Configuração do ATLAS. Edite aqui o universo de cobertura.

UNIVERSO é a lista curada ("Universo ATLAS"). Cada ativo tem: ticker de negociação,
tipo ("acao" ou "fii"), setor, grupo ATLAS (o papel do ativo na carteira: Qualidade,
Crescimento, Watchlist...) e perfis. Os perfis destes ativos são escolhidos à mão.

Com MERCADO_COMPLETO = True, o coletor também acompanha sozinho todas as ações e FIIs
negociados na B3 com liquidez mínima (volume médio diário dos últimos pregões). Para
esses, o setor vem do cadastro da CVM e os perfis são sugeridos por regras numéricas
(ver PERFIS_AUTOMATICOS no main.py).

Perfis (escolas de investimento do ATLAS):
  Graham   - valor e margem de segurança (P/L e P/VP baixos)
  Buffett  - qualidade, vantagem competitiva e retorno sobre capital
  Barsi    - dividendos e acumulação de renda
  Lynch    - crescimento
  Dalio    - proteção e diversificação (receita ligada à inflação, petróleo, FIIs)
  Bartunek - qualidade com crescimento de longo prazo e boa gestão
  Baroni   - fundos imobiliários e renda recorrente

O CNPJ é descoberto sozinho pelo cadastro oficial da CVM (FCA para ações,
informe mensal para FIIs). Se algum não for encontrado, preencha CNPJ_MANUAL.
"""

UNIVERSO = [
    # ticker,  tipo,   setor,                      grupo ATLAS,            perfis
    ("BBAS3",  "acao", "Bancos e financeiro",      "Bancos e financeiro",  ["Barsi", "Graham"]),
    ("ITUB4",  "acao", "Bancos e financeiro",      "Bancos e financeiro",  ["Buffett", "Bartunek"]),
    ("BBDC4",  "acao", "Bancos e financeiro",      "Bancos e financeiro",  ["Graham"]),
    ("SANB11", "acao", "Bancos e financeiro",      "Bancos e financeiro",  ["Barsi", "Graham"]),
    ("B3SA3",  "acao", "Bancos e financeiro",      "Bancos e financeiro",  ["Buffett", "Bartunek"]),
    ("TAEE11", "acao", "Energia e saneamento",     "Energia",              ["Barsi", "Dalio"]),
    ("EGIE3",  "acao", "Energia e saneamento",     "Energia",              ["Barsi", "Buffett"]),
    ("ISAE4",  "acao", "Energia e saneamento",     "Energia",              ["Graham", "Dalio"]),
    ("CPLE3",  "acao", "Energia e saneamento",     "Energia",              ["Dalio"]),
    ("AXIA3",  "acao", "Energia e saneamento",     "Energia",              ["Dalio"]),
    ("PETR4",  "acao", "Commodities",              "Commodities",          ["Barsi", "Graham", "Dalio"]),
    ("VALE3",  "acao", "Commodities",              "Commodities",          ["Barsi", "Graham"]),
    ("PRIO3",  "acao", "Commodities",              "Commodities",          ["Lynch", "Dalio"]),
    ("CMIN3",  "acao", "Commodities",              "Commodities",          ["Lynch", "Graham"]),
    ("GGBR4",  "acao", "Commodities",              "Commodities",          ["Graham"]),
    ("WEGE3",  "acao", "Indústria",                "Qualidade",            ["Buffett", "Lynch", "Bartunek"]),
    ("RAIL3",  "acao", "Transporte e logística",   "Qualidade",            ["Buffett", "Bartunek"]),
    ("FLRY3",  "acao", "Saúde",                    "Qualidade",            ["Buffett"]),
    ("TOTS3",  "acao", "Tecnologia e telecom",     "Qualidade",            ["Buffett", "Lynch", "Bartunek"]),
    ("HAPV3",  "acao", "Saúde",                    "Crescimento",          ["Lynch"]),
    ("RDOR3",  "acao", "Saúde",                    "Crescimento",          ["Lynch", "Bartunek"]),
    ("LWSA3",  "acao", "Tecnologia e telecom",     "Crescimento",          ["Lynch"]),
    ("VIVA3",  "acao", "Consumo e varejo",         "Crescimento",          ["Lynch", "Bartunek"]),
    ("GMAT3",  "acao", "Consumo e varejo",         "Crescimento",          ["Lynch"]),
    ("FRAS3",  "acao", "Indústria",                "Watchlist",            []),
    ("TUPY3",  "acao", "Indústria",                "Watchlist",            []),
    ("KNRI11", "fii",  "FII Híbrido",              "FII Híbrido",          ["Baroni", "Dalio"]),
    ("HGLG11", "fii",  "FII Logístico",            "FII Logístico",        ["Baroni"]),
    ("MXRF11", "fii",  "FII Papel",                "FII Papel",            ["Baroni", "Dalio"]),
    ("XPLG11", "fii",  "FII Logístico",            "FII Logístico",        ["Baroni"]),
    ("BTLG11", "fii",  "FII Logístico",            "FII Logístico",        ["Baroni"]),
]

# Preencha só se o coletor avisar que não encontrou o CNPJ de algum ativo.
# Formato: "TICKER": "00.000.000/0000-00"
CNPJ_MANUAL = {
    "CMIN3": "08.902.291/0001-15",  # CSN Mineração (não aparece no FCA com esse código)
}

# Quantos dias os fundamentos da CVM ficam em cache antes de baixar de novo.
# Balanços mudam só a cada trimestre; preços e macro são atualizados todo dia.
DIAS_CACHE_FUNDAMENTOS = 7

# Anos de histórico anual (DFP) usados no CAGR e na consistência de dividendos.
ANOS_HISTORICO = 5

# Alíquota usada no ROIC (IR + CSLL padrão de lucro real).
ALIQUOTA_ROIC = 0.34

# ---------------------------------------------------------------------------
# Mercado completo (além da lista curada acima)
# ---------------------------------------------------------------------------
# True = acompanha todas as ações e FIIs com liquidez mínima. False = só a lista UNIVERSO.
MERCADO_COMPLETO = True

# Volume médio diário mínimo (R$) nos últimos PREGOES_LIQUIDEZ pregões.
LIQUIDEZ_MINIMA_ACOES = 1_000_000
LIQUIDEZ_MINIMA_FIIS = 500_000
PREGOES_LIQUIDEZ = 63  # cerca de 3 meses

# Tickers que nunca devem entrar pelo filtro automático (ex.: "ABCD3").
EXCLUIR = []
