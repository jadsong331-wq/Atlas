import csv, io, json, zipfile, urllib.request
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=300) as r: return r.read()
z = zipfile.ZipFile(io.BytesIO(get("https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_2026.zip")))
alvo = {"30578417000105":"HABT11","26614291000100":"GGRC11","63375304000153":"ADSH11","12005956000165":"KNRI11","11728688000147":"HGLG11","97521225000125":"MXRF11","30048651000112":"PATC11","53764894000152":"PATA11","28152272000126":"RECR11","63134454000175":"TRXF11","20748515000181":"BRCO11","26502794000185":"XPLG11","17554274000125":"VISC11"}
d = lambda s: "".join(c for c in s if c.isdigit())
out = {"arquivos": z.namelist()}
for n in z.namelist():
    rd = csv.DictReader(io.StringIO(z.read(n).decode("latin-1")), delimiter=";")
    out.setdefault("cols", {})[n] = rd.fieldnames
    for r in rd:
        c = d(r.get("CNPJ_Fundo_Classe") or r.get("CNPJ_Fundo") or "")
        if c in alvo:
            k = alvo[c]
            keep = {kk: v for kk, v in r.items() if any(x in kk for x in ("Data_Referencia", "Taxa", "Patrimonio_Liquido", "Dividend", "Rentabilidade", "Valor_Ativo", "Total_Passivo", "Rendimentos_Distribuir"))}
            out.setdefault("dados", {}).setdefault(k, []).append(keep)
json.dump(out, open("sonda/taxa_saida.json", "w"), ensure_ascii=False, indent=0)
