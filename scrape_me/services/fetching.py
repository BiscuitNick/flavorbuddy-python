"""Public-only HTTP transport. The socket connects to the validated numeric IP.

TLS still verifies the original hostname. No environment proxies, automatic
redirects, content decompression, or parser-owned fetching are permitted.
"""

import http.client
import ipaddress
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit, urlunsplit, urljoin

import dns.resolver
from scrape_me.api.errors import ImportFailure

MAX_BYTES = 2 * 1024 * 1024
DEADLINE = 15


class FetchFailure(ImportFailure):
    default_code = "source_unavailable"
    default_detail = "This page could not be imported safely. Paste the recipe text or enter it manually."


def canonical_url(value):
    try:
        if (
            not isinstance(value, str)
            or len(value) > 2000
            or any(ord(c) < 33 for c in value.strip())
        ):
            raise ValueError
        parts = urlsplit(value.strip())
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
        ):
            raise ValueError
        port = parts.port
        if port not in (None, 443 if parts.scheme == "https" else 80):
            raise ValueError
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if "%" in host or "\\" in value:
            raise ValueError
        netloc = f"[{host}]" if ":" in host else host
        return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
    except (ValueError, UnicodeError):
        raise FetchFailure() from None


def resolve_public(host, deadline):
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = []
        resolver = dns.resolver.Resolver()
        for kind in ("A", "AAAA"):
            try:
                answer = resolver.resolve(
                    host, kind, lifetime=max(0.01, deadline - time.monotonic())
                )
                addresses.extend(ipaddress.ip_address(str(record)) for record in answer)
            except dns.resolver.NoAnswer:
                continue
            except Exception:
                raise FetchFailure() from None
    if not addresses or any(
        not ip.is_global
        or ip.is_reserved
        or ip.is_multicast
        or (ip.version == 6 and (ip.ipv4_mapped or ip.sixtofour or ip.teredo))
        for ip in addresses
    ):
        raise FetchFailure()
    return str(addresses[0])


class PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, ip, port, secure, timeout):
        super().__init__(host, port, timeout=timeout)
        self.ip = ip
        self.secure = secure
        self.transport_socket = None

    def connect(self):
        family = socket.AF_INET6 if ":" in self.ip else socket.AF_INET
        self.sock = socket.socket(family, socket.SOCK_STREAM)
        self.transport_socket = self.sock
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.ip, self.port))
        if self.secure:
            self.sock = ssl.create_default_context().wrap_socket(
                self.sock, server_hostname=self.host
            )
            self.transport_socket = self.sock

    def abort(self):
        if self.transport_socket:
            try:
                self.transport_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.close()


def fetch_html(value):
    deadline = time.monotonic() + DEADLINE
    url = canonical_url(value)
    for hop in range(6):
        parts = urlsplit(url)
        ip = resolve_public(parts.hostname, deadline)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchFailure()
        connection = PinnedConnection(
            parts.hostname,
            ip,
            443 if parts.scheme == "https" else 80,
            parts.scheme == "https",
            min(5, remaining),
        )
        watchdog = threading.Timer(remaining, connection.abort)
        watchdog.daemon = True
        watchdog.start()
        try:
            connection.request(
                "GET",
                urlunsplit(("", "", parts.path, parts.query, "")),
                headers={
                    "User-Agent": "FlavorBuddy/alpha recipe importer",
                    "Accept": "text/html, application/xhtml+xml",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = response.getheader("Location")
                if not target or hop == 5:
                    raise FetchFailure()
                url = canonical_url(urljoin(url, target))
                continue
            if response.status != 200 or response.getheader("Content-Type", "").split(
                ";"
            )[0].strip().lower() not in ("text/html", "application/xhtml+xml"):
                raise FetchFailure()
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise FetchFailure()
            length = response.getheader("Content-Length")
            if length and (int(length) < 0 or int(length) > MAX_BYTES):
                raise FetchFailure()
            chunks = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise FetchFailure()
                chunk = response.read(min(65536, MAX_BYTES + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > MAX_BYTES:
                    raise FetchFailure()
            return bytes(chunks).decode("utf-8", errors="replace"), url
        except ImportFailure:
            raise
        except (OSError, ValueError, http.client.HTTPException):
            raise FetchFailure() from None
        finally:
            watchdog.cancel()
            connection.close()
    raise FetchFailure()
