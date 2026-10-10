from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from .models import ManualSpace
from .policy import require
from .views import get_node
from .exchange import import_documents, published_pdf, MAX_UPLOAD

@login_required
@require_POST
def import_files(request, pk):
    space = get_object_or_404(ManualSpace, pk=pk)
    require(request.user, space, 'edit')
    upload = request.FILES.get('file')
    try:
        if not upload or upload.size > MAX_UPLOAD:
            raise ValidationError('10MB 이하의 문서를 선택하세요.')
        nodes = import_documents(request.user, space, upload.name, upload.read())
        messages.success(request, f'{len(nodes)}개 문서를 초안으로 가져왔습니다.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    return redirect('manuals:space', pk=pk)

@login_required
def export_pdf(request, pk):
    node = get_node(request, pk, 'export')
    if not node.published_id:
        raise Http404
    response = HttpResponse(published_pdf(request.user, node), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="manual-{node.pk}.pdf"'
    return response
