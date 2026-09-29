# ATLAS Invest Research

Sistema de análise de ações e FIIs brasileiros que funciona sem IA e sem assinatura.

- **Dados oficiais:** CVM (balanços DFP e ITR, cadastro FCA, informe mensal de FII), B3 (arquivo diário de cotações COTAHIST) e Banco Central (Selic, IPCA, dólar e Boletim Focus).
- **Coleta automática:** o GitHub roda o coletor de segunda a sábado às 6h17 (Brasília), de graça.
- **App no navegador e no celular:** ranking pelo Score Atlas, carteira de renda, aporte mensal, macro, régua editável e, se você quiser, perguntas a uma IA.

O que é seu (carteira, régua personalizada, chave de IA) fica salvo só no seu navegador. O repositório guarda apenas dados públicos.

---

## Instalação (cerca de 15 minutos, uma vez só)

### 1. Criar a conta e o repositório
1. Crie uma conta gratuita em github.com.
2. Clique em **New repository**. Nome: `atlas`. Marque **Public** (o GitHub Pages gratuito exige repositório público). Clique em **Create repository**.

### 2. Enviar os arquivos
1. Descompacte o `atlas.zip` no seu computador.
2. No repositório, clique em **uploading an existing file** (ou **Add file > Upload files**).
3. Arraste **o conteúdo** da pasta `atlas` (as pastas `coletor`, `docs`, `data`, `testes`, `.github` e o `README.md`) e clique em **Commit changes**.

**Se a pasta `.github` não subir** (Windows e Mac escondem pastas que começam com ponto):
1. No repositório, vá em **Add file > Create new file**.
2. No nome, digite `.github/workflows/coleta.yml`.
3. Cole o conteúdo do arquivo `coleta.yml` que está dentro de `.github/workflows` no zip e clique em **Commit changes**.

### 3. Dar permissão para a coleta salvar os dados
**Settings > Actions > General > Workflow permissions**: marque **Read and write permissions** e salve.

### 4. Publicar o app
**Settings > Pages > Build and deployment**: em Source escolha **Deploy from a branch**, branch **main**, pasta **/docs**, e salve.

### 5. Rodar a primeira coleta
1. Aba **Actions**. Se aparecer um aviso, clique em **I understand my workflows, go ahead and enable them**.
2. Clique em **Coleta ATLAS > Run workflow**, marque a opção de baixar os balanços e confirme.
3. Leva de 5 a 15 minutos. Um sinal verde indica sucesso.

### 6. Abrir
O endereço é `https://SEU-USUARIO.github.io/atlas/`. No celular, abra no navegador e use **Adicionar à tela inicial** para instalar como app.

Antes da primeira coleta, o app mostra dados de exemplo com uma faixa amarela avisando.

---

## Conferência na primeira coleta

Os cálculos foram testados com arquivos no layout oficial, mas a primeira execução com os arquivos reais é o teste de verdade. Vale:

1. Abrir **Fontes** no app e ver as pendências.
2. Comparar 3 ou 4 ativos (por exemplo P/L, DY e ROE) com o RI da empresa ou um site de sua confiança. Diferenças pequenas são normais; o DY aqui usa dividendos efetivamente pagos no fluxo de caixa.
3. Se algo falhar, o registro completo fica em `data/log_ultima_execucao.txt` e também na aba **Actions**, clicando na execução.

---

## Manutenção

| O que | Onde |
| --- | --- |
| Incluir ou tirar ativos | `coletor/config.py`, lista `UNIVERSO` |
| CNPJ que o coletor não achou | `coletor/config.py`, `CNPJ_MANUAL` |
| Régua de pontuação padrão | `docs/regua.json` (ou pela aba Régua do app, que salva no seu aparelho) |
| Rodar a coleta na hora | Actions > Coleta ATLAS > Run workflow |
| Texto para levar a qualquer IA | `docs/data/DADOS_ATLAS.md` (também tem link na aba Fontes) |

O GitHub pausa agendamentos de repositórios públicos sem atividade por 60 dias. Os commits diários da coleta contam como atividade, mas se um dia aparecer aviso de pausa na aba Actions, basta reativar.

---

## Rodar no seu computador (sem GitHub)

Precisa só do Python 3.10 ou superior, sem pacotes extras.

```
python coletor/main.py --forcar
cd docs
python -m http.server 8000
```

Depois abra `http://localhost:8000` no navegador.

Teste dos cálculos, sem internet: `python testes/teste_coletor.py`

---

## IA opcional

Na aba **Perguntar à IA**, escolha Gemini, DeepSeek, Claude ou OpenRouter, cole a chave e o modelo. A IA recebe os números já calculados e é instruída a não inventar dados. Defina um limite de gasto mensal no painel do provedor. Sem chave, use **Copiar pergunta com dados** e cole em qualquer chat gratuito.

---

## Como os números são calculados

- **Últimos 12 meses:** acumulado do ano no ITR mais recente + ano anterior completo (DFP) − mesmo período do ano anterior.
- **Valor de mercado:** ações ON e PN em circulação (sem tesouraria) × preço de cada classe no último pregão.
- **P/L, P/VP, ROE:** sobre lucro e patrimônio atribuídos aos controladores.
- **EBITDA:** resultado antes do financeiro e dos tributos + depreciação e amortização do fluxo de caixa.
- **ROIC:** EBIT × (1 − 34%) ÷ (patrimônio + dívida líquida).
- **DY de ações:** dividendos e JCP pagos no fluxo de caixa em 12 meses ÷ valor de mercado.
- **DY de FIIs:** soma dos 12 últimos DY mensais informados à CVM.
- **Bancos:** EBITDA, ROIC, margem e dívida líquida não se aplicam e ficam fora da régua.

O ATLAS é uma ferramenta de cálculo com regras definidas por você. Não é recomendação de investimento.
