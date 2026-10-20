# -*- coding: utf-8 -*-
"""
Teste do coletor com arquivos simulados no layout oficial (CVM, B3, BCB).
Roda offline: python testes/teste_coletor.py
"""
import io, json, os, sys, shutil, tempfile, zipfile
from datetime import date, timedelta
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "coletor"))
import config, fonte_b3, fonte_bcb, fonte_cvm, fonte_b3_proventos, historico, main, util  # noqa

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
            lf(cnpj,nome,dtref,ordem,ini,fim,"3.06.02","Despesas Financeiras",-200),
            lf(cnpj,nome,dtref,ordem,ini,fim,"3.99.01.01","ON",1.23)]
def dfc_ano(cnpj,nome,dtref,ordem,ini,fim,da,div):
    return [lf(cnpj,nome,dtref,ordem,ini,fim,"6.01.01.02","Depreciação e Amortização",da),
            lf(cnpj,nome,dtref,ordem,ini,fim,"6.03.01","Dividendos e JCP Pagos",-div),
            lf(cnpj,nome,dtref,ordem,ini,fim,"6.03.02","Dividendos recebidos",99),
            lf(cnpj,nome,dtref,ordem,ini,fim,"6.01","Caixa Líquido Atividades Operacionais",div*2.4),
            lf(cnpj,nome,dtref,ordem,ini,fim,"6.02.01","Aquisição de Imobilizado",-div*0.8),
            lf(cnpj,nome,dtref,ordem,ini,fim,"6.02.02","Venda de Imobilizado",50),
            lf(cnpj,nome,dtref,ordem,ini,fim,"6.02.03","Aplicações Financeiras",-999)]
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
    if ano not in anual: return zipa({"vazio.csv":"x"})
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
        g+=f"{fmt_cnpj('88888888000188')};{dt};1;FUNDO DE OFERTA;;Híbrido\n"
        c+=f"{fmt_cnpj('88888888000188')};{dt};1;970000000;10000000;97;0,01;5000;0,001\n"
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
def linha_opc(data, ticker, premio, strike, tipo, esp):
    s_ = list(linha_cot(data, ticker, premio, "BRTAEEO00000", bdi="78" if tipo=="call" else "82", vol=50000))
    def put(i,j,v):
        v=str(v)
        for k,ch in enumerate(v.ljust(j-i+1)[:j-i+1]): s_[i-1+k]=ch
    put(25,27,"070" if tipo=="call" else "080"); put(40,49,esp)
    put(189,201,str(int(round(strike*100))).zfill(13))
    from datetime import timedelta
    put(203,210,(HOJE+timedelta(days=60)).strftime("%Y%m%d"))
    return "".join(s_)
def cot_zip(d):
    ds=d.isoformat()
    linhas=["00COTAHIST.2026BOVESPA", linha_cot(ds,"TAEE3",10,"BRTAEEACNOR0",vol=100), linha_cot(ds,"TAEE4",12,"BRTAEEACNPR0",vol=900),
            linha_cot(ds,"TAEE11",34,"BRTAEECDAM10"), linha_cot(ds,"BBAS3",20,"BRBBASACNOR3"),
            linha_cot(ds,"HGLG11",160,"BRHGLGCTF004","12",8000000), linha_cot(ds,"OUTR11",11,"BROUTRCTF000","12",900000),
            linha_opc(ds,"TAEEK350",1.20,35.0,"call","PN"), linha_opc(ds,"TAEEW320",0.80,32.0,"put","PN")]
    return zipa({"COTAHIST.TXT":"\n".join(linhas)})

def cot_anual_zip():
    """70 pregões: OUTR11 (FII líquido), WXYZ3 (líquida, sem CNPJ), LOWV3 (pouco líquida), TAEE4 (curada)."""
    from datetime import timedelta
    linhas=["00COTAHIST.2026BOVESPA"]
    d=HOJE-timedelta(days=120); n=0
    while n<70:
        d+=timedelta(days=1)
        if d.weekday()>=5 or d>=HOJE: continue
        ds=d.isoformat(); n+=1
        linhas+=[linha_cot(ds,"OUTR11",10+n/100,"BROUTRCTF000","12",900000),
                 linha_cot(ds,"WXYZ3",5,"BRWXYZACNOR0",vol=3000000),
                 linha_cot(ds,"LOWV3",5,"BRLOWVACNOR0",vol=10000),
                 linha_cot(ds,"TAEE4",12,"BRTAEEACNPR0",vol=5000000),
                 linha_cot(ds,"HGLG11",159,"BRHGLGCTF004","12",8000000)]
    return zipa({"COTAHIST_A.TXT":"\n".join(linhas)})

CAD = ("CNPJ_CIA;DENOM_SOCIAL;SIT;SETOR_ATIV\n"
       f"{fmt_cnpj(T)};TRANSM SA;CANCELADA;Comércio\n{fmt_cnpj(T)};TRANSM SA;ATIVO;Emp. Adm. Part. - Energia Elétrica\n"
       f"{fmt_cnpj(B)};BANCO SA;ATIVO;Bancos\n").encode("latin-1")

MACRO = {"432":[{"data":"17/09/2026","valor":"14.00"},{"data":"28/09/2026","valor":"13.75"}],
         "13522":[{"data":"01/08/2026","valor":"4.40"}], "433":[{"data":"01/08/2026","valor":"-0.10"}], "1":[{"data":"25/09/2026","valor":"5.1834"}]}

# valores reais do BB (conglomerado prudencial) no IF.data de 06/2026, em R$ e frações
IFD_BB={1:[{"i":140220,"v":2583568802583.73},{"i":140246,"v":181838430069.62},{"i":141840,"v":-36841452046.38},{"i":141842,"v":-35196087503.89},
           {"i":141851,"v":10681974176.86},{"i":141855,"v":224922378.15},{"i":141856,"v":3214133368.92},{"i":141857,"v":10778458140.92},
           {"i":141858,"v":-14481786819.09},{"i":141859,"v":-8427702469.11},{"i":141870,"v":6550624863.77},{"i":141873,"v":1128399194489.67}],
        3:[{"i":24454,"v":1115404849436.43},{"i":148833,"v":104092086027.33},{"i":148834,"v":65383226229.8}],
        5:[{"i":79659,"v":0.112707132516234},{"i":79664,"v":0.139146075963478}]}
def fake(url, obrigatorio=False, **kw):
    if "FCA" in url: return FCA
    if "/DFP/" in url: return zip_dfp(int(url[-8:-4]))
    if "/ITR/" in url: return zip_itr(int(url[-8:-4]))
    if "INF_MENSAL" in url: return fii_zip(int(url[-8:-4]))
    if "COTAHIST_D" in url:
        return cot_zip(date(int(url[-8:-4]), int(url[-10:-8]), int(url[-12:-10])))
    if "listedCompaniesProxy" in url:
        import base64 as b6
        q=json.loads(b6.b64decode(url.rsplit("/",1)[1]))
        if q["issuingCompany"]=="TAEE":
            d1=f"{HOJE.day:02d}/{HOJE.month:02d}/{Y}"; dant=f"01/01/{Y-2}"
            return json.dumps([{"cashDividends":[
                {"isinCode":"BRTAEEACNOR0","label":"DIVIDENDO","lastDatePrior":d1,"rate":"0,50000000","paymentDate":d1},
                {"isinCode":"BRTAEEACNPR0","label":"JRS CAP PROPRIO","lastDatePrior":d1,"rate":"0,60000000","paymentDate":d1},
                {"isinCode":"BRTAEEACNPR0","label":"JRS CAP PROPRIO","lastDatePrior":d1,"rate":"0,60000000","paymentDate":d1},
                {"isinCode":"BRTAEEACNPR0","label":"DIVIDENDO","lastDatePrior":dant,"rate":"9,0","paymentDate":dant}],
                "stockDividends":[]}]).encode()
        return None
    if "fundsProxy" in url:
        d1=f"{HOJE.day:02d}/{HOJE.month:02d}/{Y}"
        return json.dumps({"cashDividends":[{"isinCode":"BRHGLGCTF004","label":"RENDIMENTO","lastDatePrior":d1,"rate":"1,10"},
                                            {"isinCode":"BRHGLGCTF004","label":"AMORTIZACAO","lastDatePrior":d1,"rate":"5,00"}]}).encode()
    if "COTAHIST_A" in url: return cot_anual_zip() if url.endswith(f"A{Y}.ZIP") else None
    if "cad_cia_aberta" in url: return CAD
    if "bcdata.sgs.4391" in url or "bcdata.sgs.433/dados?" in url:
        import calendar
        out=[]; a,m=Y-10,HOJE.month
        while (a,m)<(Y,HOJE.month):
            out.append({"data":f"01/{m:02d}/{a}","valor":"1.00" if "4391" in url else "0.40"}); m+=1
            if m==13: a,m=a+1,1
        return json.dumps(out).encode()
    if "bcdata.sgs.12/" in url:
        d=HOJE-timedelta(days=400); out=[]
        while d<HOJE:
            if d.weekday()<5: out.append({"data":d.strftime("%d/%m/%Y"),"valor":"0.05"})
            d+=timedelta(days=1)
        return json.dumps(out).encode()
    if "bcdata.sgs" in url:
        s=url.split("sgs.")[1].split("/")[0]; return json.dumps(MACRO[s]).encode()
    if "ifdata/rest/relatorios" in url:
        return json.dumps([{"dt":202603,"files":[]},{"dt":202606,"files":[{"f":"x//202606/cadastro202606_1009.json"},{"f":"x//202606/dados202606_1.json"},
                           {"f":"x//202606/dados202606_3.json"},{"f":"x//202606/dados202606_5.json"}]}]).encode()
    if "ifdata/rest/arquivos" in url:
        import urllib.parse as u; n=u.unquote(url)
        if "cadastro" in n: return json.dumps([{"c0":"1000080329","c2":"BB - PRUDENCIAL","c33":"C0080329"},{"c0":"68987","c2":"COOPERATIVA X","c33":"00068987"},{"c0":"77","c2":"COOPERATIVA DE SERGIPE E BANESE","c33":"00000077"}]).encode()
        if "dados202606_1" in n: return json.dumps({"id":1,"values":[{"e":68987,"v":[{"i":141870,"v":1}]},{"e":1000080329,"v":IFD_BB[1]}]}).encode()
        if "dados202606_3" in n: return json.dumps({"id":3,"values":[{"e":1000080329,"v":IFD_BB[3]}]}).encode()
        if "dados202606_5" in n: return json.dumps({"id":5,"values":[{"e":1000080329,"v":IFD_BB[5]}]}).encode()
        return None
    if "OFERTA/DISTRIB" in url:
        cab="Numero_Requerimento;Numero_Processo;Data_Registro;Data_Encerramento;Status_Requerimento;Valor_Mobiliario;CNPJ_Emissor;Nome_Emissor;Nome_Lider;Emissao;Qtde_Total_Registrada;Valor_Total_Registrado;Oferta_inicial;Publico_alvo;Destinacao_recursos;Mercado_negociacao;Regime_distribuicao;Administrador;Gestor;Titulo_incentivado;Num_Invest_Pessoa_Natural\n"
        h=HOJE.isoformat(); velho=(HOJE-timedelta(days=400)).isoformat(); rec=(HOJE-timedelta(days=30)).isoformat()
        l=[f"1;SRE/1;{rec};;Registro Concedido;Cotas de FII;88.888.888/0001-88;FUNDO DE OFERTA FII;XP;1;10750000;1075000000.00;S;Público Geral;Imóveis;(i) MDA e (ii) Fundos21;Melhores Esforços;XP;GESTORA X;;0",
           f"2;SRE/2;{rec};;Registro Concedido;Cotas de FII;{fmt_cnpj(F)};FII LOG;BTG;5;1000000;160000000.00;N;Público Geral;Imóveis;Bolsa - Segmento Listado;Melhores Esforços;BTG;BTG;;0",
           f"3;SRE/3;{rec};;Registro Concedido;Cotas de FII;11.111.111/0001-11;FII PROFISSIONAL;ITAU;1;100;10000000.00;S;Profissional;x;Bolsa - Segmento Listado;;;;;0",
           f"4;SRE/4;{velho};{velho};Oferta Encerrada;Cotas de FII;22.222.222/0001-22;FII ANTIGO;XP;1;100;10000.00;S;Público Geral;x;x;;;;;0",
           f"5;SRE/5;{rec};{h};Oferta Encerrada;Certificados de Recebíveis Imobiliários;33.333.333/0001-33;SECURITIZADORA;XP;1;1000;1000000.00;S;Público Geral;x;CETIP21;;;;S;250",
           f"6;SRE/6;{rec};;Registro Concedido;Cotas de FIDC;44.444.444/0001-44;FIDC;XP;1;1;1.00;S;Público Geral;x;x;;;;;0"]
        ant="Numero_Registro_Oferta;Numero_Processo;Tipo_Ativo;CNPJ_Emissor;Nome_Emissor;Nome_Lider;Rito_Oferta;Modalidade_Oferta;Data_Registro_Oferta;Data_Inicio_Oferta;Data_Encerramento_Oferta;Emissao;Quantidade_Total;Preco_Unitario;Valor_Total;Oferta_Inicial;Oferta_Incentivo_Fiscal;Ultimo_Comunicado;Nr_Pessoa_Fisica\n"
        ant+=f"R7;P7;COTAS DE FII;55.555.555/0001-55;FII ORDINARIO;XP;RCVM 160 (ordinário);Registrada;{rec};{rec};;2;1000;100;100000;N;N;Anúncio de Início;0\n"
        return zipa({"oferta_resolucao_160.csv":(cab+"\n".join(l)+"\n").encode("latin-1").decode("latin-1"), "oferta_distribuicao.csv":ant})
    if "olinda" in url:
        import urllib.parse as u; q=u.unquote(url)
        for ind,v in [("IPCA",(4.92,4.3)),("Selic",(13.5,12)),("PIB Total",(1.88,1.43)),("Câmbio",(5.2,5.28))]:
            if f"'{ind}'" in q:
                return json.dumps({"value":[{"Data":"2026-09-21","DataReferencia":str(Y),"Mediana":v[0]},{"Data":"2026-09-21","DataReferencia":str(Y+1),"Mediana":v[1]}]}).encode()
    return None

import fonte_ifdata, fonte_ofertas
fonte_ifdata.time.sleep=lambda s: None
for mod in (fonte_b3, fonte_bcb, fonte_cvm, fonte_b3_proventos, historico, fonte_ifdata, fonte_ofertas):
    mod.baixar = fake
config.UNIVERSO = [("TAEE11","acao","Energia e saneamento","Energia",["Barsi"]),("BBAS3","acao","Bancos e financeiro","Bancos",["Barsi"]),
                   ("HGLG11","fii","FII Logístico","FII Logístico",[]),("ZZZZ3","acao","X","X",[])]
config.MERCADO_COMPLETO=True; config.LIQUIDEZ_MINIMA_ACOES=1_000_000; config.LIQUIDEZ_MINIMA_FIIS=500_000; config.PREGOES_LIQUIDEZ=63; config.PRESENCA_MINIMA=0.5
tmp = tempfile.mkdtemp()
main.ARQ_CACHE=os.path.join(tmp,"f.json"); main.ARQ_HIST=os.path.join(tmp,"h.csv"); main.ARQ_UNIV=os.path.join(tmp,"u.json")
main.ARQ_ANOS=os.path.join(tmp,"anos.json"); main.ARQ_BACKFILL=os.path.join(tmp,"bf.json"); main.ARQ_PROV=os.path.join(tmp,"prov.json"); main.ARQ_MACRO_OK=os.path.join(tmp,"macro_ok.json"); main.ARQ_REF_OK=os.path.join(tmp,"ref_ok.json"); main.ARQ_DERIV=os.path.join(tmp,"deriv.json"); fonte_b3_proventos.time.sleep=lambda s: None; main.ARQ_HIST_JSON=os.path.join(tmp,"historico.json")
main.ARQ_JSON=os.path.join(tmp,"dados.json"); main.ARQ_MD=os.path.join(tmp,"DADOS.md"); main.ARQ_IFDATA=os.path.join(tmp,"ifdata.json"); main.ARQ_OFERTAS=os.path.join(tmp,"ofertas.json"); main.ARQ_SAUDE=os.path.join(tmp,"saude.json"); main.ARQ_ALERTA=os.path.join(tmp,"alerta.txt")
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
 "DY caixa": (t["dy_caixa"], (400+750-300)*1000/mcap*100), "payout caixa": (t["payout_caixa"], (400+750-300)/(800+1500-700)*100),
 "DY B3 (unit: total declarado / valor de mercado)": (t["dy"], (0.5*100000+0.6*200000)/mcap*100),
 "payout B3": (t["payout"], (0.5*100000+0.6*200000)/luc*100),
 "CAGR receita": (t["cagr_receita"], ((2500/2000)**(1/5)-1)*100), "CAGR lucro": (t["cagr_lucro"], ((1500/1000)**(1/5)-1)*100),
 "anos c/ provento (CVM, 5 anos)": (t["anos_com_dividendo"], 5),
 "DY médio 5 anos (CVM)": (t["dy_medio5"], sum((1000+100*i)*0.5*1000 for i in range(1,6))/5/mcap*100),
 "P/L sobre lucro médio 5 anos": (t["p_l_medio5"], mcap/(sum(1000+100*i for i in range(1,6))/5*1000)),
 "PEG": (t["peg"], (mcap/luc)/(((1500/1000)**(1/5)-1)*100)),
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
if not perto(h["dy"], 1.10/160*100): erros.append(f"DY FII pela B3 {h['dy']}")
if not perto(h["dy_cvm"], 8.4): erros.append(f"DY FII CVM {h['dy_cvm']}")
if h.get("vp_var_12m") is None or abs(h["vp_var_12m"]) > 1e-9: erros.append(f"variação VP FII {h.get('vp_var_12m')}")
if not any("ZZZZ3" in p for p in d["pendencias"]): erros.append("ZZZZ3 deveria estar pendente")
# quantidade de ações informada em milhares (caso real: VALE3, ITUB4, TAEE11...)
m, on_, pn_, aj = main.corrigir_escala_acoes("VALE3", 71.16 * 4072366, 196635e6, 4072366, 0)
if not aj or not perto(m, 71.16 * 4072366000): erros.append(f"escala em milhares não corrigida: {m}")
m, on_, pn_, aj = main.corrigir_escala_acoes("HAPV3", 6.23 * 475087930, 48062e6, 475087930, 0)
if aj: erros.append("HAPV3 (P/VP real de 0,06) não deveria ser ajustado")
# ---- mercado completo
if "OUTR11" not in A: erros.append("OUTR11 (FII líquido) deveria entrar no mercado completo")
else:
    o=A["OUTR11"]
    if o["curado"] or o["setor"]!="FII Papel": erros.append(f"OUTR11 curado={o['curado']} setor={o['setor']}")
    if not o.get("perfis_auto"): erros.append("OUTR11 deveria ter perfis automáticos")
    if len(o.get("serie") or [])<30: erros.append("OUTR11 sem histórico de preço (backfill do arquivo anual)")
for t_ in ("LOWV3","TAEE4","WXYZ3"):
    if t_ in A: erros.append(f"{t_} não deveria entrar (pouco líquida, classe de empresa curada ou sem CNPJ)")
if not A["TAEE11"]["curado"] or A["TAEE11"]["grupo"]!="Energia" or A["TAEE11"]["perfis"]!=["Barsi"]:
    erros.append("ativo curado deve manter grupo e perfis manuais")
if d["universo"]["automaticos"]!=1: erros.append(f"automáticos {d['universo']['automaticos']}")
liq={"AAAA3":(2e6,"02"),"AAAA4":(5e6,"02"),"BBBB11":(3e6,"02"),"CCCC3":(9e5,"02"),"DDDD34":(9e9,"02"),
     "FFFF11":(6e5,"12"),"GGGG11":(4e5,"12"),"TAEE3":(9e9,"02")}
ac,fi=fonte_b3.selecionar_mercado(liq,1e6,5e5,{"TAEE11"})
if [t for t,_ in ac]!=["AAAA4","BBBB11"] or [t for t,_ in fi]!=["FFFF11"]: erros.append(f"seleção por liquidez {ac} {fi}")
ac,fi=fonte_b3.selecionar_mercado({"EEEE3":(5e6,"02",0.3),"HHHH3":(5e4,"02",0.9)},2e4,2e4,set(),presenca_min=0.5)
if [t for t,_ in ac]!=["HHHH3"]: erros.append(f"presença mínima {ac}")
lq,_=fonte_b3.liquidez_media([{"ticker":"X","data":"2026-01-0%d"%i,"volume":10,"codbdi":"02"} for i in range(1,5)]+
                             [{"ticker":"Y","data":"2026-01-01","volume":40,"codbdi":"02"}],{},63)
if lq["X"]!=(10.0,"02",1.0) or lq["Y"]!=(10.0,"02",0.25): erros.append(f"liquidez média {lq}")
if fonte_cvm.mapear_cnpjs(["TAEE4"]).get("TAEE4")!=T: erros.append("mapeamento de CNPJ pelo prefixo falhou")
for cvm,esp in [("Bancos","Bancos e financeiro"),("Emp. Adm. Part. - Energia Elétrica","Energia e saneamento"),
                ("Saneamento, Serv. Água e Gás","Energia e saneamento"),("Petróleo e Gás","Commodities"),
                ("Agricultura (Açúcar, Álcool e Cana)","Agronegócio"),("Construção Civil, Mat. Constr. e Decoração","Construção e imóveis"),
                ("Comércio (Atacado e Varejo)","Consumo e varejo"),("Serviços Médicos","Saúde"),("Telecomunicações","Tecnologia e telecom"),
                ("Máquinas, Equipamentos, Veículos e Peças","Indústria"),("Serviços Transporte e Logística","Transporte e logística"),
                ("Crédito Imobiliário","Bancos e financeiro"),("Emp. Adm. Part. - Const. Civil, Mat. Const. e Decoração","Construção e imóveis"),("Sem Setor Principal","Outros")]:
    if main.setor_atlas(cvm)!=esp: erros.append(f"setor '{cvm}' -> {main.setor_atlas(cvm)} (esperado {esp})")
ind_={"anos_com_dividendo":5,"dy":9,"payout":60,"lucro_ttm":1,"p_l":7,"p_vp":1.2,"anos_com_lucro":5,"roe":18,
      "div_liq_ebitda":1,"margem_liquida":25,"cagr_lucro":16,"cagr_receita":11}
pa=main.perfis_automaticos("acao","Energia e saneamento",ind_,False)
if pa!=["Barsi","Graham","Buffett","Lynch","Bartunek","Dalio"]: erros.append(f"perfis automáticos {pa}")
if main.perfis_automaticos("acao","Outros",{"p_l":30,"roe":5},False): erros.append("perfis automáticos deveriam vir vazios")
for nome_,seg_,esp in [("CSHG LOGÍSTICA FII","Multicategoria","FII Logístico"),("MAXI RENDA FII","Logística","FII Logístico"),
                       ("KINEA RENDIMENTOS IMOBILIÁRIOS","Multicategoria","FII Híbrido"),("XP MALLS","Shopping","FII Shopping"),
                       ("RBR CRÉDITO IMOBILIÁRIO","Multicategoria","FII Papel"),("QUALQUER","Multicategoria","FII Híbrido"),("QUALQUER","Residencial","FII Outros")]:
    if main.segmento_fii(seg_,"",nome_)!=esp and nome_!="MAXI RENDA FII": erros.append(f"tipo FII {nome_}: {main.segmento_fii(seg_,'',nome_)}")
# composição real (informe de set/2026): MXRF11 75% em CRI, KNRI11 90% em imóveis, HGLG11 imóveis + SPEs
mx={"Total_Investido":5176.4,"CRI_CRA":3892.9,"FII":718.4,"Direitos_Bens_Imoveis":287.9,"Acoes_Sociedades_Atividades_FII":277.2}
kn={"Total_Investido":4670.8,"Direitos_Bens_Imoveis":4203.3,"Cotas_Sociedades_Atividades_FII":78.5,"CRI_CRA":389.6}
hg={"Total_Investido":8291.8,"Direitos_Bens_Imoveis":7060.4,"FII":148.3,"Acoes_Sociedades_Atividades_FII":1051.7,"CRI_CRA":31.4}
for nome_,seg_,cart_,esp in [("MAXI RENDA","Logística",mx,"FII Papel"),("KINEA RENDA IMOBILIÁRIA","Multicategoria",kn,"FII Híbrido"),
                             ("CSHG LOGÍSTICA","Multicategoria",hg,"FII Logístico")]:
    if main.segmento_fii(seg_,"",nome_,cart_)!=esp: erros.append(f"tipo FII por composição {nome_}: {main.segmento_fii(seg_,'',nome_,cart_)}")
if main.perfis_automaticos("fii","FII Papel",{"meses_com_rendimento":12,"dy":11,"p_vp":0.95},False)!=["Baroni"]: erros.append("perfil Baroni")
# ---- histórico comparativo
import historico as H
if H._proporcao_redonda(0.5)!=0.5 or H._proporcao_redonda(10.02)!=10 or H._proporcao_redonda(0.6) or H._proporcao_redonda(0.3):
    erros.append("detecção de desdobramento/grupamento")
serie=[("2025-01-02",40.0),("2025-01-03",41.0),("2025-01-06",20.6),("2025-01-07",21.0)]
ev=H.detectar_eventos(serie)
if ev!=[("2025-01-06",0.5)]: erros.append(f"eventos {ev}")
if H.detectar_eventos([("a",12.7),("b",14.4),("c",8.2),("d",4.1),("e",5.4)]): erros.append("tombo real confundido com desdobramento")
anos={str(Y-1):{"PETX4":{"m":{"11":40.0,"12":42.0},"ini":["%d-01-02"%(Y-1),30.0],"fim":["%d-12-30"%(Y-1),42.0],"ev":[]}}}
dia={(f"{Y}-01-02","PETX4"):21.0,(f"{Y}-01-03","PETX4"):22.0}
hh=H.montar_historico({"PETX4"},anos,dia,hoje=date(Y,1,10))
pm=dict(zip(hh["meses"],hh["precos_m"]["PETX4"]))
if not perto(pm[f"{Y-1}-12"],21.0) or not perto(pm[f"{Y}-01"],22.0) or hh["ajustes"]["PETX4"][0][0]!=f"{Y}-01-02":
    erros.append(f"ajuste entre anos {pm} {hh['ajustes']}")
hj=json.load(open(main.ARQ_HIST_JSON,encoding="utf-8"))
cdi=hj["referencias"].get("CDI",{})
if not cdi or not perto(cdi["m"][12], 1.01**12, 1e-4): erros.append(f"índice CDI {cdi.get('m',[None]*13)[:13]}")
if "TAEE11" not in hj["anual"] or "HGLG11" not in hj["fii_mensal"]: erros.append("histórico anual/FII ausente")
if len(hj["precos_s"].get("TAEE11") or [])<1: erros.append("série semanal ausente")
import fonte_b3_proventos as BP
for ev_,m_ in [({"tipo":"DESDOBRAMENTO","fator":100.0},2.0),({"tipo":"DESDOBRAMENTO","fator":400.0},5.0),({"tipo":"GRUPAMENTO","fator":0.0333333333},0.0333333333),
               ({"tipo":"BONIFICACAO","fator":3.0},1.03),({"tipo":"CIS RED CAP","fator":100.0},None)]:
    if BP.multiplicador_acoes(ev_)!=m_ and not (m_ and abs(BP.multiplicador_acoes(ev_)-m_)<1e-9): erros.append(f"fator B3 {ev_}")
ep=BP.eventos_preco([{"isin":"BRBBASACNOR3","tipo":"DESDOBRAMENTO","data_com":"2024-04-15","fator":100.0},
                     {"isin":"BRBBASACNOR3","tipo":"DESDOBRAMENTO","data_com":"2024-04-15","fator":100.0}],"BRBBASACNOR3")
if ep!=[("2024-04-16",0.5)]: erros.append(f"evento B3 {ep}")
parc=[{"isin":"X","tipo":"JRS CAP PROPRIO","data_com":HOJE.isoformat(),"valor":0.3131,"pagamento":"2026-05-20","ref":""},
      {"isin":"X","tipo":"JRS CAP PROPRIO","data_com":HOJE.isoformat(),"valor":0.3131,"pagamento":"2026-06-22","ref":""},
      {"isin":"X","tipo":"JRS CAP PROPRIO","data_com":HOJE.isoformat(),"valor":0.3131,"pagamento":"2026-06-22","ref":""}]
if not perto(BP.soma_12m(parc,"X")[0],0.6262): erros.append("parcelas com mesma data-com")
# macro: falha do Banco Central reaproveita o último valor bom
ok_=json.load(open(main.ARQ_MACRO_OK,encoding="utf-8"))
mm=main.completar_macro({"series":{"selic":{"valor":None},"ipca_12m":{"valor":None},"dolar":{"valor":None}},"focus":{}})
if mm["series"]["selic"]["valor"]!=ok_["series"]["selic"]["valor"] or "aviso" not in mm: erros.append(f"macro sem reserva {mm}")
# ---- retorno total e risco
rt=H.retorno_total([10,10,11],["2026-01","2026-02","2026-03"],[("2026-02-15",1.0)],True)
if rt is None or not perto(rt[1],1.1) or not perto(rt[2],1.1*1.1): erros.append(f"retorno total {rt}")
fake_at=[{"ticker":"X","ind":{}}]
main.risco_por_preco(fake_at,{"precos_s":{"X":[100,110]*15}})
if not fake_at[0]["ind"].get("volatilidade") or not perto(fake_at[0]["ind"]["queda_12m"],(100/110-1)*100): erros.append(f"risco {fake_at}")
# ---- validação (backtest) com dados sintéticos
import validacao as VA
reg_=json.load(open(os.path.join(AQUI,"..","docs","regua.json"),encoding="utf-8"))
meses_=[f"{2021+(k+3)//12}-{(k+3)%12+1:02d}" for k in range(40)]
at_,emp_,pm_={}, {}, {}
lista_=[]
for k in range(25):
    t_=f"T{k:03d}3"; c_=str(k)
    hist_={str(a):{"lucro":100.0*(1+k%5),"receita":1000.0,"dividendos_pagos":50.0*(1+k%5)} for a in range(2017,2025)}
    emp_[c_]={"historico_anual":hist_}
    pm_[t_]=[10.0*(1+0.01*k)**(i/12) for i in range(40)]
    lista_.append({"tipo":"acao","ticker":t_,"cnpj":c_,"liquidez_media":5e6,"acoes_circulacao":100.0})
hv_={"meses":meses_,"precos_m":pm_,"retorno_m":pm_,"referencias":{"CDI":{"m":[1.01**i for i in range(40)]}}}
bt_=VA.backtest(lista_,emp_,hv_,reg_)
if not bt_["periodos"] or len(bt_["periodos"][0]["carteira"])!=10: erros.append(f"backtest {bt_}")
# ---- reserva Ipeadata quando o Banco Central falha
_orig=H.sgs_periodo; H.sgs_periodo=lambda *a, **k: None; _ob=H.baixar
def _ipea(url, **k):
    if "ipeadata" in url:
        cod="CDI" if "TJCDI" in url else "IPCA"
        vals=[]; a,m=Y-10,1
        while (a,m)<=(Y,12):
            vals.append({"VALDATA":f"{a}-{m:02d}-01T00:00:00-03:00","VALVALOR":1.0 if cod=="CDI" else 0.4}); m+=1
            if m==13: a,m=a+1,1
        return json.dumps({"value":vals}).encode()
    return None
H.baixar=_ipea; H.time=None
import time as _t; _sl=_t.sleep; _t.sleep=lambda x: None
ri=H.indice_cdi_ipca(["2025-01","2025-02","2025-03"],["2025-01-03","2025-01-10"])
_t.sleep=_sl; H.sgs_periodo=_orig; H.baixar=_ob
if not ri.get("CDI") or not perto(ri["CDI"]["m"][2],1.01**2) or "Ipeadata" not in ri["CDI"]["fonte"] or ri["CDI"]["s"][1] is None:
    erros.append(f"reserva Ipeadata {ri}")
# ---- outros fundos
import fundos_listados as FL
for nm_,bdi_,fa_,esp_ in [("FIAGRO KNCA","12",False,"FIAGRO"),("IT NOW IMAB","14",False,"ETF"),("KINEA INFRA","14",False,"FI-Infra"),("QUALQUER","12",True,"FIAGRO")]:
    if FL.classificar(nm_,"CI",bdi_,fa_)!=esp_: erros.append(f"classificação de fundo {nm_}")
cot_={"KNCA11":{"preco":100.0,"data":"2026-10-16","isin":"BRKNCACTF000","codbdi":"12","nome":"FIAGRO KNCA"}}
fa_={"BRKNCACTF000":{"cnpj":"1","nome":"KINEA CRA FIAGRO","mes":"2026-09","vp_cota":98.0,"patrimonio":1e9,"cotistas":1000}}
pf_={"KNCA":{"dinheiro":[{"isin":"BRKNCACTF000","tipo":"RENDIMENTO","data_com":HOJE.isoformat(),"valor":1.0,"pagamento":None,"ref":""}]}}
fo_=FL.montar(["KNCA11"],cot_,{"KNCA11":2e6},{},fa_,pf_,lambda t: None)
if not fo_ or fo_[0]["tipo_fundo"]!="FIAGRO" or not perto(fo_[0]["p_vp"],100/98) or not perto(fo_[0]["dy"],1.0): erros.append(f"outros fundos {fo_}")
# ---- derivativos
import derivativos as DV
dv_=json.load(open(main.ARQ_DERIV,encoding="utf-8"))
if not dv_["ativos"] or dv_["ativos"][0]["ativo"]!="TAEE4": erros.append(f"opções: ativo-objeto {dv_['ativos'][:1]}")
else:
    c_=next(o for o in dv_["ativos"][0]["opcoes"] if o["tipo"]=="call")
    if not perto(c_["renda"],1.20/12*100) or c_["intr"]!=0 or c_.get("iv") is None: erros.append(f"opção de compra {c_}")
    pt_=next(o for o in dv_["ativos"][0]["opcoes"] if o["tipo"]=="put")
    if not perto(pt_["compra_efetiva"],31.2): erros.append(f"opção de venda {pt_}")
bs_=DV.black_scholes("call",100,100,1,0.1,0.2)
if abs(bs_-13.2697)>0.01: erros.append(f"Black-Scholes {bs_}")
if abs(DV.vol_implicita("call",bs_,100,100,1,0.1)-0.2)>1e-4: erros.append("volatilidade implícita")
# ---- bancos (IF.data)
b_=A["BBAS3"]["ind"]
exp_={"basileia":13.9146075963478,"capital_principal":11.2707132516234,"inadimplencia":65383226229.8/1115404849436.43*100,
      "ativos_problematicos":104092086027.33/1115404849436.43*100,
      "eficiencia":(14481786819.09+8427702469.11)/(10681974176.86+35196087503.89+224922378.15+3214133368.92+10778458140.92)*100,
      "custo_credito":36841452046.38*2/1128399194489.67*100}
for k_,v_ in exp_.items():
    if not perto(b_.get(k_),v_): erros.append(f"IF.data {k_}: {b_.get(k_)} != {v_}")
if A["BBAS3"].get("ifdata",{}).get("data_base")!=202606: erros.append(f"IF.data data-base {A['BBAS3'].get('ifdata')}")
if "eficiencia" in A["TAEE11"]["ind"]: erros.append("IF.data aplicado a empresa que não é banco")
if abs(exp_["eficiencia"]-38.12)>0.05 or abs(exp_["inadimplencia"]-5.86)>0.01: erros.append("conferência manual do BB")
# ---- nota relativa ao setor (régua v7)
import validacao as VA
it_=[("S",{"roe":r_,"p_l":10-r_}) for r_ in (1,2,3,4,5)]+[("T",{"roe":50})]
pc_=VA.percentis_setor(it_)
if pc_[0].get("roe")!=0 or pc_[4].get("roe")!=1 or pc_[2].get("roe")!=0.5 or pc_[5]: erros.append(f"percentis do setor {pc_}")
rg_={"acoes":[{"id":"qualidade","peso":1,"criterios":[{"ind":"roe","faixas":[[20,None,10],[None,20,0]]}]}]}
if VA._score({"roe":5},rg_,{"qualidade":1},{"roe":1.0},False)!=50: erros.append("mistura nota absoluta e setor")
# ---- caixa livre e cobertura de juros (Buffett/Graham)
ti_=A["TAEE11"]["ind"]
fcf5_=sum((anual[a][1]*0.5*2.4-anual[a][1]*0.5*0.8)*1000 for a in sorted(anual)[-5:])/5*(8000/8500)  # parte dos controladores
if not perto(ti_.get("fcf_medio5"),fcf5_) or not perto(ti_.get("fcf_yield"),fcf5_/mcap*100): erros.append(f"caixa livre {ti_.get('fcf_medio5')} != {fcf5_}")
if not perto(ti_.get("cobertura_juros"),ti_["ebit_ttm"]/200000): erros.append(f"cobertura de juros {ti_.get('cobertura_juros')}")
import validacao as VA2
if ti_.get("diluicao") != 0: erros.append(f"diluição {ti_.get('diluicao')}")
dh_={str(2018+i):{"acoes":q} for i,q in enumerate([100,102,104.04,1040.4,1061.2])}
dd_=VA2.diluicao_anual(dh_)
if not dd_ or abs(dd_["taxa"]-2)>0.01 or dd_["saltos"]!=["2021"]: erros.append(f"diluição com desdobramento {dd_}")
bh_={str(2020+i):{"acoes":q} for i,q in enumerate([100,100,110,110,110])}
if VA2.diluicao_anual(bh_, eventos=[("2022-04-18",1.10)])["taxa"]!=0: erros.append("bonificação contada como diluição")
if not perto(ti_.get("divida_cp_caixa"),1000/500): erros.append(f"dívida de curto prazo/caixa {ti_.get('divida_cp_caixa')}")
# ---- qualidade dos dados
import saude as SA
a_={"ticker":"XX","tipo":"acao","ind":{"dy":95.0,"roe":20.0},"avisos":[]}
SA.limitar([a_])
if a_["ind"]["dy"] is not None or a_["ind"]["roe"]!=20.0 or not a_["avisos"]: erros.append(f"limites de plausibilidade {a_}")
sd_=json.load(open(main.ARQ_SAUDE,encoding="utf-8"))
if not sd_["itens"] or not any(i["fonte"].startswith("Cotações") for i in sd_["itens"]): erros.append(f"saúde das fontes {sd_}")
# ---- ofertas públicas (CVM)
of_=json.load(open(main.ARQ_OFERTAS,encoding="utf-8"))["ofertas"]; O_={o["id"]:o for o in of_}
if set(O_)!={"1","2","3","5","R7"}: erros.append(f"ofertas na lista: {sorted(O_)}")
else:
    o1=O_["1"]
    if o1["situacao"]!="aberta" or o1["mercado"]!="balcão" or o1["preco"]!=100 or not o1["inicial"] or o1["tipo"]!="FII": erros.append(f"oferta 1 {o1}")
    if not o1.get("acompanhamento") or o1["acompanhamento"]["vp_cota"]!=97 or o1["acompanhamento"]["cotistas"]!=5000: erros.append(f"acompanhamento da oferta {o1.get('acompanhamento')}")
    if O_["2"].get("ticker")!="HGLG11" or O_["2"]["mercado"]!="bolsa": erros.append(f"oferta de fundo listado {O_['2']}")
    if O_["5"]["tipo"]!="CRI" or O_["5"]["situacao"]!="encerrada" or not O_["5"]["incentivado"]: erros.append(f"oferta CRI {O_['5']}")
    if O_["R7"]["tipo"]!="FII" or O_["R7"]["situacao"]!="aberta": erros.append(f"oferta rito ordinário {O_['R7']}")
    if of_[0]["situacao"]!="aberta": erros.append("ofertas abertas devem vir primeiro")
if "OFERTA:88888888000188" in A or any(k.startswith("OFERTA:") for k in A): erros.append("fundo de oferta virou ativo do ranking")
if d["macro"].get("selic_tendencia") != "queda": erros.append(f"tendência Selic {d['macro'].get('selic_tendencia')}")
print(open(main.ARQ_MD, encoding="utf-8").read()[:3000])
print("\nRESULTADO:", "OK - todos os cálculos conferem" if not erros else "FALHAS:\n - " + "\n - ".join(erros))
shutil.rmtree(tmp)
sys.exit(1 if erros else 0)
