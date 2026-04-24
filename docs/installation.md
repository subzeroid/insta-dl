# Installation

## Requirements

- Python **3.11+** (uses `dataclass(slots=True)`, `X | Y` union syntax, and `datetime.fromisoformat` accepting `Z`)
- A HikerAPI token *(default backend)* — grab a free one at [hikerapi.com](https://hikerapi.com/p/18j4ib4j) (100 requests, no card)

## Install from PyPI

!!! note "Not yet on PyPI"
    insta-dl is in alpha and not published to PyPI yet. Use the editable install from source for now.

```bash
pip install insta-dl
```

## Install from source

```bash
git clone https://github.com/subzeroid/insta-dl
cd insta-dl
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

For development (tests + docs):

```bash
pip install -e '.[dev]'   # pytest + pytest-asyncio + pytest-cov
pip install -e '.[docs]'  # mkdocs-material
```

## Get a HikerAPI token

1. Sign up at [hikerapi.com](https://hikerapi.com/p/18j4ib4j) — first **100 requests are free**, no credit card.
2. Copy your access token from the dashboard.
3. Make it available to insta-dl:

```bash
# environment variable (recommended)
export HIKERAPI_TOKEN='your_token_here'

# or pass via flag every time
insta-dl --hiker-token 'your_token_here' instagram
```

For shells started fresh, add the export to `~/.zshrc` / `~/.bashrc` or use a secret manager (1Password CLI, `pass`, `direnv`).

## Set up aiograpi *(optional, in development)*

The aiograpi backend uses your real Instagram credentials. It's stubbed pending an upstream sync — these instructions will work once the integration ships:

```bash
insta-dl --backend aiograpi --login YOUR_USER --password YOUR_PASS \
    --session ~/.config/insta-dl/session.json instagram
```

The `--session` file is created on first successful login and reused on subsequent runs (so you don't keep typing the password and don't trigger 2FA every time).

## Verify the install

```bash
insta-dl --help
insta-dl --dest /tmp/test-out post:DXZlTiKEpxw   # downloads one post
ls -la /tmp/test-out/instagram/
```

You should see one `.mp4` (or `.jpg`) and one `.json` sidecar with the post date as mtime.

## Uninstall

```bash
pip uninstall insta-dl
```
