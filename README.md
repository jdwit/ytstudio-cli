# ytcli

CLI tool to manage and analyze your YouTube channel.

## Features

- **Authentication**: OAuth2 login flow with token refresh
- **Video Management**: List, update, and bulk-edit video metadata
- **Analytics**: Retention curves, traffic sources, real-time stats

## Installation

```bash
pip install ytcli
```

Or install from source:

```bash
git clone https://github.com/jdwit/ytcli.git
cd ytcli
pip install -e .
```

## Setup

Before using ytcli, you need to create Google Cloud credentials:

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Note your project ID

### 2. Enable YouTube APIs

1. Go to [APIs & Services > Library](https://console.cloud.google.com/apis/library)
2. Search for and enable:
   - **YouTube Data API v3**
   - **YouTube Analytics API**

### 3. Create OAuth Credentials

1. Go to [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials** > **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - User Type: External
   - App name: ytcli (or your preferred name)
   - Add your email as a test user
4. For Application type, select **Desktop app**
5. Download the JSON file

### 4. Configure ytcli

Option A: Provide the JSON file:

```bash
yt init --client-secrets /path/to/client_secrets.json
```

Option B: Enter credentials interactively:

```bash
yt init
# Enter your Client ID and Client Secret when prompted
```

### 5. Authenticate

```bash
yt login
```

This opens a browser for Google OAuth. After authorizing, you're ready to go.

## Usage

### Check Status

```bash
yt status
```

### List Videos

```bash
yt videos list
yt videos list --limit 20 --output json
```

### Get Video Details

```bash
yt videos get VIDEO_ID
```

### Update Video

```bash
yt videos update VIDEO_ID --title "New Title"
yt videos update VIDEO_ID --description "New description"
```

### Bulk Update

```bash
# Preview changes (dry-run is default)
yt videos bulk-update --search "old text" --replace "new text" --field title

# Apply changes
yt videos bulk-update --search "old text" --replace "new text" --field title --execute
```

### Analytics

```bash
# Audience retention
yt analytics retention VIDEO_ID

# Traffic sources
yt analytics traffic VIDEO_ID --days 28

# Channel overview
yt analytics overview --days 7

# Real-time stats
yt analytics realtime
```

### Output Formats

Most commands support multiple output formats:

```bash
yt videos list --output table  # Default, human-readable
yt videos list --output json   # JSON for scripting
yt videos list --output csv    # CSV for spreadsheets
```

## Configuration

Credentials are stored in `~/.config/ytcli/`:

- `client_secrets.json` - Your OAuth client credentials
- `credentials.json` - Access and refresh tokens

## License

MIT
