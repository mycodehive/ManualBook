from django import template
from apps.organizations.labels import user_label, group_label

register = template.Library()
register.filter('organization_user', user_label)
register.filter('organization_group', group_label)
