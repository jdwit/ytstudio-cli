# terminaltrove demo tape for ytstudio-cli
#
# Records the first-run demo mode end-to-end against the built-in fake channel.
# No OAuth, no network, no sandbox account required.
#
# Render with: vhs scripts/terminaltrove-demo.tape

Output scripts/terminaltrove-demo.gif

Set FontSize 16
Set Width 1200
Set Height 720
Set Padding 20
Set Theme "Dracula"
Set Shell "bash"

Type "ytstudio demo tour --no-pauses"
Sleep 500ms
Enter
Sleep 4s
