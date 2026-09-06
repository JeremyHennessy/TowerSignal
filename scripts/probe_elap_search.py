from __future__ import annotations

import json
import re
import time
from collections import Counter
from http.cookiejar import CookieJar
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse, parse_qs
from urllib.request import HTTPCookieProcessor, Request, build_opener

SEARCH_URL = "https://apps.health.ny.gov/pubdoh/applinks/wc/elappublicweb/"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"
PREFERRED_TEST_LAB = "DIST WATER QUAL OPS NYCDEP DISTRIBUTION LAB"


class ElapProbeError(RuntimeError):
    pass


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.selects: list[dict] = []
        self.links: list[str] = []
        self.forms: list[dict] = []
        self.hidden_inputs: list[dict] = []
        self._select: dict | None = None
        self._option: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value for key, value in attrs}
        tag = tag.lower()
        if tag == "form":
            self.forms.append(
                {
                    "action": attrs_dict.get("action"),
                    "method": attrs_dict.get("method"),
                    "id": attrs_dict.get("id"),
                    "name": attrs_dict.get("name"),
                }
            )
        elif tag == "select":
            self._select = {
                "id": attrs_dict.get("id"),
                "name": attrs_dict.get("name"),
                "options": [],
            }
        elif tag == "option" and self._select is not None:
            self._option = {
                "value": attrs_dict.get("value"),
                "text_parts": [],
            }
        elif tag == "input" and str(attrs_dict.get("type") or "").lower() == "hidden":
            if attrs_dict.get("name"):
                self.hidden_inputs.append(
                    {
                        "name": attrs_dict.get("name"),
                        "value": attrs_dict.get("value") or "",
                    }
                )
        elif tag == "a" and attrs_dict.get("href"):
            self.links.append(urljoin(SEARCH_URL, str(attrs_dict["href"])))

    def handle_data(self, data: str) -> None:
        if self._option is not None:
            self._option["text_parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "option" and self._option is not None and self._select is not None:
            text = re.sub(r"\s+", " ", "".join(self._option.pop("text_parts"))).strip()
            self._option["text"] = text
            self._select["options"].append(self._option)
            self._option = None
        elif tag == "select" and self._select is not None:
            self.selects.append(self._select)
            self._select = None


def _opener():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def fetch_page(opener, url: str, *, data: bytes | None = None, retries: int = 4, timeout: int = 90) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        request = Request(
            url,
            data=data,
            method="POST" if data is not None else "GET",
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Content-Type": "application/x-www-form-urlencoded" if data is not None else "text/plain",
                "Referer": SEARCH_URL,
            },
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, UnicodeError) as exc:
            last_error = exc
            if isinstance(exc, HTTPError) and 400 <= exc.code < 500:
                break
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise ElapProbeError(f"Failed to fetch ELAP public page {url}: {last_error}")


def classify_value(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "BLANK"
    if text.isdigit():
        return "INTEGER"
    if re.fullmatch(r"[A-Za-z0-9_-]+", text):
        return "TOKEN"
    if "labId=" in text or "labid=" in text.lower():
        return "LABID_URL_OR_QUERY"
    return "OTHER"


def _select_label(select: dict) -> str:
    return f"{select.get('id') or ''} {select.get('name') or ''}".strip().lower()


def _normalized(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _lab_detail_links(links: list[str]) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    for url in links:
        if "labdetail" not in url.lower():
            continue
        query = parse_qs(urlparse(url).query)
        lab_ids = query.get("labId") or query.get("labid") or []
        result.append({"url": url, "lab_id": lab_ids[0] if lab_ids else None})
    return result


def build_probe() -> dict:
    opener = _opener()
    html = fetch_page(opener, SEARCH_URL)
    if "Search NY Accredited Environmental Laboratories" not in html:
        raise ElapProbeError("ELAP search-page marker missing")
    parser = FormParser()
    parser.feed(html)
    parser.close()
    if len(parser.selects) < 5:
        raise ElapProbeError(f"Implausibly few ELAP selects: {len(parser.selects)}")

    result_selects = []
    explicit_lab_candidates = []
    for select in parser.selects:
        options = [option for option in select["options"] if option.get("text")]
        value_classes = Counter(classify_value(option.get("value")) for option in options)
        result = {
            "id": select.get("id"),
            "name": select.get("name"),
            "option_count": len(options),
            "value_class_counts": dict(sorted(value_classes.items())),
            "sample_options": [
                {"value": option.get("value"), "text": option.get("text")}
                for option in options[:8]
            ],
        }
        result_selects.append(result)
        if "lab" in _select_label(select):
            explicit_lab_candidates.append((select, options, value_classes))

    if len(explicit_lab_candidates) != 1:
        raise ElapProbeError(
            "Expected exactly one explicitly lab-named ELAP selector; "
            f"found {[(item[0].get('id'), item[0].get('name'), len(item[1])) for item in explicit_lab_candidates]}; "
            f"all_selects={[(s.get('id'), s.get('name'), len(s.get('options') or [])) for s in parser.selects]}"
        )

    lab_select, lab_options, lab_value_classes = explicit_lab_candidates[0]
    if not lab_select.get("name"):
        raise ElapProbeError(f"ELAP lab selector lacks form name: {lab_select}")
    populated = [
        option for option in lab_options
        if _normalized(option.get("value")) and _normalized(option.get("text"))
    ]
    if len(populated) < 250:
        raise ElapProbeError(f"Implausibly few populated ELAP lab options: {len(populated)}")

    name_value_options = [
        option for option in populated
        if _normalized(option.get("value")).casefold() == _normalized(option.get("text")).casefold()
    ]
    non_name_options = [option for option in populated if option not in name_value_options]
    if len(name_value_options) < 250 or len(non_name_options) > 10:
        raise ElapProbeError(
            "ELAP lab enumeration is not predominantly exact name-valued options: "
            f"name_value={len(name_value_options)} non_name={non_name_options[:10]}"
        )

    test_option = next(
        (
            option for option in name_value_options
            if _normalized(option["text"]).upper() == PREFERRED_TEST_LAB
        ),
        name_value_options[0],
    )

    if len(parser.forms) != 1:
        raise ElapProbeError(f"Expected one ELAP search form, got {parser.forms}")
    form = parser.forms[0]
    if str(form.get("method") or "").lower() != "post" or not form.get("action"):
        raise ElapProbeError(f"Unexpected ELAP search form contract: {form}")

    post_fields = {
        str(item["name"]): str(item.get("value") or "")
        for item in parser.hidden_inputs
        if item.get("name")
    }
    post_fields[str(lab_select["name"])] = str(test_option["value"])
    result_url = urljoin(SEARCH_URL, str(form["action"]))
    result_html = fetch_page(
        opener,
        result_url,
        data=urlencode(post_fields).encode("utf-8"),
    )
    result_parser = FormParser()
    result_parser.feed(result_html)
    result_parser.close()
    detail_links = _lab_detail_links(result_parser.links)
    matching_detail_links = [
        item for item in detail_links if item.get("lab_id") and str(item["lab_id"]).isdigit()
    ]
    captcha_marker = any(
        marker in result_html.lower()
        for marker in ("g-recaptcha", "recaptcha", "not a robot")
    )

    detail_resolution_status = (
        "LAB_ID_LINK_PROVEN" if matching_detail_links else
        "CAPTCHA_OR_INTERACTIVE_GATE" if captcha_marker else
        "NO_LAB_ID_LINK_RETURNED"
    )

    return {
        "search_url": SEARCH_URL,
        "html_byte_count": len(html.encode("utf-8")),
        "form_count": len(parser.forms),
        "forms": parser.forms,
        "select_count": len(parser.selects),
        "selects": result_selects,
        "lab_selector": {
            "id": lab_select.get("id"),
            "name": lab_select.get("name"),
            "option_count": len(lab_options),
            "populated_option_count": len(populated),
            "exact_name_value_option_count": len(name_value_options),
            "non_name_value_options": non_name_options[:10],
            "value_class_counts": dict(sorted(lab_value_classes.items())),
            "first_10": [
                {"value": option.get("value"), "text": option.get("text")}
                for option in populated[:10]
            ],
        },
        "detail_resolution_probe": {
            "test_lab_name": test_option["text"],
            "test_lab_value": test_option["value"],
            "form_field_name": lab_select["name"],
            "result_url": result_url,
            "captcha_marker": captcha_marker,
            "detail_resolution_status": detail_resolution_status,
            "lab_detail_links": matching_detail_links[:10],
        },
    }


def main() -> None:
    print(json.dumps(build_probe(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
