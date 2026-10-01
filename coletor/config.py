# -*- coding: utf-8 -*-
"""
Configuração do ATLAS. Edite aqui o universo de cobertura.

Cada ativo tem: ticker de negociação, tipo ("acao" ou "fii"), setor e perfis.

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
    # ticker,  tipo,   setor,                    perfis
    ("BBAS3",  "acao", "Bancos e financeiro",    ["Barsi", "Graham"]),
    ("ITUB4",  "acao", "Bancos e financeiro",    ["Buffett", "Bartunek"]),
    ("BBDC4",  "acao", "Bancos e financeiro",    ["Graham"]),
    ("SANB11", "acao", "Bancos e financeiro",    ["Barsi", "Graham"]),
    ("B3SA3",  "acao", "Bancos e financeiro",    ["Buffett", "Bartunek"]),
    ("TAEE11", "acao", "Energia",                ["Barsi", "Dalio"]),
    ("EGIE3",  "acao", "Energia",                ["Barsi", "Buffett"]),
    ("ISAE4",  "acao", "Energia",                ["Graham", "Dalio"]),
    ("CPLE3",  "acao", "Energia",                ["Dalio"]),
    ("AXIA3",  "acao", "Energia",                ["Dalio"]),
    ("PETR4",  "acao", "Commodities",            ["Barsi", "Graham", "Dalio"]),
    ("VALE3",  "acao", "Commodities",            ["Barsi", "Graham"]),
    ("PRIO3",  "acao", "Commodities",            ["Lynch", "Dalio"]),
    ("CMIN3",  "acao", "Commodities",            ["Lynch", "Graham"]),
    ("GGBR4",  "acao", "Commodities",            ["Graham"]),
    ("WEGE3",  "acao", "Qualidade",              ["Buffett", "Lynch", "Bartunek"]),
    ("RAIL3",  "acao", "Qualidade",              ["Buffett", "Bartunek"]),
    ("FLRY3",  "acao", "Qualidade",              ["Buffett"]),
    ("TOTS3",  "acao", "Qualidade",              ["Buffett", "Lynch", "Bartunek"]),
    ("HAPV3",  "acao", "Crescimento",            ["Lynch"]),
    ("RDOR3",  "acao", "Crescimento",            ["Lynch", "Bartunek"]),
    ("LWSA3",  "acao", "Crescimento",            ["Lynch"]),
    ("VIVA3",  "acao", "Crescimento",            ["Lynch", "Bartunek"]),
    ("GMAT3",  "acao", "Crescimento",            ["Lynch"]),
    ("FRAS3",  "acao", "Watchlist",              []),
    ("TUPY3",  "acao", "Watchlist",              []),
    ("KNRI11", "fii",  "FII Híbrido",            ["Baroni", "Dalio"]),
    ("HGLG11", "fii",  "FII Logístico",          ["Baroni"]),
    ("MXRF11", "fii",  "FII Papel",              ["Baroni", "Dalio"]),
    ("XPLG11", "fii",  "FII Logístico",          ["Baroni"]),
    ("BTLG11", "fii",  "FII Logístico",          ["Baroni"]),
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
