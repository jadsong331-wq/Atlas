# -*- coding: utf-8 -*-
"""Gera o DADOS_ATLAS.md (texto) a partir do dados.json, para usar em qualquer IA."""


def _n(v, casas=2, suf=""):
    if v is None:
        return "n/d"
    s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + suf


def _p(v):
    return _n(v, 2, "%")


def _bi(v):
    return "n/d" if v is None else "R$ " + _n(v / 1e9, 1) + " bi"


def _data(iso):
    if not iso:
        return "n/d"
    iso = str(iso)[:10]
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if len(iso) == 10 and iso[4] == "-" else iso


def gerar_markdown(d):
    m = d.get("macro", {})
    s = m.get("series", {})
    f = m.get("focus", {})
    L = [
        "DADOS ATLAS — BASE QUANTITATIVA (FONTES OFICIAIS)",
        "",
        f"GERADO EM: {_data(d.get('gerado_em'))} | PREGÃO: {_data(d.get('pregao'))} | BALANÇOS COLETADOS EM: {_data(d.get('fundamentos_em'))}",
        "Gerado automaticamente pelo coletor ATLAS, sem IA e sem estimativas. \"n/d\" = não disponível na fonte.",
        "",
        "FONTES: B3 (COTAHIST), CVM Dados Abertos (DFP, ITR, FCA, informe mensal de FII), Banco Central (SGS, Focus).",
        "Indicadores de ações calculados a partir dos balanços oficiais: últimos 12 meses (TTM) e balanço mais recente.",
        "DY de ações = dividendos e JCP efetivamente pagos no fluxo de caixa (12 meses) ÷ valor de mercado.",
        "DY de FIIs = soma dos 12 últimos DY mensais informados à CVM.",
        "",
        "---",
        "",
        "MACRO",
        "",
    ]
    for k in ("selic", "ipca_12m", "ipca_mes", "dolar"):
        x = s.get(k, {})
        L.append(f"- {x.get('nome', k)}: {_n(x.get('valor'), 4 if k == 'dolar' else 2)} ({x.get('data') or 'n/d'})")
    if m.get("selic_tendencia"):
        L.append(f"- Tendência recente da Selic: {m['selic_tendencia']}")
    if m.get("juro_real") is not None:
        L.append(f"- Juro real aproximado (Selic vs IPCA 12m): {_p(m['juro_real'])}")
    anos = sorted({a for v in f.values() for a in v})
    if anos:
        L += ["", f"Boletim Focus de {_data(m.get('focus_data'))} (medianas):",
              "| Indicador | " + " | ".join(anos) + " |", "| --- |" + " --- |" * len(anos)]
        for nome, k in (("IPCA", "ipca"), ("Selic fim de ano", "selic"), ("PIB", "pib"), ("Câmbio", "cambio")):
            vals = [(_n(f.get(k, {}).get(a)) if k == "cambio" else _p(f.get(k, {}).get(a))) for a in anos]
            L.append(f"| {nome} | " + " | ".join(vals) + " |")

    acoes = [a for a in d["ativos"] if a["tipo"] == "acao"]
    fiis = [a for a in d["ativos"] if a["tipo"] == "fii"]
    L += ["", "---", "", "AÇÕES", "",
          "| Ticker | Setor | Preço | P/L | P/VP | EV/EBITDA | DY 12m | Payout | ROE | ROIC | Marg. Líq. | Dív.Líq/EBITDA | CAGR Rec. | CAGR Lucro | Anos c/ div. | Valor de mercado | Balanço |",
          "| --- |" + " --- |" * 16]
    for a in acoes:
        i = a.get("ind", {})
        pl = "prejuízo" if i.get("p_l_negativo") else _n(i.get("p_l"))
        banco = a.get("banco")
        L.append("| " + " | ".join([
            a["ticker"], a["setor"], _n(a.get("preco")), pl, _n(i.get("p_vp")),
            "banco" if banco else _n(i.get("ev_ebitda")), _p(i.get("dy")), _p(i.get("payout")),
            _p(i.get("roe")), "banco" if banco else _p(i.get("roic")), _p(i.get("margem_liquida")),
            "banco" if banco else _n(i.get("div_liq_ebitda")), _p(i.get("cagr_receita")),
            _p(i.get("cagr_lucro")),
            f"{i.get('anos_com_dividendo')}/{i.get('anos_avaliados')}" if i.get("anos_avaliados") else "n/d",
            _bi(i.get("valor_mercado")), _data(a.get("dt_balanco")),
        ]) + " |")
    L += ["", "FIIs", "",
          "| Ticker | Segmento | Preço | P/VP | VP da cota | DY 12m (CVM) | Meses c/ rendimento | Patrimônio | Cotistas | Informe |",
          "| --- |" + " --- |" * 9]
    for a in fiis:
        i = a.get("ind", {})
        L.append("| " + " | ".join([
            a["ticker"], a["setor"], _n(a.get("preco")), _n(i.get("p_vp")), _n(i.get("vp_cota")),
            _p(i.get("dy")), str(i.get("meses_com_rendimento") if i.get("meses_com_rendimento") is not None else "n/d"),
            _bi(i.get("patrimonio")), _n(i.get("cotistas"), 0), _data(a.get("data_informe")),
        ]) + " |")
    L += ["", "ALERTAS AUTOMÁTICOS (regras numéricas, não são recomendação)", ""]
    tem = False
    for a in d["ativos"]:
        if a.get("alertas") or a.get("avisos"):
            tem = True
            L.append(f"- {a['ticker']}: " + "; ".join(a.get("alertas", []) + a.get("avisos", [])) + ".")
    if not tem:
        L.append("- Nenhum.")
    L += ["", "PENDÊNCIAS", ""] + ([f"- {p}" for p in d.get("pendencias", [])] or ["- Nenhuma."])
    L.append("")
    return "\n".join(L)
