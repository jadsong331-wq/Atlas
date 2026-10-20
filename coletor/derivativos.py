# -*- coding: utf-8 -*-
"""
Opções sobre ações e ETFs negociadas na B3 (arquivo oficial COTAHIST do último pregão).

Para cada opção com negócio no dia: tipo (compra/venda), preço de exercício, vencimento,
último preço (prêmio), volume. Calcula, com fórmulas padrão de mercado:
- valor intrínseco e extrínseco;
- para opções de compra: quanto o prêmio representa do preço da ação (renda da venda coberta);
- para opções de venda: o preço efetivo de compra se a opção for exercida (exercício - prêmio);
- volatilidade implícita pelo modelo de Black-Scholes, usando a Selic como juro (estimativa;
  as opções de compra de ações na B3 são americanas, então o número é aproximado).
Nada aqui é recomendação: derivativos podem gerar perdas maiores que o valor aplicado.
"""

import math
from collections import defaultdict
from datetime import date

from util import log

SUFIXOS_PN = ("4", "5", "6")
RAIZES_INDICE = ("IBOV", "IBXX", "SMLL", "IDIV")  # opções sobre índice: preço em pontos, não em reais


def _dias_uteis(d0, d1):
    """Dias de segunda a sexta entre d0 (exclusivo) e d1 (inclusivo). Feriados não são descontados."""
    if d1 <= d0:
        return 0
    n, d = 0, d0.toordinal() + 1
    while d <= d1.toordinal():
        if date.fromordinal(d).weekday() < 5:
            n += 1
        d += 1
    return n


def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def black_scholes(tipo, S, K, T, r, vol):
    if T <= 0 or vol <= 0 or S <= 0 or K <= 0:
        return max(0.0, (S - K) if tipo == "call" else (K - S))
    d1 = (math.log(S / K) + (r + vol * vol / 2) * T) / (vol * math.sqrt(T))
    d2 = d1 - vol * math.sqrt(T)
    if tipo == "call":
        return S * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2)
    return K * math.exp(-r * T) * _ncdf(-d2) - S * _ncdf(-d1)


def vol_implicita(tipo, premio, S, K, T, r):
    """Volatilidade que faz o Black-Scholes bater o prêmio (bisseção). None se não houver solução."""
    if T <= 0 or premio <= 0:
        return None
    lo, hi = 0.01, 4.0
    if not (black_scholes(tipo, S, K, T, r, lo) <= premio <= black_scholes(tipo, S, K, T, r, hi)):
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if black_scholes(tipo, S, K, T, r, mid) < premio:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _subjacente(op, cot):
    """Ativo-objeto pela raiz do código (4 letras) e pela especificação (ON, PN, unit/ETF)."""
    raiz, esp = op["ticker"][:4], (op["especi"] or "").upper()
    if raiz in RAIZES_INDICE:
        return None
    cands = {t: r for t, r in cot.items() if t[:4] == raiz and r.get("codbdi") in ("02", "14", "12")}
    if not cands:
        return None
    if esp.startswith("ON") and raiz + "3" in cands:
        return raiz + "3"
    if esp.startswith("PN"):
        pns = [t for t in cands if len(t) == 5 and t[4] in SUFIXOS_PN]
        if pns:
            return max(pns, key=lambda t: cands[t]["volume"])
    if (esp.startswith("CI") or esp.startswith("UNT")) and raiz + "11" in cands:
        return raiz + "11"
    return max(cands, key=lambda t: cands[t]["volume"])


def montar(opcoes, cot, selic, hoje=None, max_ativos=25, min_negocios=1):
    hoje = hoje or date.today()
    r = math.log(1 + (selic or 0) / 100)
    por_ativo = defaultdict(list)
    sem = 0
    for op in opcoes:
        if op["negocios"] < min_negocios or op["preco"] <= 0 or op["strike"] <= 0:
            continue
        try:
            venc = date.fromisoformat(op["vencimento"])
        except ValueError:
            continue
        if venc < hoje:
            continue
        sub = _subjacente(op, cot)
        if not sub:
            sem += 1
            continue
        S = cot[sub]["preco"]
        du = _dias_uteis(hoje, venc)
        if du < 1 or not (0.3 <= op["strike"] / S <= 3):
            continue  # vence hoje, ou exercício incompatível com o preço (ativo-objeto errado)
        T = du / 252
        K, p = op["strike"], op["preco"]
        intr = max(0.0, S - K) if op["tipo"] == "call" else max(0.0, K - S)
        reg = {"t": op["ticker"], "tipo": op["tipo"], "k": round(K, 2), "v": op["vencimento"], "du": du,
               "p": round(p, 2), "vol": round(op["volume"]), "neg": op["negocios"],
               "intr": round(intr, 2), "extr": round(max(0.0, p - intr), 2),
               "dist": round((K / S - 1) * 100, 2)}
        iv = vol_implicita(op["tipo"], p, S, K, T, r) if du >= 1 else None
        if iv is not None:
            reg["iv"] = round(iv * 100, 1)
        if op["tipo"] == "call":
            reg["renda"] = round(p / S * 100, 2)               # prêmio ÷ preço da ação
        else:
            reg["compra_efetiva"] = round(K - p, 2)            # se exercida, compra a K pagando o prêmio antes
            reg["desconto"] = round(((K - p) / S - 1) * 100, 2)
        por_ativo[sub].append(reg)
    ativos = []
    for sub, ops in por_ativo.items():
        vol_tot = sum(o["vol"] for o in ops)
        ativos.append({"ativo": sub, "preco": cot[sub]["preco"], "volume_opcoes": vol_tot,
                       "vencimentos": sorted({o["v"] for o in ops}),
                       "opcoes": sorted(ops, key=lambda o: (o["v"], o["tipo"], o["k"]))})
    ativos.sort(key=lambda a: -a["volume_opcoes"])
    ativos = ativos[:max_ativos]
    log(f"Derivativos: {sum(len(a['opcoes']) for a in ativos)} opções com negócio em {len(ativos)} ativos"
        + (f"; {sem} sem ativo-objeto identificado" if sem else ""))
    return {"pregao": opcoes[0]["data"] if opcoes else None, "selic": selic, "ativos": ativos,
            "fonte": "B3 - COTAHIST (mercado de opções, último pregão)"}
