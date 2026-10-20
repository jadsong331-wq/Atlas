import json, urllib.request, urllib.parse, sys
B = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
out = {}
def get(path, **q):
    q.setdefault("$format", "json")
    url = B + path + "?" + urllib.parse.urlencode(q, safe="@'$=")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"erro": str(e), "url": url}
out["lista"] = get("ListaDeRelatorio()")
for am in ("202606", "202603"):
    cad = get("IfDataCadastro(AnoMes=@AnoMes)", **{"@AnoMes": am})
    v = cad.get("value") if isinstance(cad, dict) else None
    out["cad_" + am + "_n"] = len(v or [])
    if v:
        out["cad_" + am + "_amostra"] = [r for r in v if any(k in (r.get("NomeInstituicao") or "").upper() for k in ("ITAU", "BRADESCO", "BCO DO BRASIL", "BANRISUL", "BTG", "ABC", "SANTANDER", "BMG", "PINE"))][:60]
        out["cad_" + am + "_cnpjs"] = [r for r in v if (r.get("CodInst") or "") in ("60872504", "60746948", "00000000", "90400888", "30306294", "92702067", "28195667", "62144175", "61186680", "10739356", "17184037", "04902979", "28127603", "00000208", "13009717")]
        break
for rel in ("1", "5", "4", "8", "2", "3", "6"):
    r = get("IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)",
            **{"@AnoMes": am, "@TipoInstituicao": "1", "@Relatorio": "'" + rel + "'"})
    v = r.get("value") if isinstance(r, dict) else None
    if not v:
        out["rel" + rel] = r
        continue
    cods = sorted({x["CodInst"] for x in v})
    out["rel" + rel] = {"n": len(v), "colunas": sorted(set(v[0])), "nomescol": sorted({(x.get("NomeColuna"), x.get("NumeroRelatorio"), x.get("NomeRelatorio")) for x in v}, key=str)[:120],
                        "cods_amostra": cods[:10], "linhas_primeiro": [x for x in v if x["CodInst"] == cods[0]][:80]}
json.dump(out, open("sonda/ifdata_saida.json", "w"), ensure_ascii=False, indent=1, default=str)
