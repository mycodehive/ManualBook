"""Organization-authorized, atomic menu graph operations and portable JSON exchange."""
import hashlib
import json
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.services import audit
from apps.organizations.models import Organization, OrganizationGroup
from apps.organizations.scoping import current_organization, is_org_admin
from .models import Menu, validate_menu_url, validate_workspace_name

class StaleMenuTree(ValidationError):
    pass

def authorize(user):
    org=current_organization()
    if not org or not is_org_admin(user):
        raise PermissionDenied('현재 조직의 관리자만 메뉴를 관리할 수 있습니다.')
    return org

def lock_organization(user):
    org=authorize(user)
    locked=Organization.objects.select_for_update().get(pk=org.pk)
    if not is_org_admin(user,organization=locked): raise PermissionDenied('조직 관리자 권한이 변경되었습니다.')
    return locked

def tree_revision(menus):
    values=[(m.pk,m.organization_id,m.parent_menu_id,m.order,m.code,m.name,m.url,m.is_active,m.children_as_tabs,m.inherited_group_rules,sorted(group.pk for group in m.allowed_groups.all()),m.updated_at.isoformat()) for m in sorted(menus,key=lambda m:m.pk)]
    return hashlib.sha256(json.dumps(values,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def validate_tree(menus):
    org=current_organization()
    by_id={m.pk:m for m in menus}
    if not org or len(by_id)!=len(menus) or any(m.organization_id!=org.pk for m in menus):
        raise ValidationError('메뉴는 현재 조직 안에서만 구성할 수 있습니다.')
    for menu in menus:
        seen={menu.pk};depth=1;parent_id=menu.parent_menu_id
        while parent_id is not None:
            if parent_id in seen or parent_id not in by_id:
                raise ValidationError('상위 메뉴가 없거나 메뉴 계층에 순환 참조가 있습니다.')
            seen.add(parent_id);depth+=1
            if depth>3:
                raise ValidationError('하위 메뉴를 포함해 최대 3단계까지 구성할 수 있습니다.')
            parent_id=by_id[parent_id].parent_menu_id

def group_mapping(lock=False):
    queryset=OrganizationGroup.objects.all()
    if lock: queryset=queryset.select_for_update()
    return {group.name:group.group_id for group in queryset}

def validate_rules(rules,group_ids):
    if not isinstance(rules,list) or len(rules)>1000:
        raise ValidationError('상속 그룹 권한은 목록이어야 합니다.')
    for rule in rules:
        if not isinstance(rule,list) or len(rule)>1000 or any(type(pk) is not int or pk not in group_ids for pk in rule):
            raise ValidationError('상속 그룹 권한에 다른 조직 또는 없는 그룹이 포함되어 있습니다.')

def validate_graph_groups(menus,mapping):
    valid=set(mapping.values())
    for menu in menus:
        validate_rules(menu.inherited_group_rules,valid)
        if menu.pk and menu.pk>0 and any(group.pk not in valid for group in menu.allowed_groups.all()):
            raise ValidationError('현재 조직에 속하지 않는 허용 그룹이 있습니다.')

@transaction.atomic
def move_menu(source_id,target_id,position,revision,user):
    lock_organization(user)
    menus=list(Menu.objects.select_for_update().prefetch_related('allowed_groups').order_by('pk'))
    if not isinstance(revision,str) or revision!=tree_revision(menus):
        raise StaleMenuTree('다른 창에서 메뉴가 변경되었습니다. 새로고침 후 다시 이동하세요.')
    by_id={m.pk:m for m in menus}
    if type(source_id) is not int or type(target_id) is not int or source_id not in by_id or target_id not in by_id or source_id==target_id:
        raise ValidationError('이동할 메뉴와 대상 메뉴를 확인하세요.')
    if position not in ('before','after','inside'):
        raise ValidationError('올바른 이동 위치를 선택하세요.')
    validate_graph_groups(menus,group_mapping(lock=True))
    source=by_id[source_id];target=by_id[target_id]
    old_parent=source.parent_menu_id
    new_parent=target.pk if position=='inside' else target.parent_menu_id
    siblings=sorted([m for m in menus if m.parent_menu_id==new_parent and m.pk!=source.pk],key=lambda m:(m.order,m.name,m.pk))
    index=len(siblings) if position=='inside' else next(i for i,m in enumerate(siblings) if m.pk==target.pk)+(position=='after')
    siblings.insert(index,source);source.parent_menu_id=new_parent
    validate_tree(menus)
    changed={source.pk:source}
    for i,menu in enumerate(siblings,1): menu.order=i;changed[menu.pk]=menu
    if old_parent!=new_parent:
        old_siblings=sorted([m for m in menus if m.parent_menu_id==old_parent],key=lambda m:(m.order,m.name,m.pk))
        for i,menu in enumerate(old_siblings,1): menu.order=i;changed[menu.pk]=menu
    now=timezone.now()
    for menu in changed.values(): menu.updated_at=now
    # Trusted escape hatch only after the complete, locked same-organization graph is validated.
    Menu.all_objects.filter(organization=current_organization()).bulk_update(list(changed.values()),['parent_menu','order','updated_at'])
    audit(user,'menu.move',source,{'target_code':target.code,'position':position})
    return source

@transaction.atomic
def export_menus(user=None):
    lock_organization(user)
    menus=list(Menu.objects.select_related('parent_menu').prefetch_related('allowed_groups').order_by('order','name','pk'))
    validate_tree(menus)
    mapping=group_mapping(lock=True); names={pk:name for name,pk in mapping.items()}
    validate_graph_groups(menus,mapping)
    rows=[]
    for menu in menus:
        rows.append({'code':menu.code,'name':menu.name,'url':menu.url,'order':menu.order,'parent_code':menu.parent_menu.code if menu.parent_menu else None,'is_active':menu.is_active,'children_as_tabs':menu.children_as_tabs,'description':menu.description,'workspace_dir_name':menu.workspace_dir_name,'allowed_groups':[names[g.pk] for g in menu.allowed_groups.all()],'inherited_group_rules':[[names[pk] for pk in rule] for rule in menu.inherited_group_rules]})
    audit(user,'menu.export',details={'count':len(rows)})
    return {'schema_version':1,'kind':'manualbook-menus','menus':rows}

@transaction.atomic
def import_menus(data,user):
    org=lock_organization(user)
    if not isinstance(data,dict) or type(data.get('schema_version')) is not int or data.get('schema_version')!=1 or data.get('kind') not in ('iacf-menus','manualbook-menus'):
        raise ValidationError('지원하지 않는 메뉴 파일 형식입니다.')
    try:
        if len(json.dumps(data,ensure_ascii=False).encode('utf-8'))>1024*1024: raise ValidationError('메뉴 파일은 1MB 이하입니다.')
    except (TypeError,ValueError): raise ValidationError('메뉴 JSON 형식이 올바르지 않습니다.')
    rows=data.get('menus')
    if not isinstance(rows,list) or not rows or len(rows)>1000:
        raise ValidationError('메뉴는 1개 이상 1,000개 이하로 입력하세요.')
    existing=list(Menu.objects.select_for_update().prefetch_related('allowed_groups').order_by('pk'))
    by_code={m.code:m for m in existing};groups=group_mapping(lock=True)
    validate_graph_groups(existing,groups)
    seen=set();prepared=[]
    def ids(names):
        if not isinstance(names,list) or len(names)>1000 or any(not isinstance(name,str) or name not in groups for name in names):
            raise ValidationError('파일의 그룹을 현재 조직의 그룹 관리에서 먼저 등록하세요.')
        return list(dict.fromkeys(groups[name] for name in names))
    for i,row in enumerate(rows,1):
        if not isinstance(row,dict): raise ValidationError('메뉴 항목은 JSON 객체여야 합니다.')
        code=row.get('code')
        if not isinstance(code,str) or not code.strip() or len(code)>50 or code in seen: raise ValidationError('메뉴 코드가 없거나 중복 또는 길이 초과입니다.')
        seen.add(code)
        for key in ['name','url','description','workspace_dir_name']:
            if key in row and not isinstance(row[key],str): raise ValidationError('메뉴 문자열 필드 형식이 올바르지 않습니다.')
        if not isinstance(row.get('name'),str) or not row['name'].strip(): raise ValidationError('메뉴 이름이 필요합니다.')
        if type(row.get('order')) is not int or not 0<=row['order']<=2147483647: raise ValidationError('순서는 0 이상의 정수여야 합니다.')
        if type(row.get('is_active')) is not bool: raise ValidationError('활성 상태는 true 또는 false여야 합니다.')
        if 'children_as_tabs' in row and type(row['children_as_tabs']) is not bool: raise ValidationError('탭 메뉴 상태는 true 또는 false여야 합니다.')
        parent=row.get('parent_code')
        if parent is not None and (not isinstance(parent,str) or not parent or len(parent)>50): raise ValidationError('상위 메뉴 코드 형식이 올바르지 않습니다.')
        allowed=ids(row.get('allowed_groups'))
        rules=row.get('inherited_group_rules',[])
        if not isinstance(rules,list) or len(rules)>1000: raise ValidationError('상속 그룹 권한 형식이 올바르지 않습니다.')
        rules=[ids(rule) for rule in rules]
        obj=by_code.get(code)
        if obj is None:
            obj=Menu(organization=org,pk=-i,code=code,name=row['name']);by_code[code]=obj;existing.append(obj)
        for key in ['name','url','order','is_active','children_as_tabs','description','workspace_dir_name']:
            if key in row: setattr(obj,key,row[key])
        if 'inherited_group_rules' in row or obj.pk<0: obj.inherited_group_rules=rules
        obj.url=obj.url.strip();validate_menu_url(obj.url);validate_workspace_name(obj.workspace_dir_name)
        obj.clean_fields(exclude=['id','parent_menu'])
        validate_rules(obj.inherited_group_rules,set(groups.values()))
        prepared.append((obj,parent,allowed))
    for obj,parent,allowed in prepared:
        if parent is not None and parent not in by_code: raise ValidationError('파일 또는 기존 목록에 없는 상위 메뉴 코드입니다.')
        obj.parent_menu_id=by_code[parent].pk if parent is not None else None
    validate_tree(existing)
    # New records are first inserted as valid roots; all planned parent links are applied together.
    planned_parents={obj.code:parent for obj,parent,_ in prepared}
    for obj,parent,allowed in prepared:
        if obj.pk<0:
            obj.pk=None;obj.parent_menu_id=None;obj.save()
    for obj,parent,allowed in prepared:
        obj.parent_menu_id=by_code[planned_parents[obj.code]].pk if planned_parents[obj.code] is not None else None
    validate_tree(existing)
    now=timezone.now()
    for obj,parent,allowed in prepared: obj.updated_at=now
    fields=['name','url','order','is_active','children_as_tabs','description','workspace_dir_name','inherited_group_rules','parent_menu','updated_at']
    Menu.all_objects.filter(organization=org).bulk_update([obj for obj,_,_ in prepared],fields)
    for obj,parent,allowed in prepared: obj.allowed_groups.set(allowed)
    audit(user,'menu.import',details={'count':len(prepared)})
    return len(prepared)

@transaction.atomic
def save_menu(form,user):
    org=lock_organization(user)
    from .forms import MenuForm
    if not isinstance(form,MenuForm) or form.instance.organization_id!=org.pk: raise PermissionDenied('다른 조직의 메뉴를 저장할 수 없습니다.')
    current=Menu.objects.select_for_update().get(pk=form.instance.pk) if form.instance.pk else None
    validated=MenuForm(form.data,form.files,instance=current)
    if not validated.is_valid(): raise ValidationError('메뉴 입력값을 확인하세요.')
    obj=validated.save();audit(user,'menu.updated',obj)
    return obj

@transaction.atomic
def delete_menu(pk,user):
    lock_organization(user)
    obj=Menu.objects.select_for_update().get(pk=pk)
    if Menu.all_objects.filter(parent_menu_id=obj.pk).exclude(organization=current_organization()).exists(): raise ValidationError('다른 조직의 잘못된 하위 참조를 먼저 복구하세요.')
    if obj.children.exists(): raise ValidationError('하위 메뉴를 먼저 이동하거나 삭제하세요.')
    audit(user,'menu.deleted',obj);obj.delete()
