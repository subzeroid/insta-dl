# VHS tape for the README demo GIF.
# Regenerate with: `brew install vhs && vhs docs/demo.tape` (from the repo root).
# Requires `.venv/bin/insta-dl` to exist — run `pip install -e .` in the repo venv first.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1100
Set Height 620
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type "source .venv/bin/activate"
Enter
Type "export PS1='$ '"
Enter
Type "cd $(mktemp -d)"
Enter
Type "mkdir -p instagram && cd instagram"
Enter
Type "touch -t 202604211604.15 2026-04-21_16-04-15_DXZlTiKEpxw.mp4 2026-04-21_16-04-15_DXZlTiKEpxw.json"
Enter
Type "touch -t 202604201230.01 2026-04-20_12-30-01_DXYm99kEpaq.jpg 2026-04-20_12-30-01_DXYm99kEpaq.json"
Enter
Type "touch -t 202604190845.22 2026-04-19_08-45-22_DXXpZRLEo4n.mp4 2026-04-19_08-45-22_DXXpZRLEo4n.json"
Enter
Type "cd .."
Enter
Type "clear"
Enter
Show

Sleep 500ms
Type "# insta-dl — async Instagram downloader CLI"
Enter
Sleep 400ms
Type "# install:  pip install instagram-dl"
Enter
Sleep 800ms

Type "insta-dl --help"
Sleep 200ms
Enter
Sleep 4000ms

Type "clear"
Enter
Sleep 300ms

Type "# archived posts keep their original taken_at as file mtime,"
Enter
Type "# plus a JSON sidecar next to every media file"
Enter
Sleep 400ms

Type "ls -la instagram/"
Sleep 200ms
Enter
Sleep 3500ms
