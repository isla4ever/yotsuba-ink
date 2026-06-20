from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class ReverseProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    target_host = "127.0.0.1"
    target_port = 54862

    def do_GET(self) -> None:
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()

    def do_OPTIONS(self) -> None:
        self._proxy()

    def do_HEAD(self) -> None:
        self._proxy()

    def log_message(self, fmt: str, *args: object) -> None:
        print("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), fmt % args), flush=True)

    def _forward_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            if key.lower() in HOP_BY_HOP_HEADERS:
                continue
            headers[key] = value
        headers["Host"] = f"{self.target_host}:{self.target_port}"
        headers["X-Forwarded-Host"] = self.headers.get("Host", "")
        headers["X-Forwarded-Proto"] = "http"
        return headers

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else None
        conn = http.client.HTTPConnection(self.target_host, self.target_port, timeout=600)
        try:
            conn.request(self.command, self.path, body=body, headers=self._forward_headers())
            upstream = conn.getresponse()
            self.send_response(upstream.status, upstream.reason)
            for key, value in upstream.getheaders():
                if key.lower() in HOP_BY_HOP_HEADERS or key.lower() == "content-length":
                    continue
                self.send_header(key, value)
            self.end_headers()
            if self.command == "HEAD":
                return
            while True:
                chunk = upstream.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception as exc:
            message = str(exc).encode("ascii", errors="replace").decode("ascii")
            self.send_error(502, f"Proxy error: {message}")
        finally:
            conn.close()


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Tiny local reverse proxy for natapp fixed local port.")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=80)
    parser.add_argument("--target-host", default="127.0.0.1")
    parser.add_argument("--target-port", type=int, default=54862)
    args = parser.parse_args(argv)

    ReverseProxyHandler.target_host = args.target_host
    ReverseProxyHandler.target_port = args.target_port
    server = ThreadingHTTPServer((args.listen_host, args.listen_port), ReverseProxyHandler)
    print(
        f"reverse_proxy listening http://{args.listen_host}:{args.listen_port} -> "
        f"http://{args.target_host}:{args.target_port}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
