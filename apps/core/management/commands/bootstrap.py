from django.core.management.base import BaseCommand
from apps.core.bootstrap import seed_platform
class Command(BaseCommand):
    help='Create default organization, groups, and menus without overwriting existing administrator settings.'
    def handle(self,*args,**options):
        seed_platform()
        self.stdout.write(self.style.SUCCESS('ManualBook 기본 메뉴와 그룹을 확인했습니다. 관리자 계정은 createsuperuser로 생성하세요.'))
