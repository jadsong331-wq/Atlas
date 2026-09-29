# -*- coding: utf-8 -*-
"""
Fundamentos oficiais da CVM (Portal Dados Abertos).

- FCA (valor mobiliário): liga ticker -> CNPJ da companhia
- DFP (anual) e ITR (trimestral): DRE, balanço, fluxo de caixa e composição do capital
- Informe mensal de FII: valor patrimonial da cota, patrimônio, cotistas, DY do mês

Todos os valores monetários saem em reais (a escala "MIL" da CVM é convertida).
"""

from collections import defaultdict
from datetime import date

from util import baixar, coluna, ler_csv_do_zip, log, num_br, sem_acento, so_digitos

BASE = "https://dados.cvm.gov.br/dados"
URL_FCA = BASE + "/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"
URL_DOC = BASE + "/CIA_ABERTA/DOC/{T}/DADOS/{t}_cia_aberta_{ano}.zip"
URL_FII = BASE + "/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip"

DEMONSTRACOES = ["DRE", "BPA", "BPP", "DFC_MI", "DFC_MD"]


# ---------------------------------------------------------------------------
# Ticker -> CNPJ
# ---------------------------------------------------------------------------

def mapear_cnpjs(tickers):
    """Usa o FCA (formulário cadastral) para achar o CNPJ de cada ticker."""
    alvo = set(tickers)
    achados = {}
    for ano in (date.today().year, date.today().year - 1):
        zb = baixar(URL_FCA.format(ano=ano))
        if not zb:
            continue
        rd = ler_csv_do_zip(zb, ["valor_mobiliario"])
        if rd is None:
            continue
        c_cnpj = coluna(rd.fieldnames, "CNPJ_Companhia", "CNPJ_CIA", "cnpj")
        c_cod = coluna(rd.fieldnames, "Codigo_Negociacao", "codigo_negociacao")
        if not c_cnpj or not c_cod:
            log(f"FCA {ano}: colunas não reconhecidas {rd.fieldnames}")
            continue
        for r in rd:
            cod = (r.get(c_cod) or "").strip().upper()
            if cod in alvo and cod not in achados:
                achados[cod] = so_digitos(r[c_cnpj])
        if len(achados) == len(alvo):
            break
    log(f"FCA: {len(achados)} de {len(alvo)} tickers ligados a CNPJ")
    return achados


# ---------------------------------------------------------------------------
# Leitura das demonstrações
# ---------------------------------------------------------------------------

class Base:
    """Linhas das demonstrações filtradas para as companhias do universo."""

    def __init__(self):
        # (st, cnpj) -> lista de linhas
        self.linhas = defaultdict(list)
        # cnpj -> {dt_refer: {"on":..., "pn":...}}
        self.capital = defaultdict(dict)
        # cnpj -> nome
        self.nomes = {}
        self.docs = defaultdict(set)  # cnpj -> {(tipo, dt_refer)}


def _escala(txt):
    t = sem_acento(txt or "")
    return 1000.0 if t.startswith("mil") else 1.0


def carregar(base, tipo, ano, cnpjs):
    """Carrega um ZIP DFP/ITR de um ano na Base (só as companhias pedidas)."""
    zb = baixar(URL_DOC.format(T=tipo.upper(), t=tipo.lower(), ano=ano))
    if not zb:
        return False
    for st in DEMONSTRACOES:
        achados = set()
        for sufixo in ("con", "ind"):
            rd = ler_csv_do_zip(zb, [f"_{st.lower()}_{sufixo}_"])
            if rd is None:
                continue
            f = rd.fieldnames
            cols = {k: coluna(f, k) for k in ("CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "ESCALA_MOEDA",
                                               "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC", "CD_CONTA",
                                               "DS_CONTA", "VL_CONTA")}
            for r in rd:
                cnpj = so_digitos(r[cols["CNPJ_CIA"]])
                if cnpj not in cnpjs:
                    continue
                if sufixo == "ind" and cnpj in achados:
                    continue  # prefere o consolidado
                if sufixo == "con":
                    achados.add(cnpj)
                base.nomes[cnpj] = r[cols["DENOM_CIA"]]
                v = num_br(r[cols["VL_CONTA"]])
                if v is None:
                    continue
                ordem = sem_acento(r[cols["ORDEM_EXERC"]])
                base.linhas[(st, cnpj)].append({
                    "tipo": tipo, "dt_refer": r[cols["DT_REFER"]], "versao": int(r[cols["VERSAO"]] or 0),
                    "ultimo": ordem.startswith("ultimo"),
                    "dt_ini": r.get(cols["DT_INI_EXERC"]) if cols["DT_INI_EXERC"] else None,
                    "dt_fim": r[cols["DT_FIM_EXERC"]], "cd": r[cols["CD_CONTA"]].strip(),
                    "ds": sem_acento(r[cols["DS_CONTA"]]),
                    "valor": v * _escala(r[cols["ESCALA_MOEDA"]]),
                })
                base.docs[cnpj].add((tipo, r[cols["DT_REFER"]]))
    rd = ler_csv_do_zip(zb, ["composicao_capital"])
    if rd is not None:
        f = rd.fieldnames
        c = {k: coluna(f, k) for k in ("CNPJ_CIA", "DT_REFER", "QT_ACAO_ORDIN_CAP_INTEGR", "QT_ACAO_PREF_CAP_INTEGR",
                                        "QT_ACAO_ORDIN_TESOURO", "QT_ACAO_PREF_TESOURO")}
        for r in rd:
            cnpj = so_digitos(r[c["CNPJ_CIA"]])
            if cnpj not in cnpjs:
                continue
            g = lambda k: num_br(r.get(c[k])) if c[k] else 0  # noqa: E731
            base.capital[cnpj][r[c["DT_REFER"]]] = {
                "on": (g("QT_ACAO_ORDIN_CAP_INTEGR") or 0) - (g("QT_ACAO_ORDIN_TESOURO") or 0),
                "pn": (g("QT_ACAO_PREF_CAP_INTEGR") or 0) - (g("QT_ACAO_PREF_TESOURO") or 0),
            }
    return True


# ---------------------------------------------------------------------------
# Consultas às contas
# ---------------------------------------------------------------------------

def _prof(cd):
    return cd.count(".") + 1


def _doc(linhas, dt_refer):
    """Linhas de um documento (maior versão) para uma data de referência."""
    sel = [l for l in linhas if l["dt_refer"] == dt_refer]
    if not sel:
        return []
    v = max(l["versao"] for l in sel)
    return [l for l in sel if l["versao"] == v]


def _ano_ini(dt_fim):
    return dt_fim[:4] + "-01-01"


def _conta(linhas, achar, ultimo=True, dt_fim=None, acumulado=True):
    """Valor de uma conta. `achar(cd, ds)` diz se a linha é a desejada."""
    cand = []
    for l in linhas:
        if l["ultimo"] != ultimo:
            continue
        if dt_fim and l["dt_fim"] != dt_fim:
            continue
        if acumulado and l["dt_ini"] and l["dt_ini"] != _ano_ini(l["dt_fim"]):
            continue
        if achar(l["cd"], l["ds"]):
            cand.append(l)
    if not cand:
        return None
    cand.sort(key=lambda l: (_prof(l["cd"]), l["cd"]))
    return cand[0]["valor"]


def _soma(linhas, achar, ultimo=True, dt_fim=None):
    tot, ok = 0.0, False
    for l in linhas:
        if l["ultimo"] != ultimo or (dt_fim and l["dt_fim"] != dt_fim):
            continue
        if l["dt_ini"] and l["dt_ini"] != _ano_ini(l["dt_fim"]):
            continue
        if achar(l["cd"], l["ds"]):
            tot += l["valor"]
            ok = True
    return tot if ok else None


# Localizadores de contas (código CVM + descrição, sem acento)
RECEITA = lambda cd, ds: cd == "3.01"  # noqa: E731
EBIT = lambda cd, ds: _prof(cd) == 2 and "resultado antes do resultado financeiro" in ds  # noqa: E731


def LUCRO_CTRL(cd, ds):
    return cd.startswith("3.") and "atribuido a socios da empresa controladora" in ds


def LUCRO_TOTAL(cd, ds):
    return (cd.startswith("3.") and _prof(cd) == 2 and "lucro" in ds and "periodo" in ds
            and "por acao" not in ds and "operac" not in ds)


def DA(cd, ds):
    return (cd.startswith("6.01.01.") and _prof(cd) == 4
            and any(k in ds for k in ("deprecia", "amortiza", "exaust")))


PALAVRAS_DIVIDENDO = ("dividendo", "juros sobre capital", "juros sobre o capital", "juros s/ capital",
                      "juros s/capital", "juros s/ o capital", "jscp", "jcp", "remuneracao aos acionistas",
                      "remuneracao ao acionista", "proventos")
PALAVRAS_EXCLUIR = ("recebid", "nao controlador", "minoritar", "emprestimo", "financiamento", "debenture",
                    "arrendamento")


def _eh_dividendo(ds):
    return any(k in ds for k in PALAVRAS_DIVIDENDO) and not any(k in ds for k in PALAVRAS_EXCLUIR)


def DIVIDENDOS(cd, ds):
    return cd.startswith("6.03.") and _prof(cd) >= 3 and _eh_dividendo(ds)


def _soma_dividendos(linhas, ultimo=True, dt_fim=None):
    """Soma os pagamentos a acionistas sem contar duas vezes uma conta e suas subcontas."""
    sel = [l for l in linhas if l["ultimo"] == ultimo and (not dt_fim or l["dt_fim"] == dt_fim)
           and (not l["dt_ini"] or l["dt_ini"] == _ano_ini(l["dt_fim"])) and DIVIDENDOS(l["cd"], l["ds"])]
    if not sel:
        return None
    cods = {l["cd"] for l in sel}
    topo = [l for l in sel if not any(l["cd"].startswith(c + ".") for c in cods if c != l["cd"])]
    return sum(l["valor"] for l in topo)


CAIXA = lambda cd, ds: cd in ("1.01.01", "1.01.02")  # noqa: E731


def DIVIDA(cd, ds):
    return cd in ("2.01.04", "2.02.01") and "emprestimo" in ds


def PL_TOTAL(cd, ds):
    return cd.startswith("2.") and _prof(cd) == 2 and ds.startswith("patrimonio liquido")


def PL_MINORITARIOS(cd, ds):
    return cd.startswith("2.") and _prof(cd) == 3 and "nao controlador" in ds


def _lucro(linhas, **kw):
    v = _conta(linhas, LUCRO_CTRL, **kw)
    return v if v is not None else _conta(linhas, LUCRO_TOTAL, **kw)


# ---------------------------------------------------------------------------
# Cálculo por companhia
# ---------------------------------------------------------------------------

def _menos_um_ano(dt):
    return f"{int(dt[:4]) - 1}{dt[4:]}"


def fundamentos_empresa(base, cnpj, anos_hist):
    """Monta os números dos últimos 12 meses e o histórico anual de uma companhia."""
    L = {st: base.linhas.get((st, cnpj), []) for st in DEMONSTRACOES}
    dfc = L["DFC_MI"] or L["DFC_MD"]
    docs = sorted(base.docs.get(cnpj, set()), key=lambda x: x[1])
    if not docs:
        return None
    tipo_ult, dt_ult = docs[-1]
    res = {"cnpj": cnpj, "nome": base.nomes.get(cnpj), "dt_refer": dt_ult, "fonte_ultima": tipo_ult.upper()}

    dre_u, dfc_u = _doc(L["DRE"], dt_ult), _doc(dfc, dt_ult)
    receita_3_01 = [l["ds"] for l in dre_u if l["cd"] == "3.01"]
    res["banco"] = bool(receita_3_01 and "intermediacao financeira" in receita_3_01[0])

    # ---- Fluxos dos últimos 12 meses (TTM)
    def ttm(stmt_linhas, func):
        doc = _doc(stmt_linhas, dt_ult)
        atual = func(doc, ultimo=True, dt_fim=dt_ult)
        if atual is None:
            return None
        if tipo_ult == "dfp" or dt_ult.endswith("-12-31"):
            return atual
        ano_ant = str(int(dt_ult[:4]) - 1) + "-12-31"
        anual = func(_doc(stmt_linhas, ano_ant), ultimo=True, dt_fim=ano_ant)
        prev = func(doc, ultimo=False, dt_fim=_menos_um_ano(dt_ult))
        if prev is None:  # comparativo ausente: usa o ITR do ano anterior
            prev = func(_doc(stmt_linhas, _menos_um_ano(dt_ult)), ultimo=True, dt_fim=_menos_um_ano(dt_ult))
        if anual is None or prev is None:
            return None
        return atual + anual - prev

    f_rec = lambda d, **k: _conta(d, RECEITA, **k)  # noqa: E731
    f_ebit = lambda d, **k: _conta(d, EBIT, **k)  # noqa: E731
    f_luc = lambda d, **k: _lucro(d, **k)  # noqa: E731
    f_da = lambda d, **k: _soma(d, DA, **k)  # noqa: E731
    f_div = lambda d, **k: _soma_dividendos(d, **k)  # noqa: E731

    res["receita_ttm"] = ttm(L["DRE"], f_rec)
    res["lucro_ttm"] = ttm(L["DRE"], f_luc)
    if not res["banco"]:
        res["ebit_ttm"] = ttm(L["DRE"], f_ebit)
        da = ttm(dfc, f_da)
        res["da_ttm"] = da
        res["ebitda_ttm"] = (res["ebit_ttm"] + da) if res["ebit_ttm"] is not None and da is not None else None
    div = ttm(dfc, f_div)
    res["dividendos_pagos_ttm"] = abs(div) if div is not None else None
    res["contas_dividendos"] = sorted({f"{l['cd']} {l['ds']}" for l in dfc_u
                                       if l["ultimo"] and DIVIDENDOS(l["cd"], l["ds"])})
    if res["contas_dividendos"]:
        log(f"CVM {res['nome']}: dividendos somados de {res['contas_dividendos']}")
    if div is None:
        contas = sorted({f"{l['cd']} {l['ds']}" for l in dfc_u if l["cd"].startswith("6.03.")})
        log(f"CVM {res['nome']}: nenhum pagamento a acionistas identificado no fluxo de caixa. "
            f"Contas de financiamento: {contas[:15]}")
    res["periodo_ttm"] = f"12 meses até {dt_ult[8:10]}/{dt_ult[5:7]}/{dt_ult[:4]}"

    # ---- Balanço na data mais recente
    bpa, bpp = _doc(L["BPA"], dt_ult), _doc(L["BPP"], dt_ult)
    pl_tot = _conta(bpp, PL_TOTAL, acumulado=False)
    minor = _conta(bpp, PL_MINORITARIOS, acumulado=False) or 0.0
    res["patrimonio_liquido"] = (pl_tot - minor) if pl_tot is not None else None
    if not res["banco"]:
        res["caixa"] = _soma(bpa, CAIXA)
        res["divida_bruta"] = _soma(bpp, DIVIDA)
        if res["divida_bruta"] is not None:
            res["divida_liquida"] = res["divida_bruta"] - (res["caixa"] or 0)

    # ---- Ações em circulação (sem tesouraria)
    cap = base.capital.get(cnpj, {})
    if cap:
        dt_cap = max(cap)
        res["acoes_on"], res["acoes_pn"] = cap[dt_cap]["on"], cap[dt_cap]["pn"]
        res["acoes_data"] = dt_cap

    # ---- Histórico anual (DFP)
    hist = {}
    for (tipo, dt) in docs:
        if tipo != "dfp" or not dt.endswith("-12-31"):
            continue
        ano = dt[:4]
        d_dre, d_dfc = _doc(L["DRE"], dt), _doc(dfc, dt)
        dv = _soma_dividendos(d_dfc, dt_fim=dt)
        hist[ano] = {
            "receita": _conta(d_dre, RECEITA, dt_fim=dt),
            "lucro": _lucro(d_dre, dt_fim=dt),
            "dividendos_pagos": abs(dv) if dv is not None else None,
        }
    anos = sorted(hist)[-(anos_hist + 1):]
    res["historico_anual"] = {a: hist[a] for a in anos}

    def cagr(chave):
        if len(anos) < 2:
            return None
        ini, fim = hist[anos[0]][chave], hist[anos[-1]][chave]
        n = int(anos[-1]) - int(anos[0])
        if not ini or not fim or ini <= 0 or fim <= 0 or n <= 0:
            return None
        return ((fim / ini) ** (1 / n) - 1) * 100

    res["cagr_receita"] = cagr("receita")
    res["cagr_lucro"] = cagr("lucro")
    res["cagr_anos"] = (int(anos[-1]) - int(anos[0])) if len(anos) >= 2 else 0
    ult5 = anos[-anos_hist:]
    res["anos_com_dividendo"] = sum(1 for a in ult5 if (hist[a]["dividendos_pagos"] or 0) > 0)
    res["anos_com_lucro"] = sum(1 for a in ult5 if (hist[a]["lucro"] or 0) > 0)
    res["anos_avaliados"] = len(ult5)
    return res


def coletar_fundamentos(ticker_cnpj, anos_hist):
    """Baixa DFP/ITR necessários e devolve {cnpj: fundamentos}."""
    hoje = date.today()
    cnpjs = set(ticker_cnpj.values())
    base = Base()
    for ano in (hoje.year, hoje.year - 1):
        carregar(base, "itr", ano, cnpjs)
    for ano in range(hoje.year - anos_hist - 1, hoje.year):
        carregar(base, "dfp", ano, cnpjs)
    saida = {}
    for cnpj in cnpjs:
        try:
            f = fundamentos_empresa(base, cnpj, anos_hist)
        except Exception as e:  # noqa: BLE001
            log(f"CVM: erro ao calcular {cnpj}: {e}")
            f = None
        if f:
            saida[cnpj] = f
        else:
            log(f"CVM: sem demonstrações para CNPJ {cnpj}")
    return saida


# ---------------------------------------------------------------------------
# FIIs
# ---------------------------------------------------------------------------

def coletar_fiis(isins):
    """
    isins: {ticker: isin (vindo da B3)}
    Devolve {ticker: {...}} com dados do informe mensal (últimos 12 meses).
    """
    hoje = date.today()
    geral, compl = [], []
    for ano in (hoje.year - 1, hoje.year):
        zb = baixar(URL_FII.format(ano=ano))
        if not zb:
            continue
        g = ler_csv_do_zip(zb, ["geral"])
        c = ler_csv_do_zip(zb, ["complemento"])
        if g is not None:
            geral.extend(list(g))
        if c is not None:
            compl.extend(list(c))
    if not geral or not compl:
        log("FII: informe mensal indisponível")
        return {}

    gc = list(geral[0].keys())
    c_cnpj_g = coluna(gc, "CNPJ_Fundo_Classe", "CNPJ_Fundo")
    c_isin = coluna(gc, "Codigo_ISIN", "ISIN")
    c_nome = coluna(gc, "Nome_Fundo_Classe", "Nome_Fundo")
    c_seg = coluna(gc, "Segmento_Atuacao", "Segmento")
    isin_cnpj, info = {}, {}
    for r in geral:
        cnpj = so_digitos(r.get(c_cnpj_g))
        if c_isin and r.get(c_isin):
            isin_cnpj[r[c_isin].strip().upper()] = cnpj
        info[cnpj] = {"nome": r.get(c_nome), "segmento": r.get(c_seg) if c_seg else None}

    cc = list(compl[0].keys())
    k = {
        "cnpj": coluna(cc, "CNPJ_Fundo_Classe", "CNPJ_Fundo"),
        "data": coluna(cc, "Data_Referencia"),
        "versao": coluna(cc, "Versao"),
        "pl": coluna(cc, "Patrimonio_Liquido"),
        "vp": coluna(cc, "Valor_Patrimonial_Cotas"),
        "cotas": coluna(cc, "Cotas_Emitidas"),
        "cotistas": coluna(cc, "Total_Numero_Cotistas", "Numero_Cotistas"),
        "dy": coluna(cc, "Percentual_Dividend_Yield_Mes"),
        "rent": coluna(cc, "Percentual_Rentabilidade_Efetiva_Mes"),
        "adm": coluna(cc, "Percentual_Despesas_Taxa_Administracao"),
    }
    por_cnpj = defaultdict(dict)
    todos_dy = []
    for r in compl:
        cnpj = so_digitos(r.get(k["cnpj"]))
        d = r.get(k["data"])
        ver = int(num_br(r.get(k["versao"])) or 0) if k["versao"] else 0
        atual = por_cnpj[cnpj].get(d)
        if atual and atual["versao"] >= ver:
            continue
        linha = {key: num_br(r.get(col)) if col else None for key, col in k.items()
                 if key not in ("cnpj", "data", "versao")}
        linha["versao"] = ver
        por_cnpj[cnpj][d] = linha
        if linha.get("dy") is not None:
            todos_dy.append(abs(linha["dy"]))

    # A CVM pode informar percentuais como fração (0,008) ou em % (0,8).
    todos_dy.sort()
    mediana = todos_dy[len(todos_dy) // 2] if todos_dy else 1
    fator = 100.0 if mediana < 0.05 else 1.0

    saida = {}
    for ticker, isin in isins.items():
        cnpj = isin_cnpj.get((isin or "").upper())
        if not cnpj or cnpj not in por_cnpj:
            log(f"FII: {ticker} (ISIN {isin}) não encontrado no informe mensal")
            continue
        meses = sorted(por_cnpj[cnpj])[-12:]
        ult = por_cnpj[cnpj][meses[-1]]
        dys = [por_cnpj[cnpj][m]["dy"] for m in meses if por_cnpj[cnpj][m].get("dy") is not None]
        saida[ticker] = {
            "cnpj": cnpj, "nome": info.get(cnpj, {}).get("nome"),
            "segmento": info.get(cnpj, {}).get("segmento"),
            "data_informe": meses[-1],
            "vp_cota": ult.get("vp"), "patrimonio_liquido": ult.get("pl"),
            "cotistas": ult.get("cotistas"), "cotas": ult.get("cotas"),
            "dy_12m_cvm": sum(dys) * fator if len(dys) == 12 else None,
            "dy_meses_informados": len(dys),
            "meses_com_rendimento": sum(1 for x in dys if x and x > 0),
            "taxa_adm_mes": (ult.get("adm") * fator) if ult.get("adm") is not None else None,
        }
    log(f"FII: {len(saida)} de {len(isins)} fundos com informe mensal")
    return saida
