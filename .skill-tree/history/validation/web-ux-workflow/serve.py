"""Serve a published Blazor build on an ephemeral loopback port."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

class FixtureServer(ThreadingHTTPServer):
    request_queue_size = 256


class PublishedApp(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if urlsplit(self.path).path == "/privacy":
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    root = parser.parse_args().root.resolve()
    if not (root / "_framework/blazor.boot.json").is_file():
        parser.error("Expected a published Blazor wwwroot")
    server = FixtureServer(("127.0.0.1", 0), partial(PublishedApp, directory=root))
    print(f"http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
