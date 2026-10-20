# -*- coding: utf-8 -*-
"""
Indicadores de bancos do IF.data, o portal oficial do Banco Central com os dados de cada instituição
financeira (https://www3.bcb.gov.br/ifdata/). Usa os mesmos arquivos que o próprio portal carrega,
por conglomerado prudencial (o grupo inteiro que o Banco Central supervisiona).

Indicadores (data-base trimestral mais recente):
- Índice de Basileia: patrimônio de referência ÷ ativos ponderados pelo risco. Mínimo exigido no
  Brasil: 8% + 2,5% de adicional de conservação = 10,5% (bancos sistêmicos têm adicional extra).
- Índice de Capital Principal: capital de melhor qualidade ÷ ativos ponderados pelo risco.
- Inadimplência: carteira inadimplida (com arrasto) ÷ carteira de crédito total (relatório
  "por carteiras de instrumentos financeiros", regras da Resolução CMN 4.966).
- Ativos problemáticos: inadimplida + reestruturada/com sinais de perda ÷ carteira total.
- Eficiência: (despesas de pessoal + administrativas) ÷ (resultado de intermediação antes da perda
  esperada + transações de pagamento + tarifas + serviços). Menor é melhor. É o critério ATLAS sobre
  o IF.data; cada banco divulga o próprio índice com ajustes diferentes.
- Custo do crédito: perda esperada de operações de crédito no período, anualizada, ÷ carteira.

O resultado (DRE) do IF.data é acumulado no semestre: março e setembro têm 3 meses; junho e dezembro, 6.
"""

import json
import os
import time
import urllib.parse

from util import baixar, log

URL = "https://www3.bcb.gov.br/ifdata/rest/"
VERSAO = 2  # muda quando a regra de correspondência ou os cálculos mudam (refaz a coleta)

# códigos internos (lid) das colunas do IF.data a partir de 2025 (Res. CMN 4.966)
LID = {
    "basileia": 79664, "capital_principal": 79659,
    "cart_total": 24454, "inadimplida": 148834, "problematicos": 148833,
    "res_intermed": 141851, "perda_esperada": 141842, "perda_credito": 141840,
    "transacoes_pag": 141855, "tarifas": 141856, "servicos": 141857,
    "pessoal": 141858, "administrativas": 141859, "lucro": 141870,
    "ativo_total": 140220, "carteira": 141873, "patrimonio": 140246,
}

# raiz do ticker -> nome do conglomerado prudencial no cadastro do IF.data (conferido no cadastro de 06/2026)
CONGLOMERADO = {
    "BBDC": "BRADESCO", "ITUB": "ITAU", "BBAS": "BB", "SANB": "SANTANDER", "BPAC": "BTG PACTUAL",
    "BRSR": "BANRISUL", "ABCB": "ABC-BRASIL", "PINE": "PINE", "BMGB": "BMG", "BRBI": "BR PARTNERS",
    "BMEB": "MERCANTIL DO BRASIL", "BAZA": "BCO DA AMAZONIA S.A.", "BEES": "BANESTES", "BSLI": "BRB",
    "BNBR": "BCO DO NORDESTE DO BRASIL S.A.",
}
# quando o nome exato não está no cadastro: trechos aceitos no nome do conglomerado
TRECHOS = {"BGIP": ("BANESE", "SERGIPE"), "BSLI": ("BRB",), "BAZA": ("AMAZONIA",), "BNBR": ("NORDESTE DO BRASIL",)}


def _json(caminho, grande=False):
    for i in range(3):
        b = baixar(URL + caminho, silencioso=not grande)
        if b:
            try:
                return json.loads(b.decode("utf-8"))
            except ValueError:
                return None
        time.sleep(3 * (i + 1))
    return None


def _arq(nome, grande=False):
    return _json("arquivos?nomeArquivo=" + urllib.parse.quote(nome, safe=""), grande)


def _nome_base(nome):
    n = (nome or "").upper().strip()
    return n[:-len(" - PRUDENCIAL")].strip() if n.endswith(" - PRUDENCIAL") else n


def entidades_bancos(cadastro, bancos):
    """
    cadastro: linhas do cadastro de conglomerados prudenciais (c0 = código, c2 = nome, c33 = raiz do CNPJ).
    bancos: {ticker: cnpj}. Devolve {ticker: (codigo, nome)}.
    Primeiro pelo nome do conglomerado; se não achar, instituição independente pela raiz do CNPJ.
    """
    por_nome = {_nome_base(c.get("c2")): c for c in cadastro}
    por_cnpj = {(c.get("c33") or "").zfill(8): c for c in cadastro if (c.get("c33") or "").isdigit()}
    out = {}
    for t, cnpj in bancos.items():
        c = por_nome.get(CONGLOMERADO.get(t[:4], "\0"))
        if c is None and t[:4] in TRECHOS:
            achados = [v for n, v in por_nome.items() if any(x in n for x in TRECHOS[t[:4]])]
            if len(achados) == 1:
                c = achados[0]
        if c is None and cnpj:
            c = por_cnpj.get(str(cnpj)[:8])
        if c is not None:
            out[t] = (str(c["c0"]), (c.get("c2") or "").strip())
    return out


def _meses_no_resultado(anomes):
    return 3 if str(anomes)[4:6] in ("03", "09") else 6


def calcular(v, anomes):
    """v: {lid: valor} de uma instituição. Devolve indicadores em %."""
    g = lambda k: v.get(LID[k])  # noqa: E731
    out = {}
    if g("basileia") is not None and g("basileia") > 0:
        out["basileia"] = g("basileia") * 100
    if g("capital_principal") is not None and g("capital_principal") > 0:
        out["capital_principal"] = g("capital_principal") * 100
    tot = g("cart_total")
    if tot and tot > 0:
        if g("inadimplida") is not None:
            out["inadimplencia"] = g("inadimplida") / tot * 100
        if g("problematicos") is not None:
            out["ativos_problematicos"] = g("problematicos") / tot * 100
    desp = [g("pessoal"), g("administrativas")]
    rec = [g("res_intermed"), g("perda_esperada"), g("transacoes_pag"), g("tarifas"), g("servicos")]
    if all(x is not None for x in desp + rec):
        receita = rec[0] - rec[1] + rec[2] + rec[3] + rec[4]   # intermediação antes da perda esperada
        if receita > 0:
            out["eficiencia"] = -(desp[0] + desp[1]) / receita * 100
    cart = g("carteira")
    if g("perda_credito") is not None and cart and cart > 0:
        out["custo_credito"] = -g("perda_credito") * (12 / _meses_no_resultado(anomes)) / cart * 100
    for k in ("ativo_total", "carteira", "patrimonio", "lucro"):
        if g(k) is not None:
            out[k] = g(k)
    out["meses_resultado"] = _meses_no_resultado(anomes)
    return out


def coletar(bancos, arq_cache):
    """
    bancos: {ticker: cnpj} das ações classificadas como banco.
    Usa cache em arq_cache; só baixa os arquivos grandes quando sai uma data-base nova.
    """
    cache = {}
    if os.path.exists(arq_cache):
        try:
            cache = json.load(open(arq_cache, encoding="utf-8"))
        except ValueError:
            cache = {}
    lista = _json("relatorios2025a2030")
    if not isinstance(lista, list) or not lista:
        log("IF.data: o Banco Central não respondeu; ficam os dados da última coleta" if cache else
            "IF.data: o Banco Central não respondeu")
        return cache
    ult = max(lista, key=lambda r: r.get("dt", 0))
    dt = ult["dt"]
    if cache.get("versao") == VERSAO and cache.get("data_base") == dt and set(bancos) <= set(cache.get("bancos", {})) | set(cache.get("sem_dado", [])):
        log(f"IF.data: data-base {dt} já coletada")
        return cache
    arquivos = [f["f"] for f in ult.get("files", [])]
    f_cad = next((f for f in arquivos if "cadastro" in f and f.endswith("_1009.json")), None)
    cad = _arq(f_cad) if f_cad else None
    if not isinstance(cad, list):
        log("IF.data: cadastro indisponível; ficam os dados da última coleta")
        return cache
    ent = entidades_bancos(cad, bancos)
    alvo = {cod for cod, _ in ent.values()}
    valores = {}
    lidos = 0
    for f in arquivos:
        if "/dados" not in f:
            continue
        d = _arq(f, grande=True)
        if not isinstance(d, dict):
            log(f"IF.data: arquivo {f} indisponível")
            continue
        lidos += 1
        for e in d.get("values", []):
            if str(e.get("e")) in alvo:
                vv = valores.setdefault(str(e["e"]), {})
                for x in e.get("v", []):
                    vv[x["i"]] = x["v"]
    if not lidos:
        log("IF.data: nenhum arquivo de dados respondeu; ficam os dados da última coleta")
        return cache
    saida = {"versao": VERSAO, "data_base": dt, "fonte": "Banco Central - IF.data (conglomerado prudencial)",
             "bancos": {}, "sem_dado": sorted(set(bancos) - set(ent))}
    for t, (cod, nome) in ent.items():
        ind = calcular(valores.get(cod, {}), dt)
        if ind:
            saida["bancos"][t] = {"codigo": cod, "instituicao": nome, **ind}
    json.dump(saida, open(arq_cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"IF.data {dt}: {len(saida['bancos'])} bancos com indicadores; sem correspondência: {saida['sem_dado']}")
    return saida
