import json, urllib.request, urllib.parse
B = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
out = {}
def get(path, **q):
    q.setdefault("$format", "json")
    url = B + path + "?" + urllib.parse.urlencode(q, safe="@'$=(),", quote_via=urllib.parse.quote)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=180) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"erro": str(e), "url": url, "corpo": (getattr(e, "read", lambda: b"")() or b"")[:500].decode("utf-8", "replace")}
RAIZES = ["60872504", "60701190", "60746948", "00000000", "90400888", "30306294", "92702067", "28195667", "62144175",
          "61186680", "10739356", "17184037", "04902979", "28127603", "00000208", "13009717", "07237373", "59588111"]
for am in ("202606", "202603"):
    for variante in ({"@AnoMes": am}, {"@AnoMes": "'" + am + "'"}):
        cad = get("IfDataCadastro(AnoMes=@AnoMes)", **variante)
        v = cad.get("value") if isinstance(cad, dict) else None
        out[f"cad_{am}_{list(variante.values())[0]}"] = {"n": len(v or []), "erro": None if v else cad,
            "colunas": sorted(v[0]) if v else None,
            "nossos": [r for r in (v or []) if (r.get("CodInst") or "")[:8] in RAIZES]}
        if v:
            break
cods = set()
for k, x in out.items():
    for r in x.get("nossos") or []:
        for c in ("CodInst", "CodConglomeradoPrudencial", "CodConglomeradoFinanceiro"):
            if r.get(c):
                cods.add(r[c])
out["cods"] = sorted(cods)
for am in ("202606", "202603"):
    for tipo in ("1", "2"):
        for rel in ("1", "4", "5", "8"):
            filtro = " or ".join(f"CodInst eq '{c}'" for c in sorted(cods)) if cods else None
            q = {"@AnoMes": am, "@TipoInstituicao": tipo, "@Relatorio": "'" + rel + "'"}
            if filtro:
                q["$filter"] = filtro
            r = get("IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)", **q)
            v = r.get("value") if isinstance(r, dict) else None
            key = f"v_{am}_t{tipo}_r{rel}"
            if not v:
                out[key] = r
                continue
            por = {}
            for x in v:
                por.setdefault(x["CodInst"], []).append([x.get("Grupo"), x["NomeColuna"], x.get("Conta"), x["Saldo"]])
            out[key] = {"n": len(v), "por_inst": por}
json.dump(out, open("sonda/ifdata_saida.json", "w"), ensure_ascii=False, indent=1, default=str)
