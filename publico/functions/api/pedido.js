// Pedido de acesso (projeto público "atlas-acesso" no Cloudflare Pages).
// Guarda nome, e-mail e motivo no KV PEDIDOS, o mesmo que o painel /admin/ do ATLAS lê.
// Fica num projeto separado porque o site do ATLAS inteiro fica atrás do Cloudflare Access.

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function emailValido(e) {
  return typeof e === "string" && e.length <= 254 && /^[^\s@<>"']+@[^\s@<>"']+\.[a-z]{2,}$/i.test(e);
}

function limpar(txt, max) {
  return String(txt || "").replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, max);
}

const DIAS_PEDIDO = 90;
const MAX_POR_HORA = 5;

export async function onRequest({ request, env }) {
  if (request.method !== "POST") return json({ ok: false, erro: "Use o formulário de pedido de acesso." }, 405);
  if (!env.PEDIDOS) return json({ ok: false, erro: "Cadastro indisponível no momento." }, 503);
  let d;
  try {
    const tipo = request.headers.get("content-type") || "";
    d = tipo.includes("application/json") ? await request.json() : Object.fromEntries(await request.formData());
  } catch {
    return json({ ok: false, erro: "Pedido inválido." }, 400);
  }
  // campo escondido: só robôs preenchem
  if (d.site) return json({ ok: true });
  const nome = limpar(d.nome, 80);
  const email = limpar(d.email, 254).toLowerCase();
  const motivo = limpar(d.motivo, 500);
  if (nome.length < 2) return json({ ok: false, erro: "Informe seu nome." }, 400);
  if (!emailValido(email)) return json({ ok: false, erro: "Informe um e-mail válido." }, 400);

  const ip = request.headers.get("cf-connecting-ip") || "local";
  const chaveIp = "ip:" + ip;
  const n = parseInt((await env.PEDIDOS.get(chaveIp)) || "0", 10);
  if (n >= MAX_POR_HORA) return json({ ok: false, erro: "Muitos pedidos seguidos. Tente de novo mais tarde." }, 429);
  await env.PEDIDOS.put(chaveIp, String(n + 1), { expirationTtl: 3600 });

  const chave = "pedido:" + email;
  const ja = await env.PEDIDOS.get(chave);
  const pedido = { nome, email, motivo, data: new Date().toISOString() };
  await env.PEDIDOS.put(chave, JSON.stringify(pedido), { expirationTtl: DIAS_PEDIDO * 86400 });

  // aviso opcional ao dono por issue no repositório (o GitHub manda e-mail)
  if (!ja && env.GITHUB_TOKEN && env.GITHUB_REPO) {
    try {
      await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/issues`, {
        method: "POST",
        headers: {
          authorization: `Bearer ${env.GITHUB_TOKEN}`, accept: "application/vnd.github+json",
          "user-agent": "atlas-acesso", "content-type": "application/json",
        },
        body: JSON.stringify({
          title: `Pedido de acesso: ${nome}`,
          body: `**Nome:** ${nome}\n**E-mail:** ${email}\n**Motivo:** ${motivo || "(não informado)"}\n\nAprove ou recuse no painel /admin/ do ATLAS e feche esta issue.`,
          labels: ["pedido-de-acesso"],
        }),
      });
    } catch {
      // o pedido já está salvo; o aviso é só conveniência
    }
  }
  return json({ ok: true });
}
