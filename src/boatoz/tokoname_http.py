"""HTTPを子プロセスに閉じ込め、親が総時間上限で確実に終了できるようにする。"""

import base64
import json
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 2 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    url, timeout = sys.argv[1:]
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.boatrace-tokoname.jp"
        or not parsed.path.startswith("/modules/yosou/group-")
    ):
        raise ValueError("対象外のURLです")
    request = Request(
        url,
        headers={
            "User-Agent": "mypublish-py-boatoz/0.1 (+https://github.com/bluehive/mypublish-py-boatoz)",
            "Accept": "text/html",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with build_opener(NoRedirect).open(request, timeout=float(timeout)) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("HTMLのサイズ上限を超えました")
            if "text/html" not in response.headers.get("Content-Type", ""):
                raise ValueError("HTML以外の応答です")
            result = {"status": response.status, "body": base64.b64encode(raw).decode("ascii")}
    except HTTPError as exc:
        result = {"status": exc.code, "retry_after": exc.headers.get("Retry-After")}
    except Exception as exc:
        result = {"error": str(exc)}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
