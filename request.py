"""The Request: what a view is given about the request it's answering.

environ has all of it, but in the shape WSGI needs: the query is one
string, the headers are HTTP_ keys and the body is a file. A Request reads
them out once, into plain values.
"""

from urllib.parse import parse_qsl


class Request:
    def __init__(self, environ):
        # For anything not below, such as REMOTE_ADDR.
        self.environ = environ
        self.method = environ["REQUEST_METHOD"]
        self.path = environ["PATH_INFO"]

        # ?q=shoes&page=2 becomes {"q": "shoes", "page": "2"}. A name sent
        # twice keeps only its last value.
        self.args = dict(parse_qsl(environ.get("QUERY_STRING", ""),
                                   keep_blank_values=True))

        # The server turned User-Agent into HTTP_USER_AGENT; turn it back.
        # Look names up as written here, "X-Test", not "x-test".
        self.headers = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                name = key[len("HTTP_"):]
            elif key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                name = key
            else:
                continue
            self.headers[name.replace("_", "-").title()] = value

        # The PEP says not to read past CONTENT_LENGTH.
        length = int(environ.get("CONTENT_LENGTH") or 0)
        self.body = environ["wsgi.input"].read(length)

        # A form from a page arrives in the body, shaped like a query.
        # "; charset=..." may follow the type.
        content_type = self.headers.get("Content-Type", "").split(";")[0]
        if content_type.strip() == "application/x-www-form-urlencoded":
            self.form = dict(parse_qsl(self.body.decode("utf-8", "replace"),
                                       keep_blank_values=True))
        else:
            self.form = {}
