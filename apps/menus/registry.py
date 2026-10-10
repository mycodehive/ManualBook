from dataclasses import dataclass
from urllib.parse import urlsplit
@dataclass(frozen=True)
class Feature:
    code: str
    label: str
    connection_kind: str = ''
FEATURES = {'manuals.ai': Feature('manuals.ai', '매뉴얼 AI 보조', 'llm'), 'manuals.notion': Feature('manuals.notion', 'Notion 가져오기', 'notion')}
def matches_path(path, url):
    if not url or not url.startswith('/') or url.startswith('//'): return False
    prefix = urlsplit(url).path.rstrip('/')
    return path.rstrip('/') == prefix or bool(prefix and path.startswith(prefix + '/'))

BASELINE_ROUTES = {'dashboard':'/home/', 'manuals.spaces':'/manuals/', 'settings.organization':'/settings/', 'settings.menus':'/menus/', 'settings.users':'/accounts/', 'settings.integrations':'/settings/integrations/', 'settings.audit':'/settings/audit/'}
