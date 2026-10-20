"use strict";
// Fills a login form. Injected into the page's isolated world by the popup and the content script.
globalThis.mvFill = (username, password) => {
  const visible = (element) => {
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0 && !element.disabled && !element.readOnly;
  };
  const passwords = [...document.querySelectorAll('input[type="password"]')].filter(visible);
  const scope = passwords[0]?.closest("form") || document;
  const users = [...scope.querySelectorAll('input:not([type]), input[type="text"], input[type="email"], input[type="tel"], input[autocomplete="username"]')].filter(visible);
  const usernameField = users.find((field) => field.autocomplete === "username" || /user|email|login|account/i.test(`${field.name} ${field.id} ${field.placeholder}`)) || (users.length === 1 ? users[0] : null);
  if (!passwords.length && !usernameField) return { error: "noPasswordField" };
  // The native setter plus input/change events lets frameworks (and other extensions) see an ordinary edit.
  const setValue = (field, value) => {
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(field), "value")?.set;
    if (setter) setter.call(field, value); else field.value = value;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
  };
  if (usernameField && username) setValue(usernameField, username);
  if (passwords.length) setValue(passwords[0], password);
  return { username: Boolean(usernameField && username), password: passwords.length > 0 };
};
