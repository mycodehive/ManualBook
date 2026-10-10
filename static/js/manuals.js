(() => {
 const content=document.querySelector('#manual-content'), toc=document.querySelector('#manual-toc');
 if(content && toc) content.querySelectorAll('h1,h2,h3').forEach((h,i)=>{h.id=h.id||'heading-'+i;const link=document.createElement('a');link.href='#'+h.id;link.textContent=h.textContent;link.className='toc-'+h.tagName.toLowerCase();toc.append(link)});
 let dragged=null;
 document.querySelectorAll('[data-node-id]').forEach(item=>{
  item.addEventListener('dragstart',event=>{dragged=item;event.dataTransfer.setData('text/plain',item.dataset.nodeId)});
  item.addEventListener('dragover',event=>{if(dragged&&dragged!==item&&item.dataset.kind==='folder'){event.preventDefault();item.classList.add('manual-drop-target')}});
  item.addEventListener('dragleave',()=>item.classList.remove('manual-drop-target'));
  item.addEventListener('drop',async event=>{
   event.preventDefault();item.classList.remove('manual-drop-target');
   if(!dragged||dragged===item||item.dataset.kind!=='folder')return;
   if(!confirm('선택한 노드와 하위 문서를 이 폴더로 이동할까요?'))return;
   const token=document.querySelector('[name="csrfmiddlewaretoken"]')?.value;
   const data=new URLSearchParams({parent:item.dataset.nodeId,sort_order:'0',csrfmiddlewaretoken:token});
   const response=await fetch(dragged.dataset.moveUrl,{method:'POST',body:data});
   if(response.ok)location.reload();else alert('이동 권한 또는 트리 구조를 확인하세요.');
  });
 });
 const form=document.querySelector('#manual-editor'); if(!form)return;
 const status=document.querySelector('#save-status'), field=form.querySelector('[name="markdown"]'),version=form.querySelector('[name="version"]');
 let timer,dirty=false,pending=false,conflicted=false,sequence=0;
 const mark=()=>{dirty=true;sequence++;clearTimeout(timer);if(!conflicted)timer=setTimeout(save,1800)};
 field.addEventListener('input',mark);form.querySelector('[name="title"]').addEventListener('input',mark);
 async function save(){
  if(!dirty||pending||conflicted)return;
  pending=true;const sent=sequence;status.textContent='저장 중…';
  try{
   const response=await fetch(form.dataset.autosave,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':form.querySelector('[name="csrfmiddlewaretoken"]').value},body:JSON.stringify({title:form.querySelector('[name="title"]').value,markdown:field.value,version:Number(version.value)})});
   const data=await response.json();
   if(response.status===409){conflicted=true;status.textContent=data.error+' 현재 내용을 복사한 후 새로고침하세요.';status.classList.add('save-conflict');return;}
   if(!response.ok)throw Error(data.error||'저장 실패');
   version.value=data.version;dirty=sequence!==sent;status.textContent='자동저장 완료 · v'+data.version;
  }catch(error){status.textContent='자동저장 실패. 내용을 유지하고 다시 저장하세요.';}
  finally{pending=false;if(dirty&&!conflicted)timer=setTimeout(save,2500)}
 }
 form.addEventListener('submit',e=>{clearTimeout(timer);if(pending){e.preventDefault();status.textContent='자동저장이 끝난 뒤 저장하세요.'}});
 window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
})();
