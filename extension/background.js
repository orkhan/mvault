"use strict";
importScripts("vault-client.js");

const t = (key, substitutions) => chrome.i18n.getMessage(key, substitutions);
const ALL_SITES = ["https://*/*", "http://*/*"];
const SCRIPT_ID = "mvault-autofill";
const PENDING_TTL = 60 * 1000;
const STEP_TTL = 5 * 60 * 1000;
const FILLED_TTL = 10 * 60 * 1000;
const CACHE_TTL = 30 * 1000;
const DEFAULTS = { vaultBase: "", autoEnabled: false, autoShow: true, autoSave: true, neverShow: [], neverSave: [], lastTarget: null };

const settings = () => chrome.storage.local.get(DEFAULTS);
const sessionGet = async (key) => (await chrome.storage.session.get(key))[key];
const sessionSet = (key, value) => chrome.storage.session.set({ [key]: value });

// Registers the content script only while the member has opted in and granted access to all sites.
async function syncContentScripts() {
  const s = await settings();
  const existing = await chrome.scripting.getRegisteredContentScripts({ ids: [SCRIPT_ID] }).catch(() => []);
  if (existing.length) await chrome.scripting.unregisterContentScripts({ ids: [SCRIPT_ID] });
  if (!s.vaultBase || !s.autoEnabled || !await chrome.permissions.contains({ origins: ALL_SITES })) return;
  await chrome.scripting.registerContentScripts([{
    id: SCRIPT_ID, js: ["fill.js", "content.js"], matches: ALL_SITES, excludeMatches: [`${new URL(s.vaultBase).origin}/*`],
    runAt: "document_idle", allFrames: false, persistAcrossSessions: true,
  }]);
}

chrome.runtime.onInstalled.addListener(() => { syncContentScripts().catch(() => {}); });
chrome.runtime.onStartup.addListener(() => { syncContentScripts().catch(() => {}); });
chrome.permissions.onRemoved.addListener(() => { syncContentScripts().catch(() => {}); });
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && (changes.vaultBase || changes.autoEnabled)) syncContentScripts().catch(() => {});
});

function setBadge(tabId, text, title) {
  chrome.action.setBadgeText({ tabId, text }).catch(() => {});
  chrome.action.setTitle({ tabId, title: title || t("extName") }).catch(() => {});
  if (text) {
    chrome.action.setBadgeBackgroundColor({ tabId, color: "#d6b978" }).catch(() => {});
    Promise.resolve(chrome.action.setBadgeTextColor?.({ tabId, color: "#171816" })).catch(() => {});
  }
}

chrome.tabs.onUpdated.addListener((tabId, info) => { if (info.status === "loading") setBadge(tabId, ""); });
chrome.tabs.onRemoved.addListener((tabId) => { chrome.storage.session.remove([`pending:${tabId}`, `step:${tabId}`, `filled:${tabId}`]); });

async function lookup(base, host, fresh) {
  const key = `matches:${host}`;
  const cached = await sessionGet(key);
  if (!fresh && cached && Date.now() - cached.at < CACHE_TTL) return { matches: cached.matches };
  const result = await MvVault.request(base, "GET", "/extension/matches/", { hostname: host });
  if (!result.data) return result;
  await sessionSet(key, { at: Date.now(), matches: result.data.matches });
  return { matches: result.data.matches };
}

async function readPending(tabId) {
  const pending = await sessionGet(`pending:${tabId}`);
  if (pending && pending.expires > Date.now()) return pending;
  if (pending) await chrome.storage.session.remove(`pending:${tabId}`);
  return null;
}

// Decides what to offer for a captured login. The password only leaves the worker in the save-check POST.
async function decide(base, pending) {
  const found = await lookup(base, pending.host, true);
  if (!found.matches) return { error: true };
  const username = pending.username.toLowerCase();
  if (!found.matches.some((match) => match.username.trim().toLowerCase() === username)) {
    const projects = await MvVault.request(base, "GET", "/extension/projects/");
    return projects.data ? { state: "new", projects: projects.data.projects } : { error: true };
  }
  const check = await MvVault.request(base, "POST", "/extension/save-check/",
    { hostname: pending.host, username: pending.username, password: pending.password }, { interactive: true });
  if (!check.data) return { error: true };
  if (check.data.state === "exists") return { drop: true };
  return { state: check.data.state, record: check.data.record, projects: check.data.projects };
}

async function addHost(listName, host) {
  const s = await settings();
  if (!s[listName].includes(host)) await chrome.storage.local.set({ [listName]: [...s[listName], host] });
}

async function handle(message, sender) {
  const s = await settings();
  if (!s.vaultBase || !s.autoEnabled) return {};
  const tabId = sender.tab.id;
  const url = new URL(sender.url);
  if (!/^https?:$/.test(url.protocol)) return {};
  const host = url.hostname;
  const base = s.vaultBase;

  switch (message.type) {
    case "pageReady": {
      if (!s.autoShow || s.neverShow.includes(host)) return { matches: [] };
      const found = await lookup(base, host);
      if (found.matches?.length) setBadge(tabId, String(found.matches.length), t("badgeMatches"));
      else if (found.signedOut) setBadge(tabId, "!", t("badgeSignIn"));
      return { matches: found.matches || [] };
    }
    case "fill": {
      const id = Number(message.recordId);
      if (!Number.isSafeInteger(id) || id <= 0) return { error: t("retrievalError") };
      const result = await MvVault.request(base, "POST", `/extension/records/${id}/`, { hostname: host }, { interactive: true });
      if (!result.data) return { error: result.error || t("retrievalError") };
      await sessionSet(`filled:${tabId}`, { password: result.data.password, at: Date.now() });
      return { username: result.data.username, password: result.data.password };
    }
    case "usernameStep": {
      if (!s.autoSave || s.neverSave.includes(host) || typeof message.username !== "string") return {};
      await sessionSet(`step:${tabId}`, { host, username: message.username.slice(0, 255), expires: Date.now() + STEP_TTL });
      return {};
    }
    case "captured": {
      if (!s.autoSave || s.neverSave.includes(host) || typeof message.password !== "string" || !message.password || message.password.length > 1024) return {};
      const filled = await sessionGet(`filled:${tabId}`);
      if (filled && filled.password === message.password && Date.now() - filled.at < FILLED_TTL) {
        await chrome.storage.session.remove(`pending:${tabId}`);
        return {};
      }
      const step = await sessionGet(`step:${tabId}`);
      const typed = typeof message.username === "string" ? message.username.trim().slice(0, 255) : "";
      const username = typed || (step && step.host === host && step.expires > Date.now() ? step.username : "");
      await sessionSet(`pending:${tabId}`, { host, scheme: url.protocol === "http:" ? "http" : "https", username, password: message.password, expires: Date.now() + PENDING_TTL });
      return {};
    }
    case "getPending": {
      const pending = await readPending(tabId);
      if (!pending) return {};
      if (!s.autoSave || s.neverSave.includes(pending.host)) {
        await chrome.storage.session.remove(`pending:${tabId}`);
        return {};
      }
      if (!pending.decision) {
        const decision = await decide(base, pending);
        if (decision.drop) {
          await chrome.storage.session.remove(`pending:${tabId}`);
          return {};
        }
        if (decision.error) return {};
        pending.decision = decision;
        await sessionSet(`pending:${tabId}`, pending);
      }
      const { state, record, projects } = pending.decision;
      return { prompt: { host: pending.host, username: pending.username, state, record, projects: projects || [], lastTarget: s.lastTarget } };
    }
    case "save": {
      const pending = await readPending(tabId);
      if (!pending?.decision) return { error: t("saveFailed") };
      const { decision } = pending;
      const params = { hostname: pending.host, username: pending.username, password: pending.password, scheme: pending.scheme };
      if (decision.state === "update") {
        Object.assign(params, { mode: "update", record_id: decision.record.id });
      } else {
        Object.assign(params, { mode: "create", project_id: Number(message.projectId) || 0, name: String(message.name || "").slice(0, 160) });
        if (message.folderId) params.folder_id = Number(message.folderId) || 0;
      }
      const result = await MvVault.request(base, "POST", "/extension/save/", params, { interactive: true });
      if (!result.data) return { error: result.error || t("saveFailed") };
      await chrome.storage.session.remove([`pending:${tabId}`, `matches:${host}`]);
      if (params.mode === "create") await chrome.storage.local.set({ lastTarget: { projectId: params.project_id, folderId: Number(message.folderId) || null } });
      return { action: result.data.action };
    }
    case "dismiss": {
      const pending = await readPending(tabId);
      await chrome.storage.session.remove(`pending:${tabId}`);
      if (message.never && pending) await addHost("neverSave", pending.host);
      return {};
    }
    case "neverShow":
      await addHost("neverShow", host);
      setBadge(tabId, "");
      return {};
    default:
      return {};
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Only the content script in a tab's top frame may talk to the worker; the site is taken from the sender, never from the message.
  if (sender.id !== chrome.runtime.id || !sender.tab || sender.frameId !== 0 || !sender.url) return false;
  handle(message, sender).then(sendResponse, () => sendResponse({ error: t("contactError") }));
  return true;
});
