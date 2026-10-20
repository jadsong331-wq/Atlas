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
txt = (html or b"").decode("utf-8", "replace")
out["trechos"] = [txt[max(0, m.start() - 400): m.end() + 600] for m in re.finditer(r"urlArquivos|nomeArquivo|dados", txt)][:60]
b, s = raw("https://www3.bcb.gov.br/ifdata/rest/relatorios2025a2030")
out["relatorios"] = [s, (b or b"")[:6000].decode("utf-8", "replace")]
json.dump(out, open("sonda/ifdata_saida.json", "w"), ensure_ascii=False, indent=1)
open("sonda/ifdata_html.txt", "w").write(txt)
