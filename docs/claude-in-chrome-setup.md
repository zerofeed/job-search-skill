# Setting up Claude in Chrome

The `job-search` skill reads LinkedIn and job pages through **Claude in Chrome**, a browser extension that lets Claude work in your own Chrome, using the sites you are already logged in to. It is a requirement for LinkedIn search and for reading job pages that need JavaScript or a login. Without it, only `/job-search apis` works.

> Details of the extension change over time. When something here disagrees with the official pages, trust the official pages:
> - Get started: https://support.claude.com/en/articles/12012173-get-started-with-claude-in-chrome
> - Claude Code integration: https://code.claude.com/docs/en/chrome
> - Safety guidance: https://support.claude.com/en/articles/12012173-using-claude-in-chrome-safely

## What you need

- **Google Chrome.** The support article lists Chrome only. The Claude Code docs also mention Edge; if you hit problems, use Chrome.
- **A paid Claude plan:** Pro, Max, Team or Enterprise (not Free). Team has it on by default; on Enterprise an admin has to enable it.
- **Claude Code** v2.0.73 or newer and the **extension** v1.0.36 or newer (check with `claude --version`, and update if older).
- **Signed in with your Claude account** via `/login`. Authenticating Claude Code only with an API key does not enable the Chrome integration.

## Install

1. Open the Chrome Web Store, search for **Claude in Chrome** (the official Anthropic extension) and click **Add to Chrome**. The article above links to it.
2. Click the extension icon and **sign in with the same Claude account** you use in Claude Code. A different account or organization is the most common reason it will not connect.
3. Accept the permissions dialog.

## Connect it to Claude Code

Start Claude Code with the Chrome integration enabled:

```bash
claude --chrome
```

The first time, a one-time dialog about site permissions appears. Check the official docs for the current way to enable it permanently, as it may change.

## Check that it works

In Claude Code, ask:

> List my open Chrome tabs.

You should get your tabs back. The tools Claude uses are named `mcp__claude-in-chrome__*`. If Claude says it has no browser tools, see Troubleshooting.

## Log in to LinkedIn first (required for LinkedIn search)

The skill never logs in for you and never asks for your password or cookies. It uses the session that already exists in your Chrome.

1. In the **same Chrome profile** where the extension is installed, open https://www.linkedin.com and log in. Finish any verification step LinkedIn asks for.
2. Keep that profile open while the skill runs.
3. If the skill reports `login_required`, LinkedIn showed a sign-in or checkpoint page. Log in again in Chrome and re-run.

## Safety

- The skill is read-only: it searches and reads. It will not apply, message or edit anything unless you ask for that specific action.
- Pages you browse can contain text written to manipulate AI tools. The skill treats page content as data. Consider limiting which sites the extension may use, as the official safety article recommends.
- Use LinkedIn at a gentle pace. The skill waits several seconds between pages and stops on a CAPTCHA.

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| "Extension not detected" | Make sure the extension is enabled at `chrome://extensions`, update Claude Code (`claude --version`), then restart both Claude Code and Chrome. |
| "No browsers are connected" | Chrome is not open, or the extension is signed in to a different Claude account or organization than Claude Code. |
| Connects, but sees the wrong profile | If you use several Chrome profiles, close the others or make sure the extension is installed and signed in on the profile where LinkedIn is logged in. |
| Conflicts with the Claude desktop app | Users have reported connection conflicts when the desktop app is also installed. Try closing it and restarting Claude Code. |
| LinkedIn shows a login page | Log in in Chrome (see above), then re-run. |
| Still failing | Restart Chrome and Claude Code; check the official troubleshooting section linked at the top. |
