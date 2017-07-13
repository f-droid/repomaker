import bleach
from bleach.sanitizer import Cleaner
from html5lib.filters.base import Filter


class EmptyLinkFilter(Filter):
    def __iter__(self):
        remove_end_tag = False
        for token in Filter.__iter__(self):
            # only check anchor tags
            if 'name' in token and token['name'] == 'a' and token['type'] in ['StartTag', 'EndTag']:
                if token['type'] == 'StartTag' and token['data'] == {}:
                    remove_end_tag = True
                    continue
                elif token['type'] == 'EndTag' and remove_end_tag:
                    remove_end_tag = False
                    continue
            yield token


def clean(text):
    cleaner = Cleaner(
        tags=bleach.sanitizer.ALLOWED_TAGS + ['p', 'br'],
        attributes=bleach.sanitizer.ALLOWED_ATTRIBUTES,
        styles=bleach.sanitizer.ALLOWED_STYLES,
        protocols=bleach.sanitizer.ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
        filters=[EmptyLinkFilter],
    )
    return cleaner.clean(text)


def to_universal_language_code(language):
    """
    Turns a lower-cased Django language name (en-us) into a universal language code
    with the region part upper-cased (en-US).
    """
    p = language.find('-')
    if p >= 0:
        if len(language[p + 1:]) > 2:
            return language[:p].lower() + '-' + language[p + 1].upper() + language[p + 2:].lower()
        return language[:p].lower() + '-' + language[p + 1:].upper()
    else:
        return language
