const vscode = require('vscode');

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.text = '$(checklist) Prompts';
  statusBar.tooltip = 'Open Prompts Manager';
  statusBar.command = 'prompts.show';
  statusBar.show();

  context.subscriptions.push(statusBar);

  const disposable = vscode.commands.registerCommand('prompts.show', () => {
    const panel = vscode.window.createWebviewPanel('promptsManager', 'Prompts Manager', vscode.ViewColumn.One, {
      enableScripts: true
    });

    const getPrompts = () => {
      return context.globalState.get('prompts') || [];
    };

    const setPrompts = (arr) => {
      return context.globalState.update('prompts', arr);
    };

    const updateHtml = () => {
      const prompts = getPrompts();
      panel.webview.html = getWebviewContent(prompts);
    };

    panel.webview.onDidReceiveMessage(async (msg) => {
      if (msg.command === 'add') {
        const arr = getPrompts();
        arr.push({ id: Date.now().toString(), title: msg.title || 'Untitled', content: msg.content || '' });
        await setPrompts(arr);
        updateHtml();
      } else if (msg.command === 'delete') {
        const arr = getPrompts().filter(p => p.id !== msg.id);
        await setPrompts(arr);
        updateHtml();
      } else if (msg.command === 'insert') {
        const p = getPrompts().find(x => x.id === msg.id);
        if (p) {
          const editor = vscode.window.activeTextEditor;
          if (editor) {
            editor.edit(editBuilder => {
              editBuilder.insert(editor.selection.active, p.content);
            });
            vscode.window.showInformationMessage('Prompt inserted into active editor');
          } else {
            // copy to clipboard as fallback
            await vscode.env.clipboard.writeText(p.content);
            vscode.window.showInformationMessage('No active editor. Prompt copied to clipboard');
          }
        }
      }
    }, undefined, context.subscriptions);

    updateHtml();
  });

  context.subscriptions.push(disposable);
}

function deactivate() {}

function getWebviewContent(prompts) {
  const list = prompts.map(p => `
    <div class="item">
      <button class="title" data-id="${p.id}">${escapeHtml(p.title)}</button>
      <button class="delete" data-id="${p.id}">Delete</button>
    </div>
    <pre class="content">${escapeHtml(p.content)}</pre>
  `).join('\n');

  return `<!doctype html>
  <html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
      body{font-family: sans-serif;padding:10px}
      .item{display:flex;gap:8px;align-items:center;margin-bottom:6px}
      .title{flex:1}
      .content{background:#f3f3f3;padding:8px;border-radius:4px}
      .controls{display:flex;gap:8px;margin-top:8px}
      textarea{width:100%;height:120px}
      input[type=text]{width:100%}
    </style>
  </head>
  <body>
    <h2>Prompts</h2>
    <div id="list">
      ${list}
    </div>

    <div class="controls">
      <div style="flex:1">
        <input id="title" type="text" placeholder="Title" />
        <textarea id="content" placeholder="Prompt content"></textarea>
        <button id="add">Add Prompt</button>
      </div>
    </div>

    <script>
      const vscode = acquireVsCodeApi();
      document.getElementById('add').addEventListener('click', () => {
        const title = document.getElementById('title').value;
        const content = document.getElementById('content').value;
        vscode.postMessage({ command: 'add', title, content });
        document.getElementById('title').value = '';
        document.getElementById('content').value = '';
      });

      document.getElementById('list').addEventListener('click', (e) => {
        const el = e.target;
        const id = el.getAttribute && el.getAttribute('data-id');
        if (!id) return;
        if (el.classList.contains('delete')) {
          vscode.postMessage({ command: 'delete', id });
        } else if (el.classList.contains('title')) {
          vscode.postMessage({ command: 'insert', id });
        }
      });
    </script>
  </body>
  </html>`;
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"
  }[c]));
}

module.exports = { activate, deactivate };
