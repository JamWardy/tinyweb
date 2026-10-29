"""tinyweb's example app, to try the framework on its own.

From tinyAmazon/, `python -m tinyhttp tinyweb.example:app` serves it.
"""

from html import escape

from tinyweb import App, Response

app = App()


@app.route("/")
def index(request):
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Hello from tinyweb</title>
</head>
<body>
  <h1>Hello, world!</h1>
  <p>Served by tinyweb, through WSGI.</p>
</body>
</html>
"""


@app.route("/items/<int:id>")
def item(request, id):
    return f"<h1>Item {id}</h1>\n"


@app.route("/hello/<name>")
def hello(request, name):
    # Anyone can put <script> in a URL, so escape it to show as text.
    return f"<h1>Hello, {escape(name)}!</h1>\n"


@app.route("/search")
def search(request):
    q = request.args.get("q", "")
    return f"<p>You searched for: {escape(q)}</p>\n"


@app.route("/greet", methods=["GET", "POST"])
def greet(request):
    # GET shows the form, and POST is the form sent back.
    if request.method == "POST":
        name = request.form.get("name", "")
        return f"<h1>Hello, {escape(name)}!</h1>\n"
    return """<form method="post">
  <input name="name" placeholder="Your name">
  <button>Greet me</button>
</form>
"""


@app.route("/home")
def home(request):
    # 301: this page has moved for good, to Location.
    return Response("", 301, {"Location": "/"})
