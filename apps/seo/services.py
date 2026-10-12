from xml.etree.ElementTree import Element, SubElement, tostring
from django.templatetags.static import static
from .models import SEOConfiguration


def get_configuration():
    return SEOConfiguration.objects.filter(pk=1).first() or SEOConfiguration(pk=1)


def absolute_url(request, path, configuration=None):
    configuration = configuration or get_configuration()
    return configuration.site_url.rstrip('/') + path if configuration.site_url else request.build_absolute_uri(path)


def intro_metadata(request):
    configuration = get_configuration()
    return {'title': configuration.title, 'description': configuration.description,
        'keywords': configuration.keywords, 'generator': configuration.generator_content if configuration.generator_enabled else '',
        'canonical': absolute_url(request, '/intro/', configuration), 'og_site_name': configuration.og_site_name,
        'og_image_url': absolute_url(request, configuration.public_image_path, configuration) if configuration.public_image_path else configuration.og_image_url or absolute_url(request, static('intro/images/manualbook_hero.png'), configuration),
        'og_image_width': configuration.og_image_width, 'og_image_height': configuration.og_image_height,
        'twitter_card': configuration.twitter_card, 'twitter_handle': configuration.twitter_handle}


def sitemap_xml(request):
    root = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    entry = SubElement(root, 'url')
    SubElement(entry, 'loc').text = absolute_url(request, '/intro/')
    return tostring(root, encoding='utf-8', xml_declaration=True)


def robots_text(request):
    configuration = get_configuration()
    lines = ['User-agent: *', 'Disallow: /', 'Allow: /intro$', 'Allow: /intro/$', 'Allow: /static/', 'Allow: /seo-images/', 'Allow: /robots.txt$', 'Allow: /sitemap.xml$']
    if configuration.sitemap_enabled:
        lines.append('Sitemap: ' + absolute_url(request, '/sitemap.xml', configuration))
    return '\n'.join(lines) + '\n'
