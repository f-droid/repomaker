from django.conf import settings


# noinspection PyUnusedLocal
def site_notice(request):  # pylint: disable=unused-argument
    """
    Returns a site_notice context variable if SITE_NOTICE is defined in the settings.
    """
    if hasattr(settings, 'SITE_NOTICE'):
        return {'site_notice': settings.SITE_NOTICE}
    return {'site_notice': None}
