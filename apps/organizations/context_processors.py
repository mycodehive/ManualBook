from .scoping import current_organization,is_org_admin
from .models import Membership,Organization
def organization_context(request):
    org=current_organization()
    user=request.user
    choices=Organization.objects.filter(active=True) if user.is_authenticated and user.is_superuser else []
    if user.is_authenticated and not user.is_superuser:
        choices=[m.organization for m in Membership.all_objects.filter(user=user,active=True,organization__active=True).select_related('organization')]
    member=getattr(request,'membership',None)
    return {'display_username':member.display_username if member else user.get_username() if user.is_authenticated else '', 'current_organization':org,'organization_choices':choices,'organization_admin':is_org_admin(user,org) if org else False}
