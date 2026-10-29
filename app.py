"""The App: the framework's side of WSGI.

A WSGI app is any callable app(environ, start_response): the server calls
it once per request, and it calls start_response with the status and
headers, then returns the body as bytes. An App is one, so any WSGI server
can run it, as gunicorn runs a Flask app.
"""

import hashlib
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from datetime import timezone
from email.utils import formatdate, parsedate_to_datetime
from typing import Callable

from tinyweb.request import Request
from tinyweb.response import Response

# Each placeholder kind: the text it matches, and what turns it into a value.
CONVERTERS = {
    "string": (r"[^/]+", str),      # Any text but a slash, and not none
    "int": (r"[0-9]+", int),        # A whole number; [0-9], so not "٥"
    "path": (r".+", str),           # Like string, but slashes too
}

# A placeholder in a route's path: <name>, or <kind:name> such as <int:id>.
PLACEHOLDER = re.compile(r"<(?:([A-Za-z_]\w*):)?([A-Za-z_]\w*)>")


@dataclass
class Route:
    pattern: re.Pattern     # "/items/<int:id>" as /items/(?P<id>[0-9]+)
    converters: dict        # Each placeholder's name to its function: {"id": int}
    methods: set            # {"GET", "HEAD"}
    view: Callable          # The function that answers it

    def match(self, path):
        """The values from path by name, such as {"id": 5}, or None."""
        found = self.pattern.fullmatch(path)
        if found is None:
            return None
        return {name: convert(found[name])
                for name, convert in self.converters.items()}


class App:
    def __init__(self, import_name, static_folder="static"):
        """Pass __name__ as import_name, as with Flask.

        static_folder is next to that module's file, served at /static/.
        None turns it off.
        """
        # A list, since /items/5 isn't a key: each Route is tried in turn,
        # and the first match wins.
        self.routes = []

        # The folder of the file that made the App.
        root = os.path.dirname(os.path.abspath(sys.modules[import_name].__file__))
        if static_folder is None:
            self.static_folder = None
        else:
            # Real, to compare with the real paths in send_static.
            self.static_folder = os.path.realpath(os.path.join(root, static_folder))
            # An ordinary route, so 405 and HEAD work as for any other.
            self.route("/static/<path:filename>")(self.send_static)

    def route(self, path, methods=("GET",)):
        """A decorator that makes the function below it answer path.

        The function is given the Request, then each value taken from the
        path by a placeholder in <...>, by name: <int:id> takes a whole
        number, <path:name> any text with slashes, and <name> any text
        without. It returns a string for a page, or a Response.

            @app.route("/items/<int:id>")
            def item(request, id):
                return f"<h1>Item {id}</h1>"

        It answers only the methods given, GET by default, so two routes
        can share a path: GET /basket to show it, POST /basket to add.
        """
        pattern, converters = compile_path(path)
        methods = {method.upper() for method in methods}
        # HEAD is GET without the body, which the server drops, as with Flask.
        if "GET" in methods:
            methods.add("HEAD")

        def register(view):
            self.routes.append(Route(pattern, converters, methods, view))
            # Unchanged, so the name still means the function.
            return view
        return register

    def __call__(self, environ, start_response):
        """Answer one request: the WSGI entry point the server calls."""
        request = Request.from_environ(environ)
        response = self.respond(request)

        headers = list(response.headers.items())
        # tinyhttp sets its own, but gunicorn passes ours on. A 304 has no
        # body, and 0 would say the file is empty.
        if response.status != 304:
            headers.append(("Content-Length", str(len(response.body))))
        start_response(f"{response.status} {response.reason}", headers)
        return [response.body]

    def respond(self, request):
        """Run the view for request, and return its Response."""
        view, values = self.match(request.path, request.method)
        if view is not None:
            # {"id": 5} calls view(request, id=5).
            result = view(request, **values)
            if isinstance(result, str):
                return Response(result)
            return result

        allowed = self.allowed_methods(request.path)
        if allowed:
            # Right path, wrong method. Allow says which would work.
            return Response("method not allowed\n", 405,
                            {**PLAIN, "Allow": ", ".join(sorted(allowed))})
        return not_found()

    def send_static(self, request, filename):
        """The view for /static/<path:filename>: a file from static_folder."""
        # filename is from the URL, so it can be ../app.py or /etc/passwd.
        # realpath follows .. and symlinks to where the file really is.
        path = os.path.realpath(os.path.join(self.static_folder, filename))
        if os.path.commonpath([path, self.static_folder]) != self.static_folder:
            return not_found()
        # Missing, or a folder.
        if not os.path.isfile(path):
            return not_found()

        # Which version of the file this is, so the browser can ask if
        # it's changed. From stat alone, so a 304 never reads the file.
        stat = os.stat(path)
        name = hashlib.sha1(os.fsencode(path)).hexdigest()[:8]
        headers = {
            "ETag": f'"{stat.st_mtime_ns:x}-{stat.st_size:x}-{name}"',
            "Last-Modified": formatdate(stat.st_mtime, usegmt=True),
            # Keep a copy, but ask every time.
            "Cache-Control": "no-cache",
        }
        if not modified(request, headers["ETag"], int(stat.st_mtime)):
            return Response(b"", 304, headers)

        with open(path, "rb") as file:
            body = file.read()
        # From the extension; unknown ones are sent as plain bytes.
        content_type, _ = mimetypes.guess_type(path)
        headers["Content-Type"] = content_type or "application/octet-stream"
        return Response(body, 200, headers)

    def match(self, path, method):
        """Find the route that answers method on path.

        Returns (view, values): the route's function, and the values taken
        from the path, by name. Returns (None, None) if no route matches.
        """
        for route in self.routes:
            if method not in route.methods:
                continue
            values = route.match(path)
            if values is not None:
                return route.view, values
        return None, None

    def allowed_methods(self, path):
        """Every method that some route for path takes.

        Empty if no route has this path, for a 404; otherwise a 405's Allow.
        """
        allowed = set()
        for route in self.routes:
            if route.match(path) is not None:
                allowed |= route.methods
        return allowed


PLAIN = {"Content-Type": "text/plain; charset=utf-8"}


def not_found():
    """404, for an unknown path or a missing static file."""
    return Response("not found\n", 404, PLAIN)


def modified(request, etag, mtime):
    """Whether the browser's copy is out of date, so it needs a 200.

    If-None-Match comes first, as RFC 9110 says; If-Modified-Since only
    counts without it.
    """
    if "If-None-Match" in request.headers:
        # One tag only; see Known gaps in TODO.md.
        return request.headers["If-None-Match"] != etag
    if "If-Modified-Since" in request.headers:
        try:
            since = parsedate_to_datetime(request.headers["If-Modified-Since"])
        except (TypeError, ValueError):
            # The RFC says to ignore a date that can't be read.
            return True
        # A date without a zone is GMT in HTTP.
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        # Dates are to the second.
        return mtime > since.timestamp()
    return True


def compile_path(path):
    """Turn a route's path into a regex and its converters.

    "/items/<int:id>" becomes /items/(?P<id>[0-9]+) and {"id": int}.
    """
    regex = ""
    converters = {}
    end = 0
    for placeholder in PLACEHOLDER.finditer(path):
        kind, name = placeholder.groups()
        kind = kind or "string"
        # At startup, so a typo such as <itn:id> isn't a quiet 404.
        if kind not in CONVERTERS:
            raise ValueError(f"unknown placeholder {kind!r} in {path!r}")
        if name in converters:
            raise ValueError(f"placeholder {name!r} twice in {path!r}")
        text, converters[name] = CONVERTERS[kind]
        # Escaped, so the "." in "<name>.txt" is only a dot.
        regex += re.escape(path[end:placeholder.start()])
        regex += f"(?P<{name}>{text})"
        end = placeholder.end()
    regex += re.escape(path[end:])
    return re.compile(regex), converters
