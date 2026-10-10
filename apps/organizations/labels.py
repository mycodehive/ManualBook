"""Human-readable labels within the current organization."""
from .models import Membership, OrganizationGroup
from .scoping import current_organization


def user_label(user):
    if not user:
        return '—'
    org = current_organization()
    member = Membership.all_objects.filter(organization=org, user=user).first() if org else None
    if member:
        return user.get_full_name() or member.display_username
    if user.is_superuser:
        return user.get_full_name() or user.get_username()
    return '—'


def group_label(group):
    if not group:
        return '—'
    organization_group = OrganizationGroup.objects.filter(group=group).first()
    return organization_group.name if organization_group else '—'


def set_group_choices_label(field, org):
    names = dict(OrganizationGroup.all_objects.filter(organization=org).values_list('group_id', 'name'))
    field.label_from_instance = lambda group: names.get(group.pk, '—')
