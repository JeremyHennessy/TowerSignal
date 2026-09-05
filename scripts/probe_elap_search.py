from __future__ import annotations

import json
import re
import time
from collections import Counter
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

SEARCH_URL = "https://apps.health.ny.gov/pubdoh/applinks/wc/elappublicweb/"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"


class ElapProbeError(RuntimeError):
    pass


class SelectParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.selects: list[dict] = []
        self.links: list[str] = []
        self.forms: list[dict] = []
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


def fetch_html(*, retries: int = 4, timeout: int = 90) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        request = Request(
            SEARCH_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, UnicodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise ElapProbeError(f"Failed to fetch ELAP public search page: {last_error}")


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


def build_probe() -> dict:
    html = fetch_html()
    if "Search NY Accredited Environmental Laboratories" not in html:
        raise ElapProbeError("ELAP search-page marker missing")
    parser = SelectParser()
    parser.feed(html)
    parser.close()
    if len(parser.selects) < 5:
        raise ElapProbeError(f"Implausibly few ELAP selects: {len(parser.selects)}")

    result_selects = []
    lab_candidates = []
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
        joined = f"{select.get('id') or ''} {select.get('name') or ''}".lower()
        if "lab" in joined or len(options) > 200:
            lab_candidates.append((select, options, value_classes))

    if not lab_candidates:
        raise ElapProbeError("Could not identify ELAP laboratory selector")
    lab_select, lab_options, lab_value_classes = max(lab_candidates, key=lambda item: len(item[1]))
    nonblank_options = [option for option in lab_options if str(option.get("value") or "").strip()]
    stable_value_count = sum(
        1
        for option in nonblank_options
        if classify_value(option.get("value")) in {"INTEGER", "TOKEN", "LABID_URL_OR_QUERY"}
    )
    if len(nonblank_options) < 250:
        raise ElapProbeError(f"Implausibly few populated ELAP lab options: {len(nonblank_options)}")
    if stable_value_count != len(nonblank_options):
        raise ElapProbeError(
            f"ELAP lab selector contains unsupported option-value shapes: "
            f"{dict(sorted(lab_value_classes.items()))}"
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
            "populated_option_count": len(nonblank_options),
            "value_class_counts": dict(sorted(lab_value_classes.items())),
            "first_20": [
                {"value": option.get("value"), "text": option.get("text")}
                for option in nonblank_options[:20]
            ],
            "last_5": [
                {"value": option.get("value"), "text": option.get("text")}
                for option in nonblank_options[-5:]
            ],
        },
        "links_with_labdetail": [url for url in parser.links if "labdetail" in url.lower()][:20],
    }


def main() -> None:
    print(json.dumps(build_probe(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
