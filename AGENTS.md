# AGENTS.md

## Project overview

This repository builds an opinionated DigitalOcean WireGuard VPN appliance.

The intended deployment is a single Ubuntu 24.04 LTS DigitalOcean Droplet that is bootstrapped over SSH once, then managed through a Django web app that is reachable only through WireGuard.

The project should remain simple, auditable, and privacy-conscious. Prefer boring, native Linux components over complex orchestration.

## Core product goals

- Create a DigitalOcean Droplet.
- SSH in once and run an installer script.
- Installer provisions WireGuard, Django, SQLite, Nginx, Certbot, UFW, systemd services/timers, and the first admin peer.
- First admin receives a WireGuard client config/private key once.
- After setup, the admin connects via WireGuard and manages users/peers through the web app.
- Public admin web access must never be exposed.

## Final architecture decisions

- OS: Ubuntu 24.04 LTS.
- Telemetry: installer must disable or remove Ubuntu telemetry/crash reporting where present.
- Web framework: Django.
- Database: SQLite.
- Reverse proxy: Nginx.
- App server: Gunicorn on `127.0.0.1:8000`.
- Web UI listener: Nginx on WireGuard interface only, `10.44.0.1:443`.
- WireGuard interface: `wg0`.
- WireGuard subnet: `10.44.0.0/24`.
- Server VPN IP: `10.44.0.1`.
- First admin peer IP: `10.44.0.2`.
- VPN routing: IPv4 full tunnel.
- IPv6: do not route IPv6 initially; avoid `::/0` in generated client configs.
- Client DNS: Quad9, `9.9.9.9, 149.112.112.112`.
- Firewall: UFW plus explicit NAT/masquerade rules.
- Public SSH after setup: closed; DigitalOcean console is the emergency recovery path.
- SSH over WireGuard may be allowed for maintenance.
- HTTPS certificates: Certbot HTTP-01 only; DNS-01 is not available.
- Port 80: closed by default; opened temporarily only for Certbot validation/renewal.
- Port 443: never public; only on the WireGuard interface.
- DigitalOcean API token: optional at setup and configurable later in the web app.
- App install/update method: Git repository.
- Client keys: server generates client private key/config, displays them once, then stores only the public key.
- Admin authentication: WireGuard source IP identity only.

## Security invariants

These are hard requirements. Do not weaken them without explicit user approval.

1. The management web app must only be reachable through WireGuard.
2. Nginx must bind to the WireGuard IP, not `0.0.0.0`.
3. Public TCP 443 must remain closed.
4. Public TCP 80 is temporary only for ACME HTTP-01.
5. Public TCP 22 is closed after setup.
6. Django must reject requests that do not come from the WireGuard subnet.
7. Django must reject requests from unregistered or disabled peers.
8. Django identity must be derived from the real WireGuard source IP, not from user-supplied headers.
9. `X-Forwarded-For` must not be trusted for identity.
10. If using `X-Real-IP`, trust it only when the immediate peer is local Nginx on loopback.
11. Every WireGuard peer must have a unique `/32` IPv4 address.
12. A client must never be able to choose or impersonate another peer's tunnel IP.
13. Do not allow deleting/disabling the last active admin.
14. Do not allow an admin to remove their own last active admin peer unless another active admin exists.
15. The Django app must not run as root.
16. Privileged WireGuard changes must go through a small root-owned helper or tightly scoped sudo command.
17. Do not let user input become shell-interpreted command text.
18. Private client keys should be shown/downloaded once and not retained.
19. Audit/config/usage logging must respect privacy switches.
20. If logging is disabled, do not write persistent audit/config/presence records beyond the minimum required for operation.

## Installer requirements

The repository should support this install style:

```bash
curl -fsSL https://raw.githubusercontent.com/synapticloop/digitalocean-wireguard-vpn/main/install.sh | sudo bash
```

And non-interactive environment variable usage, for example:

```bash
curl -fsSL https://raw.githubusercontent.com/synapticloop/digitalocean-wireguard-vpn/main/install.sh | sudo WG_ADMIN_DOMAIN=wg.example.com bash
```

The top-level `install.sh` must bootstrap its own prerequisites before cloning, including at least:

```bash
apt-get update
apt-get install -y ca-certificates curl git gnupg lsb-release
```

The deeper bootstrap script should install runtime dependencies such as:

- wireguard
- python3
- python3-venv
- python3-pip
- nginx
- certbot
- ufw
- sqlite3
- dnsutils
- qrencode or Python QR dependencies as needed

Installer must support interactive prompts and environment variables.

Required or common environment variables:

- `WG_ADMIN_DOMAIN`
- `APP_REPO_URL`
- `APP_REPO_BRANCH`
- `APP_DIR`
- `DIGITALOCEAN_API_TOKEN` optional
- `DIGITALOCEAN_DROPLET_ID` optional

The installer must disable telemetry/crash reporting where present, using conservative commands with `|| true` where appropriate.

## WireGuard config model

SQLite is the source of truth. `/etc/wireguard/wg0.conf` is generated output.

Config commit flow:

1. Lock commits so only one runs at a time.
2. Generate a candidate config from SQLite.
3. Back up the current live config and current file.
4. Validate the candidate.
5. Apply candidate to the live interface.
6. Verify that `wg0` remains healthy and expected peers are present.
7. Atomically persist the new config.
8. Roll back live and file config if anything fails.
9. Record a commit/audit entry only if logging is enabled.

Prefer `wg syncconf` for live peer updates. Be careful with `wg-quick` fields such as `Address`, `PostUp`, `PostDown`, and NAT rules. Do not let the web app generate arbitrary shell commands for these fields.

## Django app requirements

The app should include these conceptual areas:

- accounts/users
- peers/devices
- WireGuard config generation
- config commits/rollback
- usage accounting
- DigitalOcean integration settings
- privacy/logging settings
- audit logging, when enabled

Use Django templates/server-rendered pages. HTMX is acceptable for small interactions. Avoid introducing a large SPA unless explicitly requested.

Start with a custom user model rather than Django's default user model.

Users and peers/devices are separate concepts:

- one user can have multiple peers/devices
- each peer has one unique VPN IPv4 `/32`
- peers can be enabled/disabled
- users can be active/inactive
- users can be marked as VPN admins

## Identity and access model

Admin authentication is WireGuard IP identity only.

Request identity flow:

```text
request source IP -> peer.vpn_ipv4 -> peer.user -> user.is_vpn_admin
```

If the request does not map to an active peer, deny it.

If the user is inactive, deny it.

If the source IP is outside `10.44.0.0/24`, deny it.

Admin users can manage users and peers. Non-admin behavior may be limited to viewing their own peer/config details, unless otherwise implemented.

Admins must always be allowed to access the interface even if usage limits are exceeded.

## QR code and client config behavior

When a new peer is created, display a QR code for easy WireGuard client setup.

The one-time peer creation flow should show:

- QR code
- downloadable `.conf`
- plain config text if useful

After the one-time page is dismissed or expired, do not retain the private key. Store only:

- public key
- optional preshared key if used
- assigned VPN IP
- peer metadata

Generated IPv4 full tunnel client configs should use:

```ini
AllowedIPs = 0.0.0.0/0
DNS = 9.9.9.9, 149.112.112.112
PersistentKeepalive = 25
```

Do not include `AllowedIPs = ::/0` until IPv6 support is explicitly added.

## Usage accounting

WireGuard does not provide rich logs. It exposes runtime state and counters through commands such as:

```bash
wg show wg0 dump
wg show wg0 transfer
```

The app should collect usage by polling WireGuard and storing deltas.

Counters may reset on reboot, interface restart, peer removal/re-add, or server changes. Handle resets by treating a lower current counter as a reset and adding the current value as the new delta.

Store usage in billing/accounting periods rather than deleting history.

DigitalOcean usage window handling:

- derive from DigitalOcean where possible
- fallback to calendar month UTC
- allow manual override in settings if needed

DigitalOcean metrics are droplet/interface-level, not per-peer. Use WireGuard counters for per-user usage. Use DigitalOcean API metrics for whole-droplet comparison/billing visibility.

## User limits

Each user may have a usage limit.

- Limits apply to non-admin users.
- Admin users must remain able to access the interface even if they exceed limits.
- When a non-admin user exceeds their limit, their peers should be excluded from generated WireGuard config or removed from the live interface on enforcement.
- The usage collector may enforce limits automatically.
- Avoid locking out the last admin.

## Logging and privacy settings

The app needs privacy switches, preferably under `Settings -> Privacy`.

At minimum:

- enable/disable persistent audit/config logs
- enable/disable persistent WireGuard usage accounting

When persistent audit/config logging is off:

- do not store admin action audit entries
- do not store config commit history except minimum operational state required to know whether a commit succeeded

When usage accounting is off:

- do not store per-peer byte deltas/totals
- dashboard may show current in-memory WireGuard state if needed, but avoid persistent history

Make UI wording clear that WireGuard current runtime state may still be visible through `wg show` while the interface is running.

## DigitalOcean integration

DigitalOcean API token is optional.

It can be provided during setup or later in the web app.

Web app settings should support:

- enter/update/remove API token
- enter/update droplet ID
- test connection
- show last successful sync time
- show last sync error

Do not display the full saved token again. Show only a masked token hint.

Prefer encrypting stored secrets at rest using an app secret generated at install time. If encryption is not yet implemented, clearly mark this as a TODO and avoid logging token values.

Dashboard should degrade gracefully:

- without token: show local WireGuard per-peer/current-period usage only
- with token: show DigitalOcean public bandwidth comparison and provider window where available

## Nginx requirements

Nginx should listen only on the WireGuard server IP:

```nginx
listen 10.44.0.1:443 ssl http2;
```

It should proxy to Gunicorn on loopback.

Add a defense-in-depth allow/deny rule:

```nginx
allow 10.44.0.0/24;
deny all;
```

Set `X-Real-IP` to the real remote address. Do not use `X-Forwarded-For` for identity.

## Firewall requirements

Public internet:

- allow UDP 51820 for WireGuard
- deny TCP 443
- deny TCP 22 after setup
- TCP 80 closed except during Certbot HTTP-01

WireGuard interface:

- allow TCP 443 to admin UI
- optionally allow TCP 22 for maintenance

Enable IPv4 forwarding and NAT/masquerade for full tunnel mode.

## Certbot requirements

DNS-01 is unavailable.

Use HTTP-01 with temporary port 80 exposure.

Renewal script should:

1. open TCP 80
2. run Certbot renewal using standalone HTTP-01
3. close TCP 80 with a trap even on failure
4. reload Nginx after successful renewal if necessary

Do not accidentally expose the Django admin UI publicly during certificate issuance or renewal.

## Systemd requirements

Use systemd services/timers for:

- Gunicorn/Django app
- usage collection
- optional DigitalOcean metrics sync
- certificate renewal helper if not using Certbot's default timer behavior

The usage collector should be runnable as a Django management command, for example:

```bash
python manage.py collect_wg_usage --enforce-limits
```

## Testing and validation commands

When changing Python/Django code, run at least:

```bash
python -m compileall .
```

If Django is configured and dependencies are installed, also run:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

For shell scripts, prefer:

```bash
bash -n install.sh
bash -n scripts/*.sh
```

If ShellCheck is available, run it, but do not require it to be present.

## Code style

- Keep code simple and explicit.
- Avoid unnecessary dependencies.
- Prefer standard library and Django features over custom frameworks.
- Use clear names for security-sensitive functions.
- Keep privileged operations isolated.
- Do not hide failures in commit/apply flows.
- Use atomic writes for generated configs.
- Avoid broad exception swallowing except in cleanup paths.
- Never log secrets, private keys, API tokens, or full client configs.

## Files and directories to expect

Likely repository structure:

```text
install.sh
scripts/bootstrap_ubuntu_2404.sh
scripts/certbot_renew_http01.sh
scripts/wg-admin-commit
systemd/
nginx/
wgadmin/
manage.py
requirements.txt
README.md
AGENTS.md
```

If actual structure differs, adapt while preserving the architecture and security invariants above.

## Things not to add without explicit approval

- Docker or Docker Compose.
- Public web admin access.
- Password-based admin login as a replacement for WireGuard IP identity.
- IPv6 full tunnel.
- DNS-01 ACME.
- External database by default.
- Celery/Redis for background jobs.
- Client private key persistence after one-time display.
- Public SSH access after successful setup.

## Task behavior for coding agents

When making changes:

1. Preserve the security invariants.
2. Update README/docs when user-facing behavior changes.
3. Add or adjust migrations when models change.
4. Keep install scripts idempotent where practical.
5. Run syntax checks where possible.
6. Prefer small, reviewable changes.
7. Explain any security trade-offs in the final response.
