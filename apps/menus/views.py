import json
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError
from django.http import HttpResponse,JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from apps.organizations.scoping import is_org_admin
from .models import Menu
from .forms import MenuForm
from .permissions import can_access_menu
from .operations import tree_revision,move_menu,export_menus,import_menus,StaleMenuTree,lock_organization,save_menu,delete_menu

def staff(view):
    @wraps(view)
    @login_required
    def wrapped(request,*args,**kwargs):
        if not is_org_admin(request.user): raise PermissionDenied('현재 조직의 관리자만 접근할 수 있습니다.')
        return view(request,*args,**kwargs)
    return wrapped

@staff
def index(request):
    items=list(Menu.objects.select_related('parent_menu').prefetch_related('allowed_groups').order_by('order','name','pk'))
    by_id={item.pk:item for item in items};status=request.GET.get('status','active')
    if status not in ('active','inactive','all'): status='active'
    children={}
    for menu in items:
        children.setdefault(menu.parent_menu_id,[]).append(menu)
        current=menu;seen=set();state=True
        while current:
            if current.pk in seen or current.organization_id!=menu.organization_id: state=False;break
            seen.add(current.pk);state=state and current.is_active
            if current.parent_menu_id is None: break
            current=by_id.get(current.parent_menu_id)
            if current is None: state=False;break
        menu.effective_active=state
        if menu.parent_menu_id is not None and menu.parent_menu_id not in by_id:
            menu._state.fields_cache['parent_menu']=None
    menus=[];visited=set()
    def append_branch(root):
        stack=[(root,0)]
        while stack:
            menu,depth=stack.pop()
            if menu.pk in visited: continue
            visited.add(menu.pk);menu.admin_depth=depth;menu.admin_indent=depth*24;menus.append(menu)
            stack.extend((child,depth+1) for child in reversed(children.get(menu.pk,[])))
    for menu in items:
        if menu.parent_menu_id not in by_id: append_branch(menu)
    for menu in items:
        if menu.pk not in visited: append_branch(menu)
    if status!='all': menus=[menu for menu in menus if menu.effective_active==(status=='active')]
    return render(request,'menus/list.html',{'menus':menus,'menu_revision':tree_revision(items),'status_filter':status,'status':status,'all_menus':items,'tree_revision':tree_revision(items)})

@staff
def edit(request,pk=None):
    if request.method=='POST':
        with transaction.atomic():
            lock_organization(request.user)
            obj=get_object_or_404(Menu.objects.select_for_update(),pk=pk) if pk else None
            form=MenuForm(request.POST,instance=obj)
            if form.is_valid():
                try:
                    with transaction.atomic(): save_menu(form,request.user)
                    messages.success(request,'메뉴를 저장했습니다.');return redirect('menu_list')
                except ValidationError as exc: form.add_error(None,exc)
                except IntegrityError: form.add_error(None,'이미 사용 중인 메뉴 코드입니다.')
    else:
        obj=get_object_or_404(Menu,pk=pk) if pk else None
        form=MenuForm(instance=obj)
    return render(request,'menus/form.html',{'form':form,'menu':obj})

@staff
@require_POST
def delete(request,pk):
    get_object_or_404(Menu,pk=pk)
    try: delete_menu(pk,request.user);messages.success(request,'메뉴를 삭제했습니다.')
    except ValidationError as exc: messages.error(request,' '.join(exc.messages))
    return redirect('menu_list')

@login_required
def detail(request,code):
    menu=get_object_or_404(Menu.objects.prefetch_related('allowed_groups'),code=code)
    if not can_access_menu(request.user,menu): raise PermissionDenied('이 메뉴에 접근할 권한이 없습니다.')
    children=[child for child in menu.children.prefetch_related('allowed_groups').order_by('order','name','pk') if can_access_menu(request.user,child)]
    return render(request,'menus/detail.html',{'menu':menu,'children':children})

@staff
@require_POST
def move(request):
    try:
        if len(request.body)>4096: raise ValidationError('이동 요청이 너무 큽니다.')
        if request.content_type=='application/json':
            data=json.loads(request.body)
        else:
            try: data={'source':int(request.POST.get('source_id') or request.POST.get('source','')),'target':int(request.POST.get('target_id') or request.POST.get('target','')),'position':request.POST.get('position'),'revision':request.POST.get('revision') or request.POST.get('tree_revision')}
            except (TypeError,ValueError): raise ValidationError('이동 메뉴를 선택하세요.')
        if not isinstance(data,dict): raise ValidationError('메뉴 이동 요청 형식이 올바르지 않습니다.')
        move_menu(data.get('source'),data.get('target'),data.get('position'),data.get('revision'),request.user)
    except StaleMenuTree as exc: return JsonResponse({'error':' '.join(exc.messages)},status=409)
    except ValidationError as exc: return JsonResponse({'error':' '.join(exc.messages)},status=400)
    except (ValueError,TypeError): return JsonResponse({'error':'메뉴 이동 요청 형식이 올바르지 않습니다.'},status=400)
    return JsonResponse({'ok':True})

@staff
def export(request):
    try: data=export_menus(request.user)
    except ValidationError as exc: messages.error(request,' '.join(exc.messages));return redirect('menu_list')
    response=HttpResponse(json.dumps(data,ensure_ascii=False,indent=2),content_type='application/json; charset=utf-8')
    response['Content-Disposition']='attachment; filename="manualbook-menus.json"';return response

@staff
@require_POST
def import_file(request):
    upload=request.FILES.get('file')
    try:
        if not upload or upload.size>1024*1024: raise ValidationError('1MB 이하의 메뉴 JSON 파일을 선택하세요.')
        count=import_menus(json.loads(upload.read().decode('utf-8-sig')),request.user)
        messages.success(request,f'{count}개 메뉴를 가져왔습니다. 파일에 없는 기존 메뉴는 유지됩니다.')
    except ValidationError as exc: messages.error(request,'가져오기 실패: '+' '.join(exc.messages))
    except (ValueError,TypeError,UnicodeError): messages.error(request,'가져오기 실패: 올바른 JSON 파일을 선택하세요.')
    except IntegrityError: messages.error(request,'가져오기 실패: 중복된 메뉴 코드나 이름을 확인하세요.')
    return redirect('menu_list')
