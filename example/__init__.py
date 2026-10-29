"""tinyweb's example app, to try the framework on its own.

From tinyAmazon/, `python -m tinyhttp tinyweb.example:app` serves it.
"""

from html import escape

from tinyweb import App

app = App()


@app.route("/")
def index():
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
def item(id):
    return f"<h1>Item {id}</h1>\n"


@app.route("/hello/<name>")
def hello(name):
    # name comes from the URL, so anyone can put <script> in it. escape
    # turns < into &lt; and so on, so it shows as text instead of running.
    return f"<h1>Hello, {escape(name)}!</h1>\n"
