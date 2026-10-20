# -*- coding: utf-8 -*-
"""
Outros fundos listados na B3, além dos FIIs:
- FIAGRO: investem em CRA (crédito do agronegócio), terras e cadeias agro. Dados: informe mensal
  de FIAGRO da CVM (inf_mensal_fiagro_AAAAMM.zip) e cotação da B3.
- FI-Infra: investem em debêntures incentivadas de infraestrutura. Cotação da B3.
- ETFs (fundos de índice): replicam um índice (ações, renda fixa, exterior). Cotação da B3.
Rendimentos pela data-com publicados pela B3 quando disponíveis.
"""

from collections import defaultdict
from datetime import date

from util import baixar, coluna, ler_csv_do_zip, log, num_br, sem_acento, so_digitos

URL_FIAGRO = "https://dados.cvm.gov.br/dados/FIAGRO/DOC/INF_MENSAL/DADOS/inf_mensal_fiagro_{am}.zip"


def _meses_recentes(n=14, hoje=None):
    hoje = hoje or date.today()
    a, m = hoje.year, hoje.month
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            a, m = a - 1, 12
        out.append(f"{a}{m:02d}")
    return out


def coletar_fiagro():
    """
    Lê os informes mensais de FIAGRO dos últimos meses. Devolve {isin: {...}} com o mês mais recente
    de cada fundo e a soma dos rendimentos mensais informados (quando a CVM traz o campo).
    """
    por_cnpj, isin_cnpj, info = defaultdict(dict), {}, {}
    colunas_log = False
    lidos = 0
    for am in _meses_recentes():
        zb = baixar(URL_FIAGRO.format(am=am), silencioso=True)
        if not zb:
            continue
        lidos += 1
        import io
        import zipfile
        z = zipfile.ZipFile(io.BytesIO(zb))
        for nome in z.namelist():
            if "subclasse" in nome.lower():
                continue  # valores por subclasse; o valor da cota da classe vem do arquivo principal
            rd = ler_csv_do_zip(zb, [nome.lower()])
            if rd is None or not rd.fieldnames:
                continue
            f = rd.fieldnames
            if not colunas_log:
                log(f"FIAGRO {am}: arquivo {nome} colunas {f[:40]}")
            c_cnpj = coluna(f, "CNPJ_Fundo_Classe", "CNPJ_Classe", "CNPJ_Fundo", "CNPJ")
            c_isin = coluna(f, "Codigo_ISIN", "ISIN")
            c_nome = coluna(f, "Nome_Fundo_Classe", "Nome_Classe", "Denominacao_Social", "Nome_Fundo")
            c_data = coluna(f, "Data_Referencia", "DT_COMPTC")
            campos = {
                "pl": coluna(f, "Patrimonio_Liquido", "Valor_Patrimonio_Liquido"),
                "vp": coluna(f, "Valor_Patrimonial_Cotas", "Valor_Patrimonial_Cota", "Valor_Cota"),
                "cotas": coluna(f, "Cotas_Emitidas", "Quantidade_Cotas"),
                "cotistas": coluna(f, "Total_Numero_Cotistas", "Numero_Cotistas"),
                "dy": coluna(f, "Percentual_Dividend_Yield_Mes", "Dividend_Yield"),
            }
            for r in rd:
                cnpj = so_digitos(r.get(c_cnpj)) if c_cnpj else ""
                if not cnpj:
                    continue
                if c_isin and (r.get(c_isin) or "").strip():
                    isin_cnpj[r[c_isin].strip().upper()] = cnpj
                if c_nome and r.get(c_nome):
                    info[cnpj] = r[c_nome].strip()
                d = (r.get(c_data) or am)[:7] if c_data else am
                linha = {k: num_br(r.get(c)) for k, c in campos.items() if c and num_br(r.get(c)) is not None}
                if linha:
                    por_cnpj[cnpj].setdefault(d, {}).update(linha)
        colunas_log = True
    log(f"FIAGRO: {lidos} informes mensais lidos; {len(por_cnpj)} fundos; {len(isin_cnpj)} com ISIN")
    saida = {}
    for isin, cnpj in isin_cnpj.items():
        meses = sorted(por_cnpj.get(cnpj, {}))
        if not meses:
            continue
        ult = por_cnpj[cnpj][meses[-1]]
        dys = [por_cnpj[cnpj][m].get("dy") for m in meses[-12:] if por_cnpj[cnpj][m].get("dy") is not None]
        saida[isin] = {"cnpj": cnpj, "nome": info.get(cnpj), "mes": meses[-1], "vp_cota": ult.get("vp"),
                       "patrimonio": ult.get("pl"), "cotistas": ult.get("cotistas"),
                       "dy_meses": len(dys), "dy_soma": sum(dys) if dys else None}
    return saida


def classificar(nome, especi, codbdi, eh_fiagro):
    n = " " + sem_acento(nome or "") + " "
    if eh_fiagro or "fiagro" in n or " agro" in n:
        return "FIAGRO"
    if "infra" in n or " inf " in n or "deb" in n:
        return "FI-Infra"
    if codbdi == "14":
        return "ETF"
    if n.strip().startswith("fii") or " fii " in n:
        return "FII sem informe CVM"
    return "Outros fundos"


def montar(candidatos, cot, liq, nomes, fiagro, prov_fundos, historico_52s, macro=None):
    """
    candidatos: tickers de fundos fora do grupo de FIIs (ETFs, FI-Infra, FIAGRO...).
    Devolve lista de registros para o app.
    """
    import fonte_b3_proventos as b3p
    out = []
    for t in sorted(set(candidatos)):
        c = cot.get(t)
        if not c:
            continue
        isin = (c.get("isin") or "").upper()
        fa = fiagro.get(isin)
        nm = (nomes or {}).get(t) or c.get("nome") or ""
        tipo = classificar((fa or {}).get("nome") or nm, c.get("especi"), c.get("codbdi"), bool(fa))
        reg = {"ticker": t, "tipo_fundo": tipo, "nome": (fa or {}).get("nome") or nm, "preco": c["preco"],
               "data_preco": c["data"], "liquidez_media": (liq or {}).get(t), "isin": isin}
        if fa:
            reg.update(cnpj=fa["cnpj"], vp_cota=fa.get("vp_cota"), patrimonio=fa.get("patrimonio"),
                       cotistas=fa.get("cotistas"), data_informe=fa.get("mes"))
            if fa.get("vp_cota"):
                pvp = c["preco"] / fa["vp_cota"]
                if 0.1 <= pvp <= 5:
                    reg["p_vp"] = pvp
        pf = prov_fundos.get(t[:4]) if prov_fundos else None
        if pf:
            soma, n = b3p.soma_12m(pf.get("dinheiro") or [], isin)
            if soma is None:
                soma, n = b3p.soma_12m(pf.get("dinheiro") or [])
            if soma is not None and n:
                reg["dy"] = soma / c["preco"] * 100
                reg["dy_detalhe"] = f"{n} rendimento(s) com data-com em 12 meses"
        r52 = historico_52s(t)
        if r52 and r52.get("serie") and len(r52["serie"]) > 100:
            ps = [p for _, p in r52["serie"]] + [c["preco"]]
            salto = any(b / a < 0.55 or b / a > 1.8 for a, b in zip(ps, ps[1:]) if a)
            if salto:
                # queda ou alta de quase metade num só dia num fundo = desdobramento/grupamento de cotas
                reg["var_12m_obs"] = "variação omitida: houve desdobramento ou grupamento de cotas no período"
            elif ps[0]:
                reg["var_12m"] = (c["preco"] / ps[0] - 1) * 100
        out.append(reg)
    from collections import Counter
    log(f"Outros fundos listados: {len(out)} ({dict(Counter(r['tipo_fundo'] for r in out))})")
    return out
