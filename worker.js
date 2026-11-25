const REASONS = {
  spam: "Спам",
  scam: "Мошенничество / мошенническая схема",
  threats: "Угрозы",
  impersonation: "Выдаёт себя за другого",
  other: "Другое"
};

function esc(value) {
  return String(value).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
}

async function telegram(env, method, payload) {
  const response = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: {"content-type":"application/json"},
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`Telegram API error: ${response.status}`);
  return response.json();
}

async function send(env, chatId, text) {
  return telegram(env, "sendMessage", {
    chat_id: chatId,
    text,
    parse_mode: "HTML",
    disable_web_page_preview: true
  });
}

function parseReport(text) {
  const parts = text.trim().split(/\s+/);
  if (parts.length < 3) return null;
  const target = parts[1];
  const reasonKey = parts[2].toLowerCase();
  const evidence = parts.slice(3).join(" ").trim();
  if (!/^(@[a-zA-Z0-9_]{5,32}|https?:\/\/t\\.me\/[a-zA-Z0-9_+/-]+)$/.test(target)) return null;
  if (!REASONS[reasonKey]) return null;
  return {target, reason: REASONS[reasonKey], evidence: evidence || "Не указаны"};
}

async function handleMessage(env, message) {
  if (!message?.text) return;
  const chatId = message.chat.id;
  const text = message.text.trim();
  const command = text.split(/\s+/)[0].split("@")[0].toLowerCase();

  if (command === "/start" || command === "/help") {
    await send(env, chatId,
      "Привет! Я помогу составить черновик обращения по конкретному нарушению.\n\n" +
      "Формат:\n<code>/report @username причина доказательства</code>\n\n" +
      "Причины: <code>spam</code>, <code>scam</code>, <code>threats</code>, <code>impersonation</code>, <code>other</code>.\n" +
      "Пример:\n<code>/report @example scam ссылка_на_сообщение</code>\n\n" +
      "Бот не отправляет жалобы автоматически, не использует чужие аккаунты и не создаёт массовые жалобы. Отправляй обращение только если нарушение действительно было."
    );
    return;
  }

  if (command === "/report") {
    const report = parseReport(text);
    if (!report) {
      await send(env, chatId,
        "Не получилось разобрать команду.\n\n" +
        "Используй формат:\n<code>/report @username причина доказательства</code>\n\n" +
        "Причины: <code>spam</code>, <code>scam</code>, <code>threats</code>, <code>impersonation</code>, <code>other</code>.\n" +
        "Добавь ссылку на конкретное сообщение или краткое описание фактов."
      );
      return;
    }
    const draft =
      "<b>Черновик обращения</b>\n\n" +
      `Аккаунт: ${esc(report.target)}\n` +
      `Причина: ${esc(report.reason)}\n` +
      `Доказательства: ${esc(report.evidence)}\n\n` +
      "Проверь, что сведения точны, и приложи исходные доказательства. Это только черновик — жалоба не отправлена.\n\n" +
      '<a href="https://telegram.org/support">Официальная поддержка Telegram</a>';
    await send(env, chatId, draft);
    return;
  }

  await send(env, chatId, "Напиши /help, чтобы увидеть инструкцию.");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/") {
      return Response.json({status:"ok", service:"telegram-report-bot"});
    }
    if (request.method === "GET" && url.pathname === "/setup") {
      if (!env.BOT_TOKEN || !env.WEBHOOK_SECRET) {
        return Response.json({ok:false, error:"Add BOT_TOKEN and WEBHOOK_SECRET in Worker Settings > Variables and Secrets, then visit /setup again."}, {status:500});
      }
      const webhookUrl = `${url.origin}/telegram`;
      const result = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/setWebhook`, {
        method: "POST",
        headers: {"content-type":"application/json"},
        body: JSON.stringify({
          url: webhookUrl,
          secret_token: env.WEBHOOK_SECRET,
          allowed_updates: ["message"]
        })
      });
      const data = await result.json();
      if (!result.ok || !data.ok) {
        return Response.json({ok:false, telegram:data}, {status:502});
      }
      return Response.json({ok:true, message:"Telegram webhook registered. Open your bot in Telegram and send /start."});
    }
    if (request.method !== "POST" || url.pathname !== "/telegram") {
      return new Response("Not found", {status:404});
    }
    if (!env.BOT_TOKEN || !env.WEBHOOK_SECRET) {
      return new Response("Missing Worker secrets", {status:500});
    }
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
      return new Response("Forbidden", {status:403});
    }
    const update = await request.json();
    if (update.message) await handleMessage(env, update.message);
    return Response.json({ok:true});
  }
};
