from apps.organizations.scoping import current_organization, is_org_admin, organization_group_ids

def can_access_menu(user,menu,by_id=None,groups=None):
    org=current_organization()
    if not org or not org.active or not user.is_authenticated or not user.is_active or menu.organization_id!=org.pk:
        return False
    from apps.organizations.models import Membership, OrganizationGroup
    if not user.is_superuser and not Membership.objects.filter(user=user,active=True).exists():
        return False
    groups=set(groups) if groups is not None else organization_group_ids(user)
    valid_groups=set(OrganizationGroup.objects.values_list('group_id',flat=True))
    groups &= valid_groups
    administrator=is_org_admin(user);seen=set()
    while menu:
        if menu.organization_id!=org.pk or menu.pk in seen or not menu.is_active: return False
        if menu.code=='settings' and not administrator: return False
        seen.add(menu.pk)
        allowed={group.pk for group in menu.allowed_groups.all()}
        if not allowed<=valid_groups: return False
        if allowed and not administrator and not allowed&groups: return False
        rules=menu.inherited_group_rules
        if not isinstance(rules,list): return False
        for rule in rules:
            if not isinstance(rule,list) or any(type(pk) is not int or pk not in valid_groups for pk in rule): return False
            if rule and not administrator and not groups&set(rule): return False
        parent_id=menu.parent_menu_id
        if parent_id is None: break
        parent=by_id.get(parent_id) if by_id is not None else menu.parent_menu
        if parent is None: return False
        menu=parent
    return True
