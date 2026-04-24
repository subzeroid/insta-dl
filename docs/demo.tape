# VHS tape for the README demo GIF.
# Regenerate with: `brew install vhs && vhs docs/demo.tape`.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1100
Set Height 620
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms

Type "# insta-dl — async Instagram downloader CLI"
Sleep 600ms
Enter
Enter

Type "pip install instagram-dl"
Sleep 400ms
Enter
Sleep 1500ms

Type "export HIKERAPI_TOKEN=..."
Sleep 400ms
Enter
Sleep 600ms

Type "insta-dl --dest ./out instagram"
Sleep 400ms
Enter
Sleep 800ms

# Fake output lines so the GIF doesn't hit the network.
Type "2026-04-21_16-04-15_DXZlTiKEpxw.mp4  (3.2 MB)"
Enter
Sleep 200ms
Type "2026-04-21_16-04-15_DXZlTiKEpxw.json"
Enter
Sleep 200ms
Type "2026-04-20_12-30-01_DXYm99kEpaq.jpg  (412 KB)"
Enter
Sleep 200ms
Type "2026-04-20_12-30-01_DXYm99kEpaq.json"
Enter
Sleep 800ms

Type "insta-dl --fast-update --latest-stamps ./stamps.ini --dest ./out instagram"
Sleep 400ms
Enter
Sleep 500ms
Type "up to date — 0 new posts."
Enter
Sleep 1200ms

Type "clear"
Enter
Sleep 300ms

Type "insta-dl --stories --highlights '#sunset' post:DXZlTiKEpxw"
Sleep 400ms
Enter
Sleep 2000ms
