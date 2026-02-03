# VHS tape file for ytstudio-cli demo
# Run: vhs demo.tape

Output demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"
Set Padding 20

Set TypingSpeed 50ms

Set Env "YTS_DEMO" "1"

Type "# ytstudio-cli - manage your YouTube channel from the terminal"
Enter
Sleep 1s

Type "yts videos list"
Enter
Sleep 3s

Type "yts videos get vSzx36FRX-E"
Enter
Sleep 3s

Type "yts analytics overview --days 28"
Enter
Sleep 3s

Type "# Export to JSON for automation"
Enter
Sleep 500ms

Type "yts videos list --output json | head -20"
Enter
Sleep 2s

Type "# 🎬 github.com/jdwit/ytstudio-cli"
Enter
Sleep 2s
