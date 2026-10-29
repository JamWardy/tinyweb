"""Sending a file from a folder, with the headers for caching it.

The App's view for /static/ calls send_file with its static folder.
"""

import hashlib
import mimetypes
import os
from datetime import timezone
from email.utils import formatdate, parsedate_to_datetime

from tinyweb.response import Response, not_found


def send_file(request, folder, filename):
    """The file at filename in folder, or 304 if the browser's copy is current.

    folder must be a real path, from os.path.realpath. 404 if the file is
    missing, a folder, or outside folder.
    """
    # filename is from the URL, so it can be ../app.py or /etc/passwd.
    # realpath follows .. and symlinks to where the file really is.
    path = os.path.realpath(os.path.join(folder, filename))
    if os.path.commonpath([path, folder]) != folder:
        return not_found()
    # Missing, or a folder.
    if not os.path.isfile(path):
        return not_found()

    # Which version of the file this is, so the browser can ask if
    # it's changed. From stat alone, so a 304 never reads the file.
    stat = os.stat(path)
    name = hashlib.sha1(os.fsencode(path)).hexdigest()[:8]
    headers = {
        "ETag": f'"{stat.st_mtime_ns:x}-{stat.st_size:x}-{name}"',
        "Last-Modified": formatdate(stat.st_mtime, usegmt=True),
        # Keep a copy, but ask every time.
        "Cache-Control": "no-cache",
    }
    if not modified(request, headers["ETag"], int(stat.st_mtime)):
        return Response(b"", 304, headers)

    with open(path, "rb") as file:
        body = file.read()
    # From the extension; unknown ones are sent as plain bytes.
    content_type, _ = mimetypes.guess_type(path)
    headers["Content-Type"] = content_type or "application/octet-stream"
    return Response(body, 200, headers)


def modified(request, etag, mtime):
    """Whether the browser's copy is out of date, so it needs a 200.

    If-None-Match comes first, as RFC 9110 says; If-Modified-Since only
    counts without it.
    """
    if "If-None-Match" in request.headers:
        # One tag only; see Known gaps in TODO.md.
        return request.headers["If-None-Match"] != etag
    if "If-Modified-Since" in request.headers:
        try:
            since = parsedate_to_datetime(request.headers["If-Modified-Since"])
        except (TypeError, ValueError):
            # The RFC says to ignore a date that can't be read.
            return True
        # A date without a zone is GMT in HTTP.
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        # Dates are to the second.
        return mtime > since.timestamp()
    return True
