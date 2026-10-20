import json, re, time, urllib.request, urllib.parse
out = {}
def raw(url, tent=3):
    err = None
    for i in range(tent):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
                return r.read(), r.status
        except Exception as e:
            err = str(e); time.sleep(4)
    return None, err
html, st = raw("https://www3.bcb.gov.br/ifdata/")
out["html_status"] = st
txt = (html or b"").decode("utf-8", "replace")
out["html"] = txt[:3000]
scripts = re.findall(r'src="([^"]+\.js[^"]*)"', txt)
out["scripts"] = scripts
trechos = []
for s in scripts:
    u = urllib.parse.urljoin("https://www3.bcb.gov.br/ifdata/", s)
    js, st2 = raw(u)
    if not js:
        trechos.append([u, st2]); continue
    j = js.decode("utf-8", "replace")
    for m in re.finditer(r"nomeArquivo|rest/|\.json", j):
        trechos.append([u, j[max(0, m.start() - 250): m.end() + 250]])
out["trechos"] = trechos[:120]
for nome in ["ifdata_2025_2030//202506/info202506.json", "ifdata_2025_2030//202506/cadastro202506_1005.json",
             "ifdata_2025_2030//202506/dados202506_5_1005.json", "arquivos.json", "relatorios.json"]:
    b, st3 = raw("https://www3.bcb.gov.br/ifdata/rest/arquivos?nomeArquivo=" + urllib.parse.quote(nome, safe=""), tent=1)
    out["f_" + nome] = [st3, (b or b"")[:1500].decode("utf-8", "replace")]
b, st4 = raw("https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/IfDataCadastro(AnoMes=@AnoMes)?@AnoMes=202606&$format=json&$top=3")
out["olinda_cad"] = [st4, (b or b"")[:800].decode("utf-8", "replace")]
json.dump(out, open("sonda/ifdata_saida.json", "w"), ensure_ascii=False, indent=1)
