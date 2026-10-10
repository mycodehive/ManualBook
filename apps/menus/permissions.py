def can_access_menu(user, menu, by_id=None, groups=None):
    if not user.is_authenticated: return False
    groups = groups if groups is not None else set(user.groups.values_list('pk', flat=True))
    seen = set()
    while menu:
        if menu.pk in seen or not menu.is_active: return False
        if menu.code == "settings" and not user.is_staff: return False
        seen.add(menu.pk)
        allowed = {g.pk for g in menu.allowed_groups.all()}
        if allowed and not user.is_superuser and not (allowed & groups): return False
        menu = by_id.get(menu.parent_menu_id) if by_id is not None else menu.parent_menu
    return True
