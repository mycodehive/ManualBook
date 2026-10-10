"""DB-backed login limits shared by all workers; keys contain no raw identities."""
import hashlib
import hmac
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import LoginThrottle

WINDOW=timedelta(minutes=15)

def keys(request):
    org=getattr(request,'organization',None)
    scope=str(org.pk) if org else 'global'
    username=str(request.POST.get('username','')).strip().casefold()[:150]
    # Use the connection address; forwarding headers are not trusted here.
    ip=request.META.get('REMOTE_ADDR','unknown')
    result=[]
    for kind,value,threshold in [('account',username,5),('ip',ip,20)]:
        digest=hmac.new(settings.SECRET_KEY.encode(),f'{scope}|{kind}|{value}'.encode(),hashlib.sha256).hexdigest()
        result.append((digest,threshold))
    return result

def retry_after(request):
    now=timezone.now()
    until=LoginThrottle.objects.filter(key__in=[k for k,_ in keys(request)],locked_until__gt=now).order_by('-locked_until').values_list('locked_until',flat=True).first()
    return max(1,int((until-now).total_seconds())) if until else 0

@transaction.atomic
def failure(request):
    now=timezone.now()
    for key,limit in keys(request):
        obj,_=LoginThrottle.objects.select_for_update().get_or_create(key=key,defaults={'window_started':now})
        if obj.window_started+WINDOW<=now:
            obj.window_started=now;obj.failures=0;obj.locked_until=None
        obj.failures+=1
        if obj.failures>=limit: obj.locked_until=now+WINDOW
        obj.save()

def success(request):
    # Do not clear the IP counter: a valid account must not bypass IP throttling.
    LoginThrottle.objects.filter(key=keys(request)[0][0]).delete()
