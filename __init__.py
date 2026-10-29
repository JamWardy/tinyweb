"""A toy web framework, built on WSGI to learn how one works.

It does Flask's job: the server hands it each request through WSGI
(PEP 3333), and it decides which of the app's code answers it.
"""

from tinyweb.app import App
