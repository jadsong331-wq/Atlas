# -*- coding: utf-8 -*-
"""
Cotações oficiais da B3 (arquivo COTAHIST, layout público da bolsa).
- Diário:  COTAHIST_DddmmAAAA.ZIP
- Anual:   COTAHIST_AAAAA.ZIP (usado só para montar o histórico na primeira vez)
"""

import csv
import io
import os
import zipfile
from datetime import date, timedelta

from util import baixar, log

URL_DIARIO = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{d:%d%m%Y}.ZIP"
URL_ANUAL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"


def _parse(zbytes, filtro=None):
    """Lê o COTAHIST e devolve lista de registros do mercado à vista."""
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    nome = z.namelist()[0]
    regs = []
    with z.open(nome) as fp:
        for bruta in io.TextIOWrapper(fp, encoding="latin-1"):
            if not bruta.startswith("01"):
                continue
            if bruta[24:27] != "010":          # TPMERC 010 = mercado à vista
                continue
            ticker = bruta[12:24].strip()
            if filtro is not None and ticker not in filtro:
                continue
            fatcot = int(bruta[210:217] or 1) or 1
            regs.append({
                "data": f"{bruta[2:6]}-{bruta[6:8]}-{bruta[8:10]}",
                "ticker": ticker,
                "codbdi": bruta[10:12],
                "preco": int(bruta[108:121]) / 100 / fatcot,
                "volume": int(bruta[170:188]) / 100,
                "negocios": int(bruta[147:152]),
                "isin": bruta[230:242].strip(),
            })
    return regs


def cotacoes_do_dia(hoje=None, max_dias=10):
    """Procura o arquivo diário mais recente (até `max_dias` para trás)."""
    hoje = hoje or date.today()
    for i in range(max_dias):
        d = hoje - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        zb = baixar(URL_DIARIO.format(d=d))
        if zb:
            regs = _parse(zb)
            if regs:
                log(f"B3: {len(regs)} cotações do pregão de {regs[0]['data']}")
                return {r["ticker"]: r for r in regs}
    log("B3: nenhum arquivo diário encontrado nos últimos dias")
    return {}


def atualizar_historico(caminho, tickers, cot_dia, hoje=None):
    """
    Mantém data/historico_precos.csv (data;ticker;preco).
    Na primeira execução, preenche com os arquivos anuais do ano atual e anterior.
    """
    hoje = hoje or date.today()
    linhas = {}
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as fp:
            for r in csv.DictReader(fp, delimiter=";"):
                linhas[(r["data"], r["ticker"])] = float(r["preco"])
    else:
        for ano in (hoje.year - 1, hoje.year):
            zb = baixar(URL_ANUAL.format(ano=ano))
            if zb:
                for r in _parse(zb, set(tickers)):
                    linhas[(r["data"], r["ticker"])] = r["preco"]
    for t in tickers:
        r = cot_dia.get(t)
        if r:
            linhas[(r["data"], t)] = r["preco"]
    # guarda só os últimos ~400 dias
    limite = (hoje - timedelta(days=400)).isoformat()
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as fp:
        w = csv.writer(fp, delimiter=";")
        w.writerow(["data", "ticker", "preco"])
        for (d, t), p in sorted(linhas.items()):
            if d >= limite:
                w.writerow([d, t, f"{p:.2f}"])
    return linhas


def resumo_52s(historico, ticker, hoje=None):
    """Mínima, máxima e série dos últimos 12 meses de um ticker."""
    hoje = hoje or date.today()
    ini = (hoje - timedelta(days=365)).isoformat()
    serie = sorted((d, p) for (d, t), p in historico.items() if t == ticker and d >= ini)
    if not serie:
        return None
    precos = [p for _, p in serie]
    return {"min": min(precos), "max": max(precos), "serie": serie}
