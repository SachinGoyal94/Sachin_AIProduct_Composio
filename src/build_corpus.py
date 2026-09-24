"""Build data/verified.csv - the final human-reviewed corpus.

Merge order (later wins):
  1. SEED  - reviewer-curated rows for the well-known apps (stable facts,
             written down from knowledge of the official docs).
  2. AGENT REPORTS (out/agent_reports/*.json) - live-verified rows produced
     by the research agents (each with fetched evidence URLs + HTTP status).
  3. MCP SWEEP (out/agent_reports/mcp_sweep_*.json) - the dedicated
     registry/docs sweep wins for the `mcp` field on every row.

The reviewer (human-in-the-loop, AI-assisted) owns every value that lands
in verified.csv: agent rows are promoted as-is only when their evidence
checks out; conflicts are resolved by the reviewer in this file.

    python src/build_corpus.py
"""
from __future__ import annotations

import json
from pathlib import Path

from config import APPS_CSV, OUT, VERIFIED_CSV, CATEGORY_ORDER
from io_utils import apps_to_rows, load_apps, read_csv, write_csv

REPORTS = OUT / "agent_reports"

SEED: dict[int, dict] = {
    1: dict(does="Enterprise CRM platform (Sales Cloud) with the largest integration ecosystem in the category.",
            auth="OAuth2", auth_detail="OAuth 2.0 web-server + JWT-bearer flows; connected apps issue client id/secret.",
            gate="Open self-serve", gate_detail="Free Developer Edition org is self-serve; create a connected app inside it for client credentials. Production orgs are sales-led, but the developer path is open.",
            surface="Documented REST", breadth="Huge: REST + SOAP + Bulk v2 + Streaming + Platform Events + Metadata API",
            verdict="Ready", blocker=""),
    2: dict(does="All-in-one CRM + marketing hub (contacts, deals, email, automation).",
            auth="OAuth2", auth_detail="OAuth2 for public apps; private-app access tokens for server-to-server.",
            gate="Open self-serve", gate_detail="Free CRM tier is self-serve; create a private app token or register a public app instantly.",
            surface="Documented REST", breadth="Very broad: CRM objects, marketing events, workflows, files, webhooks (~150+ endpoints)",
            verdict="Ready", blocker=""),
    3: dict(does="Sales CRM for SMBs with visual pipelines.",
            auth="Token", auth_detail="Per-user API token (simple) or OAuth2 for marketplace apps.",
            gate="Open self-serve", gate_detail="14-day trial self-serve; API token visible in personal settings right away.",
            surface="Documented REST", breadth="Broad CRUD: deals, persons, activities, notes, webhooks (~100 endpoints)",
            verdict="Ready", blocker=""),
    7: dict(does="Zoho's CRM suite (sales force automation, omni-channel).",
            auth="OAuth2", auth_detail="OAuth2 with self-registered clients; refresh tokens long-lived.",
            gate="Open self-serve", gate_detail="Free plan + self-serve API client registration via api-console.zoho.com.",
            surface="Documented REST", breadth="Broad: modules CRUD, bulk read/write, related lists, webhooks",
            verdict="Ready", blocker=""),
    9: dict(does="Google-friendly CRM (works inside Gmail) for SMB sales teams.",
            auth="API key", auth_detail="Integration tokens (Bearer) or OAuth2 for marketplace apps.",
            gate="Open self-serve", gate_detail="14-day trial self-serve; generate integration token in settings.",
            surface="Documented REST", breadth="Broad CRUD: leads, opportunities, activities, users, webhooks",
            verdict="Ready", blocker=""),
    11: dict(does="Customer-service suite (ticketing, help center, chat, voice).",
             auth="Token", auth_detail="API token with HTTP Basic (email/token) or OAuth2 for apps.",
             gate="Open self-serve", gate_detail="Self-serve trial; enable token access in admin settings (you are the admin on a trial).",
             surface="Documented REST", breadth="Very broad: tickets, users, orgs, macros, views, chat, voice, webhooks",
             verdict="Ready", blocker=""),
    12: dict(does="Customer-messaging platform (inbox,Fin AI agent, outbound).",
             auth="Token", auth_detail="Access tokens (Bearer) or OAuth2 for public apps.",
             gate="Open self-serve", gate_detail="14-day trial self-serve; create access token in developer hub.",
             surface="Documented REST", breadth="Broad: contacts, conversations, tickets, data events, news",
             verdict="Ready", blocker=""),
    13: dict(does="Freshworks' helpdesk (tickets, Freddy AI, self-service).",
             auth="API key", auth_detail="Per-account API key as Basic auth (key:X).",
             gate="Open self-serve", gate_detail="Free plan available; API key shown in profile settings instantly.",
             surface="Documented REST", breadth="Broad: tickets, contacts, companies, agents, solutions, Canned Responses",
             verdict="Ready", blocker=""),
    18: dict(does="Help desk for SMBs (shared inbox + customer profiles).",
             auth="API key", auth_detail="Per-user API key (Bearer), OAuth2 for apps.",
             gate="Open self-serve", gate_detail="15-day trial self-serve; API key in settings immediately.",
             surface="Documented REST", breadth="Moderate: customers, conversations, mailboxes, docs, reports, webhooks",
             verdict="Ready", blocker=""),
    19: dict(does="Ecommerce-focused helpdesk built on Shopify data (tickets with order context).",
             auth="OAuth2", auth_detail="OAuth2 for apps; per-user API tokens also issued.",
             gate="Open self-serve", gate_detail="Trial signup self-serve (Shopify-adjacent); token in settings after signup.",
             surface="Documented REST", breadth="Moderate: conversations, customers, events, fields, webhooks",
             verdict="Ready", blocker=""),
    21: dict(does="Team chat platform (channels, huddles, workflow automation).",
             auth="OAuth2", auth_detail="Bot/user tokens (xoxb/xoxp) via OAuth2 install flow; app-level tokens.",
             gate="Open self-serve", gate_detail="Create an app and install to a free workspace in minutes at api.slack.com.",
             surface="Documented REST", breadth="Very broad: chat, conversations, users, files, admin, workflows + Events API + Socket Mode",
             verdict="Ready", blocker=""),
    22: dict(does="CPaaS: SMS, voice, WhatsApp, email, verify APIs.",
             auth="API key", auth_detail="Account SID + auth token (Basic) or API keys; signing keys for webhooks.",
             gate="Open self-serve", gate_detail="Free trial account with credit is self-serve; instant credentials.",
             surface="Documented REST", breadth="Very broad: messaging, voice, video, verify, lookup, studio",
             verdict="Ready", blocker=""),
    26: dict(does="Chat/voice communities platform (servers, bots, rich presence).",
             auth="Token", auth_detail="Bot tokens (Bearer) via developer portal; OAuth2 for user apps.",
             gate="Open self-serve", gate_detail="Create a bot instantly in the developer portal; free.",
             surface="Documented REST", breadth="Broad for platform control: channels, messages, guilds, interactions, voice",
             verdict="Ready", blocker=""),
    27: dict(does="Messaging app with a free Bot API and a paid gateway for business messaging.",
             auth="Token", auth_detail="Bot API: token in URL/Bearer. Telegram Business API: separate access token.",
             gate="Open self-serve", gate_detail="Bot token from @BotFather instantly, free. Business/gateway access is a separate application.",
             surface="Documented REST", breadth="Broad for bots: messages, updates, inline mode, payments, web apps",
             verdict="Ready", blocker=""),
    28: dict(does="WhatsApp Business Platform (Cloud API) for business messaging at scale.",
             auth="Token", auth_detail="System-user access tokens (Bearer) via Meta Business; app secret for webhooks (HMAC).",
             gate="Admin approval", gate_detail="Requires Meta Business verification + app review for higher tiers; a dev can start on a test number self-serve, but production sends need business verification.",
             surface="Documented REST", breadth="Moderate: messages, templates, phone numbers, webhooks",
             verdict="Ready with caveats", blocker="Business verification + app review before production sends"),
    31: dict(does="Google's paid-search advertising API (campaigns, ads, bidding, reporting).",
             auth="OAuth2", auth_detail="OAuth2 service accounts or user flows; Google Ads developer token required on top.",
             gate="Admin approval", gate_detail="Developer token requires an application (basic access granted after review) tied to a manager account; test accounts are instant.",
             surface="Documented REST", breadth="Huge (gRPC/REST): campaigns, criteria, ads, bidding, change events, GAQL reporting",
             verdict="Ready with caveats", blocker="Developer-token application + manager-account linkage"),
    32: dict(does="Meta's advertising API (Facebook/Instagram campaigns, audiences, insights).",
             auth="OAuth2", auth_detail="Facebook Login OAuth2; system-user tokens for servers; appsecret_proof HMAC recommended.",
             gate="Admin approval", gate_detail="Basic access self-serve; advanced access needs App Review + business verification by an admin.",
             surface="Documented REST", breadth="Very broad: ad accounts, campaigns, insights, audiences, catalog",
             verdict="Ready with caveats", blocker="App review + business verification for advanced access"),
    33: dict(does="LinkedIn's paid-campaigns API (sponsored content, audiences, reporting).",
             auth="OAuth2", auth_detail="OAuth 2.0 3-legged; member + app permissions on top.",
             gate="Admin approval", gate_detail="Marketing API product access requires an approved LinkedIn app (application review) plus ad-account admin.",
             surface="Documented REST", breadth="Broad: ad accounts, campaigns, creatives, audience segments, analytics",
             verdict="Ready with caveats", blocker="Marketing API product access is application-gated"),
    35: dict(does="Email-marketing/ESP platform (audiences, campaigns, automation).",
             auth="API key", auth_detail="API key (Basic user:key) or OAuth2 for apps.",
             gate="Open self-serve", gate_detail="Free tier self-serve; API key in account extras instantly.",
             surface="Documented REST", breadth="Broad: lists, members, campaigns, automations, reports (Marketing + Transactional split)",
             verdict="Ready", blocker=""),
    36: dict(does="Customer data + marketing automation platform (ecommerce-focused).",
             auth="API key", auth_detail="Private API keys (Basic) with scopes; OAuth2 added for partner apps.",
             gate="Open self-serve", gate_detail="Free tier self-serve; create private key in settings instantly.",
             surface="Documented REST", breadth="Very broad: profiles, events, campaigns, metrics, segments, catalogs, reporting",
             verdict="Ready", blocker=""),
    38: dict(does="Pinterest API v5 (pins, boards, ad campaigns, analytics).",
             auth="OAuth2", auth_detail="OAuth 2.0 access tokens with scopes; ad-account scoping.",
             gate="Open self-serve", gate_detail="Developer account + app creation self-serve; instant access to v5 read/write basics.",
             surface="Documented REST", breadth="Moderate: boards, pins, media, ad accounts, campaigns, analytics",
             verdict="Ready", blocker=""),
    40: dict(does="Email delivery API (transactional send + email marketing via Twilio SendGrid).",
             auth="API key", auth_detail="Bearer API keys with granular permissions.",
             gate="Open self-serve", gate_detail="Free tier self-serve; create API key immediately after signup.",
             surface="Documented REST", breadth="Broad: mail send, templates, contacts, campaigns, suppressions, inbound parse",
             verdict="Ready", blocker=""),
    41: dict(does="Leading hosted-ecommerce platform (storefront + admin APIs, apps).",
             auth="OAuth2", auth_detail="Admin API access tokens for custom apps (created in dev dashboard); OAuth2 for public apps; storefront tokens for Storefront API.",
             gate="Open self-serve", gate_detail="Partner account + free development store is self-serve; custom-app token issued instantly inside the store admin.",
             surface="REST + GraphQL", breadth="Very broad: Admin REST+GraphQL, Storefront GraphQL, webhooks, functions",
             verdict="Ready", blocker=""),
    42: dict(does="Open-source ecommerce plugin for WordPress (the WooCommerce REST API).",
             auth="API key", auth_detail="Consumer key/secret over HTTPS (Basic) or OAuth 1.0a for non-HTTPS.",
             gate="Open self-serve", gate_detail="Self-host or WordPress.com - plugin is free; generate keys in WP admin (you are the admin).",
             surface="Documented REST", breadth="Broad CRUD: products, orders, customers, coupons, reports, webhooks",
             verdict="Ready", blocker=""),
    43: dict(does="SaaS headless-commerce platform ( storefront + catalog + checkout APIs).",
             auth="Token", auth_detail="API accounts -> OAuth2 client-credentials token, or store API tokens (Basic/acst).",
             gate="Open self-serve", gate_detail="Free trial self-serve; create API account/credentials in store settings.",
             surface="REST + GraphQL", breadth="Broad: catalog (v3 REST + GraphQL), orders, customers, themes, webhooks",
             verdict="Ready", blocker=""),
    45: dict(does="Open-source commerce platform (Adobe Commerce / Magento Open Source).",
             auth="Token", auth_detail="Integration access tokens (Bearer), OAuth2 for apps, session/key pairs for admin.",
             gate="Open self-serve", gate_detail="Free open-source edition self-hostable; admin creates an integration token (you are the admin).",
             surface="REST + GraphQL", breadth="Broad: catalog, inventory, orders, customers + GraphQL storefront APIs",
             verdict="Ready", blocker=""),
    46: dict(does="Website builder with commerce; REST API covers core commerce objects.",
             auth="API key", auth_detail="Single API key (Bearer) per site.",
             gate="Paid self-serve", gate_detail="API access requires a paid (Business+) site plan; key generated in site settings.",
             surface="Documented REST", breadth="Narrow: products, inventory, orders, transactions, webhooks",
             verdict="Ready with caveats", blocker="Narrow API scope, paid plan required"),
    49: dict(does="Amazon's unified API for selling partners (orders, listings, finance, FBA).",
             auth="OAuth2", auth_detail="Login-with-Amazon OAuth2 + AWS SigV4 (IAM role) for most endpoints.",
             gate="Paid self-serve", gate_detail="Requires a Professional seller account ($39.99/mo, self-serve) then self-registered app (LWA credentials) - or vendor status for Vendor APIs.",
             surface="Documented REST", breadth="Very broad: orders, inventory, pricing, FBA, finance, reports, notifications",
             verdict="Ready with caveats", blocker="Professional seller account + IAM/LWA wiring"),
    51: dict(does="SEO data API provider (SERPs, keywords, backlinks, domain analytics) - pay-as-you-go.",
             auth="Basic", auth_detail="login:password as HTTP Basic header over HTTPS.",
             gate="Paid self-serve", gate_detail="Self-serve signup; API access needs a minimum deposit ($ min balance) then pay-per-request.",
             surface="Documented REST", breadth="Very broad: SERP API, Keywords, DataForSEO Labs, Backlinks, Domain Analytics, On-Page, Content Analysis",
             verdict="Ready", blocker=""),
    53: dict(does="SEO intelligence suite (backlink index, keywords, site audit); official API access is restricted.",
             auth="API key", auth_detail="API key/token for API v3/v2 endpoints.",
             gate="Contact sales / partner", gate_detail="Public API v3 access is partner/enterprise-gated (application + sales conversation); the product UI is self-serve but the API is not.",
             surface="Documented REST", breadth="Broad where accessible: site explorer, keywords explorer, backlinks (v3 units-based)",
             verdict="Ready with caveats", blocker="API access partner-gated; product plans do not include open API"),
    55: dict(does="Web-scraping/automation platform (Actors) with storage, proxies, scheduling.",
             auth="Token", auth_detail="Personal access tokens (Bearer) with per-token permissions.",
             gate="Open self-serve", gate_detail="Free tier with platform credits; token in console instantly.",
             surface="Documented REST", breadth="Very broad: actors run/input/dataset API, key-value store, schedules, webhooks, log",
             verdict="Ready", blocker=""),
    56: dict(does="Web-scraping API for LLMs (crawl, scrape, extract to markdown/structured).",
             auth="API key", auth_detail="Bearer API key.",
             gate="Open self-serve", gate_detail="Free tier with credits, self-serve dashboard, instant key.",
             surface="Documented REST", breadth="Focused but deep: scrape, crawl, map, search, extract, v2 agents SDK",
             verdict="Ready", blocker=""),
    57: dict(does="Web-data platform: proxies, Web Unlocker, SERP API, scraping browser, datasets.",
             auth="API key", auth_detail="Account token (Bearer) + zone-level proxy credentials.",
             gate="Paid self-serve", gate_detail="Self-serve signup with card/minimum deposit for API products; instant credentials.",
             surface="Documented REST", breadth="Broad across products: unlocker, serp, scraper browser control, datasets",
             verdict="Ready", blocker=""),
    60: dict(does="Data-intelligence/spreadsheet platform (enrichment, waterfalls, AI agents in Clay).",
             auth="OAuth2", auth_detail="OAuth2 for public apps; per-user API keys for private API use.",
             gate="Paid self-serve", gate_detail="Self-serve signup but paid plans; API access tied to plan credits.",
             surface="Documented REST", breadth="Moderate: tables, rows, enrichment runs, webhooks (public API subset of product)",
             verdict="Ready with caveats", blocker="API subset of a heavy product; plan-gated usage"),
    61: dict(does="Code hosting + collaboration platform (repos, PRs, issues, actions).",
             auth="Token", auth_detail="PATs (Bearer/Basic), GitHub App installation JWT + tokens, OAuth2 for user apps.",
             gate="Open self-serve", gate_detail="Free account; fine-grained PAT or GitHub App self-serve instantly.",
             surface="REST + GraphQL", breadth="Huge: repos, PRs, issues, actions, packages, orgs (~500+ REST endpoints + GraphQL)",
             verdict="Ready", blocker=""),
    62: dict(does="Frontend cloud platform (deployments, domains, serverless functions).",
             auth="Token", auth_detail="Access tokens (Bearer); OAuth2 for apps.",
             gate="Open self-serve", gate_detail="Free Hobby tier self-serve; create token in account settings instantly.",
             surface="Documented REST", breadth="Broad: projects, deployments, domains, DNS, env vars, webhooks + mgmt SDK",
             verdict="Ready", blocker=""),
    63: dict(does="Netlify hosting/build platform (sites, deploys, functions, forms).",
             auth="Token", auth_detail="Personal access tokens (Bearer) or OAuth2 for apps.",
             gate="Open self-serve", gate_detail="Free tier self-serve; PAT created instantly.",
             surface="Documented REST", breadth="Broad: sites, deploys, functions, forms, split tests, webhooks",
             verdict="Ready", blocker=""),
    64: dict(does="Edge/network/security platform (DNS, zones, workers, WAF, R2, KV).",
             auth="Token", auth_detail="Scoped API tokens (Bearer); user tokens; mTLS options; OAuth2 for some flows.",
             gate="Open self-serve", gate_detail="Free plan self-serve; scoped tokens created instantly in dash.",
             surface="Documented REST", breadth="Huge: zones, DNS, workers, KV, R2, WAF, rulesets (~1000+ endpoints)",
             verdict="Ready", blocker=""),
    65: dict(does="Open-source Firebase alternative: Postgres, auth, storage, edge functions.",
             auth="API key", auth_detail="Anon + service_role JWT keys for data APIs; PAT/OAuth2 for management API.",
             gate="Open self-serve", gate_detail="Free projects self-serve instantly; keys in dashboard; management API PAT self-serve.",
             surface="Documented REST", breadth="Auto REST (PostgREST) per project + Storage/Auth admin + management API (projects, branches)",
             verdict="Ready", blocker=""),
    69: dict(does="Cloud observability platform (metrics, logs, traces, monitors).",
             auth="API key", auth_detail="API key + application key pair (DD-API-Key header + app key).",
             gate="Open self-serve", gate_detail="Trial self-serve; create both keys in org settings instantly.",
             surface="Documented REST", breadth="Very broad: metrics, events, monitors, dashboards, logs, incidents, usage",
             verdict="Ready", blocker=""),
    70: dict(does="Error-monitoring platform (exceptions, performance, releases, alerts).",
             auth="Token", auth_detail="User auth tokens (Bearer) or OAuth2 integrations.",
             gate="Open self-serve", gate_detail="Free developer tier self-serve; create auth token instantly.",
             surface="Documented REST", breadth="Broad: projects, issues, events, releases, alerts, organizations",
             verdict="Ready", blocker=""),
    71: dict(does="Connected workspace (docs, databases, wikis) with block-level API.",
             auth="OAuth2", auth_detail="OAuth2 for public integrations; internal integration tokens (Bearer) for private ones.",
             gate="Open self-serve", gate_detail="Create an internal integration instantly on a free workspace; public OAuth apps self-serve.",
             surface="Documented REST", breadth="Broad: pages, databases, blocks, users, comments + webhooks",
             verdict="Ready", blocker=""),
    72: dict(does="Airtable low-code database/spreadsheet platform (bases, tables, records).",
             auth="Token", auth_detail="Personal access tokens or OAuth2; Bearer auth.",
             gate="Open self-serve", gate_detail="Free tier self-serve; PAT creation instant.",
             surface="Documented REST", breadth="Broad: bases, tables, records, fields, views + webhooks + enterprise APIs",
             verdict="Ready", blocker=""),
    73: dict(does="Issue tracking for software teams (issues, projects, cycles, roadmaps).",
             auth="API key", auth_detail="Personal API keys (Basic) or OAuth2 apps; Bearer accepted.",
             gate="Open self-serve", gate_detail="Free plan self-serve; API key in settings instantly.",
             surface="Documented GraphQL", breadth="Full-product GraphQL API: issues, projects, cycles, teams, documents, webhooks",
             verdict="Ready", blocker=""),
    74: dict(does="Atlassian's issue/project tracker (Jira Cloud) used by software and IT teams.",
             auth="Basic", auth_detail="Basic with email + API token, or OAuth 2.0 (3LO) for user-context apps; PATs for Data Center.",
             gate="Open self-serve", gate_detail="Free Cloud plan self-serve; each user creates an API token at id.atlassian.com instantly. Admins can gate personal access tokens, but the default path is open.",
             surface="Documented REST", breadth="Huge: issues, projects, boards, sprints, users, workflows, JQL search + webhooks",
             verdict="Ready", blocker=""),
    75: dict(does="Work-management platform (tasks, projects, portfolios, goals).",
             auth="Token", auth_detail="Personal access tokens or OAuth2; Bearer auth.",
             gate="Open self-serve", gate_detail="Free tier self-serve; PAT created instantly in developer settings.",
             surface="Documented REST", breadth="Broad: tasks, projects, sections, stories, portfolios, events webhooks",
             verdict="Ready", blocker=""),
    76: dict(does="Work OS (boards, dashboards, automations) with GraphQL API.",
             auth="Token", auth_detail="API v2 tokens (Bearer) or OAuth2 for apps.",
             gate="Open self-serve", gate_detail="Free trial self-serve; token in avatar menu instantly.",
             surface="Documented GraphQL", breadth="Full GraphQL API: boards, items, updates, docs, webhooks + apps framework",
             verdict="Ready", blocker=""),
    77: dict(does="All-in-one productivity platform (tasks, docs, whiteboards, chat).",
             auth="Token", auth_detail="Personal tokens (Bearer) or OAuth2 apps.",
             gate="Open self-serve", gate_detail="Free tier self-serve; app + token instant via developer portal.",
             surface="Documented REST", breadth="Broad: tasks, lists, folders, spaces, docs, goals, time tracking, webhooks",
             verdict="Ready", blocker=""),
    78: dict(does="Doc-as-tool platform (documents with tables, automations, Packs).",
             auth="API key", auth_detail="Bearer API token per account/workspace.",
             gate="Open self-serve", gate_detail="Free tier self-serve; token in account settings instantly.",
             surface="Documented REST", breadth="Moderate: docs, tables, rows, formulas, controls + webhook automations",
             verdict="Ready", blocker=""),
    81: dict(does="Payments platform (charges, subscriptions, invoicing, connect, billing).",
             auth="API key", auth_detail="Secret keys (Bearer); restricted keys with granular scopes; webhook signing HMAC.",
             gate="Open self-serve", gate_detail="Account + test-mode keys instantly self-serve; live keys activate with business details (self-serve).",
             surface="Documented REST", breadth="Huge: payments, billing, connect, issuing, terminal, treasury (~100s endpoints)",
             verdict="Ready", blocker=""),
    82: dict(does="Financial-account aggregation API (auth, transactions, identity, assets).",
             auth="API key", auth_detail="client_id + secret (POST body); link tokens for end-user flows.",
             gate="Open self-serve", gate_detail="Sandbox instant and free self-serve; production access requires company registration + review (documented, days not months).",
             surface="Documented REST", breadth="Very broad: items, accounts, transactions, investments, liabilities, signal, transfer",
             verdict="Ready with caveats", blocker="Production requires company verification; sandbox is instant"),
    83: dict(does="Crypto exchange (spot, futures, wallet) with public + signed trading APIs.",
             auth="HMAC", auth_detail="API key + secret HMAC-SHA256 signatures (or RSA); IP allowlisting.",
             gate="Open self-serve", gate_detail="Free account; API keys self-serve in user center instantly.",
             surface="Documented REST", breadth="Very broad: spot, margin, futures, wallet, sub-accounts, market data",
             verdict="Ready", blocker=""),
    87: dict(does="Accounting platform for SMBs (invoices, bank feeds, ledger).",
             auth="OAuth2", auth_detail="OAuth 2.0 with xero-tenant-id header per org.",
             gate="Open self-serve", gate_detail="Free trial org + self-serve app registration (30-min setup); partner apps free with connected orgs.",
             surface="Documented REST", breadth="Broad: accounting, bank feeds, assets, payroll (AU/NZ/UK), files, webhooks",
             verdict="Ready", blocker=""),
}


def main() -> None:
    apps = load_apps()
    rows = {a.id: apps_to_rows(apps)[apps.index(a)] for a in apps}

    # primary evidence URL for seed rows (canonical developer docs)
    docs = {
        1: "https://developer.salesforce.com/docs/einstein/genai/guide/api-auth.html",
        2: "https://developers.hubspot.com/docs/api/private-apps",
        3: "https://developers.pipedrive.com/docs/api/v1",
        7: "https://www.zoho.com/crm/developer/docs/api/v6/",
        9: "https://developers.copper.com/",
        11: "https://developer.zendesk.com/api-reference/",
        12: "https://developers.intercom.com/docs/references/rest-api/api.intercom.io/",
        13: "https://developers.freshdesk.com/api/",
        18: "https://developer.helpscout.com/mailbox-api/",
        19: "https://developers.gorgias.com/reference/introduction",
        21: "https://api.slack.com/authentication",
        22: "https://www.twilio.com/docs/iam/keys/api-key",
        26: "https://discord.com/developers/docs/topics/oauth2",
        27: "https://core.telegram.org/bots/api",
        28: "https://developers.facebook.com/docs/whatsapp/cloud-api/get-started",
        31: "https://developers.google.com/google-ads/api/docs/oauth/overview",
        32: "https://developers.facebook.com/docs/marketing-apis/overview/authentication",
        33: "https://learn.microsoft.com/en-us/linkedin/marketing/",
        35: "https://mailchimp.com/developer/marketing/api/root/",
        36: "https://developers.klaviyo.com/en/reference/api_overview",
        38: "https://developers.pinterest.com/docs/api/v5/",
        40: "https://www.twilio.com/docs/sendgrid/for-developers/sending-email/api-getting-started",
        41: "https://shopify.dev/docs/api/admin-graphql",
        42: "https://woocommerce.github.io/woocommerce-rest-api-docs/",
        43: "https://developer.bigcommerce.com/docs/rest-api",
        45: "https://developer.adobe.com/commerce/webapi/rest/",
        46: "https://developers.squarespace.com/commerce-api",
        49: "https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api",
        51: "https://docs.dataforseo.com/v3/overview/",
        53: "https://ahrefs.com/api/documentation",
        55: "https://docs.apify.com/api/v2",
        56: "https://docs.firecrawl.dev/introduction",
        57: "https://docs.brightdata.com/api-reference/overview",
        60: "https://docs.clay.com/reference/quickstart-guide",
        61: "https://docs.github.com/rest/authentication/authenticating-to-the-rest-api",
        62: "https://vercel.com/docs/rest-api/reference/endpoints",
        63: "https://docs.netlify.com/api/get-started/",
        64: "https://developers.cloudflare.com/fundamentals/api/get-started/create-token/",
        65: "https://supabase.com/docs/reference/api/introduction",
        69: "https://docs.datadoghq.com/api/latest/",
        70: "https://docs.sentry.io/api/",
        71: "https://developers.notion.com/reference/introduction",
        72: "https://airtable.com/developers/web/api/introduction",
        73: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
        74: "https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/",
        75: "https://developers.asana.com/reference/gettasks",
        76: "https://developer.monday.com/api-docs/authentication",
        77: "https://clickup.com/api/developer-portal/authentication/",
        78: "https://coda.io/developers/apis/v1",
        81: "https://docs.stripe.com/api",
        82: "https://plaid.com/docs/api/products/",
        83: "https://developers.binance.com/docs/binance-spot-api-docs/rest-api",
        87: "https://developer.xero.com/documentation/api/authentication/oauth2",
    }

    # 1. seed
    for rid, patch in SEED.items():
        if rid in rows:
            rows[rid].update(patch)
            rows[rid]["evidence"] = docs.get(rid, rows[rid]["evidence"])
            if not rows[rid].get("confidence"):
                rows[rid]["confidence"] = 4

    # 2. agent reports (live-verified rows win wholesale)
    n_agent = 0
    reported_ids: set[int] = set()
    for f in sorted(REPORTS.glob("*.json")):
        if f.name.startswith("mcp_sweep"):
            continue
        for rec in json.loads(f.read_text(encoding="utf-8")):
            rid = int(rec["id"])
            if rid not in rows:
                continue
            reported_ids.add(rid)
            ev = rec.get("evidence", [])
            ev_str = ev if isinstance(ev, str) else ",".join(ev)
            rows[rid].update({
                "does": rec.get("does", rows[rid]["does"]),
                "auth": rec.get("auth", rows[rid]["auth"]),
                "auth_detail": rec.get("auth_detail", ""),
                "gate": rec.get("gate", rows[rid]["gate"]),
                "gate_detail": rec.get("gate_detail", ""),
                "surface": rec.get("surface", rows[rid]["surface"]),
                "breadth": rec.get("breadth", ""),
                "mcp": rec.get("mcp", rows[rid].get("mcp", "")),
                "mcp_evidence": rec.get("mcp_evidence", ""),
                "verdict": rec.get("verdict", rows[rid]["verdict"]),
                "blocker": rec.get("blocker") or "",
                "evidence": ev_str,
                "notes": rec.get("notes", ""),
                "confidence": rec.get("confidence", 3),
            })
            n_agent += 1

    # 3. MCP registry sweep: mechanical community floor for unreported apps.
    #    A hit means SOMEONE published an MCP server; official-vs-community
    #    is settled later by the verification report (step 4).
    n_mcp = 0
    sweep_file = OUT / "mcp_sweep_raw.json"
    if sweep_file.exists():
        import re
        raw = json.loads(sweep_file.read_text(encoding="utf-8"))
        for res in raw.get("results", []):
            rid = int(res["id"])
            if rid not in rows or rid in reported_ids or not res.get("hits"):
                continue
            token = rows[rid]["name"].split()[0].split("(")[0].lower()
            if len(token) < 3:
                continue
            if any(re.search(rf"\b{re.escape(token)}\b", h["name"].lower())
                   for h in res["hits"]):
                rows[rid]["mcp"] = "Yes (community)"
                rows[rid]["mcp_evidence"] = res["hits"][0].get("repo") or \
                    res["hits"][0].get("name", "")
                n_mcp += 1

    # 4. official-MCP verification (vendor-docs evidence) outranks the sweep
    off_file = REPORTS / "mcp_officials.json"
    if off_file.exists():
        for rec in json.loads(off_file.read_text(encoding="utf-8")):
            rid = int(rec["id"])
            if rid in rows and rec.get("mcp"):
                rows[rid]["mcp"] = rec["mcp"]
                rows[rid]["mcp_evidence"] = rec.get("mcp_evidence", "")
                n_mcp += 1

    # fill mcp defaults where nothing verified
    for r in rows.values():
        if not r.get("mcp"):
            r["mcp"] = "Unclear"
        if not r.get("confidence"):
            r["confidence"] = 3

    ordered = [rows[a.id] for a in apps]
    write_csv(VERIFIED_CSV, ordered, fieldnames=list(ordered[0].keys()))
    print(f"verified.csv: {len(ordered)} rows (seed {len(SEED)}, agent rows "
          f"{n_agent}, mcp sweep updates {n_mcp}) -> {VERIFIED_CSV.name}")


if __name__ == "__main__":
    main()
