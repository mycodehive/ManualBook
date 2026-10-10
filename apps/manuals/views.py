import difflib
import io
import json
import zipfile
from pathlib import Path
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q
from django.db import transaction
from django.http import FileResponse, HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import ManualSpace, ManualNode, ManualRevision, ApprovalRequest, ManualAttachment, ManualFavorite, ManualRecentView, ManualPermissionAssignment
from .forms import SpaceForm, NodeForm, PermissionForm
from .policy import allowed, require, spaces_for, node_visible, node_allowed, require_node
from . import services

def context(request,space=None):
    return {'manual_spaces':spaces_for(request.user),'space':space,'can_edit':bool(space and allowed(request.user,space,'edit')),'can_manage':bool(space and allowed(request.user,space,'manage'))}

def get_node(request,pk,action='view',include_deleted=False):
    node=get_object_or_404(ManualNode.objects.select_related('space','draft','published','parent'),pk=pk)
    require_node(request.user,node,action)
    if not include_deleted and not node_visible(node) and not node_allowed(request.user,node,'edit'): raise Http404
    if node.deleted and not include_deleted: raise Http404
    return node

@login_required
def index(request):
    spaces=spaces_for(request.user)
    pages=ManualNode.objects.filter(space__in=spaces,kind='page',published__isnull=False,deleted=False,archived=False).select_related('published','space','parent')
    query=request.GET.get('q','').strip()
    if query: pages=pages.filter(Q(published__title__icontains=query)|Q(published__markdown__icontains=query))
    if request.GET.get('favorites'): pages=pages.filter(manualfavorite__user=request.user)
    pages=[n for n in pages if node_visible(n) and node_allowed(request.user,n)]
    return render(request,'manuals/index.html',{**context(request),'pages':pages,'query':query,'space_count':spaces.count(),'page_count':len(pages)})

@login_required
def spaces(request):
    return render(request,'manuals/spaces.html',{**context(request),'spaces':spaces_for(request.user)})

@login_required
def space_form(request,pk=None):
    space=get_object_or_404(ManualSpace,pk=pk) if pk else None
    if space: require(request.user,space,'manage')
    elif not request.user.is_superuser: raise PermissionDenied
    form=SpaceForm(request.POST or None,instance=space)
    if request.method=='POST' and form.is_valid():
        space=form.save(); services.audit(request.user,'manual.space.settings',space); messages.success(request,'공간 설정을 저장했습니다.'); return redirect('manuals:space',pk=space.pk)
    return render(request,'manuals/form.html',{**context(request,space),'form':form,'title':'공간 설정'})

@login_required
def space(request,pk):
    obj=get_object_or_404(ManualSpace,pk=pk); require(request.user,obj)
    editor=allowed(request.user,obj,'edit')
    nodes=[n for n in obj.nodes.select_related('published','draft','parent') if node_visible(n) and node_allowed(request.user,n) and (node_allowed(request.user,n,'edit') or n.kind=='folder' or n.published_id)]
    return render(request,'manuals/space.html',{**context(request,obj),'nodes':tree_nodes(nodes)})

@login_required
def node_form(request,space_id=None,pk=None):
    node=get_node(request,pk,'edit',True) if pk else None
    obj=node.space if node else get_object_or_404(ManualSpace,pk=space_id); require(request.user,obj,'edit')
    original_parent_id=node.parent_id if node else None
    form=NodeForm(request.POST or None,instance=node,space=obj)
    if request.method=='POST' and form.is_valid():
        if node and original_parent_id != (form.cleaned_data.get('parent').pk if form.cleaned_data.get('parent') else None):
            require_node(request.user,node,'move')
            services.move_node(request.user,node.pk,form.cleaned_data.get('parent').pk if form.cleaned_data.get('parent') else None,form.cleaned_data.get('sort_order',0))
        if form.cleaned_data.get('parent'): require_node(request.user,form.cleaned_data['parent'],'create')
        node=form.save(); services.audit(request.user,'manual.settings',node); return redirect('manuals:space',pk=obj.pk)
    return render(request,'manuals/form.html',{**context(request,obj),'form':form,'node':node,'title':'문서·폴더 설정','descendants':descendants(node) if node else 0,'permission_form':PermissionForm() if node and node_allowed(request.user,node,'manage') else None,'assignments':node.permission_assignments.select_related('group','user') if node and node_allowed(request.user,node,'manage') else []})

def tree_nodes(nodes):
    by_parent={}
    for node in nodes: by_parent.setdefault(node.parent_id,[]).append(node)
    result=[];seen=set()
    def walk(parent,depth):
        for node in by_parent.get(parent,[]):
            if node.pk in seen: continue
            seen.add(node.pk);node.depth=min(depth,10);result.append(node);walk(node.pk,depth+1)
    walk(None,0)
    return result

def descendants(node):
    if not node: return 0
    count=0; pending=list(node.children.all()); seen=set()
    while pending:
        n=pending.pop()
        if n.pk in seen: continue
        seen.add(n.pk); count+=1; pending.extend(n.children.all())
    return count

@login_required
def page(request,pk):
    node=get_node(request,pk)
    if node.kind=='folder': return redirect('manuals:space',pk=node.space_id)
    revision=node.published
    if request.GET.get('draft') and node_allowed(request.user,node,'edit'): revision=node.draft
    if not revision: raise Http404('게시된 문서가 없습니다.')
    ManualRecentView.objects.update_or_create(user=request.user,node=node)
    attachments=node.attachments.filter(revision=revision)
    return render(request,'manuals/page.html',{**context(request,node.space),'node':node,'revision':revision,'can_edit':node_allowed(request.user,node,'edit'),'is_draft':revision.pk!=node.published_id,'attachments':attachments,'favorite':ManualFavorite.objects.filter(user=request.user,node=node).exists(),'nodes':tree_nodes([n for n in node.space.nodes.select_related('published','parent') if node_visible(n) and node_allowed(request.user,n) and (n.kind=='folder' or n.published_id)])})

@login_required
def edit(request,pk):
    node=get_node(request,pk,'edit')
    if node.kind!='page': raise Http404
    if request.method=='POST':
        try:
            services.save_revision(request.user,node.pk,request.POST.get('title',node.title),request.POST.get('markdown',''),request.POST.get('version',-1),request.POST.get('reason',''))
            messages.success(request,'새 버전을 저장했습니다.'); return redirect('manuals:edit',pk=pk)
        except ValidationError as exc: messages.error(request,' '.join(exc.messages))
    return render(request,'manuals/edit.html',{**context(request,node.space),'node':node,'submitted_body':request.POST.get('markdown') if request.method=='POST' else None,'editor_html':services.render_markdown(request.POST.get('markdown','')) if request.method=='POST' else (node.draft.html if node.draft else '')})

@login_required
@require_POST
def autosave(request,pk):
    node=get_node(request,pk,'edit')
    try:
        data=json.loads(request.body)
        if not isinstance(data,dict): raise ValidationError('객체 형태로 전송하세요.')
        rev=services.save_revision(request.user,node.pk,data.get('title',node.title),data.get('markdown',''),data.get('version',-1),'자동저장')
        return JsonResponse({'version':rev.number,'saved_at':rev.created_at.isoformat()})
    except services.Conflict as exc: return JsonResponse({'error':' '.join(exc.messages)},status=409)
    except (ValidationError,ValueError,TypeError) as exc: return JsonResponse({'error':str(exc)},status=400)

@login_required
@require_POST
def action(request,pk,action):
    node=get_node(request,pk,'edit',True)
    try:
        if action=='review': services.request_review(request.user,node)
        elif action=='publish': services.publish(request.user,node)
        elif action in ('delete','restore'):
            require_node(request.user,node,'delete')
            node.deleted=action=='delete'; node.save(update_fields=['deleted']); services.audit(request.user,'manual.'+action,node)
        elif action=='copy': services.copy_node(request.user,node,node.parent)
        elif action=='move': services.move_node(request.user,pk,request.POST.get('parent') or None,request.POST.get('sort_order',0))
        else: raise Http404
        messages.success(request,'처리했습니다.')
    except ValidationError as exc: messages.error(request,' '.join(exc.messages))
    return redirect('manuals:space',pk=node.space_id)

@login_required
def reviews(request):
    items=ApprovalRequest.objects.filter(revision__node__space__in=spaces_for(request.user)).select_related('revision__node__space','requester')
    items=[item for item in items if node_allowed(request.user,item.revision.node,'approve')]
    return render(request,'manuals/reviews.html',{**context(request),'reviews':items})

@login_required
@require_POST
def decision(request,pk):
    review=get_object_or_404(ApprovalRequest,pk=pk)
    try: services.decide(request.user,review.pk,request.POST.get('decision')=='approve',request.POST.get('comment','')); messages.success(request,'검토 결과를 기록했습니다.')
    except ValidationError as exc: messages.error(request,' '.join(exc.messages))
    return redirect('manuals:reviews')

@login_required
def review_detail(request,pk):
    review=get_object_or_404(ApprovalRequest.objects.select_related('revision__node__space'),pk=pk)
    require_node(request.user,review.revision.node,'approve')
    return render(request,'manuals/review_detail.html',{**context(request,review.revision.node.space),'review':review,'revision':review.revision})

@login_required
def history(request,pk):
    node=get_node(request,pk,'edit')
    versions=node.revisions.all()
    diff=''
    if request.GET.get('a') and request.GET.get('b'):
        a=get_object_or_404(versions,pk=request.GET['a']); b=get_object_or_404(versions,pk=request.GET['b'])
        diff='\n'.join(difflib.unified_diff(a.markdown.splitlines(),b.markdown.splitlines(),fromfile=f'v{a.number}',tofile=f'v{b.number}',lineterm=''))
    if request.method=='POST':
        rev=get_object_or_404(versions,pk=request.POST.get('revision'))
        try: services.save_revision(request.user,node.pk,rev.title,rev.markdown,request.POST.get('version',-1),f'v{rev.number} 복원'); return redirect('manuals:edit',pk=node.pk)
        except ValidationError as exc: messages.error(request,' '.join(exc.messages))
    return render(request,'manuals/history.html',{**context(request,node.space),'node':node,'versions':versions,'diff':diff})

@login_required
@require_POST
def favorite(request,pk):
    node=get_node(request,pk)
    if not node.published_id: raise Http404
    obj,created=ManualFavorite.objects.get_or_create(user=request.user,node=node)
    if not created: obj.delete()
    return redirect('manuals:page',pk=pk)

@login_required
def trash(request,pk):
    obj=get_object_or_404(ManualSpace,pk=pk); require(request.user,obj,'edit')
    return render(request,'manuals/trash.html',{**context(request,obj),'nodes':[n for n in obj.nodes.filter(deleted=True) if node_allowed(request.user,n,'edit')]})

@login_required
@require_POST
def upload(request,pk):
    node=get_node(request,pk,'edit'); file=request.FILES.get('file')
    if not file or not node.draft: messages.error(request,'초안을 저장하고 파일을 선택하세요.')
    elif file.size>10*1024*1024 or Path(file.name).suffix.lower() not in {'.pdf','.png','.jpg','.jpeg','.txt','.md','.csv','.xlsx','.docx'}: messages.error(request,'10MB 이하의 허용된 파일만 업로드할 수 있습니다.')
    else:
        with transaction.atomic():
            locked=ManualNode.objects.select_for_update().get(pk=node.pk)
            revision=services.save_revision(request.user,locked.pk,locked.title,locked.draft.markdown,locked.version,'첨부파일 추가')
            ManualAttachment.objects.create(node=locked,revision=revision,file=file,name=Path(file.name).name[:200],author=request.user)
            services.audit(request.user,'manual.upload',locked)
        messages.success(request,'첨부파일을 포함한 새 초안 버전을 만들었습니다.')
    return redirect('manuals:edit',pk=pk)

@login_required
def download(request,pk):
    attachment=get_object_or_404(ManualAttachment.objects.select_related('node__space'),pk=pk)
    node=get_node(request,attachment.node_id,'download_attachment')
    in_publication = attachment.revision_id == node.published_id or bool(node.published_id and node.published.attachments.filter(file=attachment.file.name).exists())
    if not in_publication and not node_allowed(request.user,node,'edit'): raise Http404
    inline = request.GET.get('inline') == '1' and Path(attachment.name).suffix.lower() in {'.png', '.jpg', '.jpeg'}
    content_type = None
    if inline:
        from PIL import Image, UnidentifiedImageError
        try:
            with attachment.file.open('rb') as file:
                image = Image.open(file)
                content_type = Image.MIME.get(image.format)
                if content_type not in {'image/png', 'image/jpeg'}:
                    raise Http404
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise Http404('올바른 이미지 파일이 아닙니다.')
    return FileResponse(attachment.file.open('rb'),as_attachment=not inline,filename=attachment.name,content_type=content_type)

@login_required
def export_page(request,pk):
    node=get_node(request,pk,'export')
    if not node.published_id: raise Http404
    response=HttpResponse(node.published.markdown,content_type='text/markdown; charset=utf-8'); response['Content-Disposition']=f'attachment; filename="manual-{node.pk}.md"'; return response

@login_required
def export_space(request,pk):
    obj=get_object_or_404(ManualSpace,pk=pk); require(request.user,obj)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for node in obj.nodes.filter(published__isnull=False).select_related('published','parent'):
            if node_visible(node) and node_allowed(request.user,node,'export'): archive.writestr(f'{node.pk}.md',f'# {node.published.title}\n\n{node.published.markdown}')
    stream.seek(0); return FileResponse(stream,as_attachment=True,filename=f'space-{pk}.zip')

@login_required
@require_POST
def import_markdown(request,pk):
    obj=get_object_or_404(ManualSpace,pk=pk); require(request.user,obj,'edit'); file=request.FILES.get('file')
    if not file or file.size>2*1024*1024 or Path(file.name).suffix.lower()!='.md': messages.error(request,'2MB 이하의 Markdown 파일을 선택하세요.')
    else:
        try:
            body=file.read().decode('utf-8-sig'); node=ManualNode.objects.create(space=obj,title=Path(file.name).stem[:200]); services.save_revision(request.user,node.pk,node.title,body,0,'Markdown 가져오기'); messages.success(request,'초안으로 가져왔습니다.')
        except UnicodeDecodeError: messages.error(request,'UTF-8 파일만 지원합니다.')
    return redirect('manuals:space',pk=pk)

@login_required
@require_POST
def preview(request):
    try: data=json.loads(request.body)
    except (ValueError,TypeError): return JsonResponse({'error':'잘못된 요청'},status=400)
    if not isinstance(data,dict) or not isinstance(data.get('markdown',''),str): return JsonResponse({'error':'잘못된 요청'},status=400)
    try: body=data.get('markdown','')
    except (ValueError,TypeError): return JsonResponse({'error':'잘못된 요청'},status=400)
    if len(body)>2*1024*1024: return JsonResponse({'error':'문서 크기 초과'},status=400)
    return JsonResponse({'html':services.render_markdown(body)})

@login_required
@require_POST
def permission(request,pk):
    node=get_node(request,pk,'manage',True)
    if request.POST.get('remove'):
        rule=get_object_or_404(ManualPermissionAssignment,node=node,pk=request.POST['remove']);rule.delete()
    else:
        form=PermissionForm(request.POST)
        if form.is_valid():
            rule=form.save(commit=False);rule.node=node;rule.save()
        else: messages.error(request,' '.join(str(e) for e in form.errors.values()))
    services.audit(request.user,'manual.permissions',node)
    return redirect('manuals:node_settings',pk=pk)
