"""The App: the framework's side of WSGI.

A WSGI app is any callable app(environ, start_response). The server calls
it once per request with environ, a dict describing the request. The app
calls start_response with the status and headers, then returns the body
as an iterable of bytes. An App is one of these, so a server runs it
without knowing it's made with tinyweb, as gunicorn runs a Flask app.
"""


class App:
    def __init__(self):
        # Each path the app answers, mapped to the function that answers it.
        # Only exact paths for now; <int:id> and methods come with routing.
        self.routes = {}

    def route(self, path):
        """A decorator that makes the function below it answer path.

            @app.route("/")
            def index():
                return "<h1>Hello</h1>"
        """
        def register(view):
            self.routes[path] = view
            # Hand the function back unchanged, so it can still be called.
            return view
        return register

    def __call__(self, environ, start_response):
        """Answer one request: the WSGI entry point the server calls."""
        view = self.routes.get(environ["PATH_INFO"])
        if view is None:
            status = "404 Not Found"
            content_type = "text/plain; charset=utf-8"
            text = "not found\n"
        else:
            status = "200 OK"
            content_type = "text/html; charset=utf-8"
            text = view()

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
