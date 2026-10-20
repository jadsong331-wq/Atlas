import json, time, urllib.request, urllib.parse
U = "https://www3.bcb.gov.br/ifdata/rest/"
def get(path):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(U + path, headers={"User-Agent": "Mozilla/5.0"}), timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            err = str(e); time.sleep(5)
    return {"erro": err}
def arq(f):
    return get("arquivos?nomeArquivo=" + urllib.parse.quote(f, safe=""))
out = {}
rel = get("relatorios2025a2030")
out["dts"] = [r["dt"] for r in rel]
ult = rel[-1]
out["ult_files"] = [{k: v for k, v in f.items() if k != "trel"} | ({"trel": {k: f["trel"].get(k) for k in ("id", "n", "ifd", "v")} } if "trel" in f else {}) for f in ult["files"]]
trels = {f["trel"]["id"]: f["trel"] for f in ult["files"] if "trel" in f}
out["trels"] = trels  # definições completas dos relatórios
dt = ult["dt"]
base = [f["f"] for f in ult["files"]]
info = arq(next(f for f in base if "/info" in f))
out["info"] = info
cad = arq(next(f for f in base if "cadastro" in f and f.endswith("_1009.json")))
out["cad1009_n"] = len(cad) if isinstance(cad, list) else cad
NOMES = ("ITAU", "BRADESCO", "BB", "BANCO DO BRASIL", "SANTANDER", "BTG", "BANRISUL", "ABC", "PINE", "BMG", "BR PARTNERS", "MERCANTIL", "AMAZONIA", "BASA", "BANESTES", "BRB", "BANESE", "INTER", "PAN", "NORDESTE", "BNB", "CAIXA", "NU", "XP", "SAFRA")
out["cad1009"] = [c for c in cad if any(n in (c.get("c2") or "").upper() for n in NOMES)] if isinstance(cad, list) else None
out["cad1009_amostra"] = cad[:3] if isinstance(cad, list) else None
ents = {c["c0"] for c in (out["cad1009"] or [])}
amostra = {}
for f in base:
    if "/dados" in f:
        d = arq(f)
        if isinstance(d, dict) and "values" in d:
            amostra[f] = {"id": d.get("id"), "chaves": sorted(d)[:10], "n": len(d["values"]),
                          "ents": [x for x in d["values"] if str(x.get("e")) in ents]}
        else:
            amostra[f] = str(d)[:300]
out["dados"] = amostra
json.dump(out, open("sonda/ifdata_saida.json", "w"), ensure_ascii=False)
