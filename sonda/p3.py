import csv, io, json, zipfile, urllib.request, collections
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=300) as r: return r.read()
out = {}
z = zipfile.ZipFile(io.BytesIO(get("https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip")))
cont = collections.Counter(); dre = collections.Counter(); bpp = collections.Counter()
for n in z.namelist():
    n0 = n; n = n.lower()
    if "_con_" not in n: continue
    rd = csv.DictReader(io.StringIO(z.read(n0).decode("latin-1")), delimiter=";")
    for r in rd:
        if not r.get("ORDEM_EXERC", "").upper().startswith("\xdaLT") and not r.get("ORDEM_EXERC", "").upper().startswith("ULT"): continue
        cd, ds = r["CD_CONTA"], r["DS_CONTA"].strip().lower()
        if "dfc_mi" in n and cd.startswith("6.02.") and cd.count(".") == 2: cont[(cd, ds[:70])] += 1
        if "dfc_mi" in n and cd == "6.01": cont[(cd, ds[:70])] += 1
        if "_dre_" in n and cd.startswith("3.06") and cd.count(".") <= 2: dre[(cd, ds[:60])] += 1
        if "_bpp_" in n and cd in ("2.01.04", "2.02.01", "2.01.04.01", "2.01.04.02"): bpp[(cd, ds[:60])] += 1
out["dfc_602"] = cont.most_common(80); out["dre_306"] = dre.most_common(25); out["bpp"] = bpp.most_common(15)
json.dump(out, open("sonda/p3_saida.json", "w"), ensure_ascii=False, indent=0)
