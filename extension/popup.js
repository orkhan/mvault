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
document.querySelector("#auto-title").textContent = t("autoTitle");
document.querySelector("#auto-hint").textContent = t("autoHint");
document.querySelector("#auto-show-label").textContent = t("optSuggest");
document.querySelector("#auto-save-label").textContent = t("optSave");
const ALL_SITES = ["https://*/*", "http://*/*"];
const autoEnabled = document.querySelector("#auto-enabled");
const autoOptions = document.querySelector("#auto-options");
const autoShow = document.querySelector("#auto-show");
const autoSave = document.querySelector("#auto-save");
const hiddenSites = document.querySelector("#hidden-sites");

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
  const result = await MvVault.request(vaultBase, "GET", "/extension/matches/", { hostname: targetUrl.hostname }, { interactive: true, excludeTabId: targetTab.id });
  if (!result.data) {
    showMessage(result.error || t("contactError"));
    return;
  }
  const data = result.data;
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
    button.addEventListener("click", () => fillRecord(record.id, targetUrl.hostname));
    matches.append(button);
  }
}

async function fillRecord(recordId, hostname) {
  try {
    showMessage(t("filling"));
    const result = await MvVault.request(vaultBase, "POST", `/extension/records/${recordId}/`, { hostname }, { interactive: true, excludeTabId: targetTab.id });
    if (!result.data) throw new Error(result.error || t("retrievalError"));
    await chrome.scripting.executeScript({ target: { tabId: targetTab.id }, files: ["fill.js"] });
    const filled = await chrome.scripting.executeScript({
      target: { tabId: targetTab.id },
      func: (username, password) => globalThis.mvFill(username, password),
      args: [result.data.username, result.data.password],
    });
    const outcome = filled[0]?.result;
    if (outcome?.error) throw new Error(t(outcome.error));
    showMessage(outcome?.username ? t("filledBoth") : t("filledPassword"));
  } catch (error) {
    showMessage(error.message || t("fillError"));
  }
}

async function renderSettings() {
  const saved = await chrome.storage.local.get({ autoEnabled: false, autoShow: true, autoSave: true, neverShow: [], neverSave: [] });
  const enabled = saved.autoEnabled && await chrome.permissions.contains({ origins: ALL_SITES });
  autoEnabled.checked = enabled;
  autoOptions.hidden = !enabled;
  autoShow.checked = saved.autoShow;
  autoSave.checked = saved.autoSave;
  hiddenSites.replaceChildren();
  for (const [list, label] of [["neverShow", "hiddenSuggestions"], ["neverSave", "hiddenSaves"]]) {
    for (const host of saved[list]) {
      const row = document.createElement("div");
      row.className = "hidden-site";
      const name = document.createElement("span");
      name.textContent = `${host} · ${t(label)}`;
      const remove = document.createElement("button");
      remove.textContent = t("remove");
      remove.addEventListener("click", async () => {
        await chrome.storage.local.set({ [list]: saved[list].filter((item) => item !== host) });
        renderSettings();
      });
      row.append(name, remove);
      hiddenSites.append(row);
    }
  }
}

autoEnabled.addEventListener("change", async () => {
  if (autoEnabled.checked) {
    if (!await chrome.permissions.request({ origins: ALL_SITES })) {
      autoEnabled.checked = false;
      showMessage(t("autoDenied"));
      return;
    }
    await chrome.storage.local.set({ autoEnabled: true });
    showMessage(t("autoReload"));
  } else {
    await chrome.storage.local.set({ autoEnabled: false });
    await chrome.permissions.remove({ origins: ALL_SITES }).catch(() => {});
  }
  renderSettings();
});
autoShow.addEventListener("change", () => chrome.storage.local.set({ autoShow: autoShow.checked }));
autoSave.addEventListener("change", () => chrome.storage.local.set({ autoSave: autoSave.checked }));

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
    renderSettings();
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
  renderSettings();
  try { await loadMatches(); }
  catch (error) { showMessage(error.message || t("contactError")); }
})();
