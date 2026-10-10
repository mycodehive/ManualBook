from django.core.management.base import BaseCommand
from apps.accounts.models import PublicIdentity
from django.db.models import Prefetch
from apps.organizations.models import Membership


class Command(BaseCommand):
    help = '기존 계정의 전역 로그인 아이디와 소속 조직을 확인합니다. 계정은 변경하지 않습니다.'

    def handle(self, *args, **options):
        self.stdout.write('사용자 번호\t로그인 아이디\t조직')
        identities = PublicIdentity.objects.select_related('user').prefetch_related(Prefetch('user__organization_memberships', queryset=Membership.all_objects.select_related('organization'))).order_by('user_id')
        for identity in identities:
            slugs = ','.join(sorted(member.organization.slug for member in identity.user.organization_memberships.all()))
            self.stdout.write(f'{identity.user_id}\t{identity.public_username}\t{slugs or "—"}')
