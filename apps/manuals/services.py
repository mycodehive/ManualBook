import bleach
import markdown
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import ManualNode, ManualRevision, ApprovalRequest, ManualAttachment
from .policy import require, require_node, node_allowed

class Conflict(ValidationError): pass

def render_markdown(value):
    html = markdown.markdown(value, extensions=['tables','fenced_code','toc'])
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    for item in soup.find_all('li'):
        if not item.contents or not isinstance(item.contents[0], str):
            continue
        import re
        match = re.match(r'^\[([ xX])\]\s+', str(item.contents[0]))
        if match:
            item['data-type'] = 'taskItem'
            item['data-checked'] = 'true' if match.group(1).lower() == 'x' else 'false'
            item.contents[0].replace_with(str(item.contents[0])[match.end():])
            item.parent['data-type'] = 'taskList'
    return bleach.clean(str(soup), tags=['p','br','h1','h2','h3','h4','h5','h6','ul','ol','li','strong','em','s','blockquote','pre','code','a','table','thead','tbody','tr','th','td','hr','details','summary','img'], attributes={'a':['href','title'],'h1':['id'],'h2':['id'],'h3':['id'],'h4':['id'],'h5':['id'],'h6':['id'],'code':['class'],'ul':['data-type'],'li':['data-type','data-checked'],'img':lambda tag,name,value: name=='alt' or (name=='src' and value.startswith('/manuals/attachments/'))}, protocols=['http','https','mailto'], strip=True)

def audit(user,action,node):
    from apps.core.services import audit as record
    record(user, action, node)

@transaction.atomic
def save_revision(user,node_id,title,body,version,reason=''):
    node=ManualNode.objects.select_for_update().select_related('space').get(pk=node_id)
    require_node(user,node,'edit')
    if node.kind != 'page' or node.deleted: raise ValidationError('편집할 수 없는 문서입니다.')
    try: version=int(version)
    except (TypeError,ValueError): raise ValidationError('버전 값이 올바르지 않습니다.')
    if not isinstance(title,str) or not title.strip() or len(title)>200: raise ValidationError('제목은 1~200자로 입력하세요.')
    if not isinstance(body,str) or len(body)>2*1024*1024: raise ValidationError('본문은 2MB 이하의 문자열이어야 합니다.')
    if not isinstance(reason,str) or len(reason)>250: raise ValidationError('변경 사유는 250자 이하로 입력하세요.')
    if node.version != version: raise Conflict('다른 사용자가 수정했습니다. 최신 내용을 다시 불러오세요.')
    rev=ManualRevision.objects.create(node=node,number=node.version+1,title=title,markdown=body,html=render_markdown(body),reason=reason,author=user)
    if node.draft_id:
        for attachment in node.draft.attachments.all():
            ManualAttachment.objects.create(node=node,revision=rev,file=attachment.file.name,name=attachment.name,author=attachment.author)
    node.version+=1; node.title=title; node.draft=rev; node.save(update_fields=['version','title','draft'])
    audit(user,'manual.save',node)
    return rev

@transaction.atomic
def move_node(user,node_id,parent_id,order):
    node=ManualNode.objects.select_for_update().select_related('space').get(pk=node_id)
    require_node(user,node,'move')
    list(ManualNode.objects.select_for_update().filter(space=node.space))
    try:
        node.parent=ManualNode.objects.get(pk=int(parent_id)) if parent_id else None
        order=int(order)
    except (ManualNode.DoesNotExist,TypeError,ValueError): raise ValidationError('이동할 폴더 또는 순서가 올바르지 않습니다.')
    if node.parent: require_node(user,node.parent,'create')
    node.sort_order=int(order); node.clean(); node.save(update_fields=['parent','sort_order'])
    audit(user,'manual.move',node)
    return node

@transaction.atomic
def request_review(user,node):
    node=ManualNode.objects.select_for_update().get(pk=node.pk)
    require_node(user,node,'edit')
    if node.deleted or node.archived: raise ValidationError('삭제·보관된 문서는 검토 요청할 수 없습니다.')
    if not node.draft: raise ValidationError('초안을 먼저 저장하세요.')
    obj,created=ApprovalRequest.objects.get_or_create(revision=node.draft,status='pending',defaults={'requester':user})
    audit(user,'manual.review',node)
    return obj

@transaction.atomic
def decide(user,request_id,approve,comment):
    review=ApprovalRequest.objects.select_for_update().select_related('revision__node__space').get(pk=request_id)
    node=ManualNode.objects.select_for_update().get(pk=review.revision.node_id)
    require_node(user,node,'approve')
    if review.status!='pending': raise ValidationError('이미 처리된 요청입니다.')
    if not node.space.allow_self_approval and (review.requester_id==user.pk or review.revision.author_id==user.pk): raise ValidationError('본인 문서는 승인할 수 없습니다.')
    review.status='approved' if approve else 'rejected'; review.decided_by=user; review.decided_at=timezone.now(); review.comment=comment; review.save()
    audit(user,'manual.'+review.status,node)
    return review

@transaction.atomic
def publish(user,node):
    node=ManualNode.objects.select_for_update().get(pk=node.pk)
    require_node(user,node,'publish' if node.space.require_approval else 'edit')
    if node.deleted or node.archived: raise ValidationError('삭제·보관된 문서는 게시할 수 없습니다.')
    if not node.draft: raise ValidationError('저장된 초안이 없습니다.')
    if node.space.require_approval and not node.draft.approvals.filter(status='approved').exists(): raise ValidationError('현재 초안 버전의 승인이 필요합니다.')
    node.published=node.draft; node.save(update_fields=['published']); audit(user,'manual.publish',node)
    return node

@transaction.atomic
def copy_node(user,node,parent=None):
    require_node(user,node,'edit')
    if parent: require_node(user,parent,'create')
    copy=ManualNode(space=node.space,parent=parent,title=node.title+' (복사)',kind=node.kind,sort_order=node.sort_order)
    copy.clean(); copy.save()
    if node.draft: save_revision(user,copy.pk,copy.title,node.draft.markdown,0,'문서 복사')
    for child in node.children.filter(deleted=False):
        if node_allowed(user,child,'edit'): copy_node(user,child,copy)
    audit(user,'manual.copy',copy)
    return copy
