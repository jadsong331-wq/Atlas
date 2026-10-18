# -*- coding: utf-8 -*-
"""
ATLAS INVEST RESEARCH - coletor oficial (sem IA).

Fontes: CVM (DFP, ITR, FCA, informe mensal de FII), B3 (COTAHIST) e Banco Central (SGS, Focus).
Saídas:
  docs/data/dados.json      -> lido pelo app
  docs/data/DADOS_ATLAS.md  -> mesmo conteúdo em texto, para anexar em qualquer IA
  data/fundamentos.json     -> cache dos balanços (renovado a cada N dias)
  data/historico_precos.csv -> preços diários dos últimos ~13 meses
  data/universo.json        -> ações e FIIs escolhidos por liquidez (renovado a cada N dias)
  data/log_ultima_execucao.txt

Uso:  python coletor/main.py            (normal)
      python coletor/main.py --forcar   (rebaixa os balanços mesmo com cache novo)
"""

import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from fonte_b3 import (atualizar_historico, cotacoes_anuais, cotacoes_do_dia,  # noqa: E402
                      liquidez_media, resumo_52s, selecionar_mercado)
from fonte_bcb import coletar_macro  # noqa: E402
from fonte_cvm import coletar_fiis, coletar_fundamentos, mapear_cnpjs, setores_cvm  # noqa: E402
from gera_md import gerar_markdown  # noqa: E402
from historico import REFERENCIAS_B3, anos_fechados, indice_cdi_ipca, montar_historico  # noqa: E402
import fonte_b3_proventos as b3p  # noqa: E402
from util import LOG, log, sem_acento, so_digitos  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ_CACHE = os.path.join(RAIZ, "data", "fundamentos.json")
ARQ_HIST = os.path.join(RAIZ, "data", "historico_precos.csv")
ARQ_UNIV = os.path.join(RAIZ, "data", "universo.json")
ARQ_ANOS = os.path.join(RAIZ, "data", "historico_anos.json")
ARQ_BACKFILL = os.path.join(RAIZ, "data", "backfill.json")
ARQ_PROV = os.path.join(RAIZ, "data", "proventos_b3.json")
ARQ_HIST_JSON = os.path.join(RAIZ, "docs", "data", "historico.json")
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
    total = (on or 0) + (pn or 0)
    relevante = lambda q: q and total and q / total > 0.02  # noqa: E731
    if on and p_on is None and p_pn is not None:
        p_on = p_pn
        if relevante(on):
            avisos.append("sem cotação da ação ON; valor de mercado usa o preço da PN")
    if pn and p_pn is None and p_on is not None:
        p_pn = p_on
        if relevante(pn):
            avisos.append("sem cotação da ação PN; valor de mercado usa o preço da ON")
    if (on and p_on is None) or (pn and p_pn is None):
        return None
    return (on or 0) * (p_on or 0) + (pn or 0) * (p_pn or 0)


def corrigir_escala_acoes(ticker, mcap, pl, on, pn):
    """
    Algumas companhias informam à CVM a quantidade de ações em milhares.
    Se o P/VP resultante for absurdo (< 0,02) e multiplicar por mil o trouxer
    para uma faixa plausível, a quantidade é tratada como milhares.
    """
    if not mcap or not pl or pl <= 0:
        return mcap, on, pn, False
    pvp = mcap / pl
    if pvp < 0.02 and 0.05 <= pvp * 1000 <= 60:
        log(f"{ticker}: quantidade de ações informada em milhares; ajustada (x1000)")
        return mcap * 1000, (on or 0) * 1000, (pn or 0) * 1000, True
    return mcap, on, pn, False


def _ler_json(caminho):
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as fp:
        return json.load(fp)


def _gravar_json(caminho, obj):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=1)


def carregar_cache():
    return _ler_json(ARQ_CACHE)


def _idade(iso):
    return (date.today() - date.fromisoformat(iso[:10])).days


def fundamentos(forcar, acoes=None, curados=None):
    """
    Balanços da CVM das ações pedidas (cache de N dias).
    Baixa de novo se o cache estiver velho, se pedirem --forcar ou se entrar ticker novo.
    """
    acoes = sorted(set(acoes if acoes is not None else
                       [t for t, tipo, *_ in config.UNIVERSO if tipo == "acao"]))
    cache = carregar_cache()
    if cache and not forcar:
        idade = _idade(cache["gerado_em"])
        pedidos = set(cache.get("tickers_pedidos") or cache.get("ticker_cnpj", {}))
        novos = [t for t in acoes if t not in pedidos]
        if idade < config.DIAS_CACHE_FUNDAMENTOS and not novos:
            log(f"Fundamentos: usando cache de {idade} dia(s)")
            return cache
        if novos and idade < config.DIAS_CACHE_FUNDAMENTOS:
            log(f"Fundamentos: {len(novos)} ticker(s) novo(s) no universo; baixando balanços de novo")
    mapa = mapear_cnpjs(acoes)
    for t, cnpj in config.CNPJ_MANUAL.items():
        if t in acoes:
            mapa[t] = so_digitos(cnpj)
    sem = sorted(t for t in acoes if t not in mapa)
    if sem:
        log(f"Sem CNPJ no FCA (ficam de fora, ou preencha CNPJ_MANUAL): {sem}")
    detalhar = {mapa[t] for t in (curados or []) if t in mapa}
    dados = coletar_fundamentos(mapa, config.ANOS_HISTORICO, detalhar) if mapa else {}
    setores = setores_cvm(set(mapa.values())) if mapa else {}
    novo = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
            "tickers_pedidos": acoes, "ticker_cnpj": mapa, "setores_cvm": setores, "empresas": dados}
    if not dados and cache:
        log("Fundamentos: coleta falhou, mantendo cache anterior")
        return cache
    _gravar_json(ARQ_CACHE, novo)
    return novo


# ---------------------------------------------------------------------------
# Universo: lista curada + mercado completo filtrado por liquidez
# ---------------------------------------------------------------------------

def _parametros_universo():
    return {"mercado_completo": config.MERCADO_COMPLETO,
            "min_acoes": config.LIQUIDEZ_MINIMA_ACOES, "min_fiis": config.LIQUIDEZ_MINIMA_FIIS,
            "presenca": getattr(config, "PRESENCA_MINIMA", 0),
            "pregoes": config.PREGOES_LIQUIDEZ, "excluir": sorted(config.EXCLUIR),
            "curados": sorted(t for t, *_ in config.UNIVERSO)}


def universo_mercado(cot, forcar):
    """
    Devolve (cache_universo, registros_anuais_ou_None).
    O arquivo anual da B3 (~90 MB) só é baixado quando o universo é renovado.
    """
    if not config.MERCADO_COMPLETO:
        return {"acoes": [], "fiis": [], "liquidez": {}}, None
    cache = _ler_json(ARQ_UNIV)
    par = _parametros_universo()
    if (cache and not forcar and cache.get("parametros") == par
            and _idade(cache["gerado_em"]) < config.DIAS_CACHE_FUNDAMENTOS):
        log(f"Universo: usando seleção de {_idade(cache['gerado_em'])} dia(s) "
            f"({len(cache['acoes'])} ações e {len(cache['fiis'])} FIIs além da lista curada)")
        return cache, None
    regs = cotacoes_anuais(min_pregoes=300)  # ano atual + anterior: liquidez e 12 meses de preço de quem entrar
    if not regs:
        log("Universo: arquivo anual da B3 indisponível; mantendo a seleção anterior")
        return (cache or {"acoes": [], "fiis": [], "liquidez": {}}), None
    liq, datas = liquidez_media(regs, cot, config.PREGOES_LIQUIDEZ)
    curados = {t for t, *_ in config.UNIVERSO}
    acoes, fiis = selecionar_mercado(liq, config.LIQUIDEZ_MINIMA_ACOES, config.LIQUIDEZ_MINIMA_FIIS,
                                     curados, set(config.EXCLUIR), getattr(config, "PRESENCA_MINIMA", 0))
    todos = curados | {t for t, _ in acoes} | {t for t, _ in fiis}
    novo = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "parametros": par,
            "periodo": [datas[0], datas[-1]] if datas else None, "pregoes": len(datas),
            "acoes": [t for t, _ in acoes], "fiis": [t for t, _ in fiis],
            "liquidez": {t: round(liq[t][0]) for t in sorted(todos) if t in liq},
            "isin": {r["ticker"]: r["isin"] for r in regs if r["ticker"] in todos and r.get("isin")}}
    log(f"Universo: {len(acoes)} ações e {len(fiis)} FIIs negociados com regularidade, além dos "
        f"{len(curados)} curados (média de {len(datas)} pregões)")
    _gravar_json(ARQ_UNIV, novo)
    return novo, regs


# Setor de atividade da CVM -> setor ATLAS (palavras sem acento, a primeira que bater vale)
MAPA_SETORES = [
    ("Bancos e financeiro", ("banco", "intermediacao financeira", "seguradora", "bolsa", "arrendamento",
                             "credito", "factoring", "securitizacao", "previdencia", "financeir")),
    ("Commodities", ("petroleo", "mineral", "minera", "metalurgia", "siderurgia", "papel e celulose",
                     "petroquim", "quimic")),
    ("Energia e saneamento", ("energia", "saneamento", "agua", "gas")),
    ("Agronegócio", ("agricultura", "acucar", "pesca", "reflorestamento", "agro", "pecuaria")),
    ("Construção e imóveis", ("construcao", "const. civil", "const civil", "imobili", "incorpora")),
    ("Transporte e logística", ("transporte", "logistic")),
    ("Saúde", ("medic", "saude", "farmac", "hospital", "laborat")),
    ("Tecnologia e telecom", ("telecom", "informatica", "comunicacao", "tecnologia", "software")),
    ("Consumo e varejo", ("comercio", "varejo", "alimento", "bebida", "fumo", "textil", "vestuario", "calcado",
                          "hospedagem", "turismo", "lazer", "educacao", "brinquedo", "higiene")),
    ("Indústria", ("maquina", "maqs", "equip", "veiculo", "veic.", "eletroeletron", "embalage", "plastico", "borracha",
                   "grafica", "metal", "industria")),
]


def setor_atlas(setor_cvm, nao_mapeados=None):
    t = sem_acento(setor_cvm or "")
    for nome, chaves in MAPA_SETORES:
        if any(k in t for k in chaves):
            return nome
    if nao_mapeados is not None and setor_cvm:
        nao_mapeados.add(setor_cvm)
    return "Outros"


PAPEL = ("CRI", "CRI_CRA", "LCI", "LCI_LCA", "LIG", "Letras_Hipotecarias", "Titulos_Privados", "Debentures",
         "Cedulas_Debentures", "Notas_Promissorias")
IMOVEIS = ("Direitos_Bens_Imoveis", "Acoes_Sociedades_Atividades_FII", "Cotas_Sociedades_Atividades_FII")


def composicao_fii(carteira):
    """Frações da carteira em recebíveis (papel), imóveis e cotas de outros FIIs (informe mensal da CVM)."""
    c = carteira or {}
    tot = c.get("Total_Investido") or 0
    if tot <= 0:
        return None
    soma = lambda ks: sum(max(0.0, c.get(k) or 0) for k in ks)  # noqa: E731
    return {"papel": soma(PAPEL) / tot, "imoveis": soma(IMOVEIS) / tot, "fof": max(0.0, c.get("FII") or 0) / tot}


def segmento_fii(segmento, mandato, nome=None, carteira=None):
    """
    Tipo do FII. 1) Pela composição da carteira informada à CVM (o mais confiável).
    2) Pelo nome do fundo. 3) Pelo Segmento_Atuacao declarado, que tem erros
    (ex.: MXRF11 declarado como "Logística") e usa "Multicategoria" para tudo.
    """
    comp = composicao_fii(carteira)
    if comp and comp["papel"] >= 0.6:
        return "FII Papel"
    if comp and comp["fof"] >= 0.5:
        return "FII Híbrido"
    n = " " + sem_acento(nome or "") + " "
    seg, man = sem_acento(segmento or ""), sem_acento(mandato or "")
    if not comp and any(k in n for k in ("receb", "credito", " cri ", "juros", "renda fixa", "high yield", " hy ",
                                         "papel", "securitiz", "high grade")):
        return "FII Papel"
    if any(k in n for k in ("logist", "galp")):
        return "FII Logístico"
    if any(k in n for k in ("shopping", "malls")):
        return "FII Shopping"
    if any(k in n for k in ("lajes", "corporate", "escritor", "office")):
        return "FII Lajes"
    if not comp and ("titulo" in man or "titulos" in seg or "receb" in seg or "papel" in seg):
        return "FII Papel"
    if comp and comp["imoveis"] < 0.6:
        return "FII Híbrido"  # nem papel nem imóveis dominam
    if "logist" in seg:
        return "FII Logístico"
    if "shopping" in seg:
        return "FII Shopping"
    if "laje" in seg or "escritorio" in seg:
        return "FII Lajes"
    if "hibrido" in seg or "multi" in seg:
        return "FII Híbrido"
    return "FII Outros"


SETORES_DALIO = {"Energia e saneamento", "Commodities", "Agronegócio"}


def perfis_automaticos(tipo, setor, ind, banco):
    """
    Perfis sugeridos por regras numéricas para ativos fora da lista curada.
    Não é recomendação: só indica com qual escola os números combinam.
    """
    g = lambda k: ind.get(k)  # noqa: E731
    ge = lambda k, v: g(k) is not None and g(k) >= v  # noqa: E731
    le = lambda k, v: g(k) is not None and g(k) <= v  # noqa: E731
    p = []
    if tipo == "fii":
        if ge("meses_com_rendimento", 12) and ge("dy", 8) and le("p_vp", 1.1):
            p.append("Baroni")
        return p
    lucro5 = ge("anos_com_lucro", 5)
    lucro_pos = g("lucro_ttm") is not None and g("lucro_ttm") > 0
    if ge("anos_com_dividendo", 5) and ge("dy", 6) and le("payout", 100) and lucro_pos:
        p.append("Barsi")
    if g("p_l") and 0 < g("p_l") <= 15 and g("p_vp") and g("p_l") * g("p_vp") <= 22.5 and lucro5:
        p.append("Graham")
    if ge("roe", 15) and lucro5 and (banco or (le("div_liq_ebitda", 2) and ge("margem_liquida", 10))):
        p.append("Buffett")
    if ge("cagr_lucro", 15) and ge("cagr_receita", 10):
        p.append("Lynch")
    if ge("roe", 15) and ge("cagr_receita", 10) and lucro5:
        p.append("Bartunek")
    if setor in SETORES_DALIO:
        p.append("Dalio")
    return p


def _br(v, casas=1):
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def alertas_acao(ind, f):
    a = []
    pl = ind.get("p_l")
    if f.get("lucro_ttm") is not None and f["lucro_ttm"] < 0:
        a.append("Prejuízo nos últimos 12 meses")
    if ind.get("payout") is not None and ind["payout"] > 100:
        a.append(f"Dividendos pagos acima do lucro (payout {_br(ind['payout'], 0)}%)")
    if ind.get("roe") is not None and 0 < ind["roe"] < 10:
        a.append(f"ROE baixo ({_br(ind['roe'])}%)")
    d = ind.get("div_liq_ebitda")
    if d is not None and d > 3.5:
        a.append(f"Endividamento elevado (Dív.Líq/EBITDA {_br(d)})")
    if ind.get("cagr_lucro") is not None and ind["cagr_lucro"] < 0:
        a.append(f"Lucro encolheu em {f.get('cagr_anos')} anos")
    if pl is not None and pl > 40:
        a.append("P/L muito alto: lucro deprimido ou preço exigente")
    return a


def proventos_b3(forcar, emissores, fundos):
    """Proventos declarados (data-com) e eventos societários da B3, com cache de N dias."""
    cache = _ler_json(ARQ_PROV)
    if cache and not forcar:
        idade = _idade(cache["gerado_em"])
        novos = set(emissores) - set(cache.get("empresas", {})) - set(cache.get("sem_resposta", []))
        if idade < config.DIAS_CACHE_FUNDAMENTOS and len(novos) <= 5:
            log(f"B3 proventos: usando cache de {idade} dia(s)")
            return cache
    novo = b3p.coletar(emissores, fundos)
    if not novo["empresas"] and cache:
        log("B3 proventos: consulta falhou, mantendo cache anterior")
        return cache
    novo["sem_resposta"] = sorted(set(emissores) - set(novo["empresas"]))
    _gravar_json(ARQ_PROV, novo)
    return novo


def _classe_isin(isin):
    """ON, PN ou UNIT pelo código ISIN da B3 (ACNOR = ON, ACNP* = PN, CDAM/UNT = unit)."""
    i = (isin or "").upper()
    if "ACNOR" in i:
        return "on"
    if "ACNP" in i:
        return "pn"
    return "outro"


def dy_b3(ticker, isin, preco, prov_emp, q_on, q_pn, mcap):
    """
    DY de 12 meses pela data-com (proventos brutos declarados ÷ preço), padrão de mercado.
    Usa o ISIN do próprio papel; se a B3 não listar proventos nesse ISIN (ex.: units),
    usa o total declarado pela empresa (ON × ações ON + PN × ações PN) ÷ valor de mercado.
    Devolve (dy, total_declarado_empresa, explicação).
    """
    if not prov_emp:
        return None, None, None
    itens = prov_emp.get("dinheiro") or []
    total_emp = None
    on = [i for i in itens if _classe_isin(i["isin"]) == "on"]
    pn = [i for i in itens if _classe_isin(i["isin"]) == "pn"]
    s_on, _ = b3p.soma_12m(on)
    if pn:
        por_isin = {}
        for i in pn:
            por_isin.setdefault(i["isin"], []).append(i)
        # várias classes PN (PNA, PNB): usa a de maior soma (simplificação conservadora não aplicada ao DY do papel)
        s_pn = max((b3p.soma_12m(v)[0] or 0) for v in por_isin.values())
    else:
        s_pn = None
    if (s_on or s_pn) and (q_on or q_pn):
        total_emp = (s_on or 0) * (q_on or 0) + (s_pn or 0) * (q_pn or 0)
    proprio, n = b3p.soma_12m(itens, isin)
    if proprio is not None and preco:
        return proprio / preco * 100, total_emp, f"{n} provento(s) com data-com em 12 meses, R$ {proprio:.4f} por ação"
    if total_emp is not None and mcap:
        return total_emp / mcap * 100, total_emp, "total declarado pela empresa ÷ valor de mercado"
    if itens and isin and preco:
        return 0.0, 0.0, "nenhum provento com data-com nos últimos 12 meses"
    return None, total_emp, None


def gerar_historico(ativos, diario, fund, fiis):
    anos = anos_fechados(ARQ_ANOS)
    tickers = {a["ticker"] for a in ativos} | set(REFERENCIAS_B3)
    h = montar_historico(tickers, anos, diario)
    ref = {}
    for t, (chave, nome) in REFERENCIAS_B3.items():
        if t in h["precos_m"] or t in h["precos_s"]:
            ref[chave] = {"nome": nome, "ticker": t, "m": h["precos_m"].pop(t, None), "s": h["precos_s"].pop(t, None)}
    ref.update(indice_cdi_ipca(h["meses"], h["semanas"]))
    h["referencias"] = ref
    anual = {}
    for a in ativos:
        if a["tipo"] == "acao" and a.get("cnpj"):
            f = fund["empresas"].get(a["cnpj"]) or {}
            if f.get("historico_anual"):
                anual[a["ticker"]] = f["historico_anual"]
    h["anual"] = anual
    h["fii_mensal"] = {t: f["historico"] for t, f in fiis.items() if f.get("historico")}
    h["gerado_em"] = datetime.now().isoformat(timespec="seconds")
    h["fontes"] = {"precos": "B3 COTAHIST (preço de fechamento; desdobramentos e grupamentos ajustados)",
                   "anual": "CVM DFP (demonstrações anuais)", "fii": "CVM informe mensal de FII",
                   "cdi": "Banco Central SGS 4391 (mensal) e 12 (diário)", "ipca": "Banco Central SGS 433"}
    with open(ARQ_HIST_JSON, "w", encoding="utf-8") as fp:
        json.dump(h, fp, ensure_ascii=False, separators=(",", ":"))
    log(f"Histórico comparativo: {len(h['precos_m'])} ativos com preço mensal, {len(h['ajustes'])} com "
        f"desdobramento/grupamento ajustado, referências {sorted(ref)}")


def montar():
    forcar = "--forcar" in sys.argv
    hoje = date.today()
    log("=== Início da coleta ATLAS ===")

    cot = cotacoes_do_dia()
    univ, anual = universo_mercado(cot, forcar)
    curados = {t for t, *_ in config.UNIVERSO}
    lista = [{"ticker": t, "tipo": tipo, "setor": setor, "grupo": grupo, "perfis": perfis, "curado": True}
             for t, tipo, setor, grupo, perfis in config.UNIVERSO]
    lista += [{"ticker": t, "tipo": "acao", "curado": False} for t in univ.get("acoes", []) if t not in curados]
    lista += [{"ticker": t, "tipo": "fii", "curado": False} for t in univ.get("fiis", []) if t not in curados]
    liq = univ.get("liquidez", {})

    alvo_hist = {x["ticker"] for x in lista} | set(REFERENCIAS_B3)
    if anual is None and os.path.exists(ARQ_HIST):
        # Ativos com menos de 30 dias no histórico diário são completados pelo arquivo anual da B3,
        # uma única vez por ativo (fica anotado em data/backfill.json).
        feitos = _ler_json(ARQ_BACKFILL) or {}
        cont = defaultdict(int)
        with open(ARQ_HIST, encoding="utf-8") as fp:
            for linha in fp:
                partes = linha.split(";")
                if len(partes) == 3:
                    cont[partes[1]] += 1
        faltam = sorted(t for t in alvo_hist if cont[t] < 30 and t not in feitos)
        if faltam:
            log(f"Histórico diário curto para {len(faltam)} ativo(s) ({faltam[:10]}); completando pelo arquivo anual")
            anual = cotacoes_anuais(min_pregoes=300)  # ano atual + anterior: 12 meses completos
            if anual:
                feitos.update({t: hoje.isoformat() for t in faltam})
                _gravar_json(ARQ_BACKFILL, feitos)
    historico = atualizar_historico(ARQ_HIST, alvo_hist, cot, anual=anual)

    # Sem negócio no último pregão: usa o último preço dos 30 dias anteriores (com aviso)
    ultimo = {}
    for (d, t), p in historico.items():
        if t not in cot and (t not in ultimo or d > ultimo[t][0]):
            ultimo[t] = (d, p)
    limite = (hoje - timedelta(days=30)).isoformat()
    sem_negocio = set()
    for x in lista:
        t = x["ticker"]
        if t not in cot and t in ultimo and ultimo[t][0] >= limite:
            cot[t] = {"ticker": t, "data": ultimo[t][0], "preco": ultimo[t][1], "volume": 0.0, "negocios": 0,
                      "codbdi": "12" if x["tipo"] == "fii" else "02", "isin": univ.get("isin", {}).get(t, "")}
            sem_negocio.add(t)
    if sem_negocio:
        log(f"Sem negócio no último pregão (usado o último preço até 30 dias): {sorted(sem_negocio)}")

    fund = fundamentos(forcar, [x["ticker"] for x in lista if x["tipo"] == "acao"],
                       [x["ticker"] for x in lista if x["curado"] and x["tipo"] == "acao"])
    fiis_isin = {x["ticker"]: cot.get(x["ticker"], {}).get("isin") for x in lista if x["tipo"] == "fii"}
    fiis = coletar_fiis(fiis_isin) if any(fiis_isin.values()) else {}
    macro = coletar_macro()
    prov = proventos_b3(forcar, sorted({x["ticker"][:4] for x in lista if x["tipo"] == "acao"}),
                        {t[:4]: f.get("cnpj") for t, f in fiis.items() if f.get("cnpj")})
    setores = fund.get("setores_cvm", {})
    nao_mapeados, fora = set(), []

    ativos, pendencias = [], []
    for x in lista:
        ticker, tipo, curado = x["ticker"], x["tipo"], x["curado"]
        c = cot.get(ticker)
        reg = {"ticker": ticker, "tipo": tipo, "setor": x.get("setor"), "grupo": x.get("grupo"),
               "perfis": x.get("perfis", []), "curado": curado,
               "preco": c["preco"] if c else None, "data_preco": c["data"] if c else None,
               "volume_dia": c["volume"] if c else None, "liquidez_media": liq.get(ticker),
               "ind": {}, "alertas": [], "avisos": []}
        r52 = resumo_52s(historico, ticker)
        if r52:
            reg["min_52s"], reg["max_52s"] = r52["min"], r52["max"]
            s_ = r52["serie"]
            pontos = 60 if curado else 30
            reg["serie"] = [[d, round(p, 2)] for d, p in s_[::max(1, len(s_) // pontos)]]
        if not c:
            reg["avisos"].append("sem cotação no último pregão disponível")
        elif ticker in sem_negocio:
            reg["avisos"].append(f"sem negócio no último pregão; preço de {c['data'][8:10]}/{c['data'][5:7]}/{c['data'][:4]}")

        if tipo == "acao":
            cnpj = fund["ticker_cnpj"].get(ticker)
            f = fund["empresas"].get(cnpj) if cnpj else None
            if not f:
                if curado:
                    pendencias.append(f"{ticker}: demonstrações da CVM não encontradas")
                    ativos.append(reg)
                else:
                    fora.append(ticker)
                continue
            if not curado:
                reg["setor_cvm"] = setores.get(cnpj)
                reg["setor"] = setor_atlas(setores.get(cnpj), nao_mapeados)
            reg.update({"empresa": f.get("nome"), "cnpj": cnpj, "banco": f.get("banco"),
                        "dt_balanco": f.get("dt_refer"), "periodo": f.get("periodo_ttm"),
                        "fonte_balanco": f.get("fonte_ultima")})
            if not curado and f.get("banco"):
                reg["setor"] = "Bancos e financeiro"
            luc, pl_ = f.get("lucro_ttm"), f.get("patrimonio_liquido")
            mcap = valor_de_mercado(ticker[:4], cot, f.get("acoes_on"), f.get("acoes_pn"), reg["avisos"])
            mcap, q_on, q_pn, ajustado = corrigir_escala_acoes(ticker, mcap, pl_, f.get("acoes_on"), f.get("acoes_pn"))
            if mcap and pl_ and pl_ > 0 and mcap / pl_ < 0.02:
                reg["avisos"].append("quantidade de ações informada à CVM inconsistente com o preço; "
                                     "valor de mercado e múltiplos descartados")
                mcap = None
            reg["acoes_circulacao"] = (q_on or 0) + (q_pn or 0)
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
            # Dividend yield: padrão de mercado pela data-com (B3); o cálculo pelo caixa (CVM) fica como apoio
            ind["dy_caixa"] = ind["dy"]
            ind["payout_caixa"] = ind["payout"]
            dyb, tot_decl, expl = dy_b3(ticker, (c or {}).get("isin"), reg["preco"],
                                        prov.get("empresas", {}).get(ticker[:4]), q_on, q_pn, mcap)
            if dyb is not None:
                ind["dy"] = dyb
                ind["dy_fonte"] = "B3 (data-com, 12 meses)"
                reg["dy_detalhe"] = expl
                if tot_decl is not None and luc and luc > 0:
                    ind["payout"] = tot_decl / luc * 100
            else:
                ind["dy_fonte"] = "CVM (pago no fluxo de caixa, 12 meses)"
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
            if ind.get("margem_liquida") is not None and abs(ind["margem_liquida"]) > 100:
                reg["avisos"].append(f"margem líquida de {_br(ind['margem_liquida'], 0)}% (lucro ou prejuízo maior que a "
                                     "receita: holding, ganho ou perda não recorrente); não entra na nota")
                ind["margem_liquida_bruta"] = ind["margem_liquida"]
                ind["margem_liquida"] = None
            reg["ind"] = ind
            reg["alertas"] = alertas_acao(ind, f)
            idade = (hoje - date.fromisoformat(f["dt_refer"])).days
            if idade > 150:
                reg["alertas"].append(f"Último balanço na CVM tem {idade} dias")
        else:
            f = fiis.get(ticker)
            if not f:
                if curado:
                    pendencias.append(f"{ticker}: informe mensal do FII não encontrado")
                    ativos.append(reg)
                else:
                    fora.append(ticker)
                continue
            reg.update({"empresa": f.get("nome"), "cnpj": f.get("cnpj"),
                        "segmento_cvm": f.get("segmento"), "mandato_cvm": f.get("mandato"),
                        "data_informe": f.get("data_informe")})
            if curado:
                log(f"{ticker}: CVM informa segmento '{f.get('segmento')}', mandato '{f.get('mandato')}' "
                    f"-> regra automática daria '{segmento_fii(f.get('segmento'), f.get('mandato'), f.get('nome'), f.get('carteira'))}' "
                    f"(lista curada usa '{reg['setor']}'); composição: "
                    f"{ {k: round(v, 2) for k, v in (composicao_fii(f.get('carteira')) or {}).items()} }")
            else:
                reg["setor"] = segmento_fii(f.get("segmento"), f.get("mandato"), f.get("nome"), f.get("carteira"))
            pvp_fii = _div(reg["preco"], f.get("vp_cota"))
            if pvp_fii is not None and not (0.1 <= pvp_fii <= 5):
                reg["avisos"].append(f"P/VP calculado ({_br(pvp_fii, 2)}) incompatível com o informe; descartado")
                pvp_fii = None
            reg["ind"] = {
                "p_vp": pvp_fii,
                "vp_cota": f.get("vp_cota"), "vp_var_12m": f.get("vp_var_12m"), "dy": f.get("dy_12m_cvm"),
                "patrimonio": f.get("patrimonio_liquido"), "cotistas": f.get("cotistas"),
                "meses_com_rendimento": f.get("meses_com_rendimento"),
                "liquidez_dia": reg["volume_dia"], "taxa_adm_mes": f.get("taxa_adm_mes"),
                "dy_cvm": f.get("dy_12m_cvm"), "dy_fonte": "CVM (informe mensal)",
            }
            pf = prov.get("fundos", {}).get(ticker[:4])
            if pf and reg["preco"]:
                soma, n = b3p.soma_12m(pf.get("dinheiro") or [], (c or {}).get("isin"))
                if soma is None:  # alguns fundos não informam o ISIN em cada rendimento
                    soma, n = b3p.soma_12m(pf.get("dinheiro") or [])
                if soma is not None and n >= 1:
                    reg["ind"]["dy"] = soma / reg["preco"] * 100
                    reg["ind"]["dy_fonte"] = "B3 (data-com, 12 meses)"
                    reg["dy_detalhe"] = f"{n} rendimento(s) com data-com em 12 meses, R$ {soma:.4f} por cota"
                    if f.get("meses_com_rendimento") is None:
                        reg["ind"]["meses_com_rendimento"] = min(12, n)
            if f.get("meses_com_rendimento") is not None and f["meses_com_rendimento"] < 12:
                reg["alertas"].append(f"Distribuiu rendimento em {f['meses_com_rendimento']} de 12 meses")
            if reg["ind"]["p_vp"] and reg["ind"]["p_vp"] > 1.2:
                reg["alertas"].append("Negociado bem acima do valor patrimonial")
        if not curado:
            reg["perfis"] = perfis_automaticos(tipo, reg["setor"], reg["ind"], reg.get("banco"))
            reg["perfis_auto"] = True
        ativos.append(reg)

    if nao_mapeados:
        log(f"Setores da CVM sem correspondência (ficaram em 'Outros'): {sorted(nao_mapeados)}")
    if fora:
        log(f"{len(fora)} ativo(s) do mercado sem dados oficiais suficientes ficaram de fora: {sorted(fora)}")

    # ---- Histórico comparativo (arquivo separado, carregado só na aba Histórico)
    try:
        gerar_historico(ativos, historico, fund, fiis)
    except Exception as e:  # noqa: BLE001
        import traceback
        log(f"Histórico comparativo: falhou ({e!r}); dados principais seguem normais")
        log(traceback.format_exc())

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
            "proventos": "B3 - Empresas listadas, eventos corporativos (dividendos, JCP e rendimentos pela data-com)",
            "setores": "CVM - Cadastro de companhias abertas (setor de atividade)",
        },
        "macro": macro,
        "universo": {
            "mercado_completo": config.MERCADO_COMPLETO,
            "curados": sum(1 for a in ativos if a["curado"]),
            "automaticos": sum(1 for a in ativos if not a["curado"]),
            "liquidez_minima_acoes": config.LIQUIDEZ_MINIMA_ACOES,
            "liquidez_minima_fiis": config.LIQUIDEZ_MINIMA_FIIS,
            "presenca_minima": getattr(config, "PRESENCA_MINIMA", 0),
            "pregoes_liquidez": config.PREGOES_LIQUIDEZ,
            "selecionado_em": univ.get("gerado_em"),
        },
        "ativos": ativos,
        "pendencias": pendencias,
    }
    os.makedirs(os.path.dirname(ARQ_JSON), exist_ok=True)
    with open(ARQ_JSON, "w", encoding="utf-8") as fp:
        json.dump(saida, fp, ensure_ascii=False, separators=(",", ":"))
    with open(ARQ_MD, "w", encoding="utf-8") as fp:
        fp.write(gerar_markdown(saida))
    ok = sum(1 for a in ativos if a["ind"])
    ok_c = sum(1 for a in ativos if a["ind"] and a["curado"])
    log(f"=== Fim: {ok} de {len(ativos)} ativos com indicadores ({ok_c} de {len(curados)} curados); "
        f"pendências: {len(pendencias)} ===")
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
