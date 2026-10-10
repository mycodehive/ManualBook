from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import ManualSpace,ManualNode,ManualRevision,ManualAttachment,ManualPermissionAssignment
from . import services
from .policy import node_allowed

class ManualSecurityTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.writer=User.objects.create_user('writer',password='longpassword!')
        self.reader=User.objects.create_user('reader',password='longpassword!')
        self.manager=User.objects.create_user('manager',password='longpassword!')
        self.stranger=User.objects.create_user('stranger',password='longpassword!')
        self.edit=Group.objects.create(name='Writers'); self.view=Group.objects.create(name='Readers'); self.approve=Group.objects.create(name='Approvers')
        self.writer.groups.add(self.edit);self.reader.groups.add(self.view);self.manager.groups.add(self.approve)
        self.space=ManualSpace.objects.create(name='Operations');self.space.edit_groups.add(self.edit);self.space.view_groups.add(self.view);self.space.approve_groups.add(self.approve)
        self.node=ManualNode.objects.create(space=self.space,title='Guide')
    def publish(self):
        rev=services.save_revision(self.writer,self.node.pk,'Public guide','published content',0)
        self.node.refresh_from_db(); review=services.request_review(self.writer,self.node)
        services.decide(self.manager,review.pk,True,'OK');services.publish(self.manager,self.node)
        self.node.refresh_from_db();return rev
    def test_drafts_do_not_leak_and_stale_writes_conflict(self):
        public=self.publish();services.save_revision(self.writer,self.node.pk,'Secret title','TOP SECRET DRAFT',1)
        self.client.force_login(self.reader)
        response=self.client.get(reverse('manuals:page',args=[self.node.pk])+'?draft=1')
        self.assertContains(response,'published content');self.assertNotContains(response,'TOP SECRET DRAFT');self.assertNotContains(response,'Secret title')
        self.assertNotContains(self.client.get(reverse('manuals:index')+'?q=TOP+SECRET'),'TOP SECRET DRAFT')
        with self.assertRaises(services.Conflict): services.save_revision(self.writer,self.node.pk,'stale','oops',1)
    def test_idor_search_export_and_attachment_denied(self):
        rev=self.publish();attachment=ManualAttachment.objects.create(node=self.node,revision=rev,file=SimpleUploadedFile('secret.txt',b'secret'),name='secret.txt',author=self.writer)
        self.client.force_login(self.stranger)
        for name,args in [('page',[self.node.pk]),('edit',[self.node.pk]),('history',[self.node.pk]),('export_page',[self.node.pk]),('export_space',[self.space.pk]),('download',[attachment.pk])]:
            self.assertEqual(self.client.get(reverse('manuals:'+name,args=args)).status_code,403)
        self.assertNotContains(self.client.get(reverse('manuals:index')),'Public guide')
    def test_exact_approved_revision_required(self):
        services.save_revision(self.writer,self.node.pk,'Guide','v1',0);self.node.refresh_from_db();review=services.request_review(self.writer,self.node)
        with self.assertRaises(PermissionDenied):services.decide(self.writer,review.pk,True,'')
        services.decide(self.manager,review.pk,True,'')
        services.save_revision(self.writer,self.node.pk,'Guide','v2',1)
        with self.assertRaises(ValidationError):services.publish(self.manager,self.node)
    def test_self_approval_blocked(self):
        self.writer.groups.add(self.approve);services.save_revision(self.writer,self.node.pk,'Guide','draft',0);self.node.refresh_from_db();review=services.request_review(self.writer,self.node)
        with self.assertRaises(ValidationError):services.decide(self.writer,review.pk,True,'')
    def test_tree_cycle_and_deny_precedence(self):
        parent=ManualNode.objects.create(space=self.space,title='Parent',kind='folder')
        child=ManualNode.objects.create(space=self.space,title='Child',kind='folder',parent=parent)
        with self.assertRaises(ValidationError):services.move_node(self.writer,parent.pk,child.pk,0)
        ManualPermissionAssignment.objects.create(node=parent,user=self.writer,action='edit',effect='deny')
        ManualPermissionAssignment.objects.create(node=child,user=self.writer,action='edit',effect='allow')
        self.assertFalse(node_allowed(self.writer,child,'edit'))
        with self.assertRaises(PermissionDenied): services.move_node(self.writer,child.pk,None,0)
    def test_revision_immutable_and_xss_sanitized(self):
        rev=services.save_revision(self.writer,self.node.pk,'Guide','<script>alert(1)</script>[bad](javascript:alert(1))',0)
        self.assertNotIn('<script>',rev.html);self.assertNotIn('href="javascript:',rev.html)
        with self.assertRaises(ValidationError):rev.save()
    def test_upload_creates_new_unapproved_revision(self):
        self.publish();self.client.force_login(self.writer)
        self.client.post(reverse('manuals:upload',args=[self.node.pk]),{'file':SimpleUploadedFile('file.txt',b'secret')})
        self.node.refresh_from_db();self.assertNotEqual(self.node.draft_id,self.node.published_id)
        self.assertEqual(self.node.published.attachments.count(),0);self.assertEqual(self.node.draft.attachments.count(),1)
