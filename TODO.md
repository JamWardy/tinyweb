# TODO

What tinyweb needs, step by step. The steps are the ones in
`../TODO.md`, which has the plan for the whole project; this file
breaks tinyweb's share of them into parts. tinyweb does Flask's job:
the server hands it each request through WSGI, and it decides which of
the app's code answers it.

## Rules

- **Python's standard library only.** tinyweb is here to learn how a
  framework works by writing one, so every part of it is written here.
- **Flask and gunicorn are for testing only.** They're never imported,
  called or run from this repo, tests included, and that goes for
  Werkzeug and Jinja too: they're the likeliest shortcuts for routing,
  requests and templates. They live only in `../tinyAmazonTest/`, for
  Part 6. See `../tinyAmazonTest/TODO.md`, which has the full rules
  and a grep to check them. Comments comparing ours to theirs, such as
  "as Flask does", are fine.
- **No shortcuts from the standard library either.** `wsgiref`,
  `http.server` and `http.cookies` already do parts of this repo's job,
  so none of them are used here, not even in part. That goes for the
  whole `http` package, `http.HTTPStatus` included: status phrases are
  our own table, `REASONS` in `response.py`. Small building blocks are
  fine: `urllib.parse` for `%XX` and query strings, `mimetypes` for a
  file's type, `hashlib` and `json`.
- **The framework only, never the shop.** The shop imports tinyweb,
  never the other way round, as Flask knows nothing of the apps built
  on it. An app tells tinyweb what it needs, such as where its static
  files are. The shop isn't started until the system design (step 3 in
  `../TODO.md`), so until then tinyweb is tried on its own example app.
  From `tinyAmazon/`, this finds nothing:

  ```
  grep -rnw shop --include='*.py' tinyweb
  ```

## Step 2: a framework, with routing and static files

The example app lives in `example/`, as Flask's examples do: a
hello-world page, a route that takes a value, and a `static/` folder.
`python -m tinyhttp tinyweb.example:app` from `tinyAmazon/` serves it.
It's tested end to end, on tinyhttp, in `../tinyAmazonTest/`, not with
tests of its own here.

- [x] Part 1: the package, `tinyweb/__init__.py`, and an `App` that's
      itself a WSGI app: `__call__(environ, start_response)`. Then
      `example/`, with `app = App()` and a hello-world `/`
- [x] Part 2: routing. `@app.route("/items/<int:id>")` sends
      `GET /items/5` to that route's function with `id=5`; unknown
      paths get `404`, and a known path with the wrong method `405`
      with an `Allow` header. Paths that aren't ASCII are left for
      later; see "Known gaps"
- [x] Part 3: what a view gets and returns. A request object with the
      method, path, query parsed into a dict (`urllib.parse`), headers
      and body; a view returns a string, or a response with a status,
      headers and body
- [x] Before Part 4, rework Parts 1 to 3 for quality, so new features
      don't mean editing the matcher each time:
  - Matching: compile each route to one regular expression (`re`)
    when it's added, as Werkzeug does. Each converter is a pattern and
    a function: `string` is `[^/]+` then `str`, `int` is `[0-9]+` then
    `int`, and a new `path` is `.+` then `str`, slashes included. The
    plain text is `re.escape`d. Then `/files/<name>.txt` works, and a
    new converter is one line, not a change to `match_parts`. Rename
    `<str:...>` to `<string:...>` while there, as Flask has it
  - Dataclasses: a `Route` (pattern, converters, methods, view) in
    place of the `(parts, methods, view)` tuples, as tinyhttp's
    `Request` is one. Check `Request` and `Response` for the same:
    such as `Request.from_environ(environ)`, as tinyhttp has
    `parse_head`
  - The example still answers every route as before
- [x] Part 4: static files. `App(__name__)`, as Flask's, says which
      module made it, and its static folder is by default `static/`
      next to that module's file, as Flask's `static_folder` is. The
      `App` adds `/static/<path:filename>` itself, as an ordinary route
      with a view of its own, as Flask does, so `405` and `HEAD` work
      as for any route. `GET /static/style.css` serves the file, with a
      `Content-Type` from the extension (`mimetypes`), `404` if it's
      missing or a folder, and never a file outside the folder: check
      the real path after joining, so `/static/../` and
      `/static/%2e%2e/` both fail, since tinyhttp decodes `%XX` first.
      The hello-world page gets a `style.css`. Later, step 5's reverse
      proxy serves `/static/` in front of the app, as nginx does for
      Django, and the CDN caches it; this stays for running without them.
      Decided while building it:
  - An extension `mimetypes` doesn't know gets
    `application/octet-stream`, just bytes, which a browser downloads
  - Text files get no `charset`: nothing here says which encoding
    they're in, so the browser decides
  - `App(__name__, static_folder=None)` serves no static files, for an
    app without any
  - A symlink in the folder that points outside it gets `404`, as
    checking the real path follows it
  - The static route is added first, so it wins over an app's own
    route under `/static/`
  - The whole file is read into memory, which is fine for CSS and small
    images; large files would want streaming
  - The `404` is one helper, `not_found()`, for unknown paths and
    missing files alike
- [ ] Part 5: caching. `Cache-Control` on static files, an `ETag` for
      each (from its size and modification time, or a hash), and
      `304 Not Modified` with no body when `If-None-Match` matches
- [ ] Part 6: the example app on a real server: on tinyhttp first, then
      on gunicorn, so tinyweb relies only on what WSGI promises and not
      on anything only tinyhttp does. That's done in
      `../tinyAmazonTest/`, and tracked in its `TODO.md`

## Known gaps

- tinyhttp sends the body in reply to `HEAD`; gunicorn drops it (see
  `../tinyhttp/TODO.md`). tinyweb answers `HEAD` as it would `GET`, as
  Flask does, and leaves dropping the body to the server.
- [ ] Paths that aren't ASCII never match. `PATH_INFO` is bytes held in
      a latin-1 string (PEP 3333), so tinyhttp hands `/café` over as
      `/caf\xc3\xa9`, which a `/café` route never equals. The fix is to
      encode it as latin-1 and decode it as UTF-8 before matching, with
      a `400` for bytes that aren't UTF-8. Nice to have: the shop's
      paths are all ASCII, such as `/products/5`.
