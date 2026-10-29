"""The App: the framework's side of WSGI.

A WSGI app is any callable app(environ, start_response): the server calls
it once per request, and it calls start_response with the status and
headers, then returns the body as bytes. An App is one, so any WSGI server
can run it, as gunicorn runs a Flask app.
"""

import re
from dataclasses import dataclass
from typing import Callable

from tinyweb.request import Request
from tinyweb.response import Response

# Each kind of placeholder: the text it matches, and the function that turns
# that text into the value the view is given. A new kind is one more line.
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
        """The values the placeholders take from path, by name, such as
        {"id": 5}, or None if path isn't this route's.
        """
        found = self.pattern.fullmatch(path)
        if found is None:
            return None
        return {name: convert(found[name])
                for name, convert in self.converters.items()}


class App:
    def __init__(self):
        # A list, since /items/5 isn't a key: each Route is tried in turn,
        # and the first match wins.
        self.routes = []

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
        # tinyhttp sets its own, but gunicorn passes ours on.
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

        plain = {"Content-Type": "text/plain; charset=utf-8"}
        allowed = self.allowed_methods(request.path)
        if allowed:
            # Right path, wrong method. Allow says which would work.
            return Response("method not allowed\n", 405,
                            {**plain, "Allow": ", ".join(sorted(allowed))})
        return Response("not found\n", 404, plain)

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


def compile_path(path):
    """Turn a route's path into a regular expression, once, when it's added.

    "/items/<int:id>" becomes /items/(?P<id>[0-9]+), and {"id": int} to turn
    what it matches into the value. The text between placeholders is
    escaped, so a "." in "/files/<name>.txt" means a dot, not any character.
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
        regex += re.escape(path[end:placeholder.start()])
        regex += f"(?P<{name}>{text})"
        end = placeholder.end()
    regex += re.escape(path[end:])
    return re.compile(regex), converters
