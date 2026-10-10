import json
from django.core.exceptions import ValidationError
SECRET_KEYS = {'password','secret','token','api_key','access_token','refresh_token','client_secret','authorization'}
def validate_options(value):
    if not isinstance(value, dict) or len(json.dumps(value)) > 65536:
        raise ValidationError('설정은 64KB 이하 JSON 객체여야 합니다.')
    def check(node):
        if isinstance(node, dict):
            for key, item in node.items():
                if str(key).lower() in SECRET_KEYS: raise ValidationError('비밀값은 비밀 정보 입력란에만 입력하세요.')
                check(item)
        elif isinstance(node, list):
            for item in node: check(item)
    check(value)
