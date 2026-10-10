import uuid
from django.conf import settings
from django.db import models
from apps.organizations.scoping import ScopedModel
from django.core.exceptions import ValidationError

class ManualSpace(ScopedModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    require_approval = models.BooleanField(default=True)
    allow_self_approval = models.BooleanField(default=False)
    view_groups = models.ManyToManyField('auth.Group', blank=True, related_name='manual_view_spaces')
    edit_groups = models.ManyToManyField('auth.Group', blank=True, related_name='manual_edit_spaces')
    approve_groups = models.ManyToManyField('auth.Group', blank=True, related_name='manual_approve_spaces')
    def __str__(self): return self.name
    def can_view(self,user):
        from .policy import allowed
        return allowed(user,self)

class ManualNode(ScopedModel):
    space = models.ForeignKey(ManualSpace, on_delete=models.CASCADE, related_name='nodes')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=[('folder','폴더'),('page','문서')], default='page')
    slug = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sort_order = models.IntegerField(default=0)
    archived = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=0)
    draft = models.ForeignKey('ManualRevision', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    published = models.ForeignKey('ManualRevision', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    class Meta: ordering = ['sort_order','id']
    def __str__(self): return self.title
    def clean(self):
        super().clean()
        self._validate_revision_links()
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.kind != self.kind and (previous.draft_id or previous.published_id or previous.children.exists()):
                raise ValidationError('문서 버전 또는 하위 노드가 있는 항목의 유형은 변경할 수 없습니다.')
        seen = {self.pk} if self.pk else set()
        parent = self.parent
        while parent:
            if parent.pk in seen: raise ValidationError('자신 또는 하위 노드로 이동할 수 없습니다.')
            if parent.space_id != self.space_id: raise ValidationError('같은 공간의 폴더만 선택하세요.')
            if parent.kind != 'folder': raise ValidationError('문서는 부모가 될 수 없습니다.')
            seen.add(parent.pk); parent = parent.parent

    def _validate_revision_links(self):
        for revision in (self.draft, self.published):
            if revision and revision.node_id != self.pk:
                raise ValidationError('초안·게시 버전은 동일한 문서에 속해야 합니다.')
    def save(self,*args,**kwargs):
        self._validate_revision_links()
        return super().save(*args,**kwargs)

class ManualRevision(ScopedModel):
    node = models.ForeignKey(ManualNode, on_delete=models.CASCADE, related_name='revisions')
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    markdown = models.TextField(blank=True)
    html = models.TextField(blank=True)
    reason = models.CharField(max_length=250, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-number']
        constraints = [models.UniqueConstraint(fields=['node','number'], name='unique_manual_revision')]
    def save(self,*args,**kwargs):
        if self.pk: raise ValidationError('문서 버전은 수정할 수 없습니다.')
        return super().save(*args,**kwargs)

class ApprovalRequest(ScopedModel):
    revision = models.ForeignKey(ManualRevision, on_delete=models.CASCADE, related_name='approvals')
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    status = models.CharField(max_length=12, choices=[('pending','검토 중'),('approved','승인'),('rejected','반려')], default='pending')
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    def save(self,*args,**kwargs):
        if self.pk:
            previous=type(self).objects.get(pk=self.pk)
            if previous.status!='pending': raise ValidationError('처리된 승인 기록은 변경할 수 없습니다.')
            if previous.revision_id!=self.revision_id or previous.requester_id!=self.requester_id: raise ValidationError('검토 대상 버전과 요청자는 변경할 수 없습니다.')
        return super().save(*args,**kwargs)

class ManualAttachment(ScopedModel):
    node = models.ForeignKey(ManualNode, on_delete=models.CASCADE, related_name='attachments')
    revision = models.ForeignKey(ManualRevision, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='manual_private/%Y/%m/')
    name = models.CharField(max_length=200)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    def clean(self):
        super().clean()
        if self.revision_id and self.revision.node_id != self.node_id:
            raise ValidationError('첨부파일 버전과 문서가 일치하지 않습니다.')
    def save(self,*args,**kwargs):
        if self.revision_id and self.revision.node_id != self.node_id:
            raise ValidationError('첨부파일 버전과 문서가 일치하지 않습니다.')
        return super().save(*args,**kwargs)

class ManualFavorite(ScopedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    node = models.ForeignKey(ManualNode, on_delete=models.CASCADE)
    class Meta: constraints = [models.UniqueConstraint(fields=['user','node'],name='unique_manual_favorite')]

class ManualRecentView(ScopedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    node = models.ForeignKey(ManualNode, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)
    class Meta: constraints = [models.UniqueConstraint(fields=['user','node'], name='unique_manual_recent')]

class ManualPermissionAssignment(ScopedModel):
    node = models.ForeignKey(ManualNode,on_delete=models.CASCADE,related_name='permission_assignments')
    group = models.ForeignKey('auth.Group',null=True,blank=True,on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.CASCADE)
    action = models.CharField(max_length=20,choices=[('view','열람'),('edit','편집'),('approve','승인'),('publish','게시'),('manage','권한 관리'),('create','생성'),('move','이동'),('delete','삭제'),('export','내보내기'),('download_attachment','첨부 다운로드')])
    effect = models.CharField(max_length=5,choices=[('allow','허용'),('deny','거부')])
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(group__isnull=False,user__isnull=True)|models.Q(group__isnull=True,user__isnull=False)),name='manual_permission_one_subject')]
