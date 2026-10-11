"""Domain plugins may register narrowly scoped, read-only public entry checks."""
_checkers = []


def register_public_reader(checker):
    if checker not in _checkers:
        _checkers.append(checker)


def is_public_read(request, organization, path):
    request.public_read_allowed = False
    if request.method not in ('GET', 'HEAD'):
        return False
    for checker in _checkers:
        if checker(request, organization, path):
            request.public_read_allowed = True
            return True
    return False
