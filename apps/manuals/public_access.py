"""Exact, read-only publication entry points; never grants organization membership."""
import re
from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponseNotAllowed
from apps.organizations.scoping import organization_scope
from .models import ManualSpace, ManualNode, ManualAttachment
from .policy import allowed, node_allowed, node_visible, revision_in_scope

PUBLIC_READ_ROUTES = (
    (re.compile(r'^/manuals/spaces/([1-9][0-9]*)/$'), 'space'),
    (re.compile(r'^/manuals/nodes/([1-9][0-9]*)/$'), 'node'),
    (re.compile(r'^/manuals/attachments/([1-9][0-9]*)/$'), 'attachment'),
)


def public_reader_for(request, organization, path):
    request.manual_public_reader = False
    if request.method not in ('GET', 'HEAD'):
        return False
    for pattern, kind in PUBLIC_READ_ROUTES:
        match = pattern.fullmatch(path)
        if not match:
            continue
        pk = int(match.group(1))
        node = None
        if kind == 'space':
            space = ManualSpace.all_objects.filter(pk=pk, organization=organization).first()
        elif kind == 'node':
            node = ManualNode.all_objects.select_related('space').filter(pk=pk, organization=organization).first()
            space = node.space if node else None
        else:
            attachment = ManualAttachment.all_objects.select_related('node__space').filter(pk=pk, organization=organization).first()
            node = attachment.node if attachment else None
            space = node.space if node else None
        if not space or space.organization_id != organization.pk or (node and node.organization_id != organization.pk):
            raise Http404
        if space.visibility != 'public':
            return False
        with organization_scope(organization):
            editor = allowed(request.user, space, 'edit')
            if node:
                editor = editor and node_allowed(request.user, node, 'edit')
        if not space.active:
            if editor:
                return False
            raise Http404
        request.manual_public_reader = not editor
        return request.manual_public_reader
    return False


def read_view(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method not in ('GET', 'HEAD'):
            return HttpResponseNotAllowed(['GET', 'HEAD'])
        if not getattr(request, 'manual_public_reader', False) and not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        return view(request, *args, **kwargs)
    return wrapped


def public_space_visible(space):
    from apps.organizations.scoping import current_organization
    org = current_organization()
    return bool(org and org.active and space.organization_id == org.pk and space.active and space.visibility == 'public')


def public_node_visible(node):
    return bool(public_space_visible(node.space) and node_visible(node) and
        (node.kind == 'folder' or (node.published_id and revision_in_scope(node.published, node))))


def public_nodes(space):
    """Include published pages and only the folders needed for their ancestry."""
    nodes = list(space.nodes.select_related('published', 'draft', 'parent'))
    pages = [node for node in nodes if node.kind == 'page' and public_node_visible(node)]
    needed = {node.pk for node in pages}
    for node in pages:
        parent = node.parent
        while parent:
            needed.add(parent.pk)
            parent = parent.parent
    return [node for node in nodes if node.pk in needed]


def published_attachment(attachment):
    """Resolve stable image links to current published metadata, never draft metadata."""
    node = attachment.node
    if node.kind != 'page' or not public_node_visible(node) or not revision_in_scope(attachment.revision, node):
        return None
    return node.published.attachments.filter(node=node, file=attachment.file.name).first()
