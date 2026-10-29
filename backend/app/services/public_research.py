"""Bounded public web research; no browser execution, proxy, or private-address access."""
from __future__ import annotations
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import time
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qs, urljoin, quote
from xml.etree import ElementTree

MAX_BYTES = 1_000_000
FETCH_SECONDS = 8
SEARCH_SECONDS = 90

class ResearchUnavailable(RuntimeError):
    """Transport/parsing failure is not proof that a company has no public information."""

def normalized_name(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()

def _resolve(host: str) -> list[str]:
    return list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)))

def validate_target(url: str) -> tuple[str, int, list[str]]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTP(S) pages are allowed")
    if any(ord(c) < 33 for c in url) or len(url) > 2048:
        raise ValueError("Invalid public URL")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in (80, 443):
        raise ValueError("Unsupported public port")
    host = parsed.hostname.encode("idna").decode("ascii")
    try:
        addresses = _resolve(host)
    except OSError as exc:
        raise ValueError("Public host cannot be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("Private, reserved or mixed-address targets are forbidden")
    return host, port, addresses

def _request_once(url: str, timeout: float, headers: dict | None = None):
    host, port, addresses = validate_target(url)
    parsed = urlsplit(url)
    # Connect to the already-validated numeric IP; TLS still authenticates the original hostname.
    # Re-resolving the hostname here would permit DNS rebinding.
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    raw = socket.create_connection((addresses[0], port), timeout=timeout)
    try:
        conn.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host) if parsed.scheme == "https" else raw
        request_headers = {"User-Agent": "MeitaiCompanyResearch/1.0", "Accept": "text/html,application/rss+xml,application/json,text/plain", "Accept-Encoding": "identity", "Host": host}
        request_headers.update(headers or {})
        conn.request("GET", urlunsplit(("", "", parsed.path or "/", parsed.query, "")), headers=request_headers)
        response = conn.getresponse()
        response_headers = {k.lower(): v for k, v in response.getheaders()}
        if int(response_headers.get("content-length", "0") or 0) > MAX_BYTES:
            raise ValueError("Public page exceeds size limit")
        deadline = time.monotonic() + timeout
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Public page read timed out")
            if conn.sock:
                conn.sock.settimeout(remaining)
            chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("Public page exceeds size limit")
            chunks.append(chunk)
        data = b"".join(chunks)
        return response.status, response_headers, data
    finally:
        conn.close()
        raw.close()

def fetch_public(url: str, *, timeout: float = FETCH_SECONDS, headers: dict | None = None) -> str:
    deadline = time.monotonic() + timeout
    for _ in range(4):
        validate_target(url)  # also validates redirected targets when the transport is replaced in tests
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Public fetch timed out")
        status, received, data = _request_once(url, remaining, headers)
        if status in (301, 302, 303, 307, 308):
            target = urljoin(url, received.get("location", ""))
            # API credentials must never cross a redirect.
            headers = None
            url = target
            continue
        if status != 200:
            raise ValueError("Public source is unavailable")
        media = received.get("content-type", "text/plain").lower()
        if not any(kind in media for kind in ("text/", "xml", "json", "html")):
            raise ValueError("Unsupported public content type")
        encoding = re.search(r"charset=([\w-]+)", media)
        charset = encoding.group(1) if encoding else "utf-8"
        try:
            return data.decode(charset, errors="replace")
        except LookupError:
            return data.decode("utf-8", errors="replace")
    raise ValueError("Too many redirects")

class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.hidden += 1
        elif tag in ("p", "div", "br", "li", "h1", "h2", "tr"):
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.hidden:
            self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

def extract_text(html: str) -> str:
    parser = _Text()
    parser.feed(html[:MAX_BYTES])
    return re.sub(r"[ \t\r\f\v]+", " ", unescape(" ".join(parser.parts))).strip()


class _Tables(HTMLParser):
    """Retain field/value ownership inside a single visible HTML table."""
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.hidden += 1
        elif not self.hidden:
            if tag == "table":
                self.table = []
            elif tag == "tr" and self.table is not None:
                self.row = []
            elif tag in ("td", "th") and self.row is not None:
                self.cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.hidden:
            self.hidden -= 1
        elif not self.hidden:
            if tag in ("td", "th") and self.cell is not None:
                self.row.append(" ".join(" ".join(self.cell).split()))
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.table.append(self.row)
                self.row = None
            elif tag == "table" and self.table is not None:
                self.tables.append(self.table)
                self.table = self.row = self.cell = None

    def handle_data(self, data):
        if self.cell is not None and not self.hidden:
            self.cell.append(data)


def _registry_evidence(html: str, company: str) -> str:
    parser = _Tables()
    parser.feed(html[:MAX_BYTES])
    for table in parser.tables:
        pairs = [(row[i].strip(" ：:"), row[i + 1]) for row in table for i in range(0, len(row) - 1, 2)]
        identities = [value for label, value in pairs if label in ("企业名称", "公司名称")]
        # A company heading elsewhere on the page cannot authorize another table.
        if len(identities) != 1 or normalized_name(identities[0]) != normalized_name(company):
            continue
        fields = [label + "：" + value[:550] for label, value in pairs
                  if label in ("所属行业", "注册资本", "注册地址", "经营范围")
                  and value and not has_other_subject(value, company)]
        if fields:
            return identities[0] + "。" + "。".join(fields)
    return ""

def canonical_url(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), quote(p.path or "/", safe="/%:@"), p.query, ""))

def duplicates_content(excerpt: str, accepted: list[str]) -> bool:
    compact = normalized_name(excerpt)
    return any(SequenceMatcher(None, compact, normalized_name(previous), autojunk=False).ratio() >= 0.85
               for previous in accepted)

def _entity_pattern(company: str):
    # A suffix of a longer registered name is a different entity. Match the whole
    # name at a prose boundary; be conservative when the boundary is ambiguous.
    return re.compile(r"(?<![\w\u4e00-\u9fff])" + re.escape(normalized_name(company))
                      + r"(?![\w\u4e00-\u9fff]{0,30}分公司)")

def has_other_subject(sentence: str, company: str) -> bool:
    without_target = _entity_pattern(company).sub("", normalized_name(sentence))
    return bool(re.search(
        r"子公司|旗下|关联公司|(?:[\u4e00-\u9fffA-Za-z]{2,})(?:有限公司|有限责任公司|股份公司)"
        r"|(?:^|[，,；;：:])(?:的|其)?(?:母公司|竞争对手)", without_target))

def evidence_excerpt(page: str, company: str) -> str:
    """Keep factual prose, not navigation or a company name appearing only in copyright."""
    candidates, identities = [], []
    identity_seen = False
    paragraph_break = False
    target = _entity_pattern(company)
    for sentence in re.split(r"[。！？]|(\n)", page):
        if sentence is None:
            continue
        if sentence == "\n":
            paragraph_break = True
            continue
        sentence = sentence.strip()
        if len(sentence) < 8 or re.search(r"版权|ICP备|隐私|联系我们|更多网站|Cookie", sentence, re.I):
            if sentence:
                identity_seen = False
            continue
        exact = bool(target.search(normalized_name(sentence)))
        # Do not attach other legal entities/subsidiaries to a company's name elsewhere on a page.
        if has_other_subject(sentence, company):
            identity_seen = False
            continue
        if exact:
            identity_seen = True
            identities.append(sentence)
        elif not (identity_seen and (
            re.match(r"^(?:该公司|本公司|公司)", sentence)
            or (not paragraph_break and re.match(
                r"^(?:总部|自成立以来|其(?=主营|主要|业务|产品|总部|成立|拥有|员工|营收|研发|生产)"
                r"|所属行业：|注册资本：|注册地址：|经营范围：|\d{4}年.{0,40}(?:挂牌上市|上市|成立|发布|推出))", sentence))
        )):
            identity_seen = False
            continue
        paragraph_break = False
        strong = len(re.findall(r"主营|业务涵盖|主要从事|成立于|总部|拥有|营收|员工|发布|生产|研发|上市|所属行业|注册资本|注册地址|经营范围", sentence))
        weak = len(re.findall(r"业务|服务|产品|制造|技术|公司", sentence))
        if strong or weak >= 2:
            candidates.append((strong * 10 + weak, sentence[:550]))
    if not candidates:
        return ""
    selected, seen = [], set()
    strongest = sorted(candidates, key=lambda x: -x[0])[:4]
    # Keep quote order: sorting prose can detach a continuation from its legal entity.
    for candidate in candidates:
        if candidate not in strongest:
            continue
        _, sentence = candidate
        if sentence not in seen:
            seen.add(sentence)
            selected.append(sentence)
        if len(selected) >= 4:
            break
    # An exact company identity is retained as an auditable quote, never synthesized.
    identity = identities[0][:300] if identities else ""
    excerpt = "。".join(selected)
    if normalized_name(company) not in normalized_name(selected[0]):
        excerpt = identity + "。" + excerpt
    return excerpt[:2400]

def _search_links(company: str, remaining: float) -> list[tuple[str, str]]:
    # Extra generic terms dilute legal-entity matching for some search providers.
    query = '"' + company + '"'
    provider = os.getenv("LITE_SEARCH_PROVIDER", "bing").lower()
    key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    if provider == "brave" and key:
        raw = fetch_public("https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": query, "count": 8}),
            timeout=min(remaining, FETCH_SECONDS), headers={"X-Subscription-Token": key})
        data = json.loads(raw)
        results = data.get("web", {}).get("results")
        if not isinstance(results, list):
            raise ValueError("Search provider did not return a result collection")
        return [(item["url"], item.get("title", "")) for item in results]
    raw = fetch_public("https://www.bing.com/search?" + urlencode({"q": query, "format": "rss", "setlang": "zh-hans"}),
                       timeout=min(remaining, FETCH_SECONDS))
    root = ElementTree.fromstring(raw)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Search provider did not return RSS")
    return [(item.findtext("link", ""), item.findtext("title", "")) for item in root.findall(".//item")]

def _fallback_links(company: str, remaining: float) -> list[tuple[str, str]]:
    raw = fetch_public("https://html.duckduckgo.com/html/?" + urlencode({"q": '"' + company + '"'}),
                       timeout=min(remaining, FETCH_SECONDS))
    if "result__a" not in raw and not re.search(r"no-results|no results found", raw, re.I):
        raise ValueError("Search provider returned an unrecognized page")
    links = []
    for href, title in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw, re.S):
        target = unescape(href)
        if "uddg=" in target:
            target = parse_qs(urlsplit(target).query).get("uddg", [""])[0]
        if target.startswith(("https://", "http://")) and "duckduckgo.com" not in urlsplit(target).netloc:
            links.append((target, extract_text(title)))
    return links

def research_company(company: str) -> list[dict]:
    deadline = time.monotonic() + SEARCH_SECONDS
    sources, seen, seen_content = [], set(), []
    target_name = normalized_name(company)
    search_success, page_success, candidate_count = 0, 0, 0
    for search in (_search_links, _fallback_links):
        if len(sources) >= 2 or deadline <= time.monotonic():
            break
        try:
            links = search(company, deadline - time.monotonic())
            search_success += 1
        except (OSError, ValueError, ElementTree.ParseError, http.client.HTTPException):
            continue
        for url, title in links[:10]:
            if len(sources) >= 5 or deadline <= time.monotonic():
                break
            url = canonical_url(url)
            if url in seen:
                continue
            seen.add(url)
            candidate_count += 1
            try:
                html = fetch_public(url, timeout=min(FETCH_SECONDS, deadline - time.monotonic()))
                page = extract_text(html)
                if re.search(r"captcha|verify (?:that )?you are human|security verification|人机验证|安全验证|访问过于频繁|请输入验证码", page, re.I) and not evidence_excerpt(page, company):
                    raise ValueError("Source returned a verification challenge")
                page_success += 1
            except (OSError, ValueError, http.client.HTTPException):
                continue
            # Search snippets alone are not accepted evidence. The source page must identify this legal company.
            compact = normalized_name(page)
            if target_name not in compact or len(page) < 60:
                continue
            excerpt = evidence_excerpt(_registry_evidence(html, company) or page, company)
            if not excerpt or target_name not in normalized_name(excerpt) or duplicates_content(excerpt, seen_content):
                continue
            seen_content.append(excerpt)
            host = urlsplit(url).hostname or ""
            kind = "工商百科" if any(x in host for x in ("baike", "qcc", "tianyancha", "qixin", "aiqicha")) else ("官网候选（请核对）" if "官网" in title or "官方网站" in title else "公开网页/报道")
            sources.append({"url": url, "title": title[:300] or company,
                "excerpt": excerpt, "retrieved_at": datetime.now(timezone.utc).isoformat(), "kind": kind})
    if not search_success or (candidate_count and not page_success):
        raise ResearchUnavailable("Public research is temporarily unavailable")
    return sources
