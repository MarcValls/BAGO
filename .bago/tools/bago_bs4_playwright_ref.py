import html
import json
import re
import threading
import time
import urllib.parse
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def _slugify(value: str) -> str:
    """Create a URL-friendly slug from a string."""
    if not value:
        return "unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "unknown"


def _normalize_seedfinder_text(value: str) -> str:
    return value.replace("\r", "").replace("\u00a0", " ").strip()


def _dedupe_tags(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        token = item.strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out


def _extract_degustation_tags(raw_text: str | None) -> dict[str, list[str]]:
    if not raw_text:
        return {"effects": [], "aromas": [], "flavors": []}

    normalized = _normalize_seedfinder_text(raw_text)
    if not normalized:
        return {"effects": [], "aromas": [], "flavors": []}

    lines = [line.strip() for line in normalized.split("\n") if line.strip()]

    def _global_stop(line: str) -> bool:
        return bool(
            re.search(
                r"(Gallery|Comparisons|Lineage\s*/\s*Genealogy|Hybrids|User comments|Threads|Videos|Pictures|Known Phenotypes|Medical Values|Do you find mistakes|Upload your info|Basic infos)",
                line,
                re.IGNORECASE,
            )
        )

    def _noise_line(line: str) -> bool:
        return bool(
            re.match(
                r"(view all|no data available|none up to now|add a phenotype|altogether we've collected)",
                line,
                re.IGNORECASE,
            )
        )

    def _collect(start_idx: int, stop_regexes: list[re.Pattern]) -> list[str]:
        if start_idx < 0:
            return []
        out: list[str] = []
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if any(rx.search(line) for rx in stop_regexes):
                break
            if _global_stop(line):
                break
            if _noise_line(line):
                continue
            if len(line) > 60:
                continue
            out.append(line)
            if len(out) >= 12:
                break
        return _dedupe_tags(out)

    effect_idx = next((i for i, line in enumerate(lines) if re.match(r"^Effect\s*/\s*Effectiveness$", line, re.IGNORECASE)), -1)
    aroma_idx = next((i for i, line in enumerate(lines) if re.match(r"^Smell\s*/\s*Aroma$", line, re.IGNORECASE)), -1)
    taste_idx = next((i for i, line in enumerate(lines) if re.match(r"^Taste$", line, re.IGNORECASE)), -1)

    effects = _collect(effect_idx, [re.compile(r"^Smell\s*/\s*Aroma$", re.IGNORECASE), re.compile(r"^Taste$", re.IGNORECASE)])
    aromas = _collect(aroma_idx, [re.compile(r"^Taste$", re.IGNORECASE)])
    flavors = _collect(taste_idx, [re.compile(r"(Gallery|Comparisons|Lineage\s*/\s*Genealogy|Hybrids)", re.IGNORECASE)])

    return {"effects": effects, "aromas": aromas, "flavors": flavors}


class SeedfinderClient:
    """
    Small client to query the SeedFinder Livewire search endpoint without hammering the site.
    - Single session reused
    - Throttled (min_interval seconds between hits)
    - Simple in-memory cache with TTL
    """

    def __init__(
        self,
        base_url: str = "https://seedfinder.eu",
        user_agent: str = "GeneMapsProxy/1.0 (+mailto:genemapsv1@gmail.com)",
        min_interval: float = 3.0,
        cache_ttl: float = 60 * 60 * 6,  # 6 hours
    ):
        self.base_url = base_url.rstrip("/")
        self.search_page = f"{self.base_url}/en/search/"
        self.update_endpoint = f"{self.base_url}/livewire/update"
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.cache_ttl = cache_ttl

        self._session = requests.Session()
        self._lock = threading.Lock()
        self._last_call = 0.0
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _throttle(self):
        with self._lock:
            now = time.time()
            delta = now - self._last_call
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last_call = time.time()

    def _cached(self, key: str):
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() - entry["time"] > self.cache_ttl:
            self._cache.pop(key, None)
            return None
        return entry["value"]

    def _set_cache(self, key: str, value: Any):
        self._cache[key] = {"value": value, "time": time.time()}

    def search(self, query: str) -> List[Dict[str, Any]]:
        q = query.strip()
        if not q:
            return []

        cached = self._cached(q.lower())
        if cached is not None:
            return cached

        self._throttle()
        resp = self._session.get(
            self.search_page,
            headers={"User-Agent": self.user_agent},
            timeout=15,
        )
        resp.raise_for_status()

        csrf = self._extract_csrf(resp.text)
        snapshot = self._extract_snapshot(resp.text)

        payload = self._build_payload(snapshot, q)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json",
            "X-Livewire": "true",
            "X-CSRF-TOKEN": csrf,
            "X-XSRF-TOKEN": self._xsrf_cookie(),
            "Referer": self.search_page,
            "X-Requested-With": "XMLHttpRequest",
        }

        search_resp = self._session.post(
            self.update_endpoint,
            json=payload,
            headers=headers,
            timeout=20,
        )

        # Fail fast on CSRF/429/etc to avoid hammering.
        search_resp.raise_for_status()
        data = search_resp.json()

        candidates = self._parse_candidates(data)
        if candidates:
            self._set_cache(q.lower(), candidates)
            return candidates

        # Fallback to Playwright if Livewire path returns empty
        try:
            candidates = self._search_with_playwright(q)
            if candidates:
                self._set_cache(q.lower(), candidates)
            return candidates
        except Exception:
            return []

    def _xsrf_cookie(self) -> str:
        # Livewire expects the raw (unquoted) XSRF token if present
        for domain in [urllib.parse.urlparse(self.base_url).hostname, "seedfinder.eu"]:
            token = self._session.cookies.get("XSRF-TOKEN", domain=domain)
            if token:
                return urllib.parse.unquote(token)
        return ""

    def _extract_csrf(self, html_text: str) -> str:
        m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html_text)
        if not m:
            raise RuntimeError("CSRF token not found in search page")
        return m.group(1)

    def _extract_snapshot(self, html_text: str) -> Dict[str, Any]:
        snapshots = re.findall(r'wire:snapshot="([^"]+)"', html_text)
        for snap in snapshots:
            obj = json.loads(html.unescape(snap))
            if obj.get("memo", {}).get("name") == "frontend.extended-search":
                return obj
        raise RuntimeError("Livewire snapshot for extended-search not found")

    def _build_payload(self, snapshot: Dict[str, Any], query: str) -> Dict[str, Any]:
        fingerprint = snapshot["memo"]
        server_memo = {
            # htmlHash is optional in many Livewire setups; checksum is required
            "htmlHash": snapshot.get("checksum"),
            "data": snapshot["data"],
            "dataMeta": {},
            "children": [],
            "errors": [],
            "locale": fingerprint.get("locale"),
            "checksum": snapshot["checksum"],
        }

        updates = [
            {"type": "syncInput", "payload": {"id": "search", "value": query, "dataPath": "search"}},
            {"type": "callMethod", "payload": {"method": "submitSearch", "params": []}},
        ]

        return {
            "fingerprint": fingerprint,
            "serverMemo": server_memo,
            "updates": updates,
        }

    def _parse_candidates(self, response_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Try to extract candidates either from serverMemo->data or from the HTML patch.
        """
        # 1) Direct data in server memo (if component exposes it)
        server_data = response_json.get("serverMemo", {}).get("data", {})
        if "results" in server_data and isinstance(server_data["results"], list):
            return [self._normalize_candidate(item) for item in server_data["results"]]

        # 2) HTML fragment in effects.html
        html_fragment = ""
        effects = response_json.get("effects") or {}
        for key in ("html", "snapshot", "rendered", "body"):
            if effects.get(key):
                html_fragment = effects[key]
                break
        if not html_fragment and response_json.get("components"):
            # Some Livewire setups return components[0].effects.html
            comp = response_json["components"][0]
            html_fragment = (comp.get("effects") or {}).get("html", "")

        if html_fragment:
            soup = BeautifulSoup(html_fragment, "html.parser")
            rows = soup.select("tr")
            candidates = []
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                
                # Extract URL from the first cell's link
                link = cells[0].find("a")
                url = link.get("href") if link else None

                name = cells[0].get_text(strip=True)
                breeder = cells[1].get_text(strip=True)
                
                # Extract other cells text
                cell_texts = [c.get_text(strip=True) for c in cells]
                
                candidates.append(
                    self._normalize_candidate(
                        {
                            "name": name,
                            "breeder": breeder,
                            "url": url,
                            "genetics": cell_texts[2] if len(cell_texts) > 2 else None,
                            "type": None,
                            "flowering_time": None,
                            "thc_content": None,
                            "cbd_content": None,
                            "description": None,
                            "terpenes": None,
                        }
                    )
                )
            if candidates:
                return candidates

        # 3) Nothing parsed
        return []

    def _normalize_candidate(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        name = raw.get("name") or ""
        breeder = raw.get("breeder") or ""
        # SeedFinder search UI exposes a "Feminized" column; in some parsing paths we store
        # it under `feminized`/`feminised`. Keep backward-compat by mapping it to `type`.
        type_value = raw.get("type") or raw.get("feminized") or raw.get("feminised")
        return {
            "name": name,
            "breeder": breeder,
            "url": raw.get("url"),
            "strain_slug": _slugify(name),
            "breeder_slug": _slugify(breeder),
            "genetics": raw.get("genetics"),
            "type": type_value,
            "flowering_time": raw.get("flowering_time"),
            "thc_content": raw.get("thc_content"),
            "cbd_content": raw.get("cbd_content"),
            "description": raw.get("description"),
            "terpenes": raw.get("terpenes"),
        }

    def fetch_strain_details(self, url: str) -> Dict[str, Any]:
        """
        Fetches the detail page to get the image URL, full description, and lineage.
        """
        if not url:
            return {"image_url": None, "full_description": None, "lineage": None, "degustation": None}

        self._throttle()
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"
        
        try:
            resp = self._session.get(full_url, headers={"User-Agent": self.user_agent}, timeout=15)
            resp.raise_for_status()
            html_content = resp.text
            soup = BeautifulSoup(html_content, "html.parser")

            # 1. Extract Image URL
            image_url = None
            # Try regex for AlpineJS bound src
            match = re.search(r"selectedIndex === -1 \? '([^']+)'", html_content)
            if match:
                image_url = match.group(1)
            else:
                # Fallback: look for the main image
                img = soup.find("img", class_="w-full h-full rounded-lg object-contain")
                if img:
                    image_url = img.get("src")

            # 2. Extract Full Description
            # Grab text from all .card elements as a heuristic for "all original info"
            description_parts = []
            cards = soup.find_all("div", class_="card")
            for card in cards:
                # Clean up text
                text = card.get_text(strip=True, separator="\n")
                if len(text) > 20: 
                    description_parts.append(text)
            
            full_description = "\n\n".join(description_parts)
            degustation = _extract_degustation_tags(full_description)
            if not any(degustation.values()):
                degustation = None

            # 3. Extract Lineage / Genealogy
            lineage = self._extract_lineage(soup, html_content)

            return {
                "image_url": image_url,
                "full_description": full_description,
                "lineage": lineage,
                "degustation": degustation,
            }

        except Exception as e:
            # print(f"Error fetching details for {url}: {e}")
            return {"image_url": None, "full_description": None, "lineage": None, "degustation": None}

    def _extract_lineage(self, soup: BeautifulSoup, html_content: str) -> Dict[str, Any]:
        """
        Extract lineage/genealogy data from the strain page.
        Returns a dict with parents list and raw lineage text.
        """
        lineage_data = {
            "parents": [],
            "raw_text": None,
            "hybrids": [],
        }
        
        try:
            # Find the Lineage section by looking for the heading
            # The section typically has an id like "lineage" or contains "Lineage" text
            lineage_section = None
            
            # Look for section with "Lineage" or "Genealogy" in heading
            for h3 in soup.find_all(["h3", "h4"]):
                text = h3.get_text(strip=True).lower()
                if "lineage" in text or "genealogy" in text:
                    # Get the parent container or next sibling
                    lineage_section = h3.find_parent("section") or h3.find_parent("div")
                    break
            
            if lineage_section:
                # Extract all strain links from the lineage section
                links = lineage_section.find_all("a", href=True)
                seen_parents = set()  # Track by name
                seen_slugs = set()    # Also track by slug to avoid duplicates
                
                for link in links:
                    href = link.get("href", "")
                    if "/strain-info/" in href or "/strain/" in href:
                        name = link.get_text(strip=True)
                        # Clean up name - remove newlines and extra whitespace
                        name = " ".join(name.split())
                        if not name or name in seen_parents or len(name) < 2:
                            continue
                        # Skip if it looks like navigation text
                        if any(skip in name.lower() for skip in ["genealogy page", "view all", "click here", "learn more"]):
                            continue
                        
                        # Parse breeder_slug and strain_slug from URL
                        # Format: /en/strain-info/{strain_slug}/{breeder_slug}
                        parts = href.rstrip("/").split("/")
                        strain_slug = None
                        breeder_slug = None
                        
                        if len(parts) >= 2:
                            # URL pattern: .../strain-info/strain-slug/breeder-slug
                            if "strain-info" in parts or "strain" in parts:
                                idx = parts.index("strain-info") if "strain-info" in parts else parts.index("strain")
                                if idx + 2 < len(parts):
                                    strain_slug = parts[idx + 1]
                                    breeder_slug = parts[idx + 2]
                                elif idx + 1 < len(parts):
                                    strain_slug = parts[idx + 1]
                        
                        # Deduplicate by strain_slug + breeder_slug combo
                        slug_key = f"{strain_slug}|{breeder_slug}"
                        if slug_key in seen_slugs:
                            continue
                        
                        seen_parents.add(name)
                        seen_slugs.add(slug_key)
                        
                        lineage_data["parents"].append({
                            "name": name,
                            "strain_slug": strain_slug,
                            "breeder_slug": breeder_slug,
                            "url": href if href.startswith("http") else f"https://seedfinder.eu{href}",
                        })
                
                # Get raw lineage text for reference
                lineage_data["raw_text"] = lineage_section.get_text(strip=True, separator=" ")[:2000]
            
            # Also look for "Hybrids & Crossbreeds" section
            for h3 in soup.find_all(["h3", "h4"]):
                text = h3.get_text(strip=True).lower()
                if "hybrid" in text or "crossbreed" in text:
                    hybrid_section = h3.find_parent("section") or h3.find_parent("div")
                    if hybrid_section:
                        links = hybrid_section.find_all("a", href=True)
                        for link in links:
                            href = link.get("href", "")
                            if "/strain-info/" in href or "/strain/" in href:
                                name = link.get_text(strip=True)
                                if name and name not in [p["name"] for p in lineage_data["hybrids"]]:
                                    lineage_data["hybrids"].append({
                                        "name": name,
                                        "url": href if href.startswith("http") else f"https://seedfinder.eu{href}",
                                    })
                    break
                    
        except Exception as e:
            print(f"Error extracting lineage: {e}")
        
        return lineage_data if lineage_data["parents"] else None

    def _search_with_playwright(self, query: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self.user_agent)
            page = context.new_page()
            page.goto("https://seedfinder.eu/en/search/", wait_until="domcontentloaded")

            page.fill('input[placeholder="Search Seeds"]', query)
            page.get_by_role("button", name="Search").click()
            page.wait_for_timeout(5000)

            rows = page.query_selector_all("table tr")
            for row in rows[1:]:  # skip header
                cells = row.query_selector_all("td")
                if not cells:
                    continue
                
                # Extract URL
                link_el = cells[0].query_selector("a")
                url = link_el.get_attribute("href") if link_el else None

                values = [c.inner_text().strip() for c in cells]
                # Expected order: Strain name, Breeder, Flowering time, Heritage, Feminized
                name = values[0] if len(values) > 0 else None
                breeder = values[1] if len(values) > 1 else None
                flowering_time = values[2] if len(values) > 2 else None
                heritage = values[3] if len(values) > 3 else None
                feminized = values[4] if len(values) > 4 else None
                results.append(
                    self._normalize_candidate(
                        {
                            "name": name,
                            "breeder": breeder,
                            "url": url,
                            "genetics": heritage,
                            "flowering_time": flowering_time,
                            "type": None,
                            "thc_content": None,
                            "cbd_content": None,
                            "description": None,
                            "terpenes": None,
                            "feminized": feminized,
                        }
                    )
                )

            browser.close()
        return results


client = SeedfinderClient()


def search_seedfinder(query: str) -> List[Dict[str, Any]]:
    return client.search(query)
