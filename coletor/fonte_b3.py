# -*- coding: utf-8 -*-
"""
Cotações oficiais da B3 (arquivo COTAHIST, layout público da bolsa).
- Diário:  COTAHIST_DddmmAAAA.ZIP
- Anual:   COTAHIST_AAAAA.ZIP (usado para montar o histórico e medir a liquidez de
           todo o mercado; baixado só quando o universo é renovado, ~1 vez por semana)
"""

import csv
import io
import os
import zipfile
from collections import defaultdict
from datetime import date, timedelta

from util import baixar, log

URL_DIARIO = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{d:%d%m%Y}.ZIP"
URL_ANUAL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"


def _parse(zbytes, filtro=None, codbdis=None):
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
            if codbdis is not None and bruta[10:12] not in codbdis:
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
                "nome": bruta[27:39].strip(),
                "especi": bruta[39:49].strip(),
            })
    return regs


ULTIMO_ZIP = {"bytes": None}


def opcoes_do_dia():
    """
    Opções de compra (TPMERC 070) e de venda (080) do último arquivo diário baixado.
    Campos oficiais do layout COTAHIST: preço de exercício (PREEXE) e vencimento (DATVEN).
    """
    zb = ULTIMO_ZIP["bytes"]
    if not zb:
        return []
    z = zipfile.ZipFile(io.BytesIO(zb))
    out = []
    with z.open(z.namelist()[0]) as fp:
        for bruta in io.TextIOWrapper(fp, encoding="latin-1"):
            if not bruta.startswith("01") or bruta[24:27] not in ("070", "080"):
                continue
            fatcot = int(bruta[210:217] or 1) or 1
            dv = bruta[202:210]
            out.append({
                "data": f"{bruta[2:6]}-{bruta[6:8]}-{bruta[8:10]}",
                "ticker": bruta[12:24].strip(), "tipo": "call" if bruta[24:27] == "070" else "put",
                "nome": bruta[27:39].strip(), "especi": bruta[39:49].strip(),
                "preco": int(bruta[108:121]) / 100 / fatcot,
                "strike": int(bruta[188:201]) / 100 / fatcot,
                "vencimento": f"{dv[0:4]}-{dv[4:6]}-{dv[6:8]}",
                "volume": int(bruta[170:188]) / 100, "negocios": int(bruta[147:152]),
                "isin": bruta[230:242].strip(),
            })
    return out


def cotacoes_do_dia(hoje=None, max_dias=10):
    """Procura o arquivo diário mais recente (até `max_dias` para trás)."""
    hoje = hoje or date.today()
    for i in range(max_dias):
        d = hoje - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        zb = baixar(URL_DIARIO.format(d=d))
        if zb:
            ULTIMO_ZIP["bytes"] = zb
            regs = _parse(zb)
            if regs:
                log(f"B3: {len(regs)} cotações do pregão de {regs[0]['data']}")
                return {r["ticker"]: r for r in regs}
    log("B3: nenhum arquivo diário encontrado nos últimos dias")
    return {}


def cotacoes_anuais(hoje=None, min_pregoes=63):
    """
    Registros de lote padrão (02) e FIIs (12) do arquivo anual do ano atual; se ele
    ainda tiver poucos pregões (início do ano), inclui também o do ano anterior.
    """
    hoje = hoje or date.today()
    regs = []
    for ano in (hoje.year, hoje.year - 1):
        zb = baixar(URL_ANUAL.format(ano=ano))
        if zb:
            regs.extend(_parse(zb, codbdis={"02", "12", "14"}))
        if len({r["data"] for r in regs}) >= min_pregoes:
            break
    log(f"B3 anual: {len(regs)} registros em {len({r['data'] for r in regs})} pregões")
    return regs


def liquidez_media(regs, cot_dia, pregoes):
    """Volume médio diário (R$) de cada ticker nos últimos `pregoes` pregões (dia sem negócio conta zero)."""
    vol = defaultdict(dict)
    info = {}
    for r in list(regs) + list(cot_dia.values()):
        vol[r["ticker"]][r["data"]] = r["volume"]
        info[r["ticker"]] = r["codbdi"]
    datas = sorted({d for v in vol.values() for d in v})[-pregoes:]
    if not datas:
        return {}, []
    corte = datas[0]
    saida = {}
    for t, vs in vol.items():
        dias = [v for d, v in vs.items() if d >= corte]
        saida[t] = (sum(dias) / len(datas), info[t], len(dias) / len(datas))
    return saida, datas


def _classe_acao(t):
    """Ações ON/PN/units do lote padrão: ABCD3..6 ou ABCD11."""
    ok = t[:4].isalnum() and t[0].isalpha()
    return ok and ((len(t) == 5 and t[4] in "3456") or (len(t) == 6 and t.endswith("11")))


def selecionar_mercado(liq, min_acoes, min_fiis, ja_tem, excluir=(), presenca_min=0.0):
    """
    liq: {ticker: (volume_medio, codbdi, presenca)}
    Devolve (acoes, fiis) com o ticker mais líquido de cada empresa (prefixo de 4 letras).
    Empresas que já estão em `ja_tem` (lista curada) não ganham outra classe.
    """
    prefixos_tem = {t[:4] for t in ja_tem}
    melhor = {}
    fiis = []
    for t, (v, bdi, *pres) in liq.items():
        if t in ja_tem or t in excluir or (pres and pres[0] < presenca_min):
            continue
        if bdi == "12" and len(t) == 6 and t.endswith("11") and v >= min_fiis:
            fiis.append((t, v))
        elif bdi == "02" and _classe_acao(t) and v >= min_acoes and t[:4] not in prefixos_tem:
            if t[:4] not in melhor or v > melhor[t[:4]][1]:
                melhor[t[:4]] = (t, v)
    acoes = sorted(melhor.values(), key=lambda x: -x[1])
    fiis.sort(key=lambda x: -x[1])
    return acoes, fiis


def atualizar_historico(caminho, tickers, cot_dia, hoje=None, anual=None):
    """
    Mantém data/historico_precos.csv (data;ticker;preco).
    Na primeira execução, preenche com os arquivos anuais do ano atual e anterior.
    Se `anual` (registros do arquivo anual) vier preenchido, completa os tickers
    novos e eventuais dias faltantes.
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
    if anual:
        alvo = set(tickers)
        for r in anual:
            if r["ticker"] in alvo:
                linhas.setdefault((r["data"], r["ticker"]), r["preco"])
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
            if d >= limite and t in tickers:
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
