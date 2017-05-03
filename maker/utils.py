import bleach


ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS + ['p']


def clean(text):
    return bleach.clean(text, tags=ALLOWED_TAGS, strip=True)
