# Chrome extension

The mVault Chrome extension fills a site's username and password after you choose a matching password record. It compares the site's exact hostname with the record's **Website** field. It does not submit the login form.

## Install for development

1. Open `chrome://extensions` and enable **Developer mode**.
2. Choose **Load unpacked** and select the repository's `extension/` directory.
3. Open the extension on a website, enter your mVault address (for example, `https://vault.example.com`), and choose **Connect**. Chrome asks to let the extension access that mVault host.
4. Sign in to mVault in the tab it opens. Return to the website and click the extension again.
5. Review the matching record names and usernames, then choose one to fill the username and password fields. Every accessible password record for the exact hostname is listed; scroll the list if needed.

Keep a signed-in mVault tab open while using the extension. It uses that browser session, so there is no separate extension password or long-lived access token. If the session expires, sign in to mVault again. To change servers, choose **Change mVault address** in the extension.

If the extension reports that the mVault API is missing, update the mVault server to a build that includes the `/extension/matches/` and `/extension/records/<id>/` endpoints, then restart the app. For a member-account message, sign in with a member account; administrator accounts do not have vault access.

## Matching and access

All active password records available to the signed-in member with an exact hostname match are listed, including shared records. Each entry shows its record name and username; passwords are returned only after you select an entry. For example, `login.example.com` does not match `example.com` or `other.example.com`. The extension supports a record website written as a full URL or a hostname. A selected record is checked again on the server against the active hostname and the signed-in member's ownership or share access. Credential responses are not cached and successful fills are recorded in the audit log.

Chrome grants the extension access only to the configured mVault host. The extension uses the active-tab permission when you open it on a site, and fills fields only after you select a record. Review the extension source before loading it, as with any password manager extension.
