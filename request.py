"""The Request: what a view is given about the request it's answering.

environ has all of it, but in the shape WSGI needs: the query is one
string, the headers are HTTP_ keys and the body is a file. A Request reads
them out once, into plain values.
"""

from dataclasses import dataclass
from urllib.parse import parse_qsl


@dataclass
class Request:
    method: str     # "GET"
    path: str       # "/items/5", without the query
    args: dict      # The query: ?q=shoes&page=2 as {"q": "shoes", "page": "2"}
    headers: dict   # Names as written here: {"User-Agent": "curl/8.7.1"}
    body: bytes     # b"" if there isn't one
    form: dict      # A form's fields from the body, or {} if it isn't one
    environ: dict   # For anything not above, such as REMOTE_ADDR

    @classmethod
    def from_environ(cls, environ):
        """Read a Request out of the environ the server passed the App."""
        # A name sent twice keeps only its last value.
        args = dict(parse_qsl(environ.get("QUERY_STRING", ""),
                              keep_blank_values=True))

        # The server turned User-Agent into HTTP_USER_AGENT; turn it back.
        # Look names up as written here, "X-Test", not "x-test".
        headers = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                name = key[len("HTTP_"):]
            elif key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                name = key
            else:
                continue
            headers[name.replace("_", "-").title()] = value

        # The PEP says not to read past CONTENT_LENGTH.
        length = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(length)

        # A form from a page arrives in the body, shaped like a query.
        # "; charset=..." may follow the type.
        content_type = headers.get("Content-Type", "").split(";")[0]
        if content_type.strip() == "application/x-www-form-urlencoded":
            form = dict(parse_qsl(body.decode("utf-8", "replace"),
                                  keep_blank_values=True))
        else:
            form = {}

        return cls(environ["REQUEST_METHOD"], environ["PATH_INFO"], args,
                   headers, body, form, environ)
