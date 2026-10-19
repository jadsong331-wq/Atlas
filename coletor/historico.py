# -*- coding: utf-8 -*-
"""
Histórico comparativo (sem IA, só fontes oficiais).

- Preços: B3 COTAHIST. Anos fechados são lidos uma única vez do arquivo anual e
  guardados em data/historico_anos.json (fechamento de cada mês + eventos de
  desdobramento/grupamento detectados). O ano corrente vem do histórico diário.
- Desdobramentos e grupamentos: o COTAHIST não ajusta preços. Um salto de um dia
  para o outro que bate com uma proporção redonda (1:2, 1:10, 10:1...) é tratado
  como evento societário e os preços anteriores são ajustados. Todos os eventos
  ficam listados na saída para conferência. Bonificações pequenas e dividendos
  não são ajustados: a comparação é de variação do PREÇO.
- Referências: Ibovespa (ETF BOVA11), IFIX (ETF XFIX11), CDI (BCB SGS 4391 mensal
  e 12 diário) e IPCA (BCB SGS 433).
"""

import json
import os
from collections import defaultdict
from datetime import date, timedelta

from fonte_b3 import URL_ANUAL, _parse
from fonte_bcb import sgs_periodo
from util import baixar, log

REFERENCIAS_B3 = {"BOVA11": ("IBOV", "Ibovespa (ETF BOVA11)"), "XFIX11": ("IFIX", "IFIX (ETF XFIX11)")}
ANOS = 5


# ---------------------------------------------------------------------------
# Desdobramentos e grupamentos
# ---------------------------------------------------------------------------

def _proporcao_redonda(r):
    """Proporção exata (k ou 1/k) se r (preço depois / antes) parece desdobramento ou grupamento; senão None."""
    if not r or 0.55 < r < 1.8:
        return None
    x = 1 / r if r < 1 else r
    k = round(x)
    if 2 <= k <= 200 and abs(x - k) / k <= 0.04:
        return 1 / k if r < 1 else float(k)
    return None


def detectar_eventos(serie):
    """
    serie: [(data, preço)] em ordem. Devolve [(data_do_evento, proporção exata)].
    Exige que o preço esteja calmo na véspera e no dia seguinte (variação abaixo de 25%),
    para não confundir um tombo real de 50% com desdobramento.
    """
    ev = []
    for i in range(1, len(serie)):
        p0, p1 = serie[i - 1][1], serie[i][1]
        if not p0 or not p1:
            continue
        k = _proporcao_redonda(p1 / p0)
        if k is None:
            continue
        antes = serie[i - 2][1] if i >= 2 else None
        depois = serie[i + 1][1] if i + 1 < len(serie) else None
        if antes and abs(p0 / antes - 1) >= 0.25:
            continue
        if depois and abs(depois / p1 - 1) >= 0.25:
            continue
        ev.append((serie[i][0], k))
    return ev


# ---------------------------------------------------------------------------
# Anos fechados (arquivo anual, uma vez por ano)
# ---------------------------------------------------------------------------

def _resumo_ano(regs):
    por_t = defaultdict(list)
    for r in regs:
        por_t[r["ticker"]].append((r["data"], r["preco"]))
    out = {}
    for t, s in por_t.items():
        s.sort()
        mensal = {}
        for d, p in s:
            mensal[d[5:7]] = round(p, 4)  # último fechamento do mês
        out[t] = {"m": mensal, "ini": [s[0][0], s[0][1]], "fim": [s[-1][0], s[-1][1]],
                  "ev": [[d, round(r, 6)] for d, r in detectar_eventos(s)]}
    return out


def anos_fechados(caminho, hoje=None, anual_corrente=None):
    """Garante no cache os últimos ANOS anos completos. Devolve {ano: {ticker: resumo}}."""
    hoje = hoje or date.today()
    cache = {}
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as fp:
            cache = json.load(fp)
    alvo = [str(a) for a in range(hoje.year - ANOS, hoje.year)]
    mudou = False
    for ano in alvo:
        if ano in cache:
            continue
        zb = baixar(URL_ANUAL.format(ano=ano))
        if not zb:
            log(f"Histórico: arquivo anual {ano} indisponível")
            continue
        regs = _parse(zb, codbdis={"02", "12", "14"})
        del zb
        cache[ano] = _resumo_ano(regs)
        log(f"Histórico: ano {ano} guardado ({len(cache[ano])} ativos)")
        mudou = True
    for ano in list(cache):
        if ano not in alvo:
            del cache[ano]
            mudou = True
    if mudou:
        with open(caminho, "w", encoding="utf-8") as fp:
            json.dump(cache, fp, ensure_ascii=False, separators=(",", ":"))
    return cache


# ---------------------------------------------------------------------------
# Séries comparáveis
# ---------------------------------------------------------------------------

def _meses(hoje, n=ANOS * 12):
    m, a = hoje.month, hoje.year
    out = []
    for _ in range(n + 1):
        out.append(f"{a}-{m:02d}")
        m -= 1
        if m == 0:
            m, a = 12, a - 1
    return out[::-1]


def _semanas(datas, n=52):
    """Último pregão de cada semana (as n mais recentes)."""
    por_sem = {}
    for d in sorted(datas):
        y, w, _ = date.fromisoformat(d).isocalendar()
        por_sem[(y, w)] = d
    return [por_sem[k] for k in sorted(por_sem)][-(n + 1):]


def _fator(eventos, d):
    """Multiplicador do preço da data d para a base de hoje (eventos posteriores a d)."""
    f = 1.0
    for de, r in eventos:
        if de > d:
            f *= r
    return f


def montar_historico(tickers, anos_cache, diario, hoje=None, macro_ini=None, oficiais=None):
    """
    tickers: ativos do app + referências da B3.
    diario: {(data, ticker): preço} do histórico diário (~13 meses).
    Devolve o dicionário gravado em docs/data/historico.json.
    """
    hoje = hoje or date.today()
    meses = _meses(hoje)
    datas_d = sorted({d for d, _ in diario})
    semanas = _semanas(datas_d)
    por_t = defaultdict(list)
    for (d, t), p in diario.items():
        if t in tickers:
            por_t[t].append((d, p))
    out_m, out_s, ajustes = {}, {}, {}
    inicio_diario = datas_d[0] if datas_d else "9999"
    for t in tickers:
        s = sorted(por_t.get(t, []))
        ev = []
        mensal = {}
        anos_ord = sorted(anos_cache)
        ult = None
        for ano in anos_ord:
            r = anos_cache[ano].get(t)
            if not r:
                ult = None
                continue
            k = _proporcao_redonda(r["ini"][1] / ult[1]) if ult and r["ini"][1] and ult[1] else None
            if k:
                ev.append((r["ini"][0], k))
            ev += [tuple(e) for e in r["ev"]]
            for mm, p in r["m"].items():
                mensal[f"{ano}-{mm}"] = p
            ult = r["fim"]
        # ano corrente (e meses que o diário cobre)
        if s:
            k = _proporcao_redonda(s[0][1] / ult[1]) if ult and s[0][0] > ult[0] and ult[1] else None
            if k:
                ev.append((s[0][0], k))
            ev += [e for e in detectar_eventos(s) if e[0] >= inicio_diario]
            for d, p in s:
                mensal[d[:7]] = p
        origem = "detectado"
        if oficiais and t in oficiais:
            # eventos publicados pela B3 têm prioridade sobre a detecção automática
            ev, origem = list(oficiais[t]), "B3"
        ev = sorted(set((d, round(r, 10)) for d, r in ev))
        # o mês só vale se tiver preço; meses de anos fechados usam o fechamento do arquivo anual
        # (o fator usa o último dia do mês como referência)
        vm = []
        for m in meses:
            p = mensal.get(m)
            vm.append(round(p * _fator(ev, m + "-31"), 4) if p else None)
        if any(v is not None for v in vm):
            out_m[t] = vm
        if s:
            dd = dict(s)
            vs, ultimo = [], None
            for d in semanas:
                if d in dd:
                    ultimo = dd[d]
                    vs.append(round(dd[d] * _fator(ev, d), 4))
                else:
                    vs.append(None)
            if any(v is not None for v in vs):
                out_s[t] = vs
        if ev:
            ajustes[t] = [[d, r, origem] for d, r in ev]
    return {"meses": meses, "semanas": semanas, "precos_m": out_m, "precos_s": out_s, "ajustes": ajustes}


def indice_cdi_ipca(meses, semanas):
    """Índices acumulados (base = 1 no primeiro ponto) de CDI e IPCA, alinhados às datas."""
    out = {}
    if not meses:
        return out
    a, m = int(meses[0][:4]), int(meses[0][5:])
    ini = date(a, m, 1)
    fim = date.today()

    def consulta(serie, a, b):
        import time
        for tentativa in range(3):
            dados = sgs_periodo(serie, a, b)
            if dados:
                return dados
            time.sleep(5 * (tentativa + 1))
        log(f"Histórico: série {serie} do Banco Central não respondeu com dados válidos")
        return None

    def mensal(serie, nome):
        dados = consulta(serie, ini, fim)
        if not dados:
            return None
        taxa = {f"{d['data'][6:10]}-{d['data'][3:5]}": d["valor"] for d in dados}
        idx, v = [], 1.0
        for i, mm in enumerate(meses):
            if i == 0:
                idx.append(1.0)  # base no fim do primeiro mês
                continue
            if mm not in taxa:
                idx.append(None)
                continue
            v *= 1 + taxa[mm] / 100
            idx.append(round(v, 6))
        return {"nome": nome, "m": idx}

    cdi = mensal(4391, "CDI")
    ipca = mensal(433, "IPCA")
    if cdi and semanas:
        d0 = date.fromisoformat(semanas[0])
        dia = consulta(12, d0 - timedelta(days=5), fim)
        if dia:
            taxas = sorted((f"{d['data'][6:10]}-{d['data'][3:5]}-{d['data'][0:2]}", d["valor"]) for d in dia)
            idx, v, j = [], 1.0, 0
            # o CDI do dia d rende de d para o dia útil seguinte; acumula as taxas entre as datas das semanas
            for k, sd in enumerate(semanas):
                if k == 0:
                    while j < len(taxas) and taxas[j][0] < sd:
                        j += 1
                    idx.append(1.0)
                    continue
                while j < len(taxas) and taxas[j][0] < sd:
                    v *= 1 + taxas[j][1] / 100
                    j += 1
                idx.append(round(v, 6))
            cdi["s"] = idx
    if cdi:
        out["CDI"] = cdi
    if ipca:
        out["IPCA"] = ipca
    log("Histórico: CDI e IPCA " + ("ok" if cdi and ipca else "incompletos"))
    return out


# ---------------------------------------------------------------------------
# Retorno total (preço + proventos reinvestidos)
# ---------------------------------------------------------------------------

def retorno_total(precos, rotulos, proventos, mensal):
    """
    precos: série ajustada (mesma base de ações de hoje) alinhada a `rotulos`.
    proventos: [(data_ex, valor por ação na base de hoje)].
    Reinveste cada provento no fim do intervalo em que a ação ficou "ex".
    Devolve índice (1 no primeiro preço) ou None.
    """
    if not precos or not any(precos):
        return None
    fim = (lambda r: r + "-31") if mensal else (lambda r: r)
    idx, nivel, ant, ant_rot = [], None, None, None
    for p, r in zip(precos, rotulos):
        if p is None:
            idx.append(None)
            continue
        if ant is None:
            nivel, ant, ant_rot = 1.0, p, r
            idx.append(1.0)
            continue
        d = sum(v for de, v in proventos if fim(ant_rot) < de <= fim(r))
        nivel *= (p + d) / ant
        ant, ant_rot = p, r
        idx.append(round(nivel, 6))
    return idx
