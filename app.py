"""The App: the framework's side of WSGI.

A WSGI app is any callable app(environ, start_response). The server calls
it once per request with environ, a dict describing the request. The app
calls start_response with the status and headers, then returns the body
as an iterable of bytes. An App is one of these, so a server runs it
without knowing it's made with tinyweb, as gunicorn runs a Flask app.
"""


class App:
    def __init__(self):
        # Each route the app answers, in the order they were added: its
        # path split into parts by parse_path, the methods it takes, and
        # the function that answers it. A list, not a dict, since /items/5
        # isn't a key: each route is tried in turn, and the first that
        # matches wins.
        self.routes = []

    def route(self, path, methods=("GET",)):
        """A decorator that makes the function below it answer path.

        A part of the path in <...> takes a value from the request's path
        and passes it to the function by name: <int:id> takes a whole
        number, and <name> any text.

            @app.route("/items/<int:id>")
            def item(id):
                return f"<h1>Item {id}</h1>"

        It answers only the methods given, GET by default. Two routes can
        share a path with different methods, so GET /basket shows the
        basket and POST /basket adds to it.
        """
        # Split now, once, rather than on every request.
        parts = parse_path(path)
        methods = {method.upper() for method in methods}
        # HEAD asks for what GET would send, without the body, so a route
        # that takes GET takes HEAD too. Dropping the body is the server's
        # job, as with Flask: gunicorn does it, though tinyhttp doesn't yet.
        if "GET" in methods:
            methods.add("HEAD")

        def register(view):
            self.routes.append((parts, methods, view))
            # Hand the function back unchanged, so it can still be called.
            return view
        return register

    def __call__(self, environ, start_response):
        """Answer one request: the WSGI entry point the server calls."""
        path = environ["PATH_INFO"]
        view, values = self.match(path, environ["REQUEST_METHOD"])
        headers = []
        if view is not None:
            status = "200 OK"
            content_type = "text/html; charset=utf-8"
            # The values from the path become the function's arguments:
            # {"id": 5} calls view(id=5).
            text = view(**values)
        else:
            content_type = "text/plain; charset=utf-8"
            allowed = self.allowed_methods(path)
            if allowed:
                # The path is right, but not the method, such as DELETE on
                # a page. Allow tells the client which methods would work.
                status = "405 Method Not Allowed"
                text = "method not allowed\n"
                headers.append(("Allow", ", ".join(sorted(allowed))))
            else:
                status = "404 Not Found"
                text = "not found\n"

        # WSGI bodies are bytes, and Content-Length counts them, not
        # characters. tinyhttp sets its own, but gunicorn passes ours on,
        # and without one it has to stream the body in chunks instead.
        body = text.encode("utf-8")
        headers.append(("Content-Type", content_type))
        headers.append(("Content-Length", str(len(body))))
        start_response(status, headers)
        # Any iterable of bytes will do; a list of one is the simplest.
        return [body]

    def match(self, path, method):
        """Find the route that answers method on path.

        Returns (view, values): the route's function, and the values taken
        from the path, by name. Returns (None, None) if no route matches.
        """
        parts = path.split("/")
        for pattern, methods, view in self.routes:
            # A route with the right path but the wrong method is skipped,
            # since a later one may have this path with this method.
            if method not in methods:
                continue
            values = match_parts(pattern, parts)
            if values is not None:
                return view, values
        return None, None

    def allowed_methods(self, path):
        """Every method that some route for path takes.

        Empty if no route has this path at all. For the Allow header of a
        405, when the path is right but the method isn't.
        """
        parts = path.split("/")
        allowed = set()
        for pattern, methods, _ in self.routes:
            if match_parts(pattern, parts) is not None:
                allowed |= methods
        return allowed


def to_int(text):
    """The <int:...> placeholder: a whole number, such as 5."""
    # isdigit alone also takes digits from other scripts, such as "٥",
    # which int() reads too, so /items/٥ would be item 5.
    if text.isascii() and text.isdigit():
        return int(text)
    return None


def to_str(text):
    """The <...> placeholder: any text, but not none at all."""
    return text if text else None


# Each kind of placeholder, and the function that checks and converts the
# text it's given. Each returns None when the text doesn't fit, so the
# route doesn't match.
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
                # <name> on its own takes any text.
                kind, name = "str", kind
            if kind not in CONVERTERS:
                # Raised when the route is added, so a typo such as
                # <itn:id> stops the app starting, rather than 404ing.
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
    # /items/5/reviews has a part too many for /items/<int:id>.
    if len(pattern) != len(parts):
        return None
    values = {}
    for want, got in zip(pattern, parts):
        if isinstance(want, str):
            # A plain part must be exactly the same.
            if want != got:
                return None
        else:
            convert, name = want
            value = convert(got)
            if value is None:
                return None
            values[name] = value
    return values
