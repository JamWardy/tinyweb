"""The Response: what a view returns when a string isn't enough.

A string is sent as an HTML page with 200 OK. For anything else, such as
a redirect, an error or JSON, a view returns a Response.
"""

# The words that go with each status, for the status line, as in
# "404 Not Found". Only the ones the plan uses; add others as needed. The
# first digit is the kind: 2 worked, 3 look elsewhere, 4 the client's
# mistake, 5 the server's.
REASONS = {
    200: "OK",
    201: "Created",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",           # After a form: go and GET this instead
    304: "Not Modified",        # Your cached copy is still good
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    401: "Unauthorized",        # Not logged in, despite the name
    403: "Forbidden",           # Logged in, but not allowed
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",            # Such as an item out of stock at checkout
    413: "Content Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Content",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


class Response:
    def __init__(self, body="", status=200, headers=None):
        """body is text or bytes, status a number, headers a dict.

            return Response("", status=303, headers={"Location": "/"})
        """
        if status not in REASONS:
            # Here, so a typo such as 4040 fails in the view that made it.
            raise ValueError(f"unknown status {status}; add it to REASONS")
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status
        self.reason = REASONS[status]
        self.headers = dict(headers or {})
        self.headers.setdefault("Content-Type", "text/html; charset=utf-8")
