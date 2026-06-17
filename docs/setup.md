# OAuth setup

ytstudio talks to YouTube through the official APIs, which means you bring
your own OAuth client. The flow is one-shot.

## 1. Create a Google Cloud project

1. Open the
   [Google Cloud Console](https://console.cloud.google.com/) and create a
   project.
2. Under **APIs & Services** :material-arrow-right: **Library**, enable both
   **YouTube Data API v3** and **YouTube Analytics API**.

## 2. Configure the OAuth consent screen

1. Go to **APIs & Services** :material-arrow-right: **OAuth consent screen**.
2. Pick **External** and create the application.
3. Fill in app name and your contact email.
4. Skip scopes for now.
5. Add yourself as a test user.
6. Leave the app in **Testing** mode; you do not need full verification for
   personal use.

## 3. Create OAuth client credentials

1. Go to **APIs & Services** :material-arrow-right: **Credentials**.
2. **Create credentials** :material-arrow-right: **OAuth client ID**.
3. Pick **Desktop app** as the application type.
4. Download the JSON file.

## 4. Initialize ytstudio

=== "From a file"

    ```bash
    ytstudio init --client-secrets path/to/client_secret_<id>.json
    ytstudio login
    ```

=== "Interactive"

    ```bash
    ytstudio init
    # prompts for client_id and client_secret
    ytstudio login
    ```

Credentials and the shared client secrets land under
`~/.config/ytstudio-cli/`. Files are stored owner-only (`0600`) and
directories owner-only (`0700`).

## Headless login

If you are setting things up on a server without a browser:

```bash
ytstudio login --headless
```

The command prints a Google OAuth URL. Open it in any browser, approve
access, and copy the failed `127.0.0.1` redirect URL back into the terminal.
ytstudio finishes the exchange locally.

## Status

```bash
ytstudio status      # show the authenticated channel for the active profile
```

To remove credentials for a channel, use `ytstudio profile remove <name>` (see
[Multi-channel profiles](profiles.md)).

If you run more than one channel, head to
[Multi-channel profiles](profiles.md) next.
