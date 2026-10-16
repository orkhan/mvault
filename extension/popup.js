const setup = document.querySelector("#setup");
const content = document.querySelector("#content");
const urlField = document.querySelector("#vault-url");
const message = document.querySelector("#message");
const matches = document.querySelector("#matches");
const siteLabel = document.querySelector("#site");
let targetTab;
let vaultBase;
const t = (key) => chrome.i18n.getMessage(key);

document.title = t("extName");
document.querySelector("#autofill-label").textContent = t("autofill");
document.querySelector("#vault-address-label").textContent = t("vaultAddress");
urlField.placeholder = t("urlPlaceholder");
document.querySelector("#save").textContent = t("connect");
document.querySelector("#change").textContent = t("changeAddress");

function cleanBase(value) {
  const parsed = new URL(value);
  if (!/^https?:$/.test(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error(t("invalidAddress"));
  }
  return `${parsed.origin}${parsed.pathname.replace(/\/+$/, "")}`;
}

function showMessage(text) {
  message.textContent = text;
}

async function loadMatches() {
  const active = await chrome.tabs.query({ active: true, currentWindow: true });
  targetTab = active[0];
  let targetUrl;
  try { targetUrl = new URL(targetTab.url); }
  catch { throw new Error(t("openWebsite")); }
  if (!/^https?:$/.test(targetUrl.protocol)) throw new Error(t("siteOnly"));
  siteLabel.textContent = targetUrl.hostname;

  const permission = `${new URL(vaultBase).origin}/*`;
  const hasPermission = await chrome.permissions.contains({ origins: [permission] });
  if (!hasPermission) throw new Error(t("reconnect"));
  const appUrl = `${vaultBase}/dashboard/`;
  const vaultTabs = await chrome.tabs.query({ url: `${new URL(vaultBase).origin}/*` });
  const candidates = vaultTabs.filter((tab) => tab.id !== targetTab.id);
  if (!candidates.length) {
    await chrome.tabs.create({ url: appUrl, active: false });
    showMessage(t("signIn"));
    return;
  }

  let vaultTab;
  let data;
  let lastError = t("signInRetry");
  for (const candidate of candidates) {
    try {
      const result = await chrome.scripting.executeScript({
        target: { tabId: candidate.id },
        world: "MAIN",
        func: async (base, hostname, signInRetry, contactError, memberRequired, missingApi) => {
          const response = await fetch(`${base}/extension/matches/?hostname=${encodeURIComponent(hostname)}`, {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
            cache: "no-store",
          });
          if (!response.headers.get("content-type")?.includes("application/json")) {
            if (response.redirected) return { error: signInRetry };
            if (response.status === 404) return { error: missingApi };
            return { error: response.status === 403 ? memberRequired : contactError };
          }
          const body = await response.json();
          if (!response.ok) return { error: body.error || contactError };
          return body;
        },
        args: [vaultBase, targetUrl.hostname, t("signInRetry"), t("contactError"), t("memberAccount"), t("missingApi")],
      });
      const candidateData = result[0]?.result;
      if (Array.isArray(candidateData?.matches)) {
        vaultTab = candidate;
        data = candidateData;
        break;
      }
      if (candidateData?.error) lastError = candidateData.error;
    } catch {
      lastError = t("contactError");
    }
  }
  if (!vaultTab || !data) throw new Error(lastError);
  if (!data.matches.length) {
    showMessage(t("noMatches"));
    return;
  }
  showMessage(t("chooseRecord"));
  for (const record of data.matches) {
    const button = document.createElement("button");
    button.className = "record";
    const name = document.createElement("span");
    name.className = "record-name";
    name.textContent = record.name;
    const username = document.createElement("small");
    username.className = "record-username";
    username.textContent = `${t("username")}: ${record.username || t("noUsername")}`;
    button.append(name, username);
    button.addEventListener("click", () => fillRecord(vaultTab.id, record.id, targetUrl.hostname));
    matches.append(button);
  }
}

async function fillRecord(vaultTabId, recordId, hostname) {
  try {
    showMessage(t("filling"));
    const response = await chrome.scripting.executeScript({
      target: { tabId: vaultTabId },
      world: "MAIN",
      func: async (base, id, site, signInRetry, refreshVault, retrievalError) => {
        const csrf = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1];
        if (!csrf) return { error: refreshVault };
        const response = await fetch(`${base}/extension/records/${id}/`, {
          method: "POST",
          credentials: "same-origin",
          headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": decodeURIComponent(csrf) },
          body: new URLSearchParams({ hostname: site }),
          cache: "no-store",
        });
        if (!response.headers.get("content-type")?.includes("application/json")) return { error: signInRetry };
        const body = await response.json();
        return response.ok ? body : { error: body.error || retrievalError };
      },
      args: [vaultBase, recordId, hostname, t("signInRetry"), t("refreshVault"), t("retrievalError")],
    });
    const credential = response[0]?.result;
    if (!credential || credential.error) throw new Error(credential?.error || t("retrievalError"));
    const filled = await chrome.scripting.executeScript({
      target: { tabId: targetTab.id },
      world: "MAIN",
      func: (username, password, noPasswordField) => {
        const visible = (element) => {
          const style = getComputedStyle(element);
          return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0 && !element.disabled;
        };
        const passwords = [...document.querySelectorAll('input[type="password"]')].filter(visible);
        if (!passwords.length) return { error: noPasswordField };
        const form = passwords[0].closest("form") || document;
        const users = [...form.querySelectorAll('input:not([type]), input[type="text"], input[type="email"], input[autocomplete="username"]')].filter(visible);
        const usernameField = users.find((field) => field.autocomplete === "username" || /user|email|login|account/i.test(`${field.name} ${field.id} ${field.placeholder}`)) || (users.length === 1 ? users[0] : null);
        const setValue = (field, value) => {
          const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(field), "value")?.set;
          if (setter) setter.call(field, value); else field.value = value;
          field.dispatchEvent(new Event("input", { bubbles: true }));
          field.dispatchEvent(new Event("change", { bubbles: true }));
        };
        if (usernameField && username) setValue(usernameField, username);
        setValue(passwords[0], password);
        return { username: Boolean(usernameField && username), password: true };
      },
      args: [credential.username, credential.password, t("noPasswordField")],
    });
    const result = filled[0]?.result;
    if (result?.error) throw new Error(result.error);
    showMessage(result?.username ? t("filledBoth") : t("filledPassword"));
  } catch (error) {
    showMessage(error.message || t("fillError"));
  }
}

document.querySelector("#save").addEventListener("click", async () => {
  try {
    vaultBase = cleanBase(urlField.value.trim());
    const permission = `${new URL(vaultBase).origin}/*`;
    if (!await chrome.permissions.request({ origins: [permission] })) {
      throw new Error(t("permissionDenied"));
    }
    await chrome.storage.local.set({ vaultBase });
    setup.hidden = true;
    content.hidden = false;
    await loadMatches();
  } catch (error) {
    setup.hidden = false;
    content.hidden = true;
    alert(error.message || t("invalidAddress"));
  }
});

document.querySelector("#change").addEventListener("click", async () => {
  await chrome.storage.local.remove("vaultBase");
  content.hidden = true;
  setup.hidden = false;
  urlField.focus();
});

(async () => {
  const saved = await chrome.storage.local.get("vaultBase");
  if (!saved.vaultBase) {
    setup.hidden = false;
    return;
  }
  vaultBase = saved.vaultBase;
  setup.hidden = true;
  content.hidden = false;
  try { await loadMatches(); }
  catch (error) { showMessage(error.message || t("contactError")); }
})();
