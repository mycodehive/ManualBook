from django.core.exceptions import PermissionDenied
from django.db.models import Q
from apps.organizations.models import Membership
from apps.organizations.scoping import current_organization, is_org_admin, organization_group_ids
from .models import ManualSpace

ACTION_BASE = {'create':'edit','move':'edit','delete':'edit','export':'view','download_attachment':'view','favorite':'view'}

def in_scope(obj):
    org = current_organization()
    return bool(org and obj and obj.organization_id == org.pk)

def is_member(user):
    org = current_organization()
    if not org or not user.is_authenticated or not user.is_active: return False
    return user.is_superuser or Membership.objects.filter(organization=org,user=user,active=True).exists()

def revision_in_scope(revision,node=None):
    return in_scope(revision) and (node is None or (in_scope(node) and revision.node_id == node.pk))

def node_integrity(node):
    if not in_scope(node) or not in_scope(node.space): return False
    for revision in (node.draft,node.published):
        if revision and not revision_in_scope(revision,node): return False
    cursor=node
    seen=set()
    while cursor:
        if cursor.pk in seen or not in_scope(cursor) or cursor.space_id != node.space_id: return False
        seen.add(cursor.pk)
        cursor=cursor.parent
    return True

def allowed(user,space,action='view'):
    if not in_scope(space) or not is_member(user): return False
    if is_org_admin(user): return True
    if not space.active: return False
    groups=organization_group_ids(user)
    manager=space.approve_groups.filter(pk__in=groups).exists()
    editor=space.edit_groups.filter(pk__in=groups).exists()
    if space.visibility == 'public' and action in ('export', 'favorite') and not (manager or editor): return False
    action=ACTION_BASE.get(action,action)
    if action in ('manage','approve','publish'): return manager
    if action=='edit': return manager or editor
    return manager or editor or space.view_groups.filter(pk__in=groups).exists()

def require(user,space,action='view'):
    if not allowed(user,space,action): raise PermissionDenied('이 조직의 공간에 접근할 권한이 없습니다.')

def spaces_for(user):
    if not is_member(user): return ManualSpace.objects.none()
    if is_org_admin(user): return ManualSpace.objects.all()
    groups=organization_group_ids(user)
    return ManualSpace.objects.filter(active=True).filter(Q(view_groups__pk__in=groups)|Q(edit_groups__pk__in=groups)|Q(approve_groups__pk__in=groups)).distinct()

def node_visible(node):
    if not node_integrity(node): return False
    while node:
        if node.deleted or node.archived: return False
        node=node.parent
    return True

def node_allowed(user,node,action='view'):
    if not node_integrity(node) or not is_member(user): return False
    if is_org_admin(user): return True
    if not allowed(user,node.space,'view'): return False
    if node.space.visibility == 'public' and action in ('export', 'favorite') and not allowed(user,node.space,'edit'): return False
    base_action=ACTION_BASE.get(action,action)
    groups=organization_group_ids(user)
    cursor=node
    assignments=[]
    while cursor:
        assignments.extend(cursor.permission_assignments.filter(action__in={action,base_action}).filter(Q(user=user)|Q(group_id__in=groups)).values_list('effect',flat=True))
        cursor=cursor.parent
    if 'deny' in assignments: return False
    if 'allow' in assignments: return True
    return allowed(user,node.space,base_action)

def require_node(user,node,action='view'):
    if not node_allowed(user,node,action): raise PermissionDenied('이 조직의 문서 작업 권한이 없습니다.')
