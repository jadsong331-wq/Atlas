# -*- coding: utf-8 -*-
"""
Controle de qualidade dos dados do ATLAS.

1. limitar(): indicador fora do intervalo possível não entra na nota. Esses valores quase sempre são
   erro de informe (escala trocada, campo errado, número digitado errado na fonte). O ativo recebe um
   aviso dizendo qual indicador foi descartado e por quê.
2. relatorio(): idade de cada fonte oficial e situação (em dia, atrasada, sem resposta), gravada em
   docs/data/saude.json e mostrada na aba Fontes. Se uma fonte essencial estiver velha, a coleta
   termina com aviso e o GitHub abre um alerta.
"""

from datetime import date, datetime

from util import log

# (mínimo, máximo) plausível; fora disso o valor é descartado. Limites largos de propósito:
# só barram o impossível, não o raro.
LIMITES_ACAO = {
    "dy": (0, 40), "dy_recorrente": (0, 40), "dy_medio5": (0, 40),
    "roe": (-300, 300), "roic": (-200, 200), "margem_liquida": (-500, 100),
    "p_vp": (0, 60), "ev_ebitda": (-300, 500), "div_liq_ebitda": (-60, 60),
    "cagr_receita": (-70, 250), "cagr_lucro": (-95, 400),
    "volatilidade": (0, 400), "queda_12m": (-100, 0),
    "fcf_yield": (-100, 100), "cobertura_juros": (-100, 1000), "conversao_caixa": (-1000, 1000),
}
LIMITES_FII = {
    "dy": (0, 40), "dy_recorrente": (0, 40), "p_vp": (0.1, 5),
    "vp_var_12m": (-50, 60), "alavancagem": (0, 500), "volatilidade": (0, 200), "queda_12m": (-100, 0),
}


def _br(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def limitar(ativos):
    descartes = []
    for a in ativos:
        lim = LIMITES_FII if a.get("tipo") == "fii" else LIMITES_ACAO
        ind = a.get("ind") or {}
        for k, (mn, mx) in lim.items():
            v = ind.get(k)
            if v is None or not isinstance(v, (int, float)):
                continue
            if v < mn or v > mx:
                ind[k] = None
                if a.get("tipo") == "fii" and k == "vp_var_12m" and ind.get("p_vp") is not None:
                    # valor da cota que dobra ou cai pela metade em 12 meses: quase sempre grupamento,
                    # desdobramento ou informe de outra classe; o P/VP desse informe também não é confiável
                    ind["p_vp"] = None
                    descartes.append(f"{a['ticker']}:p_vp")
                a.setdefault("avisos", []).append(
                    f"{k} de {_br(v)} descartado: fora do intervalo plausível ({_br(mn)} a {_br(mx)}); provável erro na fonte ou base muito pequena, fora da nota")
                descartes.append(f"{a['ticker']}:{k}={v:.4g}")
    if descartes:
        log(f"Qualidade: {len(descartes)} valor(es) fora do intervalo plausível descartados: {descartes[:40]}")
    return descartes


def _dias(iso, hoje):
    if not iso:
        return None
    t = str(iso)[:10]
    try:
        if len(t) == 10 and t[2] == "/":
            d = date(int(t[6:]), int(t[3:5]), int(t[:2]))
        elif len(t) == 7:
            d = date(int(t[:4]), int(t[5:7]), 1)
        else:
            d = date.fromisoformat(t)
    except ValueError:
        return None
    return (hoje - d).days


def relatorio(saida, extras, hoje=None):
    """
    extras: datas de referência de fontes que não estão em `saida`.
    Limites de idade em dias corridos, pensando no ritmo de publicação de cada fonte.
    """
    hoje = hoje or date.today()
    m = saida.get("macro") or {}
    s = m.get("series") or {}
    linhas = [
        ("Cotações (B3)", saida.get("pregao"), 5, True),
        ("Balanços (CVM, DFP e ITR)", saida.get("fundamentos_em"), 10, True),
        ("Selic (Banco Central)", (s.get("selic") or {}).get("data"), 10, True),
        ("IPCA (Banco Central)", (s.get("ipca_12m") or {}).get("data"), 75, False),
        ("Tesouro IPCA+ (Tesouro Transparente)", (m.get("juro_real_tesouro") or {}).get("data"), 10, False),
        ("Boletim Focus (Banco Central)", m.get("focus_data"), 14, False),
        ("Informe mensal de FIIs (CVM)", extras.get("fii_informe"), 75, True),
        ("Proventos (B3)", extras.get("proventos"), 10, False),
        ("Bancos (IF.data, Banco Central)", extras.get("ifdata"), 200, False),
        ("Ofertas públicas (CVM)", extras.get("ofertas"), 5, False),
    ]
    itens, problemas = [], []
    for nome, ref, lim, essencial in linhas:
        dias = _dias(ref, hoje)
        if dias is None:
            sit = "sem dado"
        elif dias > lim:
            sit = "atrasada"
        else:
            sit = "em dia"
        itens.append({"fonte": nome, "referencia": str(ref)[:10] if ref else None, "dias": dias,
                      "limite_dias": lim, "situacao": sit, "essencial": essencial})
        if sit != "em dia" and essencial:
            problemas.append(f"{nome}: {sit}" + (f" ({dias} dias)" if dias is not None else ""))
    out = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "itens": itens,
           "descartes": extras.get("descartes", [])[:200], "problemas": problemas,
           "aviso_macro": m.get("aviso")}
    log("Saúde das fontes: " + ("tudo em dia" if not problemas else "; ".join(problemas)))
    return out
