// Controle de acesso do ATLAS no Cloudflare Pages.
//
// Quem pode entrar no site é decidido pelo Cloudflare Access (login com código enviado por e-mail).
// A lista de e-mails liberados é uma lista do Zero Trust; o painel /admin/ inclui e tira e-mails dela
// pela API da Cloudflare. Os pedidos de acesso ficam no KV "PEDIDOS"; quem grava é o projeto público
// "atlas-acesso" (pasta publico/), porque este site inteiro fica atrás do Access.
//
// Variáveis configuradas no painel da Cloudflare (Pages > Settings > Variables and Secrets):
//   ADMIN_EMAIL     e-mail(s) do dono, separados por vírgula (só eles usam o painel)
//   TEAM_DOMAIN     https://<seu-time>.cloudflareaccess.com
//   POLICY_AUD      "Application Audience (AUD) tag" do aplicativo do Access que protege o site
//   CF_ACCOUNT_ID   ID da conta Cloudflare
//   LISTA_ID        ID da lista de e-mails liberados (Zero Trust > Lists)
//   CF_API_TOKEN    (secreto) token da API com permissão "Zero Trust: Edit"
//   URL_PEDIDO      endereço da página pública de pedido de acesso (projeto atlas-acesso)
// Binding KV: PEDIDOS

export function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

export function emailValido(e) {
  return typeof e === "string" && e.length <= 254 && /^[^\s@<>"']+@[^\s@<>"']+\.[a-z]{2,}$/i.test(e);
}

export function limpar(txt, max) {
  return String(txt || "").replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, max);
}

function b64url(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

let certsCache = { em: 0, chaves: null, dominio: null };

async function chavesPublicas(dominio) {
  const agora = Date.now();
  if (certsCache.chaves && certsCache.dominio === dominio && agora - certsCache.em < 10 * 60 * 1000) return certsCache.chaves;
  const r = await fetch(`${dominio}/cdn-cgi/access/certs`);
  if (!r.ok) throw new Error("certs " + r.status);
  const j = await r.json();
  certsCache = { em: agora, chaves: j.keys || [], dominio };
  return certsCache.chaves;
}

// Confere o token que o Cloudflare Access põe em cada requisição (assinatura, emissor, público, validade).
// Devolve o e-mail de quem está logado, ou null.
export async function usuarioAccess(request, env) {
  const token = request.headers.get("cf-access-jwt-assertion");
  if (!token || !env.TEAM_DOMAIN || !env.POLICY_AUD) return null;
  const partes = token.split(".");
  if (partes.length !== 3) return null;
  let cab, dados;
  try {
    cab = JSON.parse(new TextDecoder().decode(b64url(partes[0])));
    dados = JSON.parse(new TextDecoder().decode(b64url(partes[1])));
  } catch {
    return null;
  }
  if (cab.alg !== "RS256") return null;
  const dominio = env.TEAM_DOMAIN.replace(/\/+$/, "");
  let chaves;
  try {
    chaves = await chavesPublicas(dominio);
  } catch {
    return null;
  }
  const jwk = chaves.find((k) => k.kid === cab.kid);
  if (!jwk) return null;
  const chave = await crypto.subtle.importKey("jwk", { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", chave, b64url(partes[2]),
    new TextEncoder().encode(partes[0] + "." + partes[1]));
  if (!ok) return null;
  const agora = Math.floor(Date.now() / 1000);
  if (typeof dados.exp !== "number" || dados.exp < agora) return null;
  if (typeof dados.nbf === "number" && dados.nbf > agora + 60) return null;
  if (dados.iss !== dominio) return null;
  const aud = Array.isArray(dados.aud) ? dados.aud : [dados.aud];
  if (!aud.includes(env.POLICY_AUD)) return null;
  return typeof dados.email === "string" ? dados.email.toLowerCase() : null;
}

export function ehAdmin(email, env) {
  const lista = String(env.ADMIN_EMAIL || "").toLowerCase().split(",").map((s) => s.trim()).filter(Boolean);
  return !!email && lista.includes(email);
}

export async function apiCloudflare(env, metodo, caminho, corpo) {
  const base = (env.CF_API_BASE || "https://api.cloudflare.com/client/v4").replace(/\/+$/, "");
  const r = await fetch(`${base}/accounts/${env.CF_ACCOUNT_ID}${caminho}`, {
    method: metodo,
    headers: { authorization: `Bearer ${env.CF_API_TOKEN}`, "content-type": "application/json" },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  let j = null;
  try {
    j = await r.json();
  } catch {
    j = null;
  }
  if (!r.ok || !j || j.success === false) {
    const msg = (j && j.errors && j.errors.map((e) => e.message).join("; ")) || `HTTP ${r.status}`;
    throw new Error(msg);
  }
  return j;
}
