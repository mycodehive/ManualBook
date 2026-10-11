from django.core.exceptions import PermissionDenied
from .models import Menu
from .permissions import can_access_menu
from .registry import matches_path, BASELINE_ROUTES
class MenuAccessMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        if request.path_info in ('/login/', '/logout/', '/accounts/profile/', '/accounts/password/'):
            return self.get_response(request)
        if request.user.is_authenticated:
            menus = list(Menu.objects.prefetch_related('allowed_groups'))
            by_id = {m.pk:m for m in menus}
            matches = [m for m in menus if matches_path(request.path_info, m.url) or matches_path(request.path_info, BASELINE_ROUTES.get(m.code,''))]
            if matches:
                if any(not can_access_menu(request.user, m, by_id) for m in matches):
                    raise PermissionDenied('이 메뉴에 접근할 권한이 없습니다.')
        return self.get_response(request)
