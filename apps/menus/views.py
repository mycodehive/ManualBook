from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from apps.core.services import audit
from .models import Menu
from .forms import MenuForm
staff = user_passes_test(lambda u: u.is_staff)
@login_required
@staff
def index(request):
    return render(request,'menus/list.html',{'menus':Menu.objects.select_related('parent_menu').all()})
@login_required
@staff
def edit(request, pk=None):
    obj=get_object_or_404(Menu,pk=pk) if pk else None
    form=MenuForm(request.POST or None,instance=obj)
    if request.method=='POST' and form.is_valid():
        obj=form.save(); audit(request.user,'menu.updated',obj); messages.success(request,'메뉴를 저장했습니다.'); return redirect('menu_list')
    return render(request,'menus/form.html',{'form':form,'menu':obj})
@login_required
@staff
@require_POST
def delete(request, pk):
    obj=get_object_or_404(Menu,pk=pk)
    if obj.children.exists():
        messages.error(request,'하위 메뉴를 먼저 이동하거나 삭제하세요.')
    else:
        audit(request.user,'menu.deleted',obj);obj.delete();messages.success(request,'메뉴를 삭제했습니다.')
    return redirect('menu_list')
