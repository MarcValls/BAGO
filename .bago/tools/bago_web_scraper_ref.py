"""

Scraper usando el cliente SeedFinder (Playwright fallback).

- Modo rápido (por defecto): queries populares para poblar un catálogo básico.
- Modo completo (--full): itera a-z y 0-9 para intentar cubrir todas las cepas.
- Deduplica por (name, breeder) y guarda en backend/data/strains.json.

Uso:
  python3 scripts/seedfinder_scraper.py                   # rápido
  python3 scripts/seedfinder_scraper.py --full            # intentar todas (más lento)
  python3 scripts/seedfinder_scraper.py --full --quiet    # silencioso (solo resumen final)
"""

import argparse
import json
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

import sys
import re
import time
import requests
import shutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from backend.seedfinder import SeedfinderClient  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend.schemas_ingest import ScrapedStrainIngest  # noqa: E402
from backend.services.ingest import ingest_scraped_strain  # noqa: E402

OUT_PATH = Path(__file__).resolve().parents[1] / "backend" / "data" / "strains.json"
IMAGES_DIR = Path(__file__).resolve().parents[1] / "backend" / "data" / "images"
PROGRESS_PATH = Path(__file__).resolve().parents[1] / "backend" / "data" / "scraper_progress.json"
SEEDFINDER_BASE_URL = "https://seedfinder.eu"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "unknown"


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "")
    text = re.sub(r"[^0-9.]+", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_seedfinder_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    u = str(url).strip()
    if not u:
        return None
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("/"):
        return f"{SEEDFINDER_BASE_URL}{u}"
    return f"{SEEDFINDER_BASE_URL}/{u}"


def _normalize_tag_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    out: List[str] = []
    seen = set()
    for item in values:
        token = str(item).strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out


def load_existing(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data.get("strains", [])
    except Exception:
        return []


def load_progress() -> dict:
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text())
        except Exception:
            pass
    return {}


def save_progress(last_query_idx: int, mode: str):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps({
        "last_query_idx": last_query_idx,
        "mode": mode,
        "timestamp": time.time()
    }))


def scrape_all(
    full: bool = False,
    min_interval: float = 0.2,
    quiet: bool = False,
    log: Optional[Path] = None,
    checkpoint: bool = False,
    out_path: Path = OUT_PATH,
    count_only: bool = False,
    resume: bool = False,
    letter: Optional[str] = None,
    burst: Optional[int] = None,
    depth: str = "shallow",  # shallow: ficha básica; deep: detalle (imagen/descripcion/linaje)
    download_images: bool = False,
) -> List[Dict]:
    if letter:
        queries = [letter]
    elif full:
        # A-Z, 0-9, and popular queries to ensure coverage
        queries = list(string.ascii_lowercase + string.digits)
        queries.extend(["kush", "haze", "skunk", "gelato", "cookies", "purple", "cheese", "diesel", "glue", "cake", "runtz", "zkittlez", "wedding", "gorilla", "blue", "white", "northern", "lights", "jack", "herer", "widow", "sour", "lemon", "orange", "cherry", "banana", "strawberry", "grape", "mango", "pineapple", "papaya", "guava", "melon", "berry", "punch", "sherbet", "mint", "breath", "driver", "sundae", "slurricane", "mac", "gmo", "dosidos", "mimosa", "biscotti", "gushers", "jealousy", "gary", "payton", "cereal", "milk", "apple", "fritter", "pancakes", "waffle", "pie", "tart", "candy", "sugar", "sweet", "cream", "butter", "dough", "batter", "badder", "crumble", "shatter", "wax", "oil", "hash", "rosin", "resin", "kief", "bud", "flower", "leaf", "plant", "tree", "root", "seed", "clone", "cutting", "mother", "father", "male", "female", "hermaphrodite", "auto", "fast", "early", "late", "regular", "feminized", "cbd", "thc", "cbg", "cbn", "thcv", "cbdv", "terpene", "myrcene", "limonene", "caryophyllene", "pinene", "linalool", "humulene", "terpinolene", "ocimene", "nerolidol", "bisabolol", "guaiol", "valencene", "farnesene", "phellandrene", "carene", "camphene", "sabinene", "cymene", "eucalyptol", "borneol", "fenchol", "pulegone", "geraniol", "citronellol", "isopulegol", "camphor", "menthol", "cedrol", "elemol", "germacrene", "viridiflorol", "spathulenol", "globulol", "ledol", "palustrol", "widdrol", "cubebol", "copaene", "cadinene", "selinene", "muurolene", "amorphene", "calamenene", "gurjunene", "aromadendrene", "alloaromadendrene", "longifolene", "isolongifolene", "sativene", "cycloso"])
    else:
        queries = ["kush", "haze", "skunk", "gelato"]
    
    total_queries = len(queries)
    client = SeedfinderClient(min_interval=min_interval, cache_ttl=0)
    want_details = depth == "deep"
    run_started_at = datetime.now(timezone.utc).isoformat()
    
    collected: List[Dict] = []
    start_idx = 0
    db = SessionLocal()
    
    if letter:
        # If scraping a specific letter, we always want to append/update existing data
        collected = load_existing(out_path)
    elif resume:
        collected = load_existing(out_path)
        prog = load_progress()
        # Only resume if mode matches roughly (full vs quick)
        # We use 'full' flag as mode identifier
        saved_mode = prog.get("mode")
        current_mode = "full" if full else "quick"
        
        if saved_mode == current_mode:
            start_idx = prog.get("last_query_idx", -1) + 1
            if start_idx >= total_queries:
                print("Scraper already finished this sequence.")
                return collected
            print(f"Resuming from query index {start_idx} ('{queries[start_idx]}')...")
        else:
            print("Mode mismatch or no progress found. Starting from 0.")
    elif checkpoint:
        # If checkpoint is on but NOT resume, we might want to start fresh but save incrementally.
        # However, load_existing would load previous data if we don't clear it.
        # The caller (server.py) should handle clearing files if resume=False.
        # But for safety, if not resume, we start with empty list in memory.
        collected = []

    index_by_slug = {}
    for idx, item in enumerate(collected):
        strain_slug = item.get("strain_slug")
        breeder_slug = item.get("breeder_slug")
        if strain_slug and breeder_slug:
            index_by_slug[(breeder_slug, strain_slug)] = idx
    count_seen = set(index_by_slug.keys())
    
    # Use a queue for queries to allow dynamic addition (recursive scraping)
    query_queue = list(queries)
    processed_queries = set()
    
    # If resuming, we need to skip already processed queries
    if resume and start_idx > 0:
        # This logic is a bit tricky with a dynamic queue.
        # If we are resuming a "full" scrape, we assume the initial list is the same.
        # We just skip the first N items.
        # But if we added dynamic items, we lost them.
        # For simplicity, resume only skips the initial static list.
        # Dynamic items will be re-discovered.
        pass

    current_idx = 0
    processed_in_session = 0

    while current_idx < len(query_queue):
        if burst and processed_in_session >= burst:
            print(f"BURST LIMIT REACHED: Processed {processed_in_session} queries. Stopping.")
            break

        q = query_queue[current_idx]
        current_idx += 1
        
        # Skip if already processed (deduplication for dynamic queries)
        if q in processed_queries:
            continue
        processed_queries.add(q)
        
        # Resume logic: skip until we reach start_idx
        # Only applies to the initial set of queries
        if resume and current_idx <= start_idx:
             continue

        processed_in_session += 1
        # Respetar intervalo ético
        if current_idx > 1:
            time.sleep(min_interval)

        try:
            # Usamos Playwright porque la ruta Livewire puede devolver vacío
            results = client._search_with_playwright(q)  # type: ignore
        except Exception as exc:
            print(f"Error fetching '{q}': {exc}")
            continue
        
        new_items = 0
        total_results = len(results)
        for i, item in enumerate(results):
            name = (item.get("name") or "").strip()
            breeder = (item.get("breeder") or "").strip()
            if not name:
                continue

            strain_slug = _slugify(name)
            breeder_slug = _slugify(breeder) if breeder else "unknown"
            slug_key = (breeder_slug, strain_slug)

            if count_only:
                if slug_key in count_seen:
                    continue
                count_seen.add(slug_key)
                collected.append({"_count_only": True})
                continue

            existing_idx = index_by_slug.get(slug_key)
            existing = collected[existing_idx] if existing_idx is not None else None
            original_url = _normalize_seedfinder_url(item.get("url")) or existing.get("original_url") if existing else None

            new_items += 1 if existing is None else 0
            
            # --- RECURSIVE DEPTH: Add parents to queue ---
            if full:
                genetics = item.get("genetics") or ""
                # Simple heuristic: split by common separators and add to queue
                # Avoid adding common words or too short strings
                potential_parents = re.split(r"[\s\+\/xX]+", genetics)
                for p in potential_parents:
                    p_clean = p.strip("()[]{},.-_").lower()
                    if len(p_clean) > 3 and p_clean not in processed_queries and p_clean not in query_queue:
                        # Filter out common noise words
                        if p_clean not in ["unknown", "strain", "clone", "seed", "cut", "ibl", "bx1", "bx2", "f1", "f2", "auto", "fem", "reg"]:
                            query_queue.append(p_clean)
            # ---------------------------------------------

            record = dict(existing) if isinstance(existing, dict) else {}
            record.update(
                {
                    "name": name,
                    "breeder": breeder or record.get("breeder"),
                    "strain_slug": strain_slug,
                    "breeder_slug": breeder_slug,
                    "genetics": item.get("genetics") or record.get("genetics"),
                    "type": item.get("type") or record.get("type"),
                    "thc_content": item.get("thc_content") or record.get("thc_content"),
                    "cbd_content": item.get("cbd_content") or record.get("cbd_content"),
                    "terpenes": item.get("terpenes") or record.get("terpenes"),
                    "flowering_time": item.get("flowering_time") or record.get("flowering_time"),
                    "original_url": original_url,
                    "raw_source": item,
                }
            )

            # --- Step 1: ficha básica (identidad + evidencia + metadatos de fuente)
            sources = record.get("sources")
            if not isinstance(sources, list):
                sources = []
            source_entry = {
                "source": "seedfinder",
                "url": original_url,
                "scraped_at": run_started_at,
                "query": q,
                "depth": depth,
            }
            if original_url and not any(
                isinstance(s, dict) and s.get("source") == "seedfinder" and s.get("url") == original_url
                for s in sources
            ):
                sources.append(source_entry)
            record["sources"] = sources

            evidence_urls = record.get("evidence_urls")
            if not isinstance(evidence_urls, list):
                evidence_urls = []
            if original_url and original_url not in evidence_urls:
                evidence_urls.append(original_url)
            record["evidence_urls"] = evidence_urls

            # --- Step 2: enrich (opcional) de detalles (imagen/descripcion/linaje)
            details = {"image_url": None, "full_description": None, "lineage": None}
            should_fetch_details = want_details and bool(original_url) and not record.get("detail_cached")
            if should_fetch_details:
                try:
                    details = client.fetch_strain_details(original_url)  # type: ignore[arg-type]
                except Exception as e:
                    print(f"Error fetching details for {name}: {e}")

            if should_fetch_details and details.get("full_description"):
                record["full_description"] = details["full_description"]
                # Backward-compat: many UIs use description when full_description is missing.
                record["description"] = record.get("description") or details["full_description"]

            if should_fetch_details and details.get("lineage"):
                record["lineage"] = details.get("lineage")

            if should_fetch_details and details.get("degustation"):
                degustation = details.get("degustation")
                if isinstance(degustation, dict):
                    effects = _normalize_tag_list(degustation.get("effects"))
                    aromas = _normalize_tag_list(degustation.get("aromas"))
                    flavors = _normalize_tag_list(degustation.get("flavors"))
                    if effects:
                        record["effects"] = effects
                    tasting_notes = _normalize_tag_list(flavors + aromas)
                    if tasting_notes:
                        record["tasting_notes"] = tasting_notes

            if should_fetch_details and details.get("image_url"):
                img_url = _normalize_seedfinder_url(details.get("image_url"))
                if download_images:
                    try:
                        img_dir = IMAGES_DIR / breeder_slug
                        img_dir.mkdir(parents=True, exist_ok=True)
                        img_filename = f"{strain_slug}.jpg"
                        img_file = img_dir / img_filename

                        if img_file.exists():
                            record["image_path"] = f"images/{breeder_slug}/{img_filename}"
                        elif img_url:
                            r = requests.get(
                                str(img_url),
                                stream=True,
                                headers={"User-Agent": client.user_agent},
                                timeout=10,
                            )
                            if r.status_code == 200:
                                with open(img_file, "wb") as f:
                                    r.raw.decode_content = True
                                    shutil.copyfileobj(r.raw, f)
                                record["image_path"] = f"images/{breeder_slug}/{img_filename}"
                            else:
                                record["image_path"] = img_url
                    except Exception as e:
                        print(f"Error downloading image for {name}: {e}")
                        if img_url and (not record.get("image_path") or str(record.get("image_path", "")).startswith("http")):
                            record["image_path"] = img_url
                elif img_url:
                    if not record.get("image_path") or str(record.get("image_path", "")).startswith("http"):
                        record["image_path"] = img_url

            if should_fetch_details:
                record["detail_cached"] = True

            if existing_idx is None:
                collected.append(record)
                index_by_slug[slug_key] = len(collected) - 1
            else:
                collected[existing_idx] = record

            # Build parents list from lineage data (deep mode only)
            parents_list = []
            lineage = record.get("lineage")
            if want_details and isinstance(lineage, dict) and lineage.get("parents"):
                for parent in lineage["parents"][:10]:  # Limit to first 10 parents
                    if not isinstance(parent, dict):
                        continue
                    parents_list.append(
                        {
                            "name": parent.get("name", "Unknown"),
                            "breeder_name": None,
                            "breeder_slug": parent.get("breeder_slug"),
                            "strain_slug": parent.get("strain_slug"),
                            "is_landrace": False,
                            "notes": None,
                        }
                    )

            try:
                if original_url:
                    effects_payload = _normalize_tag_list(record.get("effects")) if want_details else []
                    tasting_payload = _normalize_tag_list(record.get("tasting_notes")) if want_details else []
                    payload = ScrapedStrainIngest(
                        name=name,
                        strain_slug=strain_slug,
                        breeder_name=breeder or "Unknown",
                        breeder_slug=breeder_slug,
                        original_url=original_url,
                        image_path=record.get("image_path"),
                        type_category=None,
                        genetics_raw=record.get("genetics"),
                        terpenes_raw=record.get("terpenes"),
                        thc_content=_to_float(record.get("thc_content")),
                        cbd_content=_to_float(record.get("cbd_content")),
                        flowering_time=record.get("flowering_time"),
                        flowering_days=None,
                        # Avoid overwriting arrays on shallow runs.
                        effects=effects_payload,
                        tasting_notes=tasting_payload,
                        source_data=({**item, "lineage": lineage} if lineage else item) if want_details else None,
                        parents=parents_list,
                    )
                    ingest_scraped_strain(db, payload)
            except Exception as ingest_err:
                db.rollback()
                print(f"[ingest] Error guardando {name} ({breeder}): {ingest_err}")

            # Real-time progress update
            progress = (current_idx / len(query_queue)) * 100
            msg = f"PROGRESS:{progress:.1f}|QUERY:{q} ({i+1}/{total_results})|FOUND:{len(results)}|TOTAL:{len(collected)}|QUEUE:{len(query_queue)}"
            if not quiet:
                print(msg)

        progress = (current_idx / len(query_queue)) * 100
        msg = f"PROGRESS:{progress:.1f}|QUERY:{q}|FOUND:{len(results)}|TOTAL:{len(collected)}|QUEUE:{len(query_queue)}"
        
        if not quiet:
            print(msg)
        if log:
            with log.open("a") as lf:
                lf.write(msg + "\n")
        
        # Save progress state
        save_progress(current_idx, "full" if full else "quick")

        if checkpoint and not count_only:
            save_to_json(collected, out_path)
            
    db.close()
    return collected


def save_to_json(strains: List[Dict], path: Path = OUT_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    enriched = []
    for idx, s in enumerate(strains, start=1):
        if "_count_only" in s: continue
        enriched.append({"id": idx, **s})
    path.write_text(json.dumps({"strains": enriched}, ensure_ascii=False, indent=2))
    print(f"Wrote {len(enriched)} strains to {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape SeedFinder catalog")
    parser.add_argument("--full", action="store_true", help="Iterar a-z0-9 (más lento, más peticiones)")
    parser.add_argument("--interval", type=float, default=0.2, help="Intervalo mínimo entre consultas (s)")
    parser.add_argument("--quiet", action="store_true", help="Modo silencioso (solo resumen final)")
    parser.add_argument("--logfile", type=Path, default=None, help="Ruta opcional para log de progreso")
    parser.add_argument("--checkpoint", action="store_true", help="Guardar avances parciales en el JSON cada query")
    parser.add_argument("--count-only", action="store_true", help="Solo contar, no guardar detalles")
    parser.add_argument("--resume", action="store_true", help="Continuar desde la última query guardada")
    parser.add_argument("--letter", type=str, default=None, help="Scrape specific letter only")
    parser.add_argument("--burst", type=int, default=None, help="Stop after N queries (burst mode)")
    parser.add_argument(
        "--depth",
        type=str,
        default="shallow",
        choices=["shallow", "deep"],
        help="shallow: ficha básica; deep: detalle (imagen/descripcion/linaje)",
    )
    parser.add_argument(
        "--download-images",
        action="store_true",
        help="Descargar imagenes y guardarlas localmente (si no, se guarda la URL remota).",
    )
    args = parser.parse_args()

    strains = scrape_all(
        full=args.full,
        min_interval=args.interval,
        quiet=args.quiet,
        log=args.logfile,
        checkpoint=args.checkpoint,
        out_path=OUT_PATH,
        count_only=args.count_only,
        resume=args.resume,
        letter=args.letter,
        burst=args.burst,
        depth=args.depth,
        download_images=args.download_images,
    )
    
    if not args.count_only:
        save_to_json(strains, OUT_PATH)
    else:
        print(f"COUNT_RESULT:{len(strains)}")
