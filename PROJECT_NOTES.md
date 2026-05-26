# Project notes

Implemented starter features:

- Ubuntu 24.04 bootstrap and remote `curl | sudo bash` installer.
- Telemetry/crash reporting disablement in bootstrap.
- Django + SQLite model layer for users, peers, usage, commits, integrations, privacy settings.
- WireGuard IP identity and VPN-only request denial.
- Nginx bound to WireGuard IP with allow/deny defence in depth.
- Generated WireGuard client config with QR setup page.
- One-time client config download that clears private-key material from the database after download.
- Per-user usage limits with admin exemption for web UI lockout.
- Optional DigitalOcean API token settings page.
- Privacy switches for persistent audit logs and persistent usage accounting.
- Systemd service/timer templates.

Still recommended before production:

- Add formal tests for rollback, config generation, and limit enforcement.
- Add real DigitalOcean Monitoring API sync.
- Review whether the usage collector should run as root or use a narrow privileged helper for `wg show`.
- Add real migrations to the repository instead of relying on bootstrap-time `makemigrations`.
- Perform a security review of the install script and sudo helper.
