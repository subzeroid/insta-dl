# Installation

## Requirements

- Python **3.11+** (uses `dataclass(slots=True)`, `X | Y` union syntax, and `datetime.fromisoformat` accepting `Z`)
- A HikerAPI token *(default backend)* — grab a free one at [hikerapi.com](https://hikerapi.com/p/18j4ib4j) (100 requests, no card)

## Install from PyPI

```bash
pip install instagram-dl
```

The PyPI distribution is called **`instagram-dl`** (because `insta-dl` is blocked by a similarly-named abandoned package). The installed CLI command is still `insta-dl`, and the Python import path is still `insta_dl`.

### With pipx (recommended for CLI-only use)

If you only want the `insta-dl` command and don't plan to import the library, install it in an isolated environment with [pipx](https://pipx.pypa.io/):

```bash
pipx install instagram-dl
```

### With Docker

A multi-arch image is published to GitHub Container Registry on every tagged release:

```bash
docker run --rm \
    -v "$PWD/out:/data" \
    -e HIKERAPI_TOKEN \
    ghcr.io/subzeroid/insta-dl:latest instagram
```

The container writes to `/data`, which we mount to `./out` on the host. Pin to a specific version with `ghcr.io/subzeroid/insta-dl:0.0.1` if you don't want `latest` to float.

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
pip uninstall instagram-dl
```
