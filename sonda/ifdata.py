import json, time, urllib.request, urllib.parse
B = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
out = {}
def get(path, tent=6, **q):
    q.setdefault("$format", "json")
    url = B + path + "?" + urllib.parse.urlencode(q, safe="@'$=(),", quote_via=urllib.parse.quote)
    err = None
    for i in range(tent):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=180) as r:
                return json.loads(r.read().decode()), i
        except Exception as e:
            err = str(e)
            time.sleep(5 * (i + 1))
    return {"erro": err, "url": url}, tent
RAIZES = ["60872504", "60701190", "60746948", "00000000", "90400888", "30306294", "92702067", "28195667", "62144175",
          "61186680", "10739356", "17184037", "04902979", "28127603", "00000208", "13009717", "07237373", "59588111", "00360305"]
# cadastro: tentativas com filtro
for rz in RAIZES[:4]:
    r, i = get("IfDataCadastro(AnoMes=@AnoMes)", **{"@AnoMes": "202606", "$filter": f"CodInst eq '{rz}'"})
    out["cadf_" + rz] = [r, i]
r, i = get("IfDataCadastro(AnoMes=@AnoMes)", **{"@AnoMes": "202606", "$top": "5"})
out["cad_top5"] = [r, i]
r, i = get("IfDataCadastro(AnoMes=@AnoMes)", **{"@AnoMes": "202606"})
v = r.get("value") if isinstance(r, dict) else None
out["cad_full"] = {"tent": i, "n": len(v or []), "erro": None if v else r, "col": sorted(v[0]) if v else None,
                   "nossos": [x for x in (v or []) if (x.get("CodInst") or "")[:8] in RAIZES],
                   "conglos": [x for x in (v or []) if str(x.get("CodInst", "")).startswith("C")][:400]}
cods = ["C0080099", "C0080329", "C0080075", "C0080185", "C0081847", "C0080336", "C0080738"]
filtro = " or ".join(f"CodInst eq '{c}'" for c in cods)
for rel in ("1", "8", "16", "6"):
    r, i = get("IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)",
               **{"@AnoMes": "202606", "@TipoInstituicao": "1", "@Relatorio": f"'{rel}'", "$filter": filtro})
    v = r.get("value") if isinstance(r, dict) else None
    if not v:
        out[f"r{rel}"] = [r, i]; continue
    por = {}
    for x in v:
        por.setdefault(x["CodInst"], []).append([x.get("Grupo"), x["NomeColuna"], x.get("Conta"), x["Saldo"]])
    out[f"r{rel}"] = {"tent": i, "n": len(v), "por": por}
json.dump(out, open("sonda/ifdata_saida.json", "w"), ensure_ascii=False, indent=1, default=str)
