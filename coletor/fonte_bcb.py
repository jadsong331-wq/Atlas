# -*- coding: utf-8 -*-
"""Macro oficial do Banco Central: SGS e Boletim Focus (API Olinda)."""

import json
import urllib.parse
from datetime import date, timedelta

from util import baixar, log

SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{s}/dados/ultimos/{n}?formato=json"
SGS_PERIODO = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.{s}/dados?formato=json"
               "&dataInicial={ini}&dataFinal={fim}")
FOCUS = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"

SERIES = {
    "selic": (432, "Meta Selic (% a.a.)"),
    "ipca_12m": (13522, "IPCA acumulado 12 meses (%)"),
    "ipca_mes": (433, "IPCA do mês (%)"),
    "dolar": (1, "Dólar comercial venda (R$)"),
}


def _json(url):
    b = baixar(url)
    if not b:
        return None
    try:
        return json.loads(b.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        log(f"BCB: resposta inválida ({e})")
        return None


def sgs(serie, n=1):
    dados = _json(SGS.format(s=serie, n=n))
    if not dados:
        return None
    try:
        return [{"data": d["data"], "valor": float(str(d["valor"]).replace(",", "."))} for d in dados]
    except Exception:  # noqa: BLE001
        return None


def sgs_periodo(serie, inicio, fim):
    """Série do SGS entre duas datas (a consulta "últimos N" aceita no máximo 20 valores)."""
    url = SGS_PERIODO.format(s=serie, ini=inicio.strftime("%d/%m/%Y"), fim=fim.strftime("%d/%m/%Y"))
    bruto = baixar(url)
    try:
        dados = json.loads(bruto.decode("utf-8")) if bruto else None
    except Exception:  # noqa: BLE001
        dados = None
    if not isinstance(dados, list):
        log(f"BCB: série {serie} devolveu resposta inesperada: {(bruto or b'')[:300]!r}")
        return None
    try:
        return [{"data": d["data"], "valor": float(str(d["valor"]).replace(",", "."))} for d in dados]
    except Exception:  # noqa: BLE001
        return None


def focus(indicador, anos):
    params = urllib.parse.urlencode({
        "$top": "60",
        "$filter": f"Indicador eq '{indicador}' and baseCalculo eq 0",
        "$orderby": "Data desc",
        "$format": "json",
        "$select": "Indicador,Data,DataReferencia,Mediana",
    }, quote_via=urllib.parse.quote)
    dados = _json(f"{FOCUS}?{params}")
    if not dados or not dados.get("value"):
        return None, {}
    linhas = dados["value"]
    ultima = max(l["Data"] for l in linhas)
    res = {}
    for l in linhas:
        if l["Data"] == ultima and str(l["DataReferencia"]) in {str(a) for a in anos}:
            res[str(l["DataReferencia"])] = float(l["Mediana"])
    return ultima, res


def coletar_macro():
    hoje = date.today()
    anos = [hoje.year, hoje.year + 1]
    macro = {"series": {}, "focus": {}, "focus_data": None}
    for chave, (serie, nome) in SERIES.items():
        v = sgs(serie, 1)
        macro["series"][chave] = {"nome": nome, "valor": v[-1]["valor"] if v else None,
                                  "data": v[-1]["data"] if v else None, "serie_sgs": serie}
    # A série 432 (meta Selic) é diária e já traz a data da próxima reunião do Copom.
    # Usa o valor vigente hoje e compara com a meta anterior diferente.
    hist = sgs_periodo(432, hoje - timedelta(days=400), hoje)
    if hist:
        hoje_iso = hoje.isoformat()
        iso = lambda d: f"{d[6:10]}-{d[3:5]}-{d[0:2]}"  # noqa: E731
        vigentes = [h for h in hist if iso(h["data"]) <= hoje_iso] or hist
        atual = vigentes[-1]["valor"]
        macro["series"]["selic"].update({"valor": atual, "data": vigentes[-1]["data"]})
        anterior = next((h for h in reversed(vigentes) if h["valor"] != atual), None)
        if anterior:
            macro["selic_tendencia"] = "queda" if atual < anterior["valor"] else "alta"
            macro["selic_anterior"] = {"valor": anterior["valor"], "ate": anterior["data"]}
        else:
            macro["selic_tendencia"] = "estável"
    for ind, chave in [("IPCA", "ipca"), ("Selic", "selic"), ("PIB Total", "pib"), ("Câmbio", "cambio")]:
        d, vals = focus(ind, anos)
        macro["focus"][chave] = vals
        macro["focus_data"] = macro["focus_data"] or d
    s, i = macro["series"]["selic"]["valor"], macro["series"]["ipca_12m"]["valor"]
    macro["juro_real"] = ((1 + s / 100) / (1 + i / 100) - 1) * 100 if s is not None and i is not None else None
    log("Macro coletado" if s is not None else "Macro: falha na Selic")
    return macro


# ---------------------------------------------------------------------------
# Tesouro Direto (Tesouro Transparente): juro real dos títulos atrelados ao IPCA
# ---------------------------------------------------------------------------
URL_TESOURO = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
               "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv")


def juro_real_tesouro():
    """
    Taxa de compra (juro real, % a.a.) do Tesouro IPCA+ de vencimento mais longo na data mais recente.
    Referência de Graham/Dalio para quem investe no longo prazo: quanto paga o título público sem risco
    acima da inflação.
    """
    import csv
    import io
    from util import coluna, num_br, sem_acento
    b = baixar(URL_TESOURO)
    if not b:
        return None
    try:
        txt = b.decode("latin-1")
    except Exception:  # noqa: BLE001
        return None
    rd = csv.DictReader(io.StringIO(txt), delimiter=";")
    c_tipo = coluna(rd.fieldnames, "Tipo Titulo")
    c_venc = coluna(rd.fieldnames, "Data Vencimento")
    c_base = coluna(rd.fieldnames, "Data Base")
    c_taxa = coluna(rd.fieldnames, "Taxa Compra Manha")
    if not all((c_tipo, c_venc, c_base, c_taxa)):
        log(f"Tesouro: colunas não reconhecidas {rd.fieldnames}")
        return None
    iso = lambda d: f"{d[6:10]}-{d[3:5]}-{d[0:2]}" if d and len(d) >= 10 else ""  # noqa: E731
    linhas = []
    for r in rd:
        tipo = sem_acento(r.get(c_tipo) or "")
        if "ipca" not in tipo or "semestra" in tipo or "renda" in tipo or "educa" in tipo:
            continue
        taxa = num_br(r.get(c_taxa))
        if taxa is None or taxa <= 0:
            continue
        linhas.append((iso(r.get(c_base)), iso(r.get(c_venc)), taxa, r.get(c_tipo)))
    if not linhas:
        log("Tesouro: nenhum Tesouro IPCA+ encontrado no arquivo")
        return None
    base = max(l[0] for l in linhas)
    hoje_ = [l for l in linhas if l[0] == base]
    venc = max(hoje_, key=lambda l: l[1])
    log(f"Tesouro: {venc[3]} {venc[1][:4]} paga IPCA + {venc[2]:.2f}% (base {base})")
    return {"valor": venc[2], "titulo": f"{venc[3]} {venc[1][:4]}", "data": f"{base[8:10]}/{base[5:7]}/{base[:4]}",
            "fonte": "Tesouro Transparente - taxas dos títulos ofertados pelo Tesouro Direto"}
