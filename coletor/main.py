# -*- coding: utf-8 -*-
"""
ATLAS INVEST RESEARCH - coletor oficial (sem IA).

Fontes: CVM (DFP, ITR, FCA, informe mensal de FII), B3 (COTAHIST) e Banco Central (SGS, Focus).
Saídas:
  docs/data/dados.json      -> lido pelo app
  docs/data/DADOS_ATLAS.md  -> mesmo conteúdo em texto, para anexar em qualquer IA
  data/fundamentos.json     -> cache dos balanços (renovado a cada N dias)
  data/historico_precos.csv -> preços diários dos últimos ~13 meses
  data/log_ultima_execucao.txt

Uso:  python coletor/main.py            (normal)
      python coletor/main.py --forcar   (rebaixa os balanços mesmo com cache novo)
"""

import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from fonte_b3 import atualizar_historico, cotacoes_do_dia, resumo_52s  # noqa: E402
from fonte_bcb import coletar_macro  # noqa: E402
from fonte_cvm import coletar_fiis, coletar_fundamentos, mapear_cnpjs  # noqa: E402
from gera_md import gerar_markdown  # noqa: E402
from util import LOG, log, so_digitos  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ_CACHE = os.path.join(RAIZ, "data", "fundamentos.json")
ARQ_HIST = os.path.join(RAIZ, "data", "historico_precos.csv")
ARQ_LOG = os.path.join(RAIZ, "data", "log_ultima_execucao.txt")
ARQ_JSON = os.path.join(RAIZ, "docs", "data", "dados.json")
ARQ_MD = os.path.join(RAIZ, "docs", "data", "DADOS_ATLAS.md")

SUFIXOS_PN = ("4", "5", "6", "7", "8")


def _div(a, b, mult=1.0):
    if a is None or b is None or b == 0:
        return None
    return a / b * mult


def irmaos(prefixo, cot):
    """Tickers da mesma companhia negociados no lote padrão (ON e PN)."""
    return {t: r for t, r in cot.items()
            if t[:4] == prefixo and len(t) == 5 and t[4].isdigit() and r["codbdi"] == "02"}


def valor_de_mercado(prefixo, cot, on, pn, avisos):
    ir = irmaos(prefixo, cot)
    p_on = ir.get(prefixo + "3", {}).get("preco")
    pns = [r for t, r in ir.items() if t[4] in SUFIXOS_PN]
    p_pn = max(pns, key=lambda r: r["volume"])["preco"] if pns else None
    if on and p_on is None and p_pn is not None:
        p_on = p_pn
        avisos.append("sem cotação da ação ON; valor de mercado usa o preço da PN")
    if pn and p_pn is None and p_on is not None:
        p_pn = p_on
        avisos.append("sem cotação da ação PN; valor de mercado usa o preço da ON")
    if (on and p_on is None) or (pn and p_pn is None):
        return None
    return (on or 0) * (p_on or 0) + (pn or 0) * (p_pn or 0)


def carregar_cache():
    if not os.path.exists(ARQ_CACHE):
        return None
    with open(ARQ_CACHE, encoding="utf-8") as fp:
        return json.load(fp)


def fundamentos(forcar):
    cache = carregar_cache()
    if cache and not forcar:
        idade = (date.today() - date.fromisoformat(cache["gerado_em"][:10])).days
        if idade < config.DIAS_CACHE_FUNDAMENTOS:
            log(f"Fundamentos: usando cache de {idade} dia(s)")
            return cache
    acoes = [t for t, tipo, *_ in config.UNIVERSO if tipo == "acao"]
    mapa = mapear_cnpjs(acoes)
    for t, cnpj in config.CNPJ_MANUAL.items():
        mapa[t] = so_digitos(cnpj)
    dados = coletar_fundamentos(mapa, config.ANOS_HISTORICO) if mapa else {}
    novo = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
            "ticker_cnpj": mapa, "empresas": dados}
    if not dados and cache:
        log("Fundamentos: coleta falhou, mantendo cache anterior")
        return cache
    os.makedirs(os.path.dirname(ARQ_CACHE), exist_ok=True)
    with open(ARQ_CACHE, "w", encoding="utf-8") as fp:
        json.dump(novo, fp, ensure_ascii=False, indent=1)
    return novo


def alertas_acao(ind, f):
    a = []
    pl = ind.get("p_l")
    if f.get("lucro_ttm") is not None and f["lucro_ttm"] < 0:
        a.append("Prejuízo nos últimos 12 meses")
    if ind.get("payout") is not None and ind["payout"] > 100:
        a.append(f"Dividendos pagos acima do lucro (payout {ind['payout']:.0f}%)")
    if ind.get("roe") is not None and 0 < ind["roe"] < 10:
        a.append(f"ROE baixo ({ind['roe']:.1f}%)")
    d = ind.get("div_liq_ebitda")
    if d is not None and d > 3.5:
        a.append(f"Endividamento elevado (Dív.Líq/EBITDA {d:.1f})")
    if ind.get("cagr_lucro") is not None and ind["cagr_lucro"] < 0:
        a.append(f"Lucro encolheu em {f.get('cagr_anos')} anos")
    if pl is not None and pl > 40:
        a.append("P/L muito alto: lucro deprimido ou preço exigente")
    return a


def montar():
    forcar = "--forcar" in sys.argv
    hoje = date.today()
    log("=== Início da coleta ATLAS ===")

    cot = cotacoes_do_dia()
    tickers_hist = set()
    for t, *_ in config.UNIVERSO:
        tickers_hist.add(t)
        tickers_hist.update(irmaos(t[:4], cot))
    historico = atualizar_historico(ARQ_HIST, tickers_hist, cot)

    fund = fundamentos(forcar)
    fiis_isin = {t: cot.get(t, {}).get("isin") for t, tipo, *_ in config.UNIVERSO if tipo == "fii"}
    fiis = coletar_fiis(fiis_isin) if any(fiis_isin.values()) else {}
    macro = coletar_macro()

    ativos, pendencias = [], []
    for ticker, tipo, setor, perfis in config.UNIVERSO:
        c = cot.get(ticker)
        reg = {"ticker": ticker, "tipo": tipo, "setor": setor, "perfis": perfis,
               "preco": c["preco"] if c else None, "data_preco": c["data"] if c else None,
               "volume_dia": c["volume"] if c else None, "ind": {}, "alertas": [], "avisos": []}
        r52 = resumo_52s(historico, ticker)
        if r52:
            reg["min_52s"], reg["max_52s"] = r52["min"], r52["max"]
            s = r52["serie"]
            reg["serie"] = [[d, round(p, 2)] for d, p in s[::max(1, len(s) // 60)]]
        if not c:
            reg["avisos"].append("sem cotação no último pregão disponível")

        if tipo == "acao":
            cnpj = fund["ticker_cnpj"].get(ticker)
            f = fund["empresas"].get(cnpj) if cnpj else None
            if not f:
                pendencias.append(f"{ticker}: demonstrações da CVM não encontradas")
                ativos.append(reg)
                continue
            reg.update({"empresa": f.get("nome"), "cnpj": cnpj, "banco": f.get("banco"),
                        "dt_balanco": f.get("dt_refer"), "periodo": f.get("periodo_ttm"),
                        "fonte_balanco": f.get("fonte_ultima")})
            mcap = valor_de_mercado(ticker[:4], cot, f.get("acoes_on"), f.get("acoes_pn"), reg["avisos"])
            luc, pl_ = f.get("lucro_ttm"), f.get("patrimonio_liquido")
            ind = {
                "valor_mercado": mcap,
                "lucro_ttm": luc, "receita_ttm": f.get("receita_ttm"), "patrimonio": pl_,
                "p_l": _div(mcap, luc) if luc and luc > 0 else None,
                "p_vp": _div(mcap, pl_) if pl_ and pl_ > 0 else None,
                "roe": _div(luc, pl_, 100) if pl_ and pl_ > 0 else None,
                "margem_liquida": _div(luc, f.get("receita_ttm"), 100),
                "dy": _div(f.get("dividendos_pagos_ttm"), mcap, 100),
                "payout": _div(f.get("dividendos_pagos_ttm"), luc, 100) if luc and luc > 0 else None,
                "cagr_receita": f.get("cagr_receita"), "cagr_lucro": f.get("cagr_lucro"),
                "anos_com_dividendo": f.get("anos_com_dividendo"),
                "anos_com_lucro": f.get("anos_com_lucro"), "anos_avaliados": f.get("anos_avaliados"),
            }
            if luc is not None and luc <= 0:
                ind["p_l_negativo"] = True
            if not f.get("banco"):
                dl, ebit, ebitda = f.get("divida_liquida"), f.get("ebit_ttm"), f.get("ebitda_ttm")
                ev = (mcap + dl) if mcap is not None and dl is not None else None
                base_roic = (pl_ or 0) + (dl or 0)
                ind.update({
                    "divida_liquida": dl, "ebit_ttm": ebit, "ebitda_ttm": ebitda,
                    "ev_ebitda": _div(ev, ebitda) if ebitda and ebitda > 0 else None,
                    "ev_ebit": _div(ev, ebit) if ebit and ebit > 0 else None,
                    "div_liq_ebitda": _div(dl, ebitda) if ebitda and ebitda > 0 else None,
                    "roic": _div(ebit * (1 - config.ALIQUOTA_ROIC), base_roic, 100)
                    if ebit is not None and base_roic > 0 else None,
                })
            reg["ind"] = ind
            reg["alertas"] = alertas_acao(ind, f)
            idade = (hoje - date.fromisoformat(f["dt_refer"])).days
            if idade > 150:
                reg["alertas"].append(f"Último balanço na CVM tem {idade} dias")
        else:
            f = fiis.get(ticker)
            if not f:
                pendencias.append(f"{ticker}: informe mensal do FII não encontrado")
                ativos.append(reg)
                continue
            reg.update({"empresa": f.get("nome"), "cnpj": f.get("cnpj"),
                        "segmento_cvm": f.get("segmento"), "data_informe": f.get("data_informe")})
            reg["ind"] = {
                "p_vp": _div(reg["preco"], f.get("vp_cota")),
                "vp_cota": f.get("vp_cota"), "dy": f.get("dy_12m_cvm"),
                "patrimonio": f.get("patrimonio_liquido"), "cotistas": f.get("cotistas"),
                "meses_com_rendimento": f.get("meses_com_rendimento"),
                "liquidez_dia": reg["volume_dia"], "taxa_adm_mes": f.get("taxa_adm_mes"),
            }
            if f.get("meses_com_rendimento") is not None and f["meses_com_rendimento"] < 12:
                reg["alertas"].append(f"Distribuiu rendimento em {f['meses_com_rendimento']} de 12 meses")
            if reg["ind"]["p_vp"] and reg["ind"]["p_vp"] > 1.2:
                reg["alertas"].append("Negociado bem acima do valor patrimonial")
        ativos.append(reg)

    datas = sorted({a["data_preco"] for a in ativos if a.get("data_preco")})
    saida = {
        "demo": False,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "pregao": datas[-1] if datas else None,
        "fundamentos_em": fund.get("gerado_em"),
        "fontes": {
            "cotacoes": "B3 - COTAHIST (arquivo diário oficial)",
            "acoes": "CVM - Dados Abertos: DFP, ITR e FCA",
            "fiis": "CVM - Informe mensal estruturado de FII",
            "macro": "Banco Central - SGS e Boletim Focus",
        },
        "macro": macro,
        "ativos": ativos,
        "pendencias": pendencias,
    }
    os.makedirs(os.path.dirname(ARQ_JSON), exist_ok=True)
    with open(ARQ_JSON, "w", encoding="utf-8") as fp:
        json.dump(saida, fp, ensure_ascii=False, separators=(",", ":"))
    with open(ARQ_MD, "w", encoding="utf-8") as fp:
        fp.write(gerar_markdown(saida))
    ok = sum(1 for a in ativos if a["ind"])
    log(f"=== Fim: {ok} de {len(ativos)} ativos com indicadores; pendências: {len(pendencias)} ===")
    return saida


if __name__ == "__main__":
    try:
        montar()
        codigo = 0
    except Exception as e:  # noqa: BLE001
        import traceback
        log("ERRO GERAL: " + repr(e))
        log(traceback.format_exc())
        codigo = 1
    os.makedirs(os.path.dirname(ARQ_LOG), exist_ok=True)
    with open(ARQ_LOG, "w", encoding="utf-8") as fp:
        fp.write("\n".join(LOG) + "\n")
    sys.exit(codigo)
