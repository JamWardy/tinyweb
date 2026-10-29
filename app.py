"""The App: the framework's side of WSGI.

A WSGI app is any callable app(environ, start_response): the server calls
it once per request, and it calls start_response with the status and
headers, then returns the body as bytes. An App is one, so any WSGI server
can run it, as gunicorn runs a Flask app.
"""

from tinyweb.request import Request
from tinyweb.response import Response


class App:
    def __init__(self):
        # (parts, methods, view) for each route. A list, since /items/5
        # isn't a key: each is tried in turn, and the first match wins.
        self.routes = []

    def route(self, path, methods=("GET",)):
        """A decorator that makes the function below it answer path.

        The function is given the Request, then each value taken from the
        path by a part in <...>, by name: <int:id> takes a whole number,
        and <name> any text. It returns a string for a page, or a Response.

            @app.route("/items/<int:id>")
            def item(request, id):
                return f"<h1>Item {id}</h1>"

        It answers only the methods given, GET by default, so two routes
        can share a path: GET /basket to show it, POST /basket to add.
        """
        parts = parse_path(path)
        methods = {method.upper() for method in methods}
        # HEAD is GET without the body, which the server drops, as with Flask.
        if "GET" in methods:
            methods.add("HEAD")

        def register(view):
            self.routes.append((parts, methods, view))
            # Unchanged, so the name still means the function.
            return view
        return register

    def __call__(self, environ, start_response):
        """Answer one request: the WSGI entry point the server calls."""
        request = Request(environ)
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
        parts = path.split("/")
        for pattern, methods, view in self.routes:
            if method not in methods:
                continue
            values = match_parts(pattern, parts)
            if values is not None:
                return view, values
        return None, None

    def allowed_methods(self, path):
        """Every method that some route for path takes.

        Empty if no route has this path, for a 404; otherwise a 405's Allow.
        """
        parts = path.split("/")
        allowed = set()
        for pattern, methods, _ in self.routes:
            if match_parts(pattern, parts) is not None:
                allowed |= methods
        return allowed


def to_int(text):
    """The <int:...> placeholder: a whole number, such as 5."""
    # isdigit alone also takes other scripts' digits, such as "٥".
    if text.isascii() and text.isdigit():
        return int(text)
    return None


def to_str(text):
    """The <...> placeholder: any text, but not none at all."""
    return text if text else None


# Each converter returns None when the text doesn't fit, so no match.
CONVERTERS = {"int": to_int, "str": to_str}


def parse_path(path):
    """Split a route's path into parts, for match_parts.

    "/items/<int:id>" becomes ["", "items", (to_int, "id")]: plain parts
    stay as text, and each placeholder becomes its converter and name.
    """
    parts = []
    for part in path.split("/"):
        if part.startswith("<") and part.endswith(">"):
            kind, colon, name = part[1:-1].partition(":")
            if not colon:
                kind, name = "str", kind
            if kind not in CONVERTERS:
                # At startup, so a typo such as <itn:id> isn't a quiet 404.
                raise ValueError(f"unknown placeholder {kind!r} in {path!r}")
            parts.append((CONVERTERS[kind], name))
        else:
            parts.append(part)
    return parts


def match_parts(pattern, parts):
    """Compare a route's parts with a request path's, one by one.

    Returns the values the placeholders took, by name, such as {"id": 5},
    or None if the path doesn't match.
    """
    if len(pattern) != len(parts):
        return None
    values = {}
    for want, got in zip(pattern, parts):
        if isinstance(want, str):
            if want != got:
                return None
        else:
            convert, name = want
            value = convert(got)
            if value is None:
                return None
            values[name] = value
    return values
