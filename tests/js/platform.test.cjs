const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');

test('destructive forms require confirmation while ordinary forms remain usable', () => {
  const dom = new JSDOM('<form id="delete" data-confirm-delete="삭제 확인"><button>삭제</button></form><form id="save"><button>저장</button></form>', {runScripts: 'outside-only', url: 'https://manualbook.test/o/alpha/'});
  dom.window.matchMedia = () => ({matches: false});
  let confirmed = 0;
  dom.window.confirm = message => { assert.equal(message, '삭제 확인'); confirmed++; return false; };
  dom.window.eval(fs.readFileSync('static/js/platform.js', 'utf8'));
  const submit = id => dom.window.document.getElementById(id).dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  assert.equal(submit('delete'), false);
  assert.equal(submit('save'), true);
  assert.equal(confirmed, 1);
  dom.window.confirm = () => true;
  assert.equal(submit('delete'), true);
  dom.window.close();
});
