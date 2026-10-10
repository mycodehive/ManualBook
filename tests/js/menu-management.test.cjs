const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
test('keyboard menu move sends organization URL, CSRF and revision and displays stale errors', async () => {
  const dom = new JSDOM(`<form data-menu-move-form><input name="csrfmiddlewaretoken" value="own-token"><select name="source"><option value="1">One</option></select><select name="target"><option value="2">Two</option></select><select name="position"><option value="inside">Inside</option></select><button>Move</button></form><p data-menu-move-status></p><table data-menu-move-url="/o/alpha/menus/move/" data-menu-revision="revision123"><tbody></tbody></table>`, {runScripts:'outside-only',url:'https://manualbook.test/o/alpha/menus/'});
  let calls=0;
  dom.window.fetch = async (url, options) => {
    calls++;assert.equal(url,'/o/alpha/menus/move/');assert.equal(options.credentials,'same-origin');assert.equal(options.headers['X-CSRFToken'],'own-token');
    assert.deepEqual(JSON.parse(options.body),{source:1,target:2,position:'inside',revision:'revision123'});
    return {ok:false,json:async()=>({error:'메뉴가 변경되었습니다. 새로고침하세요.'})};
  };
  dom.window.eval(fs.readFileSync('static/js/menu-management.js','utf8'));
  const form=dom.window.document.querySelector('form');
  form.dispatchEvent(new dom.window.Event('submit',{cancelable:true}));
  form.dispatchEvent(new dom.window.Event('submit',{cancelable:true}));
  assert.equal(form.querySelector('button').disabled,true);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls,1);assert.equal(form.querySelector('button').disabled,false);
  assert.match(dom.window.document.querySelector('p').textContent,/새로고침/);
  form.elements.target.innerHTML='<option value="1">One</option>';
  form.dispatchEvent(new dom.window.Event('submit',{cancelable:true}));
  assert.equal(calls,1);assert.match(dom.window.document.querySelector('p').textContent,/서로 다른/);
  dom.window.close();
});
test('menu status selection submits its filter',()=>{
  const dom=new JSDOM('<form><select data-menu-status-filter><option>all</option></select></form>',{runScripts:'outside-only'});
  let submissions=0;dom.window.document.querySelector('form').requestSubmit=()=>submissions++;
  dom.window.eval(fs.readFileSync('static/js/menu-management.js','utf8'));
  dom.window.document.querySelector('select').dispatchEvent(new dom.window.Event('change'));
  assert.equal(submissions,1);dom.window.close();
});
