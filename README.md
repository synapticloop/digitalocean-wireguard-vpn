# DigitalOcean WireGuard VPN Admin

A Django + SQLite WireGuard administration panel for a single DigitalOcean Ubuntu 24.04 LTS droplet.

## Key decisions

- Ubuntu 24.04 LTS target, with bootstrap disabling Ubuntu telemetry/crash reporting where present.
- Nginx terminates HTTPS and listens only on the WireGuard address `10.44.0.1:443`.
- Public surface is only WireGuard UDP `51820`; HTTP `80` opens temporarily for Certbot HTTP-01.
- Public SSH is closed after setup; DigitalOcean console is the emergency recovery path.
- Django identifies users by WireGuard source IP. No username/password login is used by default.
- SQLite is the source of truth; `/etc/wireguard/wg0.conf` is generated.
- Client private keys are generated server-side, shown once as a QR/config, and not retained after download.
- Per-user usage limits are supported. Admin users are exempt from web-interface lockout.
- DigitalOcean API token is optional during setup and can be added later in the web UI.
- Privacy switches can disable persistent audit/config logs and persistent WireGuard usage accounting.

## Remote install

```bash
curl -fsSL https://raw.githubusercontent.com/synapticloop/digitalocean-wireguard-vpn/main/install.sh | sudo bash
```

`WG_ADMIN_DOMAIN` is optional. If it is omitted, the installer detects the server's public IPv4 address and uses that for the WireGuard endpoint and admin URL.

Optional domain example:

```bash
curl -fsSL https://raw.githubusercontent.com/synapticloop/digitalocean-wireguard-vpn/main/install.sh | sudo WG_ADMIN_DOMAIN=wg.example.com bash
```

The installer bootstraps prerequisites such as `git`, clones the repository, then runs `scripts/bootstrap_ubuntu_2404.sh`. When a real domain is supplied, it attempts a Certbot HTTP-01 certificate. If certificate issuance fails, including IP-address installs, it creates a local self-signed HTTPS certificate so Nginx can still start on the WireGuard-only listener.

## First admin

The bootstrap creates `/root/wg-admin-first-client.conf` with permissions `0600`. Import it into a WireGuard client, connect, then open:

```text
https://wg.example.com
```

If no domain was supplied during install, use `https://<server-public-ip>` instead.

The web interface refuses non-VPN access at multiple layers:

- UFW only allows `443/tcp` on `wg0`.
- Nginx binds to `10.44.0.1:443` and denies non-WireGuard addresses.
- Django rejects requests outside `10.44.0.0/24` and requests from unregistered/disabled peers.

## Important paths

```text
/opt/wg-admin                         Django app
/var/lib/wg-admin/db.sqlite3          SQLite database
/etc/wireguard/wg0.conf               generated WireGuard config
/run/wg-admin/wg0.candidate.conf      generated candidate config
/usr/local/sbin/wg-admin-commit       root-owned commit helper
/root/wg-admin-first-client.conf      bootstrap admin client config
```

## Development notes

This is a starter project, not a production-audited VPN appliance. Review the commit helper, firewall rules, and privilege boundaries before exposing it beyond personal use.


Create a WireGuard VPN

```
█████████████████████████████████████
█████████████████████████████████████
████ ▄▄▄▄▄ █▄▀▀▄▄ █▄██▄▀██ ▄▄▄▄▄ ████
████ █   █ ███▄█ ▄▄ ▀▀▀▀ █ █   █ ████
████ █▄▄▄█ ██▄▀▄▀▄██▄█▄▄▀█ █▄▄▄█ ████
████▄▄▄▄▄▄▄█ █ ▀▄▀ ▀ █▄█ █▄▄▄▄▄▄▄████
████ ▄█▄ █▄██ ▄▄▀█▄▄█▄█ █▀▄▀▀█▀▀▄████
████▀ █ ▄▀▄▄█▀  ▀▄▄▄█▀█▀   ▄█▀▄█▀████
████▀ ▀▀ █▄ ▀ █▄▄▄▀ ██▀█ █ ▄▀▀▀▀ ████
█████ ▀█▀▄▄ ▄▄█ ▄█▀▄██▄▄▄▀█ ▀█ █ ████
████▀▀▄▀▀█▄ █  ▀▀▄█▄█▀█▀ ▀██▀▄▀▀█████
████  ▀▄▀▄▄▄███▄▀▀█▄▀▄▀▄ ▀▄▀▀ ▀█▄████
████▄▄█▄▄▄▄▄ ▄ █▄▀▄▀▀▄▀▄ ▄▄▄  ▄▄█████
████ ▄▄▄▄▄ ███▀█▄█  █▀▄  █▄█ ▄██▀████
████ █   █ █ █ █ ▀▄ ▀▀▀▄  ▄ ▄▄██▀████
████ █▄▄▄█ █▀▀ ▀ ▄  ██ ▀█▀▀ ▄▀ ▄ ████
████▄▄▄▄▄▄▄█▄▄▄█▄█▄█▄█▄▄▄▄██▄▄███████
█████████████████████████████████████
█████████████████████████████████████
```