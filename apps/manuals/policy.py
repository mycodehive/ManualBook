from django.core.exceptions import PermissionDenied
from django.db.models import Q
from .models import ManualSpace

def allowed(user, space, action='view'):
    if not user.is_authenticated or not user.is_active: return False
    if user.is_superuser: return True
    if not space.active: return False
    groups = user.groups.values_list('pk', flat=True)
    manager = space.approve_groups.filter(pk__in=groups).exists()
    editor = space.edit_groups.filter(pk__in=groups).exists()
    if action == 'manage': return manager
    if action in ('approve','publish'): return manager
    if action == 'edit': return manager or editor
    return manager or editor or space.view_groups.filter(pk__in=groups).exists()

def require(user, space, action='view'):
    if not allowed(user,space,action): raise PermissionDenied('이 공간에 접근할 권한이 없습니다.')

def spaces_for(user):
    if user.is_superuser: return ManualSpace.objects.all()
    return ManualSpace.objects.filter(active=True).filter(Q(view_groups__in=user.groups.all())|Q(edit_groups__in=user.groups.all())|Q(approve_groups__in=user.groups.all())).distinct()

def node_visible(node):
    seen=set()
    while node:
        if node.pk in seen or node.deleted or node.archived: return False
        seen.add(node.pk); node=node.parent
    return True

def node_allowed(user,node,action='view'):
    if not user.is_authenticated or not user.is_active: return False
    if user.is_superuser: return True
    if not node.space.active: return False
    # Space visibility is the outer boundary. Descendant exceptions never open a private space.
    if not allowed(user,node.space,'view'): return False
    base_action={'create':'edit','move':'edit','delete':'edit','export':'view','download_attachment':'view'}.get(action,action)
    cursor=node; assignments=[]; seen=set()
    while cursor:
        if cursor.pk in seen: return False
        seen.add(cursor.pk)
        assignments.extend(cursor.permission_assignments.filter(action__in={action,base_action}).filter(Q(user=user)|Q(group__in=user.groups.all())).values_list('effect',flat=True))
        cursor=cursor.parent
    if 'deny' in assignments: return False
    if 'allow' in assignments: return True
    return allowed(user,node.space,{'create':'edit','move':'edit','delete':'edit','export':'view','download_attachment':'view'}.get(action,action))

def require_node(user,node,action='view'):
    if not node_allowed(user,node,action): raise PermissionDenied('문서 작업 권한이 없습니다.')
