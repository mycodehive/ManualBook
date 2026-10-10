from apps.organizations.models import Organization, Membership, OrganizationGroup
from apps.organizations.scoping import organization_scope
import io
import zipfile
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from .models import ManualSpace, ManualNode, ManualPermissionAssignment
from .exchange import import_documents, decode_document, published_pdf
from .services import save_revision, publish

class ExchangeTests(TestCase):
    def setUp(self):
        self.organization=Organization.objects.create(name='Exchange tests',slug='exchange')
        self.scope=organization_scope(self.organization);self.scope.__enter__()
        self.addCleanup(self.scope.__exit__,None,None,None)
        self.user = User.objects.create_user('author')
        self.group = Group.objects.create(name='exchange-editors')
        membership=Membership.objects.create(user=self.user,role='member')
        wrapper=OrganizationGroup.objects.create(group=self.group,name='exchange-editors')
        membership.groups.add(wrapper)
        self.space = ManualSpace.objects.create(name='Exchange', require_approval=False)
        self.space.edit_groups.add(self.group)
    def archive(self, entries):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, value in entries:
                archive.writestr(name, value)
        return stream.getvalue()
    def test_zip_traversal_and_atomic_validation(self):
        for entries in [[('../escape.md', '# bad')], [('good.md', '# ok'), ('bad.exe', 'bad')]]:
            with self.assertRaises(ValidationError):
                import_documents(self.user, self.space, 'docs.zip', self.archive(entries))
            self.assertFalse(ManualNode.objects.exists())
    def test_zip_nested_import_is_unpublished(self):
        nodes = import_documents(self.user, self.space, 'docs.zip', self.archive([('policy/guide.md', '# 정책')]))
        self.assertEqual(nodes[0].draft.markdown, '# 정책')
        self.assertIsNone(nodes[0].published)
        self.assertEqual(nodes[0].parent.title, 'policy')
    def test_html_import_strips_executable_content(self):
        value = decode_document('safe.html', b'<h1>Guide</h1><script>alert(1)</script><img src="http://internal/">')
        self.assertIn('# Guide', value)
        self.assertNotIn('alert', value)
        self.assertNotIn('http://internal', value)
    def test_pdf_is_permission_checked_and_published_only(self):
        node = ManualNode.objects.create(space=self.space, title='Guide')
        with self.assertRaises(ValidationError):
            published_pdf(self.user, node)
        save_revision(self.user, node.pk, 'Guide', '# Published\n\nContent', 0)
        node.refresh_from_db(); publish(self.user, node); node.refresh_from_db()
        self.assertTrue(published_pdf(self.user, node).startswith(b'%PDF'))
        ManualPermissionAssignment.objects.create(node=node, user=self.user, action='export', effect='deny')
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            published_pdf(self.user, node)
