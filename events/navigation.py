def sanitize_next_url(next_url):
    next_url = next_url or '/'
    if next_url.startswith('/login'):
        return '/'
    return next_url
