import uuid
from django.conf import settings
from django.db import models,transaction
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from .scoping import ScopedModel

class Organization(models.Model):
    name=models.CharField('조직명',max_length=120)
    slug=models.SlugField('주소 식별자',max_length=80,unique=True)
    active=models.BooleanField('활성',default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['name']
    def __str__(self): return self.name
    def get_absolute_url(self): return '/o/'+self.slug+'/home/'
    def save(self,*args,**kwargs):
        if self.pk:
            old=type(self).objects.filter(pk=self.pk).values_list('slug',flat=True).first()
            if old and old!=self.slug: raise ValidationError('조직 주소 식별자는 변경할 수 없습니다.')
        self.full_clean()
        return super().save(*args,**kwargs)

class Department(ScopedModel):
    name=models.CharField('부서명',max_length=120)
    parent=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT,related_name='children')
    description=models.TextField('설명',blank=True)
    active=models.BooleanField('활성',default=True)
    class Meta:
        ordering=['name']
        constraints=[models.UniqueConstraint(fields=['organization','name'],name='organization_department_name')]
    def clean(self):
        super().clean(); seen={self.pk} if self.pk else set(); node=self.parent
        while node:
            if node.pk in seen: raise ValidationError({'parent':'부서 계층에 순환 참조가 있습니다.'})
            seen.add(node.pk); node=node.parent
    def __str__(self): return self.name

class OrganizationGroup(ScopedModel):
    name=models.CharField('그룹명',max_length=120)
    group=models.OneToOneField(Group,on_delete=models.PROTECT,related_name='organization_group')
    class Meta:
        ordering=['name']
        constraints=[models.UniqueConstraint(fields=['organization','name'],name='organization_group_name')]
    def save(self,*args,**kwargs):
        with transaction.atomic():
            self._validate_scope()
            if not self.group_id: self.group=Group.objects.create(name='org:'+str(self.organization_id)+':'+uuid.uuid4().hex)
            return super().save(*args,**kwargs)
    def __str__(self): return self.name

class Membership(ScopedModel):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='organization_memberships')
    role=models.CharField('역할',max_length=10,choices=[('admin','조직 관리자'),('member','구성원')],default='member')
    active=models.BooleanField('활성',default=True)
    department=models.ForeignKey(Department,null=True,blank=True,on_delete=models.SET_NULL,related_name='members')
    groups=models.ManyToManyField(OrganizationGroup,blank=True,related_name='memberships')
    joined_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['user__username']
        constraints=[models.UniqueConstraint(fields=['organization','user'],name='organization_membership_user')]
    def __str__(self): return str(self.user)
    @property
    def display_username(self):
        prefix='org'+str(self.organization_id)+'__'
        return self.user.username[len(prefix):] if self.user.username.startswith(prefix) else self.user.username

class LoginThrottle(models.Model):
    key=models.CharField(max_length=64,primary_key=True)
    failures=models.PositiveIntegerField(default=0)
    window_started=models.DateTimeField()
    locked_until=models.DateTimeField(null=True,blank=True)
