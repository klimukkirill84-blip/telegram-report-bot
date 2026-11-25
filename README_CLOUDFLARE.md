# Telegram Report Draft Bot

A Cloudflare Worker webhook for a Telegram bot that prepares a single, evidence-based report draft. It does not mass-report, automate complaints, or access other Telegram accounts.

## Deploy

1. Create a Worker from this GitHub repository in Cloudflare Workers & Pages.
2. Set Worker secrets:
   - `BOT_TOKEN`: a fresh token from @BotFather (revoke any token previously pasted into chats/screenshots).
   - `WEBHOOK_SECRET`: a random string of 32+ characters using letters and digits.
3. Deploy. The Worker URL will look like `https://telegram-report-bot.<your-subdomain>.workers.dev`.
4. Register the webhook once by opening this URL in a browser, replacing placeholders:
   `https://api.telegram.org/bot<NEW_BOT_TOKEN>/setWebhook?url=https://telegram-report-bot.<your-subdomain>.workers.dev/telegram&secret_token=<WEBHOOK_SECRET>`
5. Check the Worker URL root; it should return `{"status":"ok","service":"telegram-report-bot"}`.

## Bot use

- `/start` — instructions
- `/report @username scam link_to_evidence` — prepare a draft

Reasons: `spam`, `scam`, `threats`, `impersonation`, `other`.

The bot does not submit reports automatically. Submit only accurate reports through Telegram's official support process.
