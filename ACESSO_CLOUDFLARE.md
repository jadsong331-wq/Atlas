# Acesso restrito do ATLAS (Cloudflare)

Este guia deixa o ATLAS fechado. Só entra quem você liberar, com um código enviado por e-mail e sem senha. Quem não tem acesso pede pela página pública de pedido, e você aprova no painel **Acessos**.

Os menus da Cloudflare mudam de nome de vez em quando. Se algum item abaixo não estiver exatamente com esse nome, procure o equivalente.

## Como fica

| Parte | Endereço | Quem vê |
|---|---|---|
| ATLAS (projeto `atlas`) | `https://atlas.pages.dev` (ou o nome que a Cloudflare der) | Só e-mails da lista **ATLAS liberados** |
| Painel de acessos | `.../admin/` dentro do ATLAS | Só o e-mail em `ADMIN_EMAIL` |
| Pedido de acesso (projeto `atlas-acesso`) | `https://atlas-acesso.pages.dev` | Público |

Estes são os arquivos do repositório envolvidos:

- `docs/admin/`: o painel de acessos.
- `functions/api/admin/`: o que o painel usa para aprovar, recusar e remover acessos.
- `cf/acesso.js`: confere o login do Access e fala com a API da Cloudflare.
- `publico/`: a página de pedido de acesso e a função que grava os pedidos.

## Parte 1: site fechado

1. Crie uma conta gratuita em <https://dash.cloudflare.com>.
2. Vá em **Workers & Pages → Create → Pages → Connect to Git** e autorize o GitHub. Dê acesso **só** ao repositório `Atlas`.
   - Project name: `atlas`
   - Production branch: `main`
   - Framework preset: `None`
   - Build command: deixe vazio
   - Build output directory: `docs`
   - Root directory: deixe vazio
   - Clique em **Save and Deploy**.
3. No menu lateral, abra **Zero Trust**. Escolha um nome de time; ele vira `https://<time>.cloudflareaccess.com`. Selecione o plano **Free**. A Cloudflare pede cartão mesmo no plano gratuito, mas não cobra.
4. Em **Zero Trust → Settings → Authentication → Login methods**, confira se **One-time PIN** está ativo. Se não estiver, adicione.
5. Em **Zero Trust → Reusable components (ou My Team) → Lists → Create list**:
   - Nome: `ATLAS liberados`
   - Tipo: e-mails
   - Coloque o **seu** e-mail e salve.
   - Abra a lista e copie o **ID**, o código longo que aparece no endereço da página.
6. Volte em **Workers & Pages → atlas → Settings → General** e clique em **Enable access policy**. Isso cria um aplicativo no Access, mas ele só cobre as versões de teste. Então ajuste:
   - Vá em **Zero Trust → Access → Applications**, abra o aplicativo criado para o projeto e clique em **Configure**.
   - Em *Public hostname*, **apague o `*`** do campo de subdomínio, para ficar só `atlas.pages.dev`. Renomeie para `ATLAS` se der erro de nome repetido.
   - Na política, deixe **Include → Email list → ATLAS liberados** e retire as outras regras de inclusão.
   - Em *Session duration*, escolha por quanto tempo o login vale (por exemplo, 1 mês).
   - Salve e copie o **Application Audience (AUD) Tag**. Ele fica nas configurações do aplicativo, em *Additional settings* ou *Overview*.
7. Em **Workers & Pages → atlas → Settings → General**, clique de novo em **Enable access policy**. Isso cria um segundo aplicativo, que protege as versões de teste. Confira em **Access → Applications** se existem os dois.
8. **Teste:** abra `https://atlas.pages.dev` numa janela anônima. A Cloudflare deve pedir o e-mail. Use o seu, digite o código recebido e o ATLAS abre. Com outro e-mail, nenhum código chega.

## Parte 2: pedidos de acesso e painel

9. Em **Workers & Pages → KV → Create namespace**, crie `atlas-pedidos`.
10. Crie o projeto público em **Workers & Pages → Create → Pages → Connect to Git**, escolhendo o mesmo repositório `Atlas`:
    - Project name: `atlas-acesso`
    - Root directory: `publico`
    - Build output directory: `site`
    - Build command: deixe vazio
    - **Não** ative o access policy neste projeto.
    - Depois do primeiro deploy, vá em **Settings → Bindings → Add → KV namespace**: Variable name `PEDIDOS`, namespace `atlas-pedidos`.
    - Em seguida, vá em **Deployments → … → Retry deployment**.
    - Opcional: em **Settings → Build → Build watch paths**, coloque `publico/*`. Assim a coleta diária não gera builds desnecessários neste projeto.
11. Crie o token da API em **My Profile → API Tokens → Create Token → Create Custom Token**:
    - Nome: `ATLAS acessos`
    - Permissions: **Account → Zero Trust → Edit**
    - Account Resources: a sua conta
    - Crie e **copie o token na hora**, porque ele só aparece uma vez.
12. Pegue o **Account ID**. Ele aparece na lateral da página inicial de Workers & Pages e também no endereço do painel: `dash.cloudflare.com/<account id>/...`.
13. No projeto `atlas`, configure:
    - Em **Settings → Bindings → Add → KV namespace**: Variable name `PEDIDOS`, namespace `atlas-pedidos`.
    - Em **Settings → Variables and Secrets** (ambiente *Production*), cadastre:

    | Nome | Tipo | Valor |
    |---|---|---|
    | `ADMIN_EMAIL` | Text | seu e-mail (o mesmo da lista) |
    | `TEAM_DOMAIN` | Text | `https://<time>.cloudflareaccess.com` |
    | `POLICY_AUD` | Text | AUD Tag do passo 6 |
    | `CF_ACCOUNT_ID` | Text | Account ID do passo 12 |
    | `LISTA_ID` | Text | ID da lista do passo 5 |
    | `URL_PEDIDO` | Text | `https://atlas-acesso.pages.dev/` |
    | `CF_API_TOKEN` | **Secret** | token do passo 11 |

    - Depois, vá em **Deployments → … → Retry deployment**.
14. **Teste:**
    - Abra `https://atlas.pages.dev/admin/`. Deve aparecer "Entrou como (seu e-mail)", sem aviso de configuração incompleta.
    - Em **Mais ferramentas**, devem aparecer **Acessos** e **Sair**.
    - Pela página `https://atlas-acesso.pages.dev`, faça um pedido com outro e-mail. Ele aparece em Pedidos pendentes. Aprove.
    - Esse outro e-mail passa a receber o código e entra.

### Opcional: aviso por e-mail a cada pedido novo

No GitHub, crie um *fine-grained token* com acesso só ao repositório `Atlas` e permissão **Issues: Read and write**. No projeto `atlas-acesso`, cadastre:

- `GITHUB_TOKEN` (Secret): o token.
- `GITHUB_REPO` (Text): `jadsong331-wq/Atlas`.

Cada pedido novo abre uma issue no repositório, e o GitHub manda o e-mail para você.

## Parte 3: fechar o endereço antigo

Enquanto o GitHub Pages estiver ativo e o repositório for público, todos os dados continuam abertos em `jadsong331-wq.github.io/Atlas` e no próprio GitHub. Depois que a Parte 2 estiver funcionando:

- desativar o GitHub Pages;
- tornar o repositório **privado**.

A coleta automática continua funcionando. No repositório privado, o GitHub dá 2.000 minutos por mês de Actions no plano gratuito, e a coleta usa cerca de 230. A Cloudflare continua publicando a cada atualização.

## Como funciona no dia a dia

- **Liberar:** abra **Mais ferramentas → Acessos** e aprove o pedido, ou use "Liberar sem pedido".
- **Tirar acesso:** clique em **Remover** no painel. A pessoa perde o acesso no próximo login, ou quando a sessão dela expirar.
- **Limite do plano gratuito do Access:** indicado para até 50 usuários.
- **Pedidos pendentes:** ficam guardados por até 90 dias. Cada conexão de internet aceita no máximo 5 pedidos por hora, para barrar robôs.
