from django.urls import get_script_prefix
from apps.core.models import SiteConfiguration
from .models import Menu
from apps.organizations.scoping import current_organization, is_org_admin, organization_group_ids
from .permissions import can_access_menu
from .registry import matches_path, BASELINE_ROUTES

def navigation(request):
    site = SiteConfiguration.objects.first()
    result = {'company_name': site.name if site else 'ManualBook', 'site_configuration':site, 'company_logo_url':site.logo_url if site else '', 'brand_color':site.primary_color if site else '#355fe5', 'sidebar_menus':[], 'content_menu_tabs':[], 'organization':current_organization(), 'organization_admin':is_org_admin(request.user)}
    if getattr(request, 'public_read_allowed', False):
        result['organization_admin'] = False
        result['site_configuration'] = None
        return result
    if not request.user.is_authenticated: return result
    menus = list(Menu.objects.prefetch_related('allowed_groups').order_by('order','name'))
    by_id = {m.pk:m for m in menus}; children = {}
    for m in menus: children.setdefault(m.parent_menu_id,[]).append(m)
    groups = organization_group_ids(request.user)
    routes = {'basic':'/settings/', 'menus':'/menus/', 'members':'/accounts/', 'integrations':'/settings/integrations/', 'audit':'/settings/audit/'}
    result['settings_tab_access'] = {
        section: all(can_access_menu(request.user, menu, by_id, groups) for menu in menus
                     if matches_path(path, menu.url) or matches_path(path, BASELINE_ROUTES.get(menu.code, '')))
        for section, path in routes.items()
    }
    result['settings_page'] = request.path_info.startswith(('/settings/', '/menus/', '/organization/'))
    def build(menu, seen):
        if menu.pk in seen or not can_access_menu(request.user, menu, by_id, groups): return None
        menu.visible_children = [node for child in children.get(menu.pk,[]) if (node := build(child,seen|{menu.pk})) is not None]
        if not menu.url and not menu.visible_children: return None
        menu.is_current = matches_path(request.path_info, menu.url) or (menu.code == 'settings.users' and request.path_info.startswith('/organization/'))
        menu.is_expanded = menu.is_current or any(c.is_expanded for c in menu.visible_children)
        return menu
    result['sidebar_menus'] = [n for m in children.get(None,[]) if (n:=build(m,set())) is not None]
    active = [m for m in menus if matches_path(request.path_info,m.url)]
    current = max(active,key=lambda m:len(m.url)) if active else None
    parent = current if current and current.children_as_tabs else by_id.get(current.parent_menu_id) if current else None
    if parent and parent.children_as_tabs and can_access_menu(request.user,parent,by_id,groups):
        for item in children.get(parent.pk,[]):
            if item.url and can_access_menu(request.user,item,by_id,groups):
                item.tab_current = current is not None and item.pk == current.pk
                item.tab_url = get_script_prefix().rstrip('/') + item.url if item.url.startswith('/') else item.url
                result['content_menu_tabs'].append(item)
    return result
sidebar_menus = navigation
