import csv, io, json, zipfile, urllib.request
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=300) as r:
        return r.read()
out = {}
for nome, url in [("dados", "https://dados.cvm.gov.br/dados/OFERTA/DISTRIB/DADOS/oferta_distribuicao.zip"),
                  ("meta", "https://dados.cvm.gov.br/dados/OFERTA/DISTRIB/META/meta_oferta_distribuicao.zip")]:
    z = zipfile.ZipFile(io.BytesIO(get(url)))
    out[nome] = {}
    for f in z.namelist():
        b = z.read(f)
        txt = b.decode("latin-1")
        if nome == "meta":
            out[nome][f] = txt[:20000]; continue
        rd = list(csv.DictReader(io.StringIO(txt), delimiter=";"))
        cols = list(rd[0].keys()) if rd else []
        imob = [r for r in rd if any("IMOBILI" in (v or "").upper() or "FIAGRO" in (v or "").upper() or "INFRA" in (v or "").upper() for v in r.values())]
        imob.sort(key=lambda r: max((v for k, v in r.items() if k and "Data" in k and v), default=""), reverse=True)
        out[nome][f] = {"n": len(rd), "cols": cols, "n_imob": len(imob), "amostra": imob[:25],
                        "spx": [r for r in rd if "SPX PORTF" in json.dumps(r, ensure_ascii=False).upper()]}
json.dump(out, open("sonda/ofertas_saida.json", "w"), ensure_ascii=False, indent=1)
