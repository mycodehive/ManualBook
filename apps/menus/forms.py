from django import forms
from apps.organizations.forms import ScopedModelForm
from .models import Menu
class MenuForm(ScopedModelForm):
    class Meta:
        model = Menu
        fields = ['name','code','url','parent_menu','order','is_active','children_as_tabs','allowed_groups','workspace_dir_name','description']
        widgets = {'allowed_groups': forms.CheckboxSelectMultiple,'url':forms.TextInput(attrs={'placeholder':'/manuals/ 또는 https://example.com','spellcheck':'false'}),'description':forms.Textarea(attrs={'rows':4})}
        labels={'name':'메뉴 이름','code':'메뉴 코드','url':'이동 URL (내부 경로 / 외부 링크)','parent_menu':'상위 메뉴','order':'표시 순서','is_active':'활성','workspace_dir_name':'작업 폴더 이름','description':'설명'}
        help_texts={'url':'내부 메뉴는 /로 시작하는 경로, 외부 메뉴는 http:// 또는 https:// URL을 입력하세요. 외부 링크는 새 탭에서 열립니다.','workspace_dir_name':'표시 및 구성용 이름입니다. 서버의 폴더나 파일을 자동 생성하지 않습니다.'}
