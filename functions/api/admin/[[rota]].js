// Painel do dono: pedidos pendentes, aprovar, recusar, lista de liberados e remover acesso.
// Só responde para quem está logado pelo Cloudflare Access com um e-mail de ADMIN_EMAIL.
import { json, emailValido, usuarioAccess, ehAdmin, apiCloudflare } from "../../../cf/acesso.js";

async function pedidos(env) {
  const out = [];
  let cursor;
  do {
    const r = await env.PEDIDOS.list({ prefix: "pedido:", cursor });
    for (const k of r.keys) {
      const v = await env.PEDIDOS.get(k.name);
      if (v) {
        try {
          out.push(JSON.parse(v));
        } catch {
          // ignora registro corrompido
        }
      }
    }
    cursor = r.list_complete ? null : r.cursor;
  } while (cursor);
  return out.sort((a, b) => String(b.data).localeCompare(String(a.data)));
}

async function liberados(env) {
  const out = [];
  let pagina = 1;
  for (;;) {
    const j = await apiCloudflare(env, "GET", `/gateway/lists/${env.LISTA_ID}/items` + (pagina > 1 ? `?page=${pagina}` : ""));
    const itens = Array.isArray(j.result) ? j.result.flat() : [];
    for (const i of itens) out.push({ email: String(i.value || "").toLowerCase(), nome: i.description || "", desde: i.created_at || null });
    const info = j.result_info || {};
    if (!info.total_pages || pagina >= info.total_pages || !itens.length) break;
    pagina++;
  }
  return out.sort((a, b) => a.email.localeCompare(b.email));
}

export async function onRequest({ request, env, params }) {
  const quem = await usuarioAccess(request, env);
  if (!ehAdmin(quem, env)) return json({ ok: false, erro: "Sem permissão." }, 403);
  const rota = (params.rota || []).join("/");
  const faltando = ["CF_ACCOUNT_ID", "LISTA_ID", "CF_API_TOKEN"].filter((k) => !env[k]);
  if (!env.PEDIDOS) faltando.push("PEDIDOS (KV)");

  try {
    if (request.method === "GET" && rota === "eu") return json({ ok: true, email: quem, faltando, url_pedido: env.URL_PEDIDO || null });
    if (faltando.length) return json({ ok: false, erro: "Configuração incompleta: " + faltando.join(", ") }, 500);
    if (request.method === "GET" && rota === "pedidos") return json({ ok: true, pedidos: await pedidos(env) });
    if (request.method === "GET" && rota === "liberados") return json({ ok: true, liberados: await liberados(env) });

    if (request.method === "POST") {
      let d = {};
      try {
        d = await request.json();
      } catch {
        return json({ ok: false, erro: "Pedido inválido." }, 400);
      }
      const email = String(d.email || "").trim().toLowerCase();
      if (!emailValido(email)) return json({ ok: false, erro: "E-mail inválido." }, 400);
      const chave = "pedido:" + email;

      if (rota === "aprovar") {
        const p = JSON.parse((await env.PEDIDOS.get(chave)) || "null");
        const nome = String(d.nome || (p && p.nome) || "").slice(0, 80);
        const atuais = await liberados(env);
        if (!atuais.some((x) => x.email === email)) {
          await apiCloudflare(env, "PATCH", `/gateway/lists/${env.LISTA_ID}`, { append: [{ value: email, description: nome }] });
        }
        await env.PEDIDOS.delete(chave);
        return json({ ok: true });
      }
      if (rota === "recusar") {
        await env.PEDIDOS.delete(chave);
        return json({ ok: true });
      }
      if (rota === "remover") {
        if (ehAdmin(email, env)) return json({ ok: false, erro: "Você não pode remover o próprio acesso de dono." }, 400);
        await apiCloudflare(env, "PATCH", `/gateway/lists/${env.LISTA_ID}`, { remove: [email] });
        return json({ ok: true });
      }
    }
    return json({ ok: false, erro: "Rota desconhecida." }, 404);
  } catch (e) {
    return json({ ok: false, erro: "Falha ao falar com a Cloudflare: " + e.message }, 502);
  }
}
