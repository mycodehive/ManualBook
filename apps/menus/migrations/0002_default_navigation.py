from django.db import migrations


def seed(apps, schema_editor):
    Menu = apps.get_model('menus', 'Menu')
    nodes = [('dashboard','대시보드','/home/',None,0),('manuals','매뉴얼','',None,10),('manuals.spaces','스페이스','/manuals/spaces/','manuals',0),('settings','환경설정','',None,90),('settings.organization','기본정보','/settings/','settings',0),('settings.menus','메뉴 관리','/menus/','settings',10),('settings.users','사용자 · 그룹','/accounts/','settings',20),('settings.integrations','API 연결','/settings/integrations/','settings',30),('settings.audit','감사 로그','/settings/audit/','settings',40)]
    by_code={}
    for code,name,url,parent,order in nodes:
        obj,_=Menu.objects.get_or_create(code=code, defaults={'name':name,'url':url,'parent_menu':by_code.get(parent),'order':order})
        by_code[code]=obj

class Migration(migrations.Migration):
    dependencies=[('menus','0001_initial')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]
