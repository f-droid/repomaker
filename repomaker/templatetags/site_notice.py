from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
# noinspection PyUnusedLocal
def notice():
    """
    Returns a site notice if SITE_NOTICE is defined in the settings.
    """
    if hasattr(settings, 'SITE_NOTICE'):
        return settings.SITE_NOTICE
    return None
