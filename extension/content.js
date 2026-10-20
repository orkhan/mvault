"use strict";
// Top-frame content script: suggests matching logins and offers to save a login after the member submits it.
// It only reads the page and never changes, blocks or replaces anything the site or another password manager does:
// no autocomplete edits, no preventDefault/stopPropagation, no in-field icons, and nothing is filled without a click.
(() => {
  if (window.top !== window || globalThis.__mvaultContent || !document.documentElement || !/html/.test(document.contentType)) return;
  globalThis.__mvaultContent = true;

  const t = (key, substitutions) => chrome.i18n.getMessage(key, substitutions);
  const send = (message) => new Promise((resolve) => {
    try { chrome.runtime.sendMessage(message, (response) => { void chrome.runtime.lastError; resolve(response || {}); }); }
    catch { resolve({}); }
  });
  const visible = (element) => {
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0 && !element.disabled;
  };
  const passwordFields = () => [...document.querySelectorAll('input[type="password"]')]
    .filter((field) => visible(field) && !/^(one-time-code|cc-csc)$/.test(field.autocomplete));
  const textLike = (field) => ["text", "email", "tel"].includes(field.type);
  const hinted = (field) => /username|email/.test(field.autocomplete) || /user|email|login|account|identifier/i.test(`${field.name} ${field.id}`);

  // ---- Capturing a submitted login -------------------------------------------------------------------------
  function usernameFor(password) {
    const inputs = [...(password.form || document).querySelectorAll("input")].filter((field) => field !== password && textLike(field));
    const shown = inputs.filter(visible);
    const before = shown.filter((field) => field.compareDocumentPosition(password) & Node.DOCUMENT_POSITION_FOLLOWING);
    return shown.find((field) => /username/.test(field.autocomplete)) || shown.find(hinted) || before[before.length - 1]
      || inputs.find((field) => /username/.test(field.autocomplete)) || null;
  }

  // Login (1 password field), sign-up (2 equal fields) or change password (current, new, repeat).
  function snapshot(scope) {
    const all = passwordFields().filter((field) => scope.contains(field));
    if (!all.length) return null;
    const group = all.filter((field) => field.form === all[0].form);
    const values = group.map((field) => field.value);
    let index = -1;
    if (group.length === 1) index = 0;
    else if (group.length === 2 && values[0] === values[1]) index = 0;
    else if (group.length === 3 && values[1] === values[2]) index = 1;
    if (index < 0 || !values[index] || values[index].length > 1024) return null;
    const user = usernameFor(group[index]);
    const username = (user?.value || "").trim();
    if (group.length === 3 && !username) return null;
    return { username: username.slice(0, 255), password: values[index], fields: group };
  }

  // First step of a two-step login: a lone username/email field with no password field on the page.
  function usernameStep(scope) {
    if (passwordFields().length) return null;
    const inputs = [...scope.querySelectorAll("input")].filter((field) => textLike(field) && visible(field));
    const field = inputs.length === 1 ? inputs[0] : null;
    return field && (hinted(field) || field.type === "email") && field.value.trim() ? field.value.trim().slice(0, 255) : null;
  }

  let last = { key: "", at: 0 };
  let watcher;
  function onAction(scope) {
    const snap = snapshot(scope);
    if (!snap) {
      const username = usernameStep(scope);
      if (username) send({ type: "usernameStep", username });
      return;
    }
    const key = `${snap.username}\n${snap.password}`;
    if (key === last.key && Date.now() - last.at < 2000) return;
    last = { key, at: Date.now() };
    send({ type: "captured", username: snap.username, password: snap.password });
    // Single-page apps never navigate: once the password field disappears the login most likely worked.
    clearInterval(watcher);
    const started = Date.now();
    watcher = setInterval(() => {
      if (snap.fields.every((field) => !field.isConnected || !visible(field))) { clearInterval(watcher); setTimeout(checkPending, 800); }
      else if (Date.now() - started > 20000) clearInterval(watcher);
    }, 500);
  }

  // The form around a control, or for form-less single-page apps the nearest ancestor that holds a password field.
  function scopeFor(target) {
    const form = target.form || target.closest("form");
    if (form) return form;
    let node = target.parentElement;
    for (let depth = 0; node && depth < 6; depth += 1, node = node.parentElement) if (node.querySelector('input[type="password"]')) return node;
    return null;
  }

  const toggleLike = /show|hide|reveal|toggle|visib|mostrar|ocultar|göster|gizle|göstər|gizlət|показ|скры|паказ|схав|сховат/i;
  const listen = (type, handler) => window.addEventListener(type, handler, { capture: true, passive: true });
  listen("submit", (event) => { if (event.target instanceof HTMLFormElement) onAction(event.target); });
  listen("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest('button, input[type="submit"], input[type="button"], input[type="image"], [role="button"]') : null;
    if (!button || toggleLike.test(`${button.getAttribute("aria-label") || ""} ${button.title || ""} ${button.name || ""}`)) return;
    const scope = scopeFor(button);
    if (scope) onAction(scope);
  });
  listen("keydown", (event) => {
    if (event.key !== "Enter" || event.isComposing || !(event.target instanceof HTMLInputElement)) return;
    const scope = scopeFor(event.target);
    if (scope) onAction(scope);
  });

  // ---- Interface (closed shadow DOM, constructed stylesheet so page CSP cannot interfere) ------------------
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(`
    :host { all: initial; }
    * { box-sizing: border-box; font: 13px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; letter-spacing: 0; }
    .card { width: 320px; max-width: calc(100vw - 32px); padding: 14px; border: 1px solid #45463f; border-radius: 12px; background: #171816; color: #f2f0e9; box-shadow: 0 10px 30px rgba(0,0,0,.4); }
    .head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
    .brand { color: #d6b978; font-weight: 700; }
    .site { flex: 1; overflow: hidden; color: #aaa99f; text-overflow: ellipsis; white-space: nowrap; }
    .title { margin: 0 0 10px; font-weight: 600; }
    .x, .row, .primary, .secondary, .link { cursor: pointer; border: 0; }
    .x { padding: 2px 6px; background: transparent; color: #aaa99f; font-size: 16px; }
    .list { display: grid; max-height: 220px; gap: 6px; overflow-y: auto; }
    .row { display: grid; width: 100%; gap: 1px; padding: 8px 10px; border-radius: 8px; background: #d6b978; color: #171816; text-align: left; }
    .row:hover, .primary:hover { background: #e4ca91; }
    .row small { overflow: hidden; color: #3d382c; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
    .name { overflow: hidden; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
    .fact { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 4px; color: #c7c5bb; }
    .fact b { overflow: hidden; color: #f2f0e9; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
    label { display: block; margin: 8px 0 3px; color: #c7c5bb; font-size: 12px; }
    input, select { width: 100%; padding: 7px 8px; border: 1px solid #45463f; border-radius: 8px; background: #22231f; color: #f2f0e9; }
    .actions { display: flex; gap: 8px; margin-top: 12px; }
    .primary { flex: 1; padding: 8px; border-radius: 8px; background: #d6b978; color: #171816; font-weight: 650; }
    .secondary { padding: 8px 12px; border-radius: 8px; background: #2c2d28; color: #f2f0e9; }
    .link { display: block; margin-top: 8px; padding: 2px 0; background: transparent; color: #aaa99f; font-size: 12px; text-decoration: underline; }
    .msg { margin-top: 8px; color: #c7c5bb; }
    button:disabled { opacity: .6; cursor: default; }
    button:focus-visible, input:focus-visible, select:focus-visible { outline: 2px solid #e4ca91; outline-offset: 2px; }
  `);

  let hostElement;
  let shadow;
  let onKey;
  function close() {
    if (onKey) { window.removeEventListener("keydown", onKey, true); onKey = null; }
    hostElement?.remove();
    hostElement = null;
  }
  function el(tag, props = {}, ...children) {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...children);
    return node;
  }
  function show(card, onEscape) {
    close();
    hostElement = document.createElement("div");
    hostElement.setAttribute("data-mvault-autofill", "");
    hostElement.style.cssText = "all:initial;position:fixed;right:16px;bottom:16px;z-index:2147483647;";
    shadow = hostElement.attachShadow({ mode: "closed" });
    shadow.adoptedStyleSheets = [sheet];
    shadow.append(card);
    document.documentElement.append(hostElement);
    onKey = (event) => { if (event.key === "Escape") onEscape(); };
    window.addEventListener("keydown", onKey, true);
  }
  const header = (host, onClose) => el("div", { className: "head" }, el("span", { className: "brand", textContent: "mVault" }),
    el("span", { className: "site", textContent: host }), el("button", { className: "x", textContent: "×", title: t("close"), ariaLabel: t("close"), onclick: onClose }));

  function showSuggestions(matches) {
    const message = el("div", { className: "msg", role: "status" });
    const rows = matches.map((match) => {
      const row = el("button", { className: "row" }, el("span", { className: "name", textContent: match.name }),
        el("small", { textContent: `${t("username")}: ${match.username || t("noUsername")}` }));
      row.addEventListener("click", async () => {
        row.disabled = true;
        const credential = await send({ type: "fill", recordId: match.id });
        row.disabled = false;
        if (credential.error || credential.password === undefined) { message.textContent = credential.error || t("retrievalError"); return; }
        const result = globalThis.mvFill(credential.username, credential.password);
        if (result.error) { message.textContent = t(result.error); return; }
        message.textContent = t("filled");
        setTimeout(close, 1500);
      });
      return row;
    });
    const never = el("button", { className: "link", textContent: t("suggestNever"), onclick: () => { send({ type: "neverShow" }); close(); } });
    show(el("div", { className: "card", role: "dialog", ariaLabel: t("suggestTitle", [location.hostname]) }, header(location.hostname, close),
      el("div", { className: "list" }, ...rows), message, never), close);
  }

  let prompting = false;
  function showSave(prompt) {
    prompting = true;
    const done = () => { prompting = false; close(); };
    const dismiss = (never) => { send({ type: "dismiss", never }); done(); };
    const updating = prompt.state === "update";
    const message = el("div", { className: "msg", role: "status" });
    const nodes = [
      header(prompt.host, () => dismiss(false)),
      el("p", { className: "title", textContent: t(updating ? "updateTitle" : "saveTitle") }),
      el("div", { className: "fact" }, t("username"), el("b", { textContent: prompt.username || t("noUsername") })),
      el("div", { className: "fact" }, t("labelPassword"), el("b", { textContent: "••••••••" })),
    ];
    let name;
    let project;
    let folder;
    if (updating) {
      nodes.push(el("div", { className: "fact" }, t("labelName"), el("b", { textContent: prompt.record.name })));
    } else if (!prompt.projects.length) {
      nodes.push(el("div", { className: "msg", textContent: t("noProjects") }));
    } else {
      name = el("input", { id: "mv-name", placeholder: prompt.host, maxLength: 160, autocomplete: "off" });
      project = el("select", { id: "mv-project" }, ...prompt.projects.map((item) => el("option", { value: item.id, textContent: item.name })));
      folder = el("select", { id: "mv-folder" });
      const fillFolders = () => {
        const current = prompt.projects.find((item) => String(item.id) === project.value);
        folder.replaceChildren(el("option", { value: "", textContent: t("noFolder") }), ...current.folders.map((item) => el("option", { value: item.id, textContent: item.name })));
      };
      const remembered = prompt.lastTarget && prompt.projects.find((item) => item.id === prompt.lastTarget.projectId);
      if (remembered) project.value = String(remembered.id);
      fillFolders();
      if (remembered && prompt.lastTarget.folderId) folder.value = String(prompt.lastTarget.folderId);
      project.addEventListener("change", fillFolders);
      const field = (id, text, control) => [el("label", { htmlFor: id, textContent: text }), control];
      nodes.push(...field("mv-name", t("labelName"), name), ...field("mv-project", t("labelProject"), project), ...field("mv-folder", t("labelFolder"), folder));
    }
    const save = el("button", { className: "primary", textContent: t(updating ? "updateButton" : "saveButton") });
    save.addEventListener("click", async () => {
      save.disabled = true;
      const result = await send({ type: "save", name: name?.value.trim() || "", projectId: project?.value, folderId: folder?.value });
      if (result.error || !result.action) { save.disabled = false; message.textContent = result.error || t("saveFailed"); return; }
      message.textContent = t(result.action === "updated" ? "updated" : "saved");
      setTimeout(done, 1800);
    });
    if (updating || prompt.projects.length) {
      nodes.push(el("div", { className: "actions" }, save, el("button", { className: "secondary", textContent: t("notNow"), onclick: () => dismiss(false) })));
    } else {
      nodes.push(el("div", { className: "actions" }, el("button", { className: "secondary", textContent: t("notNow"), onclick: () => dismiss(false) })));
    }
    nodes.push(message, el("button", { className: "link", textContent: t("neverSave"), onclick: () => dismiss(true) }));
    show(el("div", { className: "card", role: "dialog", ariaLabel: t(updating ? "updateTitle" : "saveTitle") }, ...nodes), () => dismiss(false));
  }

  // ---- Triggers ----------------------------------------------------------------------------------------------
  async function checkPending() {
    // A password field still on screen means the login failed or has another step; wait for it to go away.
    if (prompting || passwordFields().length) return;
    const { prompt } = await send({ type: "getPending" });
    if (prompt) showSave(prompt);
  }

  let asked = "";
  let hadPassword = false;
  let timer;
  function scan() {
    const passwords = passwordFields();
    if (hadPassword && !passwords.length) setTimeout(checkPending, 800);
    hadPassword = passwords.length > 0;
    const loginPage = hadPassword || [...document.querySelectorAll('input[autocomplete~="username"]')].some(visible);
    const key = location.origin + location.pathname;
    if (!loginPage || asked === key) return;
    asked = key;
    send({ type: "pageReady" }).then(({ matches }) => { if (matches?.length && !prompting) showSuggestions(matches); });
  }
  new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(scan, 400); })
    .observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "class", "hidden"] });
  setTimeout(() => { scan(); checkPending(); }, 1000);
})();
