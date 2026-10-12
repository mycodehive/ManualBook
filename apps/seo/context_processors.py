from .services import intro_metadata


def seo(request):
    if getattr(request, 'organization', None) is None and request.path_info in ('/intro', '/intro/'):
        return {'seo_metadata': intro_metadata(request)}
    return {'seo_metadata': {}}
