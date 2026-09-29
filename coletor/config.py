# -*- coding: utf-8 -*-
"""
Configuração do ATLAS. Edite aqui o universo de cobertura.

Cada ativo tem: ticker de negociação, tipo ("acao" ou "fii"), setor e perfis.
O CNPJ é descoberto sozinho pelo cadastro oficial da CVM (FCA para ações,
informe mensal para FIIs). Se algum não for encontrado, preencha CNPJ_MANUAL.
"""

UNIVERSO = [
    # ticker,  tipo,   setor,                    perfis
    ("BBAS3",  "acao", "Bancos e financeiro",    ["Barsi", "Valor"]),
    ("ITUB4",  "acao", "Bancos e financeiro",    ["Buffett"]),
    ("BBDC4",  "acao", "Bancos e financeiro",    []),
    ("SANB11", "acao", "Bancos e financeiro",    ["Barsi"]),
    ("B3SA3",  "acao", "Bancos e financeiro",    ["Buffett"]),
    ("TAEE11", "acao", "Energia",                ["Barsi"]),
    ("EGIE3",  "acao", "Energia",                ["Barsi", "Buffett"]),
    ("ISAE4",  "acao", "Energia",                []),
    ("CPLE3",  "acao", "Energia",                []),
    ("AXIA3",  "acao", "Energia",                []),
    ("PETR4",  "acao", "Commodities",            ["Barsi", "Valor"]),
    ("VALE3",  "acao", "Commodities",            ["Barsi", "Valor"]),
    ("PRIO3",  "acao", "Commodities",            ["Lynch"]),
    ("CMIN3",  "acao", "Commodities",            ["Lynch", "Valor"]),
    ("GGBR4",  "acao", "Commodities",            []),
    ("WEGE3",  "acao", "Qualidade",              ["Buffett", "Lynch"]),
    ("RAIL3",  "acao", "Qualidade",              ["Buffett"]),
    ("FLRY3",  "acao", "Qualidade",              ["Buffett"]),
    ("TOTS3",  "acao", "Qualidade",              ["Buffett", "Lynch"]),
    ("HAPV3",  "acao", "Crescimento",            ["Lynch"]),
    ("RDOR3",  "acao", "Crescimento",            ["Lynch"]),
    ("LWSA3",  "acao", "Crescimento",            ["Lynch"]),
    ("VIVA3",  "acao", "Crescimento",            []),
    ("GMAT3",  "acao", "Crescimento",            ["Lynch"]),
    ("FRAS3",  "acao", "Watchlist",              []),
    ("TUPY3",  "acao", "Watchlist",              []),
    ("KNRI11", "fii",  "FII Híbrido",            ["Baroni"]),
    ("HGLG11", "fii",  "FII Logístico",          ["Baroni"]),
    ("MXRF11", "fii",  "FII Papel",              ["Baroni"]),
    ("XPLG11", "fii",  "FII Logístico",          ["Baroni"]),
    ("BTLG11", "fii",  "FII Logístico",          ["Baroni"]),
]

# Preencha só se o coletor avisar que não encontrou o CNPJ de algum ativo.
# Formato: "TICKER": "00.000.000/0000-00"
CNPJ_MANUAL = {}

# Quantos dias os fundamentos da CVM ficam em cache antes de baixar de novo.
# Balanços mudam só a cada trimestre; preços e macro são atualizados todo dia.
DIAS_CACHE_FUNDAMENTOS = 7

# Anos de histórico anual (DFP) usados no CAGR e na consistência de dividendos.
ANOS_HISTORICO = 5

# Alíquota usada no ROIC (IR + CSLL padrão de lucro real).
ALIQUOTA_ROIC = 0.34
