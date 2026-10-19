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
- Só entram critérios com histórico: P/L, P/L sobre lucro médio, DY, payout, anos com lucro e crescimento.
  ROE, dívida, governança, risco e macro não têm histórico guardado e ficam de fora.
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


def score_historico(hist, ano_ref, mcap, regua):
    """Score simplificado com os balanços até o ano anterior a `ano_ref`."""
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
    ind["anos_com_lucro"] = sum(1 for a in anos[-5:] if (hist[a].get("lucro") or 0) > 0)
    ind["cagr_lucro"] = _cagr({a: hist[a].get("lucro") for a in anos}, anos)
    ind["cagr_receita"] = _cagr({a: hist[a].get("receita") for a in anos}, anos)
    pesos = {d["id"]: d["peso"] for d in regua["acoes"]}
    por_dim = {}
    for k in ("p_l", "p_l_medio5", "dy_recorrente", "payout", "anos_com_lucro", "cagr_lucro", "cagr_receita"):
        dim, fx = _faixas(regua, k)
        if not dim:
            continue
        if k == "p_l" and ind.get("_prejuizo"):
            n = 0
        elif ind.get(k) is None:
            continue
        else:
            n = _nota(fx, ind[k])
        if n is not None:
            por_dim.setdefault(dim, []).append(n)
    soma = sum(sum(v) / len(v) * pesos[d] for d, v in por_dim.items())
    peso = sum(pesos[d] for d in por_dim)
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
        notas = []
        for a in ativos:
            if a["tipo"] != "acao" or not a.get("cnpj") or (a.get("liquidez_media") or 0) < liquidez_min:
                continue
            t = a["ticker"]
            serie_p, serie_r = pm.get(t), rt.get(t) or pm.get(t)
            if not serie_p or serie_p[i0] is None or not serie_r or serie_r[i0] is None or serie_r[i1] is None:
                continue
            hist = (empresas.get(a["cnpj"]) or {}).get("historico_anual") or {}
            mcap = serie_p[i0] * (a.get("acoes_circulacao") or 0)
            sc = score_historico(hist, ano, mcap, regua)
            if sc is None:
                continue
            notas.append((sc, t, serie_r[i1] / serie_r[i0] - 1))
        if len(notas) < n_top * 2:
            continue
        notas.sort(reverse=True)
        top = notas[:n_top]
        fundo = notas[-n_top:]

        def ret_ref(k):
            v = (ref.get(k) or {}).get("m")
            return v[i1] / v[i0] - 1 if v and v[i0] and v[i1] else None

        out.append({
            "inicio": meses[i0], "fim": meses[i1], "avaliadas": len(notas),
            "carteira": [[t, round(s, 1), round(r * 100, 1)] for s, t, r in top],
            "ret_top": round(sum(r for _, _, r in top) / len(top) * 100, 2),
            "ret_piores": round(sum(r for _, _, r in fundo) / len(fundo) * 100, 2),
            "ret_todas": round(sum(r for _, _, r in notas) / len(notas) * 100, 2),
            "ret_ibov": round(ret_ref("IBOV") * 100, 2) if ret_ref("IBOV") is not None else None,
            "ret_cdi": round(ret_ref("CDI") * 100, 2) if ret_ref("CDI") is not None else None,
        })

    def acum(k):
        if not out:
            return None
        v = 1.0
        for p in out:
            if p[k] is None:
                return None
            v *= 1 + p[k] / 100
        return round((v - 1) * 100, 2)

    return {"periodos": out, "acumulado": {k: acum(k) for k in ("ret_top", "ret_piores", "ret_todas", "ret_ibov", "ret_cdi")},
            "n_top": n_top, "mes": mes}
