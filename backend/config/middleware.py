"""Validate incoming hosts and keep availability out of shared caches."""

import re


class HostValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.get_host()
        return self.get_response(request)


class PrivateApiMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "private, no-store"
        return response


def frontend_headers(headers, path, url):
    # The entry point must reference the assets from the current build.
    if path.endswith(".html"):
        headers["Cache-Control"] = "no-store"


def immutable_frontend_asset(path, url):
    return bool(re.search(r"/assets/[^/]+-[A-Za-z0-9_-]{8,}\.[^/]+$", url))
