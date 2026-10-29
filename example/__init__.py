"""tinyweb's example app, to try the framework on its own.

From tinyAmazon/, `python -m tinyhttp tinyweb.example:app` serves it.
"""

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
