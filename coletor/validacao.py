# -*- coding: utf-8 -*-
"""
Validação da régua com dados passados (backtest indicativo).

Em cada fim de abril (os balanços anuais do ano anterior já foram publicados até março),
calcula um Score ATLAS simplificado só com o que se sabia naquela data e monta uma carteira
com as 10 maiores notas, pesos iguais, mantida por 12 meses. Compara o retorno total
(preço + proventos) com o Ibovespa, o CDI e a média de todas as ações avaliadas.

Limitações (mostradas no app):
- Usa as ações que existem e são líquidas hoje (viés de sobrevivência: quem quebrou ficou de fora).
- O número de ações é o de hoje (recompras e emissões no meio do caminho são ignoradas).
- Só entram critérios com histórico: P/L, P/L sobre lucro médio, P/VP, ROE, DY, payout, anos com lucro e crescimento.
  Dívida, governança, risco e macro não têm histórico guardado e ficam de fora.
"""


def _nota(faixas, v):
    for de, ate, n in faixas:
        if (de is None or v >= de) and (ate is None or v < ate):
            return n
    return None


def _cagr(hist, anos):
    ok = [(a, hist[a]) for a in anos if hist.get(a) is not None and hist[a] > 0]
    if len(ok) < 3:
        return None
    (a0, v0), (a1, v1) = ok[0], ok[-1]
    n = int(a1) - int(a0)
    return ((v1 / v0) ** (1 / n) - 1) * 100 if n > 0 else None


def _faixas(regua, ind):
    for d in regua["acoes"]:
        for c in d.get("criterios", []):
            if c["ind"] == ind:
                return d["id"], c["faixas"]
    return None, None


# opções de cada variante: "pesos" (por dimensão), "setor" (nota relativa ao setor misturada à absoluta),
# "ciclo" (commodities: lucro médio de 10 anos e nota do P/L atual limitada a 5)
VARIANTES = [
    ("regua", "Régua ATLAS atual (critérios com histórico)", None),
    ("regua_anterior", "Régua anterior (pesos iguais, sem nota relativa ao setor)", {"qualidade": 20, "crescimento": 20, "dividendos": 20, "valuation": 20}),
    ("qualidade", "Qualidade e crescimento (Buffett, Lynch)", {"qualidade": 1, "crescimento": 1}),
    ("qualidade_preco", "Qualidade com preço justo (Buffett, Graham)", {"qualidade": 2, "crescimento": 1, "valuation": 1}),
    ("valor", "Só preço baixo (Graham puro)", {"valuation": 1}),
    ("dividendos", "Só dividendos (Barsi puro)", {"dividendos": 1}),
]


REL_MAIOR = ("roe", "dy_recorrente", "cagr_lucro", "cagr_receita")   # maior é melhor
REL_MENOR = ("p_l", "p_vp")                                          # menor é melhor


def indicadores_historicos(hist, ano_ref, mcap, ciclo=False):
    """Indicadores que se sabiam em `ano_ref` (balanços até o ano anterior)."""
    todos = sorted(a for a in hist if int(a) < ano_ref)
    anos = todos[-6:]
    if len(anos) < 3 or not mcap:
        return None
    ult = hist[anos[-1]]
    luc, div = ult.get("lucro"), ult.get("dividendos_pagos")
    ind = {}
    if luc is not None:
        ind["p_l"] = mcap / luc if luc > 0 else None
        ind["_prejuizo"] = luc <= 0
    janela = todos[-10:] if ciclo else anos[-5:]
    lucros = [hist[a].get("lucro") for a in janela if hist[a].get("lucro") is not None]
    if len(lucros) >= 3 and sum(lucros) > 0:
        ind["p_l_medio5"] = mcap / (sum(lucros) / len(lucros))
    if div is not None:
        ind["dy_recorrente"] = div / mcap * 100
        if luc and luc > 0:
            ind["payout"] = div / luc * 100
    pl = ult.get("patrimonio")
    if pl and pl > 0:
        ind["p_vp"] = mcap / pl
        if luc is not None:
            ind["roe"] = luc / pl * 100
    ind["anos_com_lucro"] = sum(1 for a in anos[-5:] if (hist[a].get("lucro") or 0) > 0)
    ind["cagr_lucro"] = _cagr({a: hist[a].get("lucro") for a in anos}, anos)
    ind["cagr_receita"] = _cagr({a: hist[a].get("receita") for a in anos}, anos)
    return ind


def percentis_setor(itens):
    """itens: [(setor, ind)]. Devolve [{ind: percentil 0-1 dentro do setor}] (setores com 5 ou mais)."""
    from collections import defaultdict
    grupos = defaultdict(list)
    for k, (setor, ind) in enumerate(itens):
        if ind:
            grupos[setor].append(k)
    out = [dict() for _ in itens]
    for setor, ks in grupos.items():
        if len(ks) < 5:
            continue
        for nome in REL_MAIOR + REL_MENOR:
            vals = sorted((itens[k][1].get(nome), k) for k in ks if itens[k][1].get(nome) is not None)
            if len(vals) < 5:
                continue
            for pos, (_, k) in enumerate(vals):
                out[k][nome] = pos / (len(vals) - 1)
    return out


def score_historico(hist, ano_ref, mcap, regua, pesos_var=None, ind=None, rel=None, setor=None):
    """Score simplificado com os balanços até o ano anterior a `ano_ref`."""
    opc = pesos_var or {"_setor": bool(regua.get("setor_relativo"))}
    ciclo = bool(opc.get("_ciclo")) and setor == "Commodities"
    if ind is None:
        ind = indicadores_historicos(hist, ano_ref, mcap, ciclo)
    if ind is None:
        return None
    return _score(ind, regua, {k: v for k, v in opc.items() if not k.startswith("_")} or None,
                  rel if opc.get("_setor") else None, ciclo)


def _score_antigo(hist, ano_ref, mcap, regua, pesos_var=None):
    anos = sorted(a for a in hist if int(a) < ano_ref)[-6:]
    if len(anos) < 3 or not mcap:
        return None
    ult = hist[anos[-1]]
    luc, div = ult.get("lucro"), ult.get("dividendos_pagos")
    ind = {}
    if luc is not None:
        ind["p_l"] = mcap / luc if luc > 0 else None
        ind["_prejuizo"] = luc <= 0
    lucros = [hist[a].get("lucro") for a in anos[-5:] if hist[a].get("lucro") is not None]
    if len(lucros) >= 3 and sum(lucros) > 0:
        ind["p_l_medio5"] = mcap / (sum(lucros) / len(lucros))
    if div is not None:
        ind["dy_recorrente"] = div / mcap * 100
        if luc and luc > 0:
            ind["payout"] = div / luc * 100
    pl = ult.get("patrimonio")
    if pl and pl > 0:
        ind["p_vp"] = mcap / pl
        if luc is not None:
            ind["roe"] = luc / pl * 100
    ind["anos_com_lucro"] = sum(1 for a in anos[-5:] if (hist[a].get("lucro") or 0) > 0)
    ind["cagr_lucro"] = _cagr({a: hist[a].get("lucro") for a in anos}, anos)
    ind["cagr_receita"] = _cagr({a: hist[a].get("receita") for a in anos}, anos)
    pesos = pesos_var or {d["id"]: d["peso"] for d in regua["acoes"]}
    por_dim = {}
    for k in ("p_l", "p_l_medio5", "dy_recorrente", "payout", "anos_com_lucro", "cagr_lucro", "cagr_receita", "roe", "p_vp"):
        dim, fx = _faixas(regua, k)
        if not dim:
            continue
        if k == "p_l" and ind.get("_prejuizo"):
            n = 0
        elif ind.get(k) is None:
            continue
        else:
            n = _nota(fx, ind[k])
        if n is not None and k == "p_vp" and (ind.get("_prejuizo") or (ind.get("roe") or 0) < 5):
            n = min(n, 3)  # armadilha de valor: barato sem lucro não ganha nota alta
        if n is not None:
            por_dim.setdefault(dim, []).append(n)
    soma = sum(sum(v) / len(v) * pesos.get(d, 0) for d, v in por_dim.items())
    peso = sum(pesos.get(d, 0) for d in por_dim)
    return soma / peso * 10 if peso else None


def _score(ind, regua, pesos_var, rel, ciclo):
    pesos = pesos_var or {d["id"]: d["peso"] for d in regua["acoes"]}
    por_dim = {}
    for k in ("p_l", "p_l_medio5", "dy_recorrente", "payout", "anos_com_lucro", "cagr_lucro", "cagr_receita", "roe", "p_vp"):
        dim, fx = _faixas(regua, k)
        if not dim:
            continue
        if k == "p_l" and ind.get("_prejuizo"):
            n = 0
        elif ind.get(k) is None:
            continue
        else:
            n = _nota(fx, ind[k])
        if n is not None and rel is not None and k in rel:
            nr = 10 * rel[k] if k in REL_MAIOR else 10 * (1 - rel[k])
            n = (n + nr) / 2  # metade absoluta, metade posição no setor
        if n is not None and k == "p_vp" and (ind.get("_prejuizo") or (ind.get("roe") or 0) < 5):
            n = min(n, 3)  # armadilha de valor: barato sem lucro não ganha nota alta
        if n is not None and ciclo and k == "p_l":
            n = min(n, 5)  # cíclica: P/L do ano não vale nota máxima (Graham usava o lucro médio)
        if n is not None:
            por_dim.setdefault(dim, []).append(n)
    soma = sum(sum(v) / len(v) * pesos.get(d, 0) for d, v in por_dim.items())
    peso = sum(pesos.get(d, 0) for d in por_dim)
    return soma / peso * 10 if peso else None


def backtest(ativos, empresas, h, regua, n_top=10, mes="04", liquidez_min=1_000_000):
    meses = h.get("meses") or []
    rt = h.get("retorno_m") or {}
    pm = h.get("precos_m") or {}
    ref = h.get("referencias") or {}
    anos_teste = sorted({int(m[:4]) for m in meses if m.endswith("-" + mes)})
    out = []
    for ano in anos_teste:
        i0 = meses.index(f"{ano}-{mes}")
        i1 = i0 + 12
        if i1 >= len(meses):
            continue
        base = []
        for a in ativos:
            if a["tipo"] != "acao" or not a.get("cnpj") or (a.get("liquidez_media") or 0) < liquidez_min:
                continue
            t = a["ticker"]
            serie_p, serie_r = pm.get(t), rt.get(t) or pm.get(t)
            if not serie_p or serie_p[i0] is None or not serie_r or serie_r[i0] is None or serie_r[i1] is None:
                continue
            hist = (empresas.get(a["cnpj"]) or {}).get("historico_anual") or {}
            mcap = serie_p[i0] * (a.get("acoes_circulacao") or 0)
            base.append((t, hist, mcap, serie_r[i1] / serie_r[i0] - 1, a.get("setor")))
        if len(base) < n_top * 2:
            continue

        def ret_ref(k):
            v = (ref.get(k) or {}).get("m")
            return v[i1] / v[i0] - 1 if v and v[i0] and v[i1] else None

        per = {"inicio": meses[i0], "fim": meses[i1],
               "ret_ibov": round(ret_ref("IBOV") * 100, 2) if ret_ref("IBOV") is not None else None,
               "ret_cdi": round(ret_ref("CDI") * 100, 2) if ret_ref("CDI") is not None else None,
               "variantes": {}}
        for vid, _, pesos in VARIANTES:
            opc = pesos or {"_setor": bool(regua.get("setor_relativo"))}
            inds = [indicadores_historicos(hist, ano, mcap, bool(opc.get("_ciclo")) and setor == "Commodities")
                    for _, hist, mcap, _, setor in base]
            rels = percentis_setor([(b[4], i) for b, i in zip(base, inds)]) if opc.get("_setor") else [None] * len(base)
            notas = []
            for (t, hist, mcap, r, setor), ind, rel in zip(base, inds, rels):
                sc = score_historico(hist, ano, mcap, regua, pesos, ind=ind, rel=rel, setor=setor) if ind else None
                if sc is not None:
                    notas.append((sc, t, r))
            if len(notas) < n_top * 2:
                continue
            notas.sort(reverse=True)
            top, fundo = notas[:n_top], notas[-n_top:]
            per["variantes"][vid] = {"ret_top": round(sum(r for *_, r in top) / n_top * 100, 2),
                                     "ret_piores": round(sum(r for *_, r in fundo) / n_top * 100, 2),
                                     "carteira": [[t, round(s, 1), round(r * 100, 1)] for s, t, r in top]}
            if vid == "regua":
                per.update(avaliadas=len(notas), carteira=per["variantes"][vid]["carteira"],
                           ret_top=per["variantes"][vid]["ret_top"], ret_piores=per["variantes"][vid]["ret_piores"],
                           ret_todas=round(sum(r for *_, r in notas) / len(notas) * 100, 2))
        if "regua" in per["variantes"]:
            out.append(per)

    def acum(vals):
        vals = list(vals)
        if not vals or any(v is None for v in vals):
            return None
        x = 1.0
        for v in vals:
            x *= 1 + v / 100
        return round((x - 1) * 100, 2)

    def anual(total):
        return round(((1 + total / 100) ** (1 / len(out)) - 1) * 100, 2) if total is not None and out else None

    acumulado = {k: acum(p.get(k) for p in out) for k in ("ret_top", "ret_piores", "ret_todas", "ret_ibov", "ret_cdi")}
    variantes = []
    for vid, nome, _ in VARIANTES:
        tot = acum((p["variantes"].get(vid) or {}).get("ret_top") for p in out)
        venceu = sum(1 for p in out if p["variantes"].get(vid) and p.get("ret_ibov") is not None
                     and p["variantes"][vid]["ret_top"] > p["ret_ibov"])
        variantes.append({"id": vid, "nome": nome, "acumulado": tot, "ao_ano": anual(tot), "venceu_ibov": venceu})
    return {"periodos": out, "acumulado": acumulado, "ao_ano": {k: anual(v) for k, v in acumulado.items()},
            "variantes": variantes, "n_top": n_top, "mes": mes}
