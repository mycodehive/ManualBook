const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');

test('bundled editor initializes saved content, syncs edits and keeps Markdown fallback', () => {
  const dom = new JSDOM(`<form id="manual-editor"><textarea name="markdown" data-block-editor># Saved</textarea></form><script type="application/json" id="editor-initial-html">"<h1>Saved</h1><p>Existing content</p>"</script>`, {runScripts: 'outside-only', pretendToBeVisual: true, url: 'https://manualbook.test/'});
  let instance;
  dom.window.addEventListener('manualbook:editor-ready', event => instance = event.detail);
  dom.window.eval(fs.readFileSync('static/js/block-editor.js', 'utf8'));
  assert.ok(instance);
  assert.equal(instance.editor.getText().includes('Existing content'), true);
  assert.equal(instance.textarea.hidden, true);
  instance.editor.commands.setContent('<h2>Updated</h2><p>New text</p>');
  assert.equal(instance.textarea.value.includes('## Updated'), true);
  assert.equal(instance.textarea.value.includes('New text'), true);
  instance.editor.commands.setContent('<ul data-type="taskList"><li data-type="taskItem" data-checked="true">Done</li></ul>');
  assert.equal(instance.textarea.value.includes('- [x] Done'), true);
  [...dom.window.document.querySelectorAll('button')].find(button => button.textContent === 'Markdown 편집').click();
  assert.equal(instance.textarea.hidden, false);
  instance.textarea.value = '# Plain mode';
  instance.textarea.form.dispatchEvent(new dom.window.Event('submit'));
  assert.equal(instance.textarea.value, '# Plain mode');
  instance.editor.destroy(); dom.window.close();
});

test('autosave reads input title rather than the form title attribute', async () => {
  const dom = new JSDOM(`<form id="manual-editor" data-autosave="/autosave/"><input name="csrfmiddlewaretoken" value="csrf"><input name="title" value="Edited title"><input name="version" value="3"><textarea name="markdown">Content</textarea></form><span id="save-status"></span>`, {runScripts: 'outside-only', url: 'https://manualbook.test/'});
  let timer, sent;
  dom.window.setTimeout = callback => {timer = callback; return 1;};
  dom.window.clearTimeout = () => {};
  dom.window.fetch = async (_, options) => {sent = JSON.parse(options.body); return {ok: true, status: 200, json: async () => ({version: 4})};};
  dom.window.eval(fs.readFileSync('static/js/manuals.js', 'utf8'));
  dom.window.document.querySelector('textarea').dispatchEvent(new dom.window.Event('input'));
  await timer();
  assert.equal(sent.title, 'Edited title');
  assert.equal(sent.version, 3);
  assert.equal(dom.window.document.querySelector('[name=version]').value, '4');
  dom.window.close();
});
