"""The App: the framework's side of WSGI.

A WSGI app is any callable app(environ, start_response): the server calls
it once per request, and it calls start_response with the status and
headers, then returns the body as bytes. An App is one, so any WSGI server
can run it, as gunicorn runs a Flask app.
"""

import os
import sys

from tinyweb.request import Request
from tinyweb.response import PLAIN, Response, not_found
from tinyweb.routing import Route, compile_path
from tinyweb.static import send_file


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
            # Real, to compare with the real paths in send_file.
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
        return send_file(request, self.static_folder, filename)

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
