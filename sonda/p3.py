import csv, io, json, zipfile, urllib.request, collections
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=300) as r: return r.read()
out = {}
z = zipfile.ZipFile(io.BytesIO(get("https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip")))
cont = collections.Counter(); dre = collections.Counter(); bpp = collections.Counter()
for n in z.namelist():
    if "_con_" not in n: continue
    rd = csv.DictReader(io.StringIO(z.read(n).decode("latin-1")), delimiter=";")
    for r in rd:
        if r.get("ORDEM_EXERC", "").upper().startswith("PEN"): continue
        cd, ds = r["CD_CONTA"], r["DS_CONTA"].strip().lower()
        if "dfc_mi" in n and cd.startswith("6.02.") and cd.count(".") == 2: cont[(cd, ds[:70])] += 1
        if "dfc_mi" in n and cd == "6.01": cont[(cd, ds[:70])] += 1
        if "_dre_" in n and cd.startswith("3.06") and cd.count(".") <= 2: dre[(cd, ds[:60])] += 1
        if "_bpp_" in n and cd in ("2.01.04", "2.02.01", "2.01.04.01", "2.01.04.02"): bpp[(cd, ds[:60])] += 1
out["dfc_602"] = cont.most_common(80); out["dre_306"] = dre.most_common(25); out["bpp"] = bpp.most_common(15)
# FII trimestral
try:
    zt = zipfile.ZipFile(io.BytesIO(get("https://dados.cvm.gov.br/dados/FII/DOC/INF_TRIMESTRAL/DADOS/inf_trimestral_fii_2026.zip")))
    out["trim_arquivos"] = zt.namelist()
    out["trim"] = {}
    for n in zt.namelist():
        rd = list(csv.DictReader(io.StringIO(zt.read(n).decode("latin-1")), delimiter=";"))
        hg = [r for r in rd if "11.728.688" in json.dumps(r, ensure_ascii=False) or "11728688" in json.dumps(r)]
        out["trim"][n] = {"n": len(rd), "cols": list(rd[0].keys()) if rd else [], "hglg": hg[:6]}
except Exception as e:
    out["trim_erro"] = str(e)
json.dump(out, open("sonda/p3_saida.json", "w"), ensure_ascii=False, indent=0)
