from apps.organizations.scoping import current_organization, is_org_admin, organization_group_ids

def can_access_menu(user, menu, by_id=None, groups=None):
    org = current_organization()
    if not org or not user.is_authenticated or not user.is_active or menu.organization_id != org.pk:
        return False
    from apps.organizations.models import Membership
    if not user.is_superuser and not Membership.objects.filter(user=user, active=True).exists():
        return False
    groups = groups if groups is not None else organization_group_ids(user)
    seen = set()
    while menu:
        if menu.organization_id != org.pk or menu.pk in seen or not menu.is_active: return False
        if menu.code == "settings" and not is_org_admin(user): return False
        seen.add(menu.pk)
        allowed = {g.pk for g in menu.allowed_groups.all()}
        if allowed and not is_org_admin(user) and not (allowed & groups): return False
        menu = by_id.get(menu.parent_menu_id) if by_id is not None else menu.parent_menu
    return True
