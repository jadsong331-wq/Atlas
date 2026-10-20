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
        "DY = proventos brutos com data-com nos últimos 12 meses (B3, eventos corporativos) ÷ preço. DY recorrente = DY de 12 meses, ou a média de 5 anos quando houve pagamento extraordinário.",
        "P/L lucro médio 5a = valor de mercado ÷ lucro médio dos 5 últimos anos (Graham). PEG = P/L ÷ crescimento anual do lucro (Lynch).",
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

    cur = [a for a in d["ativos"] if a.get("curado", True)]
    outros = [a for a in d["ativos"] if not a.get("curado", True)]
    acoes = [a for a in cur if a["tipo"] == "acao"]
    fiis = [a for a in cur if a["tipo"] == "fii"]
    u = d.get("universo") or {}
    if u.get("mercado_completo"):
        L += ["", f"UNIVERSO: {u.get('curados')} ativos da lista curada (Universo ATLAS) + {u.get('automaticos')} do "
              f"mercado com volume médio diário acima de R$ {_n(u.get('liquidez_minima_acoes'), 0)} (ações) e "
              f"R$ {_n(u.get('liquidez_minima_fiis'), 0)} (FIIs) nos últimos {u.get('pregoes_liquidez')} pregões."]
    L += ["", "---", "", "AÇÕES — UNIVERSO ATLAS (lista curada)", "",
          "| Ticker | Setor | Preço | P/L | P/L lucro médio 5a | PEG | P/VP | EV/EBITDA | DY 12m | DY recorrente | DY médio 5a | Payout | ROE | ROIC | Marg. Líq. | Dív.Líq/EBITDA | CAGR Rec. | CAGR Lucro | Anos c/ prov. | Volatilidade 12m | Maior queda 12m | Valor de mercado | Balanço |",
          "| --- |" + " --- |" * 22]
    for a in acoes:
        i = a.get("ind", {})
        pl = "prejuízo" if i.get("p_l_negativo") else _n(i.get("p_l"))
        banco = a.get("banco")
        L.append("| " + " | ".join([
            a["ticker"], a["setor"], _n(a.get("preco")), pl, _n(i.get("p_l_medio5")), _n(i.get("peg")), _n(i.get("p_vp")),
            "banco" if banco else _n(i.get("ev_ebitda")), _p(i.get("dy")), _p(i.get("dy_recorrente")), _p(i.get("dy_medio5")),
            _p(i.get("payout")),
            _p(i.get("roe")), "banco" if banco else _p(i.get("roic")), _p(i.get("margem_liquida")),
            "banco" if banco else _n(i.get("div_liq_ebitda")), _p(i.get("cagr_receita")),
            _p(i.get("cagr_lucro")),
            f"{i.get('anos_com_dividendo')}/{i.get('anos_avaliados_div') or i.get('anos_avaliados')}" if i.get("anos_com_dividendo") is not None else "n/d",
            _p(i.get("volatilidade")), _p(i.get("queda_12m")),
            _bi(i.get("valor_mercado")), _data(a.get("dt_balanco")),
        ]) + " |")
    L += ["", "FIIs — UNIVERSO ATLAS (lista curada)", "",
          "| Ticker | Segmento | Preço | P/VP | VP da cota | DY 12m (CVM) | Meses c/ rendimento | Patrimônio | Cotistas | Informe |",
          "| --- |" + " --- |" * 9]
    for a in fiis:
        i = a.get("ind", {})
        L.append("| " + " | ".join([
            a["ticker"], a["setor"], _n(a.get("preco")), _n(i.get("p_vp")), _n(i.get("vp_cota")),
            _p(i.get("dy")), str(i.get("meses_com_rendimento") if i.get("meses_com_rendimento") is not None else "n/d"),
            _bi(i.get("patrimonio")), _n(i.get("cotistas"), 0), _data(a.get("data_informe")),
        ]) + " |")
    if outros:
        oa = [a for a in outros if a["tipo"] == "acao"]
        of = [a for a in outros if a["tipo"] == "fii"]
        L += ["", "---", "", "MERCADO COMPLETO — AÇÕES (seleção automática por liquidez; perfis sugeridos por regra)", "",
              "| Ticker | Setor | Preço | P/L | P/VP | DY 12m | Payout | ROE | Dív.Líq/EBITDA | CAGR Lucro | Perfis |",
              "| --- |" + " --- |" * 10]
        for a in sorted(oa, key=lambda a: a["ticker"]):
            i = a.get("ind", {})
            pl = "prejuízo" if i.get("p_l_negativo") else _n(i.get("p_l"))
            L.append("| " + " | ".join([
                a["ticker"], a.get("setor") or "n/d", _n(a.get("preco")), pl, _n(i.get("p_vp")), _p(i.get("dy")),
                _p(i.get("payout")), _p(i.get("roe")), "banco" if a.get("banco") else _n(i.get("div_liq_ebitda")),
                _p(i.get("cagr_lucro")), ", ".join(a.get("perfis") or []) or "-"]) + " |")
        L += ["", "MERCADO COMPLETO — FIIs", "",
              "| Ticker | Tipo | Preço | P/VP | DY 12m (CVM) | Meses c/ rendimento | Patrimônio | Perfis |",
              "| --- |" + " --- |" * 7]
        for a in sorted(of, key=lambda a: a["ticker"]):
            i = a.get("ind", {})
            L.append("| " + " | ".join([
                a["ticker"], a.get("setor") or "n/d", _n(a.get("preco")), _n(i.get("p_vp")), _p(i.get("dy")),
                str(i.get("meses_com_rendimento") if i.get("meses_com_rendimento") is not None else "n/d"),
                _bi(i.get("patrimonio")), ", ".join(a.get("perfis") or []) or "-"]) + " |")
    bancos = [a for a in d.get("ativos", []) if a.get("ifdata")]
    if bancos:
        db = str(d.get("ifdata_data_base") or "")
        L += ["", f"BANCOS — Banco Central, IF.data (conglomerado prudencial, data-base {db[4:6]}/{db[:4]})", "",
              "| Ticker | Instituição no IF.data | Basileia | Capital principal | Inadimplência | Ativos problemáticos | Eficiência | Custo do crédito a.a. |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for a in sorted(bancos, key=lambda x: x["ticker"]):
            i = a.get("ind", {})
            L.append("| " + " | ".join([a["ticker"], a["ifdata"].get("instituicao") or "", _p(i.get("basileia")),
                                        _p(i.get("capital_principal")), _p(i.get("inadimplencia")),
                                        _p(i.get("ativos_problematicos")), _p(i.get("eficiencia")),
                                        _p(i.get("custo_credito"))]) + " |")
        L.append("Eficiência = (pessoal + administrativas) ÷ (intermediação antes da perda esperada + transações de pagamento + tarifas + serviços); menor é melhor.")
    L += ["", "ALERTAS AUTOMÁTICOS — UNIVERSO ATLAS (regras numéricas, não são recomendação)", ""]
    tem = False
    for a in cur:
        if a.get("alertas") or a.get("avisos"):
            tem = True
            L.append(f"- {a['ticker']}: " + "; ".join(a.get("alertas", []) + a.get("avisos", [])) + ".")
    if not tem:
        L.append("- Nenhum.")
    L += ["", "PENDÊNCIAS", ""] + ([f"- {p}" for p in d.get("pendencias", [])] or ["- Nenhuma."])
    L.append("")
    return "\n".join(L)
