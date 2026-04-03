Prompts Manager - VS Code Extension

This extension provides a simple prompt manager: a status-bar icon opens a panel where you can add/delete prompts (title + content). Clicking a title inserts the prompt into the active editor or copies it to clipboard if no editor is active.

How to run locally

1. Open this folder in VS Code.
2. Press F5 to launch the Extension Development Host.

How to package to .vsix

1. Install vsce: npm install -g vsce
2. Run: vsce package
3. The generated .vsix can be installed via the Extensions view -> ... -> Install from VSIX...

Notes

- Prompts are stored in extension global state (per-user, per-machine).
- This is a minimal prototype. You can extend it to support sync, categories, and editing.
