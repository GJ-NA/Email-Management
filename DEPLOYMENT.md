# Local Deployment

The active service is the Python application in the repository root. The
previous helper project was used as a reference for verification behavior; it
is not started and its database is not used.

## Windows

1. Keep the root `.venv` that already contains the project dependencies, or
   prepare a Python environment and install `requirements.txt` once.
2. Copy `.env.example` to `.env` and fill in the local values.
3. Run `start-email-management.bat` or `start-local.ps1`.
4. Open `http://127.0.0.1:5000`.

The launcher keeps the server in the current terminal. Press `Ctrl+C` to stop
it. It does not run `pip install` or download dependencies automatically.

## Runtime files

- `runtime/data/outlook_accounts.db`: local account and settings database
- `runtime/secret_key.txt`: encryption key used by the local launcher
- `runtime/admin_password.txt`: generated local administrator password
- `runtime/logs/`: local logs

The database and encryption key must be backed up together. All of these paths
are ignored by Git. The active database currently lives under `runtime/data`;
do not replace it with the empty legacy database that was previously inside
the source checkout.

## Docker

```powershell
Copy-Item .env.example .env.local
docker compose -f docker-compose.build.yml up -d --build
```

The Docker compose file mounts `./data` and explicitly uses
`/app/data/outlook_accounts.db`. Set `LOGIN_PASSWORD`, `SECRET_KEY`, and the
GitHub repository variables before exposing the service beyond localhost.

## Combined features

- Main UI: account import, groups, tags, mailbox reading, token refresh and export
- Import format: `email----password-or-x----client_id----refresh_token`
- Automatic detection when the final two OAuth fields are reversed
- Concurrent token refresh and batch verification
- Graph and IMAP channel status shown independently
- Verification API: `/api/accounts/verify-selected`

Only use the service with accounts you own or are authorized to administer.
