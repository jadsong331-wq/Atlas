# -*- coding: utf-8 -*-
"""Funções de apoio: download, leitura de ZIP/CSV e registro de log."""

import csv
import io
import time
import unicodedata
import urllib.request
import zipfile
from datetime import datetime

HEADERS = {
    "User-Agent": "ATLAS-Invest-Research/1.0 (coletor de dados publicos; uso pessoal)",
    "Accept": "*/*",
}
TIMEOUT = 120
TENTATIVAS = 3

LOG = []


def log(msg):
    linha = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    LOG.append(linha)
    print(linha, flush=True)


def baixar(url, obrigatorio=False):
    """Baixa um arquivo e devolve os bytes. None se falhar (ou erro, se obrigatório)."""
    erro = None
    for i in range(1, TENTATIVAS + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                dados = r.read()
            log(f"OK {url} ({len(dados) / 1e6:.1f} MB)")
            return dados
        except Exception as e:  # noqa: BLE001
            erro = e
            code = getattr(e, "code", None)
            if code == 404:
                break
            time.sleep(3 * i)
    log(f"FALHA {url} -> {erro}")
    if obrigatorio:
        raise RuntimeError(f"Não foi possível baixar {url}: {erro}")
    return None


def sem_acento(txt):
    txt = unicodedata.normalize("NFKD", str(txt))
    return "".join(c for c in txt if not unicodedata.combining(c)).lower().strip()


def ler_csv_do_zip(zbytes, contem, encoding="latin-1"):
    """
    Abre, dentro de um ZIP, o CSV cujo nome contém todos os trechos de `contem`
    (lista) e devolve um gerador de dicts. None se o arquivo não existir.
    """
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    alvo = None
    for nome in z.namelist():
        n = nome.lower()
        if all(c.lower() in n for c in contem):
            alvo = nome
            break
    if alvo is None:
        return None
    bruto = z.read(alvo)
    try:
        texto = bruto.decode(encoding)
    except UnicodeDecodeError:
        texto = bruto.decode("utf-8", errors="replace")
    return csv.DictReader(io.StringIO(texto), delimiter=";")


def coluna(campos, *candidatos):
    """Acha o nome real de uma coluna, ignorando maiúsculas e acentos."""
    mapa = {sem_acento(c): c for c in campos}
    for cand in candidatos:
        k = sem_acento(cand)
        if k in mapa:
            return mapa[k]
    for cand in candidatos:  # busca por trecho
        k = sem_acento(cand)
        for norm, real in mapa.items():
            if k in norm:
                return real
    return None


def num_br(valor):
    """Converte '1.234,56' ou '1234.56' em float. None se vazio."""
    if valor is None:
        return None
    s = str(valor).strip()
    if s == "":
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def so_digitos(txt):
    return "".join(c for c in str(txt or "") if c.isdigit())
