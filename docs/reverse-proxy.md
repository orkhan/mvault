# Reverse proxy

mVault speaks plain HTTP on port 8000 and **does not include a reverse proxy**. Put your own in front for HTTPS. This page lists what any proxy must do, then gives snippets.

> **Verification status.** The Nginx Proxy Manager steps match the configuration generated in the maintainer's homelab. The Caddy, nginx, Traefik, Cloudflare Tunnel and Tailscale snippets follow those tools' documentation but were **not run** against mVault.

## What every proxy must do

1. **Terminate HTTPS** and forward to `http://<mvault-host>:8000`.
2. **Set `MVAULT_BASE_URL`** to the public `https://…` address. This configures allowed hosts, the CSRF origin, secure cookies and HSTS. Without it you will see *400 Bad Request* or *403 CSRF failed*.
3. **Forward `Host`** unchanged, and set **`X-Forwarded-Proto: https`**. mVault trusts that header to know the request was HTTPS (it is how secure cookies and CSRF checks work).
4. **Set `X-Forwarded-For`** so the proxy appends the real client address. Sign-in throttling uses the *rightmost* entry (the one your proxy added) and ignores values a client could forge. If mVault is reachable **without** a proxy, set `MVAULT_TRUST_PROXY=false`.
5. **Allow large bodies:** file records go up to 50 MB, so allow at least **55 MB** (`client_max_body_size 55m;` in nginx terms). The default of 1 MB makes uploads fail with *413*.
6. **Allow slow requests:** keep read/response timeouts **≥ 120 s** (gunicorn's worker timeout is 120 s by default). Upload and download of large files can take a while on slow links.
7. No WebSocket support is needed.

Do not expose port 8000 publicly if you can avoid it; bind it to the proxy's network or `127.0.0.1`.

## Nginx Proxy Manager (verified)

1. **Hosts → Proxy Hosts → Add Proxy Host** (or ⋮ → Edit on an existing one).
2. **Details** tab: Domain `vault.example.com`, Scheme `http`, Forward Hostname/IP = the mVault host, Forward Port `8000`, *Block Common Exploits* on, *Websockets Support* off.
3. **SSL** tab: choose your certificate, enable *Force SSL* and *HTTP/2 Support*.
4. **Advanced** tab (the last one): paste into the **Custom Nginx Configuration** box and save:

   ```nginx
   client_max_body_size 55m;
   proxy_read_timeout 180s;
   ```

NPM forwards `Host`, `X-Forwarded-Proto` and `X-Forwarded-For` by default.

## Caddy *(untested)*

```caddyfile
vault.example.com {
    request_body {
        max_size 55MB
    }
    reverse_proxy 127.0.0.1:8000 {
        transport http {
            response_header_timeout 180s
        }
    }
}
```

Caddy obtains certificates automatically and sets the forwarded headers itself.

## nginx *(untested)*

```nginx
server {
    listen 443 ssl http2;
    server_name vault.example.com;
    # ssl_certificate / ssl_certificate_key ...

    client_max_body_size 55m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
    }
}
```

## Traefik *(untested)*

Docker labels on the mVault container (v2/v3 syntax):

```yaml
labels:
  - traefik.enable=true
  - traefik.http.routers.mvault.rule=Host(`vault.example.com`)
  - traefik.http.routers.mvault.entrypoints=websecure
  - traefik.http.routers.mvault.tls.certresolver=letsencrypt
  - traefik.http.services.mvault.loadbalancer.server.port=8000
```

Traefik sets `X-Forwarded-Proto` and `X-Forwarded-For`. It has no request-size limit by default; if you add a `buffering` middleware, allow ≥ 55 MB. If large uploads time out, raise the entrypoint's `transport.respondingTimeouts.readTimeout` (the default is 60 s in Traefik v3).

## Cloudflare Tunnel *(untested)*

Point the tunnel's public hostname at `http://localhost:8000` and set `MVAULT_BASE_URL` to the public `https://` name. Cloudflare's free plan allows request bodies up to 100 MB, which covers the 50 MB file limit. Because the connection to mVault comes from `cloudflared`, the client address seen for throttling may be Cloudflare's rather than the visitor's; per-account throttling still applies. Check what your setup sends before relying on per-address limits.

## Tailscale *(untested)*

`tailscale serve` can publish mVault on your tailnet with a Tailscale-issued certificate, for example `tailscale serve --bg --https=443 http://127.0.0.1:8000`. Set `MVAULT_BASE_URL` to the resulting `https://<machine>.<tailnet>.ts.net` address. Nobody outside your tailnet can reach it, which is a good default for a family vault.

## Checking it works

- Sign in, then upload a small file record (a *File* record in any project). A *413* means the body limit is too low; a *504/502* after a delay means the timeout is too low.
- `manage.py check_config` warns when `MVAULT_BASE_URL` is unset or not HTTPS.
- Browser developer tools → the response headers of the login page should include `Strict-Transport-Security` (when the base URL is HTTPS) and `Content-Security-Policy`.
