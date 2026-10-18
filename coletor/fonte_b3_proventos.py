# -*- coding: utf-8 -*-
"""
Proventos e eventos societários publicados pela B3 (página "Empresas listadas" ->
"Eventos corporativos"), a mesma base que a bolsa usa no próprio site.

- Dividendos e JCP declarados, com a data-com (último dia "com" direito) e o valor
  bruto por ação. É o padrão de mercado para o dividend yield de 12 meses.
- Desdobramentos, grupamentos e bonificações com o fator oficial.
- Rendimentos de FIIs (cadastro de fundos listados da B3).

As respostas são guardadas em data/proventos_b3.json e renovadas a cada N dias.
Se a B3 não responder, o ATLAS segue com o cálculo pelo fluxo de caixa da CVM.
"""

import base64
import json
import time
from datetime import date, datetime

from util import baixar, log, num_br, sem_acento

URL_EMPRESA = ("https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/"
               "GetListedSupplementCompany/{p}")
URL_FUNDO = ("https://sistemaswebb3-listados.b3.com.br/fundsProxy/fundsCall/"
             "GetListedSupplementFunds/{p}")


def _b64(obj):
    return base64.b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode()


def _json(url):
    b = baixar(url, silencioso=True)
    if not b:
        return None
    try:
        return json.loads(b.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _data(txt):
    """'dd/mm/aaaa' -> 'aaaa-mm-dd' (ou None)."""
    t = (txt or "").strip()[:10]
    if len(t) == 10 and t[2] == "/" and t[5] == "/":
        return f"{t[6:10]}-{t[3:5]}-{t[0:2]}"
    if len(t) == 10 and t[4] == "-":
        return t
    return None


def _g(d, *chaves):
    for k in chaves:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _normalizar(bruto):
    """Converte a resposta da B3 em {'dinheiro': [...], 'acoes': [...]} (formato estável do ATLAS)."""
    if isinstance(bruto, list):
        bruto = bruto[0] if bruto else {}
    if not isinstance(bruto, dict):
        return None
    din, aco = [], []
    for c in bruto.get("cashDividends") or []:
        isin = (_g(c, "isinCode", "assetIsin", "isin") or "").strip().upper()
        din.append({
            "isin": isin, "tipo": (_g(c, "label", "corporateAction") or "").strip().upper(),
            "data_com": _data(_g(c, "lastDatePrior", "lastDatePriorEx")),
            "pagamento": _data(_g(c, "paymentDate")),
            "aprovado": _data(_g(c, "approvedOn", "approvalDate")),
            "valor": num_br(_g(c, "rate", "valuePerShare")),
            "ref": (_g(c, "relatedTo") or "").strip(),
        })
    for s in bruto.get("stockDividends") or []:
        aco.append({
            "isin": (_g(s, "isinCode", "assetIsin", "isin") or "").strip().upper(),
            "tipo": (_g(s, "label") or "").strip().upper(),
            "data_com": _data(_g(s, "lastDatePrior")),
            "fator": num_br(_g(s, "factor")),
            "obs": (_g(s, "remarks") or "").strip()[:200],
        })
    return {"dinheiro": din, "acoes": aco}


def coletar(emissores, fundos=None, pausa=0.25):
    """
    emissores: códigos de 4 letras das empresas (ex.: "PETR").
    fundos: {codigo_4_letras: cnpj} dos FIIs.
    Devolve {"empresas": {codigo: normalizado}, "fundos": {...}, "gerado_em": ...}.
    """
    saida = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "empresas": {}, "fundos": {}}
    amostra = False
    falhas = 0
    for cod in sorted(set(emissores)):
        bruto = _json(URL_EMPRESA.format(p=_b64({"issuingCompany": cod, "language": "pt-br"})))
        if bruto is None:
            falhas += 1
            if falhas >= 15 and not saida["empresas"]:
                log("B3 proventos: o site não está respondendo; ficam os dados da CVM")
                return saida
            continue
        if not amostra:
            obj = bruto[0] if isinstance(bruto, list) and bruto else bruto
            if isinstance(obj, dict):
                log(f"B3 proventos: campos da resposta {sorted(obj)[:30]}; "
                    f"exemplo de provento {(obj.get('cashDividends') or [None])[0]}; "
                    f"exemplo de evento {(obj.get('stockDividends') or [None])[0]}")
                amostra = True
        n = _normalizar(bruto)
        if n is not None:
            saida["empresas"][cod] = n
        time.sleep(pausa)
    amostra = False
    for cod, cnpj in sorted((fundos or {}).items()):
        bruto = _json(URL_FUNDO.format(p=_b64({"cnpj": cnpj, "identifierFund": cod, "typeFund": 7})))
        if bruto is None:
            continue
        if not amostra and isinstance(bruto, dict):
            log(f"B3 FII: campos da resposta {sorted(bruto)[:30]}; exemplo "
                f"{(bruto.get('cashDividends') or [None])[0]}")
            amostra = True
        n = _normalizar(bruto)
        if n is not None:
            saida["fundos"][cod] = n
        time.sleep(pausa)
    log(f"B3 proventos: {len(saida['empresas'])} de {len(set(emissores))} empresas e "
        f"{len(saida['fundos'])} de {len(fundos or {})} FIIs")
    return saida


def eh_rendimento(tipo):
    t = sem_acento(tipo or "")
    return any(k in t for k in ("dividendo", "jrs cap", "juros", "rendimento")) and "amortiz" not in t


def soma_12m(itens, isin=None, hoje=None):
    """Soma por ação (bruto) dos proventos com data-com nos últimos 12 meses. None se não houver dado."""
    hoje = hoje or date.today()
    ini = date(hoje.year - 1, hoje.month, min(hoje.day, 28)).isoformat()
    sel = [i for i in itens if eh_rendimento(i["tipo"]) and i.get("data_com") and i["valor"] is not None
           and ini < i["data_com"] <= hoje.isoformat() and (not isin or i["isin"] == isin)]
    if not sel:
        return None, 0
    vistos, total = set(), 0.0
    for i in sel:  # a B3 às vezes repete o mesmo evento; remove duplicados exatos
        k = (i["isin"], i["tipo"], i["data_com"], round(i["valor"], 8))
        if k in vistos:
            continue
        vistos.add(k)
        total += i["valor"]
    return total, len(vistos)
