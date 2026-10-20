# Chrome extension

The mVault Chrome extension works with your signed-in mVault in three ways:

- **Click to fill**: open the extension on a site and choose a matching password record. It never submits the login form.
- **Automatic suggestions** (opt-in): when a page with a login form opens and your vault has password records for the site's exact hostname, a small card lists them and the toolbar icon shows the count. Nothing is filled until you click a record.
- **Save prompts** (opt-in): after you sign in or sign up on a site, the extension offers to save the login to mVault, or to update the password if it changed.

Matching compares the site's exact hostname with the record's **Website** field.

## Install from a GitHub release

Chrome is the only supported browser for now (Chrome 110 or newer).

1. Download `mvault-chrome-extension-<version>.zip` from the [latest mVault release](https://github.com/orkhan/mvault/releases/latest) and extract it.
2. Open `chrome://extensions` and enable **Developer mode**.
3. Choose **Load unpacked** and select the extracted folder containing `manifest.json`.
4. Open the extension on a website, enter your mVault address (for example, `https://vault.example.com`), and choose **Connect**. Chrome asks to let the extension access that mVault host.
5. Sign in to mVault in a browser tab (the extension opens one for you if needed). Return to the website and click the extension again.
6. Review the matching record names and usernames, then choose one to fill the username and password fields. Every accessible password record for the exact hostname is listed; scroll the list if needed.

To update, extract the new ZIP over the old folder (or load the new folder) and press **Reload** on `chrome://extensions`.

## Automatic suggestions and save prompts

Tick **Automatic suggestions and save prompts** in the extension popup. Chrome asks to let the extension run on all websites (needed to see login forms); declining leaves click-to-fill working as before. Reload open pages afterwards. Two further switches turn suggestions and save prompts on or off separately, and the popup lists the sites you hid, so you can bring them back.

**Suggestions.** Only pages that contain a login field cause a lookup, and only the page's hostname is sent, to your own mVault server. The card offers *Don't suggest on this site*. A `!` on the toolbar icon means you are signed out of mVault.

**Saving.** When you submit a login form (including single-page apps and two-step logins where the username comes first), the extension remembers the username and password in browser memory for about a minute. After the next page loads, or once the form disappears on a single-page app, it checks with mVault:

- the login is already saved: nothing is shown;
- the username exists with a different password: **Update the password in mVault?** (only records you own can be updated; the old password stays in the record history);
- otherwise: **Save this login to mVault?** with a name (default: the hostname), project and folder. Only your own password projects are offered.

If the password field is still on the page the login probably failed, so nothing is offered. Choose *Not now* to dismiss or *Never for this site* to stop prompts for that site. Logins you filled with mVault are never offered again.

If no mVault tab is open, saving briefly opens one in the background and closes it again. If you are signed out it stays open so you can sign in; save again afterwards.

## Using it with other password managers

The extension is built to sit next to Bitwarden, Vaultwarden, 1Password, Chrome's and Apple's password managers:

- It only *reads* the page. It does not change `autocomplete` attributes, replace form handlers, block events or add icons inside fields, and its listeners are passive.
- It never fills on its own, so it cannot race another manager's autofill. When you click a record it sets the values the way a browser edit would (value setter plus `input`/`change` events), so other managers and web frameworks see a normal edit.
- Its card is a separate element in a closed shadow DOM in the bottom-right corner of the top frame only. Chrome's and Apple's own save bubbles are browser UI and are untouched.
- Two managers can both offer to save the same login. To avoid double prompts, turn off *Offer to save logins* (or choose *Never for this site*) in whichever manager you prefer not to use for saving; suggestions can be turned off the same way.

## Install from the repository for development

1. Open `chrome://extensions` and enable **Developer mode**.
2. Choose **Load unpacked** and select the repository's `extension/` directory.

## Sessions and servers

The extension uses your browser's mVault session, so there is no separate extension password or long-lived access token. If the session expires, sign in to mVault again. To change servers, choose **Change mVault address** in the extension.

If the extension reports that the mVault API is missing, update the mVault server to a build that includes the `/extension/` endpoints, then restart the app. Saving requires mVault 0.8.0 or newer. For a member-account message, sign in with a member account; administrator accounts do not have vault access.

## Matching and access

All active password records available to the signed-in member with an exact hostname match are listed, including shared records. Each entry shows its record name and username; passwords are returned only after you select an entry. For example, `login.example.com` does not match `example.com` or `other.example.com`. A record website can be a full URL or a hostname (ports are ignored). A selected record is checked again on the server against the active hostname and the signed-in member's ownership or share access. Credential responses are not cached and successful fills, saves and updates are recorded in the audit log.

Chrome grants the extension access to the mVault host, and (only if you enable automatic features) to all websites. The extension runs in the top frame only, skips the mVault site itself, and fills fields only after you select a record. Review the extension source before loading it, as with any password manager extension.
