import re
from collections import Counter
from django.conf import settings
from django.db import migrations


def identity_mapping(users, memberships):
    raw = {pk: username for pk, username in users}
    normalized = [username.strip().casefold() for username in raw.values()]
    collisions = [name for name, count in Counter(normalized).items() if count > 1]
    if collisions:
        raise RuntimeError('대소문자를 구분하지 않는 로그인 아이디 충돌을 먼저 해결하세요: ' + ', '.join(sorted(collisions)))
    chosen = {}
    for pk, username in raw.items():
        match = re.fullmatch(r'org([0-9]+)__(.+)', username)
        chosen[pk] = match.group(2) if match and (pk, int(match.group(1))) in memberships else username
    while True:
        counts = Counter(name.strip().casefold() for name in chosen.values())
        conflicting = {name for name, count in counts.items() if count > 1}
        if not conflicting:
            return chosen
        changed = False
        for pk, name in list(chosen.items()):
            if name.strip().casefold() in conflicting and name != raw[pk]:
                chosen[pk] = raw[pk]
                changed = True
        if not changed:
            raise RuntimeError('로그인 아이디 충돌을 먼저 해결하세요: ' + ', '.join(sorted(conflicting)))


def backfill(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    Membership = apps.get_model('organizations', 'Membership')
    Identity = apps.get_model('accounts', 'PublicIdentity')
    Policy = apps.get_model('accounts', 'IdentityPolicy')
    alias = schema_editor.connection.alias
    users = list(User.objects.using(alias).values_list('pk', 'username'))
    memberships = set(Membership.objects.using(alias).values_list('user_id', 'organization_id'))
    mapping = identity_mapping(users, memberships)
    Identity.objects.using(alias).bulk_create([
        Identity(user_id=pk, public_username=public, normalized_username=public.strip().casefold())
        for pk, public in mapping.items()
    ])
    Policy.objects.using(alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial'), ('organizations', '0003_login_throttle')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
