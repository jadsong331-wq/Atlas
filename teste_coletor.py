# -*- coding: utf-8 -*-
"""
Teste do coletor com arquivos simulados no layout oficial (CVM, B3, BCB).
Roda offline: python testes/teste_coletor.py
"""
import io, json, os, sys, shutil, tempfile, zipfile
from datetime import date
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "coletor"))
import config, fonte_b3, fonte_bcb, fonte_cvm, main, util  # noqa

HOJE = date.today()
Y = HOJE.year
T = "07859971000130"; B = "00000000000191"; F = "11728688000147"

def zipa(arquivos):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for nome, txt in arquivos.items():
            z.writestr(nome, txt.encode("latin-1"))
    return b.getvalue()

CAB = "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"
CAB_BP = "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"
def fmt_cnpj(c): return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
def lf(cnpj, nome, dtref, ordem, ini, fim, cd, ds, v, versao=1):
    return f"{fmt_cnpj(cnpj)};{dtref};{versao};{nome};1;G;REAL;MIL;{ordem};{ini};{fim};{cd};{ds};{v};S"
def lb(cnpj, nome, dtref, ordem, fim, cd, ds, v):
    return f"{fmt_cnpj(cnpj)};{dtref};1;{nome};1;G;REAL;MIL;{ordem};{fim};{cd};{ds};{v};S"

# ---- Empresa T (não financeira): lucro anual 1000..1500 (mil), receita 2000..2500
anual = {Y-6+i: (2000+100*i, 1000+100*i) for i in range(6)}
def dre_ano(cnpj, nome, dtref, ordem, ini, fim, rec, luc, ebit):
    return [lf(cnpj,nome,dtref,ordem,ini,fim,"3.01","Receita de Venda de Bens e/ou Serviços",rec),
            lf(cnpj,nome,dtref,ordem,ini,fim,"3.05","Resultado Antes do Resultado Financeiro e dos Tributos",ebit),
            lf(cnpj,nome,dtref,ordem,ini,fim,"3.11","Lucro/Prejuízo Consolidado do Período",luc+50),
            lf(cnpj,nome,dtref,ordem,ini,fim,"3.11.01","Atribuído a Sócios da Empresa Controladora",luc),
            lf(cnpj,nome,dtref,ordem,ini,fim,"3.99.01.01","ON",1.23)]
def dfc_ano(cnpj,nome,dtref,ordem,ini,fim,da,div):
    return [lf(cnpj,nome,dtref,ordem,ini,fim,"6.01.01.02","Depreciação e Amortização",da),
            lf(cnpj,nome,dtref,ordem,ini,fim,"6.03.01","Dividendos e JCP Pagos",-div),
            lf(cnpj,nome,dtref,ordem,ini,fim,"6.03.02","Dividendos recebidos",99)]
def bp(cnpj,nome,dtref,fim):
    a=[lb(cnpj,nome,dtref,"ÚLTIMO",fim,"1.01.01","Caixa e Equivalentes de Caixa",300),
       lb(cnpj,nome,dtref,"ÚLTIMO",fim,"1.01.02","Aplicações Financeiras",200)]
    p=[lb(cnpj,nome,dtref,"ÚLTIMO",fim,"2.01.04","Empréstimos e Financiamentos",1000),
       lb(cnpj,nome,dtref,"ÚLTIMO",fim,"2.02.01","Empréstimos e Financiamentos",2500),
       lb(cnpj,nome,dtref,"ÚLTIMO",fim,"2.03","Patrimônio Líquido Consolidado",8500),
       lb(cnpj,nome,dtref,"ÚLTIMO",fim,"2.03.09","Participação dos Acionistas Não Controladores",500)]
    return a,p
CAPCAB="CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;QT_ACAO_ORDIN_CAP_INTEGR;QT_ACAO_PREF_CAP_INTEGR;QT_ACAO_TOTAL_CAP_INTEGR;QT_ACAO_ORDIN_TESOURO;QT_ACAO_PREF_TESOURO;QT_ACAO_TOTAL_TESOURO"

def zip_dfp(ano):
    dre,dfc,bpa,bpp,cap=[CAB],[CAB],[CAB_BP],[CAB_BP],[CAPCAB]
    fim=f"{ano}-12-31"; ini=f"{ano}-01-01"
    rec,luc=anual[ano]
    dre+=dre_ano(T,"TRANSM SA",fim,"ÚLTIMO",ini,fim,rec,luc,luc*1.5)
    dfc+=dfc_ano(T,"TRANSM SA",fim,"ÚLTIMO",ini,fim,100,luc*0.5)
    a,p=bp(T,"TRANSM SA",fim,fim); bpa+=a; bpp+=p
    cap.append(f"{fmt_cnpj(T)};{fim};1;TRANSM SA;110000;200000;310000;10000;0;10000")
    if ano==Y-1:  # banco só tem o último DFP
        dre+=[lf(B,"BANCO SA",fim,"ÚLTIMO",ini,fim,"3.01","Receitas da Intermediação Financeira",50000),
              lf(B,"BANCO SA",fim,"ÚLTIMO",ini,fim,"3.11","Lucro ou Prejuízo Líquido Consolidado do Período",6000),
              lf(B,"BANCO SA",fim,"ÚLTIMO",ini,fim,"3.11.01","Atribuído a Sócios da Empresa Controladora",5800)]
        dfc+=[lf(B,"BANCO SA",fim,"ÚLTIMO",ini,fim,"6.03.04","Dividendos e Juros sobre o Capital Próprio Pagos",-2000)]
        bpp+=[lb(B,"BANCO SA",fim,"ÚLTIMO",fim,"2.08","Patrimônio Líquido Consolidado",40000)]
        cap.append(f"{fmt_cnpj(B)};{fim};1;BANCO SA;5000000;0;5000000;0;0;0")
    return zipa({f"dfp_cia_aberta_DRE_con_{ano}.csv":"\n".join(dre), f"dfp_cia_aberta_DFC_MI_con_{ano}.csv":"\n".join(dfc),
                 f"dfp_cia_aberta_BPA_con_{ano}.csv":"\n".join(bpa), f"dfp_cia_aberta_BPP_con_{ano}.csv":"\n".join(bpp),
                 f"dfp_cia_aberta_composicao_capital_{ano}.csv":"\n".join(cap)})

def zip_itr(ano):
    if ano!=Y: return zipa({"vazio.csv":"x"})
    d=f"{Y}-06-30"; dp=f"{Y-1}-06-30"
    dre=[CAB]+dre_ano(T,"TRANSM SA",d,"ÚLTIMO",f"{Y}-01-01",d,1300,800,1200) \
        +dre_ano(T,"TRANSM SA",d,"ÚLTIMO",f"{Y}-04-01",d,650,400,600) \
        +dre_ano(T,"TRANSM SA",d,"PENÚLTIMO",f"{Y-1}-01-01",dp,1200,700,1050)
    dfc=[CAB]+dfc_ano(T,"TRANSM SA",d,"ÚLTIMO",f"{Y}-01-01",d,60,400)+dfc_ano(T,"TRANSM SA",d,"PENÚLTIMO",f"{Y-1}-01-01",dp,50,300)
    a,p=bp(T,"TRANSM SA",d,d)
    cap=[CAPCAB,f"{fmt_cnpj(T)};{d};1;TRANSM SA;100000;200000;300000;0;0;0"]
    return zipa({f"itr_cia_aberta_DRE_con_{Y}.csv":"\n".join(dre), f"itr_cia_aberta_DFC_MI_con_{Y}.csv":"\n".join(dfc),
                 f"itr_cia_aberta_BPA_con_{Y}.csv":"\n".join([CAB_BP]+a), f"itr_cia_aberta_BPP_con_{Y}.csv":"\n".join([CAB_BP]+p),
                 f"itr_cia_aberta_composicao_capital_{Y}.csv":"\n".join(cap)})

FCA = zipa({f"fca_cia_aberta_valor_mobiliario_{Y}.csv":"CNPJ_Companhia;Data_Referencia;Valor_Mobiliario;Codigo_Negociacao\n"
            f"{fmt_cnpj(T)};{Y}-01-01;Units;TAEE11\n{fmt_cnpj(T)};{Y}-01-01;Ações Ordinárias;TAEE3\n{fmt_cnpj(B)};{Y}-01-01;Ações Ordinárias;BBAS3"})

def fii_zip(ano):
    g="CNPJ_Fundo_Classe;Data_Referencia;Versao;Nome_Fundo_Classe;Codigo_ISIN;Segmento_Atuacao\n"
    c="CNPJ_Fundo_Classe;Data_Referencia;Versao;Patrimonio_Liquido;Cotas_Emitidas;Valor_Patrimonial_Cotas;Percentual_Dividend_Yield_Mes;Total_Numero_Cotistas;Percentual_Despesas_Taxa_Administracao\n"
    for m in range(1,13):
        dt=f"{ano}-{m:02d}-01"
        if date.fromisoformat(dt) > HOJE: break
        g+=f"{fmt_cnpj(F)};{dt};1;FII LOG;BRHGLGCTF004;Logística\n{fmt_cnpj('99999999000199')};{dt};1;OUTRO;BROUTRCTF000;Papel\n"
        c+=f"{fmt_cnpj(F)};{dt};1;4900000000;30000000;163,33;0,007;400000;0,0006\n"
        c+=f"{fmt_cnpj('99999999000199')};{dt};1;100;10;10;0,009;10;0,001\n"
    return zipa({f"inf_mensal_fii_geral_{ano}.csv":g, f"inf_mensal_fii_complemento_{ano}.csv":c})

def linha_cot(data, ticker, preco, isin, bdi="02", vol=1000000):
    s = [" "]*245
    def put(i,j,v):
        v=str(v); 
        for k,ch in enumerate(v.ljust(j-i+1)[:j-i+1]): s[i-1+k]=ch
    put(1,2,"01"); put(3,10,data.replace("-","")); put(11,12,bdi); put(13,24,ticker); put(25,27,"010")
    put(109,121,str(int(round(preco*100))).zfill(13)); put(148,152,"00010"); put(171,188,str(int(vol*100)).zfill(18))
    put(211,217,"0000001"); put(231,242,isin)
    return "".join(s)
def cot_zip(d):
    ds=d.isoformat()
    linhas=["00COTAHIST.2026BOVESPA", linha_cot(ds,"TAEE3",10,"BRTAEEACNOR0",vol=100), linha_cot(ds,"TAEE4",12,"BRTAEEACNPR0",vol=900),
            linha_cot(ds,"TAEE11",34,"BRTAEECDAM10"), linha_cot(ds,"BBAS3",20,"BRBBASACNOR3"),
            linha_cot(ds,"HGLG11",160,"BRHGLGCTF004","12",8000000)]
    return zipa({"COTAHIST.TXT":"\n".join(linhas)})

MACRO = {"432":[{"data":"17/09/2026","valor":"14.00"},{"data":"28/09/2026","valor":"13.75"}],
         "13522":[{"data":"01/08/2026","valor":"4.40"}], "433":[{"data":"01/08/2026","valor":"-0.10"}], "1":[{"data":"25/09/2026","valor":"5.1834"}]}

def fake(url, obrigatorio=False):
    if "FCA" in url: return FCA
    if "/DFP/" in url: return zip_dfp(int(url[-8:-4]))
    if "/ITR/" in url: return zip_itr(int(url[-8:-4]))
    if "INF_MENSAL" in url: return fii_zip(int(url[-8:-4]))
    if "COTAHIST_D" in url:
        return cot_zip(date(int(url[-8:-4]), int(url[-10:-8]), int(url[-12:-10])))
    if "COTAHIST_A" in url: return None
    if "bcdata.sgs" in url:
        s=url.split("sgs.")[1].split("/")[0]; return json.dumps(MACRO[s]).encode()
    if "olinda" in url:
        import urllib.parse as u; q=u.unquote(url)
        for ind,v in [("IPCA",(4.92,4.3)),("Selic",(13.5,12)),("PIB Total",(1.88,1.43)),("Câmbio",(5.2,5.28))]:
            if f"'{ind}'" in q:
                return json.dumps({"value":[{"Data":"2026-09-21","DataReferencia":str(Y),"Mediana":v[0]},{"Data":"2026-09-21","DataReferencia":str(Y+1),"Mediana":v[1]}]}).encode()
    return None

for mod in (fonte_b3, fonte_bcb, fonte_cvm):
    mod.baixar = fake
config.UNIVERSO = [("TAEE11","acao","Energia",["Barsi"]),("BBAS3","acao","Bancos",["Barsi"]),("HGLG11","fii","FII Logístico",[]),("ZZZZ3","acao","X",[])]
tmp = tempfile.mkdtemp()
main.ARQ_CACHE=os.path.join(tmp,"f.json"); main.ARQ_HIST=os.path.join(tmp,"h.csv")
main.ARQ_JSON=os.path.join(tmp,"dados.json"); main.ARQ_MD=os.path.join(tmp,"DADOS.md")
d = main.montar()
A = {a["ticker"]:a for a in d["ativos"]}

def perto(a,b,tol=1e-6): return a is not None and abs(a-b)<=tol*max(1,abs(b))
t = A["TAEE11"]["ind"]; erros=[]
luc = (800+1500-700)*1000; rec=(1300+2500-1200)*1000
mcap = 100000*10 + 200000*12          # ON a 10, PN (mais líquida) a 12
checks = {
 "lucro TTM": (t["lucro_ttm"], luc), "receita TTM": (t["receita_ttm"], rec),
 "valor de mercado": (t["valor_mercado"], mcap), "P/L": (t["p_l"], mcap/luc),
 "PL controladora": (t["patrimonio"], 8000e3), "P/VP": (t["p_vp"], mcap/8000e3),
 "ROE": (t["roe"], luc/8000e3*100),
 "EBIT TTM": (t["ebit_ttm"], (1200+2250-1050)*1000), "EBITDA TTM": (t["ebitda_ttm"], (1200+2250-1050+60+100-50)*1000),
 "dív. líquida": (t["divida_liquida"], (3500-500)*1000),
 "DY": (t["dy"], (400+750-300)*1000/mcap*100), "payout": (t["payout"], (400+750-300)/(800+1500-700)*100),
 "CAGR receita": (t["cagr_receita"], ((2500/2000)**(1/5)-1)*100), "CAGR lucro": (t["cagr_lucro"], ((1500/1000)**(1/5)-1)*100),
 "anos c/ dividendo": (t["anos_com_dividendo"], 5),
}
for k,(a,b) in checks.items():
    if not perto(a,b): erros.append(f"{k}: obtido {a}, esperado {b}")
b_ = A["BBAS3"]
if not b_.get("banco"): erros.append("BBAS3 não detectado como banco")
if not perto(b_["ind"]["p_l"], 20*5000000/(5800e3)): erros.append(f"P/L banco {b_['ind']['p_l']}")
if "ev_ebitda" in b_["ind"]: erros.append("banco não deveria ter EV/EBITDA")
h = A["HGLG11"]["ind"]
if not perto(h["p_vp"], 160/163.33): erros.append(f"P/VP FII {h['p_vp']}")
esperado_dy = 0.7*12 if HOJE.month>=1 else None
if not perto(h["dy"], 8.4): erros.append(f"DY FII {h['dy']}")
if not any("ZZZZ3" in p for p in d["pendencias"]): erros.append("ZZZZ3 deveria estar pendente")
# quantidade de ações informada em milhares (caso real: VALE3, ITUB4, TAEE11...)
m, on_, pn_, aj = main.corrigir_escala_acoes("VALE3", 71.16 * 4072366, 196635e6, 4072366, 0)
if not aj or not perto(m, 71.16 * 4072366000): erros.append(f"escala em milhares não corrigida: {m}")
m, on_, pn_, aj = main.corrigir_escala_acoes("HAPV3", 6.23 * 475087930, 48062e6, 475087930, 0)
if aj: erros.append("HAPV3 (P/VP real de 0,06) não deveria ser ajustado")
if d["macro"].get("selic_tendencia") != "queda": erros.append(f"tendência Selic {d['macro'].get('selic_tendencia')}")
print(open(main.ARQ_MD, encoding="utf-8").read()[:3000])
print("\nRESULTADO:", "OK - todos os cálculos conferem" if not erros else "FALHAS:\n - " + "\n - ".join(erros))
shutil.rmtree(tmp)
sys.exit(1 if erros else 0)
