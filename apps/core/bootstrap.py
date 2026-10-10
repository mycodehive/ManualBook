from django.contrib.auth.models import Group
from apps.menus.models import Menu
from .models import SiteConfiguration

def seed_platform():
    SiteConfiguration.objects.get_or_create(pk=1)
    for name in ['매뉴얼 열람자','매뉴얼 편집자','매뉴얼 승인자','플랫폼 관리자']:
        Group.objects.get_or_create(name=name)
    nodes=[('dashboard','대시보드','/home/',None,0),('manuals','매뉴얼','',None,10),('manuals.spaces','스페이스','/manuals/spaces/','manuals',0),('settings','환경설정','',None,90),('settings.organization','기본정보','/settings/','settings',0),('settings.menus','메뉴 관리','/menus/','settings',10),('settings.users','사용자 · 그룹','/accounts/','settings',20),('settings.integrations','API 연결','/settings/integrations/','settings',30),('settings.audit','감사 로그','/settings/audit/','settings',40)]
    by_code={}
    for code,name,url,parent,order in nodes:
        obj,_=Menu.objects.get_or_create(code=code,defaults={'name':name,'url':url,'parent_menu':by_code.get(parent),'order':order})
        by_code[code]=obj
