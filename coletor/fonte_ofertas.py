# -*- coding: utf-8 -*-
"""
Ofertas públicas de cotas de fundos (FII, FIAGRO, FI-Infra) e de títulos de crédito para o público
em geral, pelo conjunto de dados oficial da CVM "Ofertas Públicas de Distribuição"
(https://dados.cvm.gov.br/dataset/oferta-distrib), atualizado diariamente pela CVM.

- oferta_resolucao_160.csv: ofertas do rito automático da Resolução CVM 160 (desde 2023),
  que é o caminho da maioria das emissões de fundos.
- oferta_distribuicao.csv: ofertas do rito ordinário e regras antigas.

A CVM traz dados cadastrais (emissor, valor, datas, coordenador, gestor, onde a cota será negociada,
destinação dos recursos). Renda projetada, imóveis e inquilinos ficam no prospecto e no material
publicitário; por isso a avaliação da oferta no app é preenchida pelo usuário.
"""

import csv
import io
import zipfile
from datetime import date, timedelta

from util import baixar, log, num_br, sem_acento, so_digitos

URL = "https://dados.cvm.gov.br/dados/OFERTA/DISTRIB/DADOS/oferta_distribuicao.zip"
URL_FNET = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM?cnpjFundo={cnpj}"
DIAS_ENCERRADAS = 120      # ofertas encerradas que continuam na lista
DIAS_VALIDADE = 210        # oferta sem encerramento registrada há mais tempo é tratada como vencida


def tipo_oferta(valor_mobiliario, publico):
    """Tipo para o app, ou None se a oferta não interessa (fundos de outros tipos, crédito só para profissionais)."""
    v = sem_acento(valor_mobiliario or "")
    if "cota" in v:
        if "fiagro" in v:
            return "FIAGRO"
        if "infra" in v:
            return "FI-Infra"
        if "fii" in v or "imobiliari" in v:
            return "FII"
        return None
    if "geral" not in sem_acento(publico or ""):
        return None
    if "imobiliari" in v and "receb" in v:
        return "CRI"
    if "agronegocio" in v and "receb" in v:
        return "CRA"
    if "debenture" in v:
        return "Debênture"
    return None


def mercado(txt):
    t = sem_acento(txt or "")
    if not t:
        return "não informado"
    if "fundos21" in t or "cetip" in t:
        return "balcão"
    if "segmento listado" in t or "mercado de bolsa" in t or "bolsa de valores" in t:
        return "bolsa"
    if "bolsa" in t and "balc" not in t:
        return "bolsa"
    if "balc" in t:
        return "balcão"
    return "não informado"


def _data(txt):
    t = (txt or "").strip()[:10]
    if len(t) == 10 and t[4] == "-":
        return t
    if len(t) == 10 and t[2] == "/":
        return f"{t[6:10]}-{t[3:5]}-{t[0:2]}"
    return None


def _ler(zb, nome):
    z = zipfile.ZipFile(io.BytesIO(zb))
    arq = next((n for n in z.namelist() if n.lower().endswith(nome)), None)
    if not arq:
        return []
    return list(csv.DictReader(io.StringIO(z.read(arq).decode("latin-1")), delimiter=";"))


def _situacao(status, registro, encerramento, hoje):
    s = sem_acento(status or "")
    if encerramento or "encerrad" in s:
        return "encerrada"
    if any(x in s for x in ("caduc", "cancel", "revog", "indeferid", "desist", "arquiv")):
        return "cancelada"
    if "suspens" in s:
        return "suspensa"
    if registro and registro < (hoje - timedelta(days=DIAS_VALIDADE)).isoformat():
        return "vencida"
    if registro:
        return "aberta"
    return "em análise"


def montar(linhas_160, linhas_antigas, hoje=None):
    hoje = hoje or date.today()
    limite = (hoje - timedelta(days=DIAS_ENCERRADAS)).isoformat()
    out = {}
    for r in linhas_160:
        tipo = tipo_oferta(r.get("Valor_Mobiliario"), r.get("Publico_alvo"))
        if not tipo:
            continue
        reg, enc = _data(r.get("Data_Registro")), _data(r.get("Data_Encerramento"))
        sit = _situacao(r.get("Status_Requerimento"), reg, enc, hoje)
        if sit in ("cancelada", "vencida", "em análise") or (sit == "encerrada" and (enc or reg or "") < limite):
            continue
        valor, qtde = num_br(r.get("Valor_Total_Registrado")), num_br(r.get("Qtde_Total_Registrada"))
        cnpj = so_digitos(r.get("CNPJ_Emissor"))
        k = r.get("Numero_Requerimento") or f"{cnpj}-{r.get('Emissao')}"
        out[k] = {
            "id": k, "processo": (r.get("Numero_Processo") or "").strip(), "rito": "automático (Res. CVM 160)",
            "tipo": tipo, "valor_mobiliario": (r.get("Valor_Mobiliario") or "").strip(),
            "emissor": (r.get("Nome_Emissor") or "").strip(), "cnpj": cnpj, "emissao": (r.get("Emissao") or "").strip(),
            "inicial": (r.get("Oferta_inicial") or "").strip().upper() == "S",
            "valor": valor, "quantidade": qtde,
            "preco": round(valor / qtde, 4) if valor and qtde else None,
            "data_registro": reg, "data_encerramento": enc, "situacao": sit,
            "status_cvm": (r.get("Status_Requerimento") or "").strip(),
            "publico": (r.get("Publico_alvo") or "").strip(),
            "lider": (r.get("Nome_Lider") or "").strip(), "gestor": (r.get("Gestor") or "").strip(),
            "administrador": (r.get("Administrador") or "").strip(),
            "regime": (r.get("Regime_distribuicao") or "").strip(),
            "mercado": mercado(r.get("Mercado_negociacao")),
            "mercado_txt": (r.get("Mercado_negociacao") or "").strip()[:300],
            "destinacao": (r.get("Destinacao_recursos") or "").strip()[:600],
            "incentivado": (r.get("Titulo_incentivado") or "").strip().upper() == "S",
            "investidores_pf": int(num_br(r.get("Num_Invest_Pessoa_Natural")) or 0) or None,
            "documentos": URL_FNET.format(cnpj=cnpj) if tipo in ("FII", "FIAGRO", "FI-Infra") and cnpj else None,
        }
    for r in linhas_antigas:
        tipo = tipo_oferta(r.get("Tipo_Ativo"), "público geral")
        if not tipo:
            continue
        reg = _data(r.get("Data_Registro_Oferta")) or _data(r.get("Data_Inicio_Oferta"))
        enc = _data(r.get("Data_Encerramento_Oferta"))
        if not reg or reg < (hoje - timedelta(days=365)).isoformat():
            continue
        sit = _situacao(r.get("Ultimo_Comunicado"), reg, enc, hoje)
        if sit in ("cancelada", "vencida") or (sit == "encerrada" and (enc or reg) < limite):
            continue
        cnpj = so_digitos(r.get("CNPJ_Emissor"))
        k = r.get("Numero_Registro_Oferta") or r.get("Numero_Processo") or f"{cnpj}-{r.get('Emissao')}"
        if k in out:
            continue
        valor = num_br(r.get("Valor_Total"))
        out[k] = {
            "id": k, "processo": (r.get("Numero_Processo") or "").strip(), "rito": (r.get("Rito_Oferta") or "").strip(),
            "tipo": tipo, "valor_mobiliario": (r.get("Tipo_Ativo") or "").strip(),
            "emissor": (r.get("Nome_Emissor") or "").strip(), "cnpj": cnpj, "emissao": (r.get("Emissao") or "").strip(),
            "inicial": (r.get("Oferta_Inicial") or "").strip().upper() in ("S", "SIM"),
            "valor": valor, "quantidade": num_br(r.get("Quantidade_Total")), "preco": num_br(r.get("Preco_Unitario")),
            "data_registro": reg, "data_encerramento": enc, "situacao": sit,
            "status_cvm": (r.get("Ultimo_Comunicado") or "").strip(), "publico": "",
            "lider": (r.get("Nome_Lider") or "").strip(), "gestor": "", "administrador": "",
            "regime": (r.get("Modalidade_Oferta") or "").strip(), "mercado": "não informado", "mercado_txt": "",
            "destinacao": "", "incentivado": (r.get("Oferta_Incentivo_Fiscal") or "").strip().upper() in ("S", "SIM"),
            "investidores_pf": int(num_br(r.get("Nr_Pessoa_Fisica")) or 0) or None,
            "documentos": URL_FNET.format(cnpj=cnpj) if tipo in ("FII", "FIAGRO", "FI-Infra") and cnpj else None,
        }
    lista = sorted(out.values(), key=lambda o: (o["situacao"] != "aberta", -(int((o["data_registro"] or "0000-00-00").replace("-", "")))))
    return lista


def coletar(hoje=None):
    zb = baixar(URL)
    if not zb:
        log("Ofertas: a CVM não respondeu")
        return None
    l160, lant = _ler(zb, "oferta_resolucao_160.csv"), _ler(zb, "oferta_distribuicao.csv")
    lista = montar(l160, lant, hoje)
    from collections import Counter
    log(f"Ofertas CVM: {len(l160)} do rito automático e {len(lant)} das demais lidas; na lista: {len(lista)} "
        f"({dict(Counter((o['tipo'], o['situacao']) for o in lista))})")
    return lista
