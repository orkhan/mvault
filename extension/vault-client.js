"use strict";
// Shared by the popup and the service worker: talks to mVault with the member's browser session.
(function (root) {
  const t = (key) => chrome.i18n.getMessage(key);

  // Runs inside an mVault tab (or, for GET, directly in the worker), so it must not use outer variables.
  async function pageRequest(method, url, params, errors, credentials) {
    const headers = { Accept: "application/json" };
    const init = { method, credentials, headers, cache: "no-store" };
    if (method !== "GET") {
      const csrf = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1];
      if (!csrf) return { error: errors.refreshVault };
      headers["Content-Type"] = "application/x-www-form-urlencoded";
      headers["X-CSRFToken"] = decodeURIComponent(csrf);
      init.body = new URLSearchParams(params);
    }
    const response = await fetch(url, init);
    if (!response.headers.get("content-type")?.includes("application/json")) {
      if (response.redirected) return { error: errors.signInRetry, signedOut: true };
      if (response.status === 404) return { error: errors.missingApi };
      return { error: response.status === 403 ? errors.memberAccount : errors.contactError };
    }
    const body = await response.json();
    return response.ok ? { data: body } : { error: body.error || errors.contactError, status: response.status };
  }

  const errors = () => ({
    signInRetry: t("signInRetry"), contactError: t("contactError"), memberAccount: t("memberAccount"),
    missingApi: t("missingApi"), refreshVault: t("refreshVault"),
  });

  async function relay(tabId, method, url, params) {
    try {
      const [result] = await chrome.scripting.executeScript({ target: { tabId }, world: "MAIN", func: pageRequest, args: [method, url, params, errors(), "same-origin"] });
      return result?.result || { error: t("contactError") };
    } catch {
      return { error: t("contactError") };
    }
  }

  function waitForLoad(tabId, timeout) {
    return new Promise((resolve) => {
      const finish = (loaded) => { chrome.tabs.onUpdated.removeListener(listener); clearTimeout(timer); resolve(loaded); };
      const listener = (id, info) => { if (id === tabId && info.status === "complete") finish(true); };
      const timer = setTimeout(() => finish(false), timeout);
      chrome.tabs.onUpdated.addListener(listener);
      chrome.tabs.get(tabId).then((tab) => { if (tab.status === "complete") finish(true); }, () => finish(false));
    });
  }

  async function viaTemporaryTab(base, method, url, params) {
    const tab = await chrome.tabs.create({ url: `${base}/dashboard/`, active: false });
    if (!await waitForLoad(tab.id, 15000)) {
      chrome.tabs.remove(tab.id).catch(() => {});
      return { error: t("contactError") };
    }
    const result = await relay(tab.id, method, url, params);
    if (result.signedOut) return { ...result, error: t("signIn") };
    chrome.tabs.remove(tab.id).catch(() => {});
    return result;
  }

  // Resolves to { data } on success, otherwise { error, signedOut?, status? }.
  // Order: an open mVault tab, then (GET only) a direct request carrying the session cookie, then, only when
  // `interactive`, a temporary background tab. Automatic lookups never open tabs.
  async function request(base, method, path, params = {}, options = {}) {
    const origin = new URL(base).origin;
    const query = method === "GET" && Object.keys(params).length ? `?${new URLSearchParams(params)}` : "";
    const url = `${base}${path}${query}`;
    const body = method === "GET" ? {} : params;
    const tabs = (await chrome.tabs.query({ url: `${origin}/*` })).filter((tab) => tab.id !== options.excludeTabId);
    let last = { error: t("signInRetry"), signedOut: true };
    for (const tab of tabs) {
      const result = await relay(tab.id, method, url, body);
      if (result.data || result.status) return result;
      last = result;
    }
    if (method === "GET") {
      try {
        const result = await pageRequest(method, url, body, errors(), "include");
        if (result.data || result.status) return result;
        last = result;
      } catch {
        last = { error: t("contactError") };
      }
    }
    if (tabs.length || !options.interactive) return last;
    return viaTemporaryTab(base, method, url, body);
  }

  root.MvVault = { request };
})(self);
