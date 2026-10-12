class IndexingPolicyMiddleware:
    """Only global public introduction routes opt into indexing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        response = self.get_response(request)
        if path not in ('/intro', '/intro/', '/robots.txt', '/sitemap.xml'):
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
