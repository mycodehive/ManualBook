const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
test('logout uses current CSRF cookie after another tab logs in and leaves other forms intact',()=>{
  const dom=new JSDOM('<form data-logout-form><input name="csrfmiddlewaretoken" value="old"></form><form id="ordinary"><input name="csrfmiddlewaretoken" value="ordinary-token"></form>',{url:'https://manualbook.test/o/writeaday/',runScripts:'outside-only'});
  dom.window.eval(fs.readFileSync('static/js/logout.js','utf8'));
  const form=dom.window.document.querySelector('form');
  const submit=()=>form.dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));
  assert.equal(submit(),true);assert.equal(form.elements.csrfmiddlewaretoken.value,'old');
  dom.window.document.cookie='csrftoken='+'a'.repeat(32)+'; path=/';
  assert.equal(submit(),true);assert.equal(form.elements.csrfmiddlewaretoken.value,'a'.repeat(32));
  dom.window.document.cookie='csrftoken='+'b'.repeat(32)+'; path=/';
  submit();assert.equal(form.elements.csrfmiddlewaretoken.value,'b'.repeat(32));
  const ordinary=dom.window.document.querySelector('#ordinary');
  ordinary.dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));
  assert.equal(ordinary.elements.csrfmiddlewaretoken.value,'ordinary-token');dom.window.close();
});
