"""Read public official references without proxies, credentials or execution."""
from __future__ import annotations

import hashlib
import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
import time
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit, urlunsplit

CATALOGUE_PATH = Path(__file__).parent / "assets/documentation/catalogue.json"
CATALOGUE = json.loads(CATALOGUE_PATH.read_text(encoding="utf8"))
CATALOGUE_SHA256 = hashlib.sha256(json.dumps(CATALOGUE, sort_keys=True).encode()).hexdigest()
SOURCES = {entry["id"]: entry for entry in CATALOGUE["sources"]}
MAX_BYTES = 24 * 1024 * 1024
MAX_TEXT = 8 * 1024 * 1024
READ_TIMEOUT = 20
INTEL_ARCHIVE_URL = "https://cdrdv2.intel.com/v1/dl/getContent/671338"


def official_url(url: str, source_id: str | None = None) -> tuple[str, str]:
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        raise ValueError("Expected a public official documentation URL")
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.query
                or parsed.port not in (None, 443) or "\\" in url):
            raise ValueError("Only HTTPS documentation without credentials or query parameters is allowed")
        path = unquote(parsed.path, errors="strict")
        if (any(part in {".", ".."} for part in path.split("/"))
                or any(ord(c) < 32 or ord(c) == 127 for c in path) or any(c in path for c in "%\\?#")):
            raise ValueError("Documentation path traversal is forbidden")
        normalized = urlunsplit(("https", (parsed.hostname or "").lower(),
                                quote(path or "/", safe="/-._~!$&'()*+,;=:@"), "", ""))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid public documentation URL") from exc
    for identifier, entry in SOURCES.items():
        if source_id is not None and source_id != identifier:
            continue
        if any(normalized.startswith(prefix) if prefix.endswith("/") else normalized == prefix
               for prefix in entry["prefixes"]):
            return normalized, identifier
    raise ValueError("URL is outside the official documentation catalogue")


class _PinnedHTTPS(http.client.HTTPSConnection):
    """Resolve once, then connect only to validated public IPs with hostname TLS."""
    def connect(self):
        timeout = self.timeout if isinstance(self.timeout, (int, float)) else READ_TIMEOUT
        deadline = time.monotonic() + timeout
        addresses = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Documentation host must resolve only to public IP addresses")
        failure = None
        for family, kind, protocol, _, address in addresses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Documentation connection timed out")
            sock = socket.socket(family, kind, protocol)
            try:
                sock.settimeout(remaining)
                sock.connect(address)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError as exc:
                failure = exc
                sock.close()
        raise OSError("Could not connect to the public documentation host") from failure


class _DocumentHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden, self.parts, self.links, self.title_parts = 0, [], [], []
        self.anchor = None
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if self.hidden:
            return
        if tag == "a" and attrs.get("href"):
            self.anchor = [attrs["href"], []]
        if tag == "intrinsic" and attrs.get("name"):
            self.parts.append("\n" + attrs["name"] + "\n")
        if tag == "intrinsics_list" and attrs.get("version"):
            self.title_parts.append("Intel Intrinsics Guide Version " + attrs["version"])
        if tag in {"return", "parameter", "instruction"}:
            signature = " ".join(f"{key}={value}" for key, value in attrs.items())
            if signature:
                self.parts.append("\n" + tag + ": " + signature + "\n")
        if tag in {"p", "div", "li", "br", "tr", "h1", "h2", "h3", "h4", "pre", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False
        if tag == "a" and self.anchor is not None:
            if len(self.links) < 10000:
                self.links.append({"url": self.anchor[0], "title": "".join(self.anchor[1]).strip()})
            self.anchor = None
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "pre", "section"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.anchor is not None:
                self.anchor[1].append(data)
            if self.in_title:
                self.title_parts.append(data)


def extract_document(raw: bytes, mime: str, charset: str = "utf8") -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError("Documentation exceeds its download size bound")
    title, links, page_count = "", [], None
    if mime in {"application/zip", "application/x-zip-compressed"}:
        # The official Intel offline guide is data plus a JavaScript viewer.
        # Read only its XML data in memory; never unpack or execute the viewer.
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = [entry for entry in archive.infolist() if re.search(r"(?:^|/)data[^/]*\.(?:xml|js)$", entry.filename)]
            if len(members) != 1 or members[0].file_size > MAX_BYTES:
                raise ValueError("Expected one bounded Intel intrinsic XML data file")
            with archive.open(members[0]) as stream:
                payload = stream.read(MAX_BYTES + 1)
            if members[0].filename.endswith(".js"):
                # Some publisher archives wrap XML in a JavaScript string.
                # Decode only a constant string assignment; never evaluate JS.
                match = re.fullmatch(r"\s*(?:var|let|const)\s+data_js\s*=\s*(.*?)\s*;?\s*",
                                     payload.decode("utf8"), re.DOTALL)
                if match is None:
                    raise ValueError("The offline guide is not a constant XML data assignment")
                literal = match[1].rstrip(";").strip()
                if literal.startswith('"'):
                    # Publisher strings contain literal XML indentation tabs.
                    xml = json.loads(re.sub(r"\\\r?\n", "", literal), strict=False)
                elif literal.startswith("`") and literal.endswith("`") and "${" not in literal:
                    xml = literal[1:-1]
                else:
                    raise ValueError("Unsupported offline intrinsic data encoding")
                if not isinstance(xml, str) or "<intrinsics_list" not in xml:
                    raise ValueError("The offline guide contains no intrinsic XML data")
                payload = xml.encode()
            document = extract_document(payload, "application/xml")
            return {**document, "container_member": members[0].filename}
    if mime == "application/pdf" or raw.startswith(b"%PDF-"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw), strict=False)
        if reader.is_encrypted:
            raise ValueError("Encrypted documentation cannot be read")
        page_count = len(reader.pages)
        if page_count > 2000:
            raise ValueError("PDF exceeds its page bound")
        parts, length, has_text = [], 0, False
        for number, page in enumerate(reader.pages, 1):
            stream = page.get_contents()
            if stream is not None and len(stream.get_data()) > MAX_BYTES:
                raise ValueError("PDF page content exceeds its extraction bound")
            page_text = page.extract_text() or ""
            has_text = has_text or bool(page_text.strip())
            part = f"\n[PDF page {number}]\n" + page_text
            parts.append(part)
            length += len(part)
            if length > MAX_TEXT:
                raise ValueError("PDF text exceeds its extraction bound")
        text = "\n".join(parts)
        if not has_text:
            raise ValueError("PDF contains no extractable text")
        title = str((reader.metadata or {}).get("/Title", ""))
    else:
        text = raw.decode(charset, errors="replace")
        if mime in {"text/html", "application/xhtml+xml", "application/xml", "text/xml"}:
            parser = _DocumentHTML()
            parser.feed(text)
            text, title, links = "".join(parser.parts), "".join(parser.title_parts), parser.links
    lines = (line.strip() for line in text.splitlines())
    text = "\n".join(line[offset:offset + 2000] for line in lines if line
                     for offset in range(0, len(line), 2000))
    if not text:
        raise ValueError("The publisher returned no readable documentation text")
    if len(text) > MAX_TEXT:
        raise ValueError("Documentation text exceeds its extraction bound")
    return {"title": title, "text": text, "links": links, "pdf_pages": page_count}


def documentation_redirect(current: str, location: str, original: str, source_id: str) -> str:
    target = urljoin(current, location)
    if original == INTEL_ARCHIVE_URL:
        parsed = urlsplit(target)
        # This CDN path is reached only from Intel's fixed official download ID.
        # Model-supplied CDN URLs are still rejected by official_url(). Signed
        # delivery URLs are never included in public references or cache receipts.
        if (parsed.scheme == "https" and parsed.hostname == "d2pgu9s4sfmw1s.cloudfront.net"
                and not parsed.username and not parsed.password and parsed.port in (None, 443)
                and re.fullmatch(r"/UAM/Prod/Done/[A-Za-z0-9-]+/[A-Za-z0-9-]+", parsed.path)
                and set(parse_qs(parsed.query)) == {"Expires", "Key-Pair-Id", "Signature"}
                and len(target) < 3000 and not parsed.fragment):
            return target
    return official_url(target, source_id)[0]


def fetch_document(url: str) -> dict:
    original, source_id = official_url(url)
    current, started = original, time.monotonic()
    context = ssl.create_default_context()
    for _ in range(4):
        remaining = READ_TIMEOUT - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Official documentation read timed out")
        parsed = urlsplit(current)
        connection = _PinnedHTTPS(parsed.hostname, timeout=remaining, context=context)
        try:
            connection.request("GET", parsed.path + ("?" + parsed.query if parsed.query else ""), headers={
                "User-Agent": "HPC-Forest-official-docs/1", "Accept-Encoding": "identity",
                "Accept": "text/html,application/pdf,text/plain,application/xml,application/json",
            })
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                current = documentation_redirect(current, response.getheader("Location", ""), original, source_id)
                continue
            if response.status != 200:
                raise OSError(f"Official publisher returned HTTP {response.status}")
            mime = response.headers.get_content_type()
            if mime not in {"text/html", "application/xhtml+xml", "text/plain", "text/markdown",
                            "application/pdf", "application/json", "application/xml", "text/xml",
                            "application/zip", "application/x-zip-compressed"}:
                raise ValueError("Publisher response is not a supported documentation format")
            if mime in {"application/zip", "application/x-zip-compressed"} and original != INTEL_ARCHIVE_URL:
                raise ValueError("Only the official Intel intrinsic archive is supported")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Compressed HTTP responses are not accepted")
            parts, size = [], 0
            while True:
                remaining = READ_TIMEOUT - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("Official documentation read timed out")
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                part = response.read1(min(65536, MAX_BYTES + 1 - size))
                if not part:
                    break
                parts.append(part)
                size += len(part)
                if size > MAX_BYTES:
                    raise ValueError("Documentation exceeds its download size bound")
            raw = b"".join(parts)
            document = extract_document(raw, mime, response.headers.get_content_charset() or "utf8")
        finally:
            connection.close()
        links = []
        for link in document.pop("links"):
            try:
                target, _ = official_url(urljoin(current, link["url"]), source_id)
            except ValueError:
                continue
            if target != current:
                links.append({"url": target, "title": link["title"]})
        resolved = original if original == INTEL_ARCHIVE_URL else current
        return {**document, "url": original, "resolved_url": resolved, "source_id": source_id,
                "media_type": mime, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "text_sha256": hashlib.sha256(document["text"].encode()).hexdigest(),
                "retrieved_at": time.time(), "links": links, "raw": raw}
    raise ValueError("Too many documentation redirects")


def source_version(url: str, text: str) -> str:
    for pattern in (r"/spec-html/([^/]+)/", r"/mpi-([^/]+)/", r"/gcc-([^/]+)/",
                    r"/archive/([^/]+)/", r"/en/(v[^/]+)/", r"/hpc-sdk/(\d+\.\d+)/"):
        if match := re.search(pattern, url):
            return "url:" + match[1]
    if match := re.search(r"(?:Version|version|Release|release)[:\s]+(\d+\.\d+(?:\.\d+)?)", text[:6000]):
        return "publisher-text:" + match[1]
    return "publisher-current; exact content pinned by SHA-256"
