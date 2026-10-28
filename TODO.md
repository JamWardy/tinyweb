# TODO

What tinyweb needs, step by step. The steps are the ones in
`../TODO.md`, which has the plan for the whole project. tinyweb does
Flask's job: the server hands it each request through WSGI, and it
decides which of the app's code answers it.

To be fleshed out.

## Step 2: routing

- [ ] Routing: send `GET /products/5` to the code for a product page,
      answer `GET /health` with `200 OK`, and unknown paths with `404`
- [ ] Check it on real gunicorn, so it only relies on what WSGI
      promises and not on anything only tinyhttp does
