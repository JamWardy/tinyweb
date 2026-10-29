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
        # path split into parts by parse_path, and the function that
        # answers it. A list, not a dict, since /items/5 isn't a key: each
        # route is tried in turn, and the first that matches wins.
        self.routes = []

    def route(self, path):
        """A decorator that makes the function below it answer path.

        A part of the path in <...> takes a value from the request's path
        and passes it to the function by name: <int:id> takes a whole
        number, and <name> any text.

            @app.route("/items/<int:id>")
            def item(id):
                return f"<h1>Item {id}</h1>"
        """
        # Split now, once, rather than on every request.
        parts = parse_path(path)

        def register(view):
            self.routes.append((parts, view))
            # Hand the function back unchanged, so it can still be called.
            return view
        return register

    def __call__(self, environ, start_response):
        """Answer one request: the WSGI entry point the server calls."""
        view, values = self.match(environ["PATH_INFO"])
        if view is None:
            status = "404 Not Found"
            content_type = "text/plain; charset=utf-8"
            text = "not found\n"
        else:
            status = "200 OK"
            content_type = "text/html; charset=utf-8"
            # The values from the path become the function's arguments:
            # {"id": 5} calls view(id=5).
            text = view(**values)

        # WSGI bodies are bytes, and Content-Length counts them, not
        # characters. tinyhttp sets its own, but gunicorn passes ours on,
        # and without one it has to stream the body in chunks instead.
        body = text.encode("utf-8")
        start_response(status, [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
        ])
        # Any iterable of bytes will do; a list of one is the simplest.
        return [body]

    def match(self, path):
        """Find the route that answers path.

        Returns (view, values): the route's function, and the values taken
        from the path, by name. Returns (None, None) if no route matches.
        """
        parts = path.split("/")
        for pattern, view in self.routes:
            values = match_parts(pattern, parts)
            if values is not None:
                return view, values
        return None, None


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
