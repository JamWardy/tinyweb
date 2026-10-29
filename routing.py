"""Routing: turning a route's path into a pattern, and matching paths to it.

"/items/<int:id>" becomes a regular expression with a named group for each
placeholder, compiled once when the route is added.
"""

import re
from dataclasses import dataclass
from typing import Callable

# Each placeholder kind: the text it matches, and what turns it into a value.
CONVERTERS = {
    "string": (r"[^/]+", str),      # Any text but a slash, and not none
    "int": (r"[0-9]+", int),        # A whole number; [0-9], so not "٥"
    "path": (r".+", str),           # Like string, but slashes too
}

# A placeholder in a route's path: <name>, or <kind:name> such as <int:id>.
PLACEHOLDER = re.compile(r"<(?:([A-Za-z_]\w*):)?([A-Za-z_]\w*)>")


@dataclass
class Route:
    pattern: re.Pattern     # "/items/<int:id>" as /items/(?P<id>[0-9]+)
    converters: dict        # Each placeholder's name to its function: {"id": int}
    methods: set            # {"GET", "HEAD"}
    view: Callable          # The function that answers it

    def match(self, path):
        """The values from path by name, such as {"id": 5}, or None."""
        found = self.pattern.fullmatch(path)
        if found is None:
            return None
        return {name: convert(found[name])
                for name, convert in self.converters.items()}


def compile_path(path):
    """Turn a route's path into a regex and its converters.

    "/items/<int:id>" becomes /items/(?P<id>[0-9]+) and {"id": int}.
    """
    regex = ""
    converters = {}
    end = 0
    for placeholder in PLACEHOLDER.finditer(path):
        kind, name = placeholder.groups()
        kind = kind or "string"
        # At startup, so a typo such as <itn:id> isn't a quiet 404.
        if kind not in CONVERTERS:
            raise ValueError(f"unknown placeholder {kind!r} in {path!r}")
        if name in converters:
            raise ValueError(f"placeholder {name!r} twice in {path!r}")
        text, converters[name] = CONVERTERS[kind]
        # Escaped, so the "." in "<name>.txt" is only a dot.
        regex += re.escape(path[end:placeholder.start()])
        regex += f"(?P<{name}>{text})"
        end = placeholder.end()
    regex += re.escape(path[end:])
    return re.compile(regex), converters
