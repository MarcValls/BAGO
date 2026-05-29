"""bago.api.routes.models — GET /api/tags, POST /api/show, POST /api/create,
POST /api/copy, POST /api/pull, DELETE /api/delete
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ...model_registry import local_model_tag, normalize_local_model_id
from ..models.schemas import (
    TagsResponse, ModelInfo, ShowRequest, ShowResponse,
    CreateRequest, CreateResponse, CopyRequest, CopyResponse,
    PullRequest, ProgressResponse, DeleteRequest,
)
from ..models.bagomodel import BagoModel, parse_bagomodel, save_bagomodel

router = APIRouter()

# ── Directorios ──────────────────────────────────────────────────────────────

def _bago_dir() -> Path:
    from ..server import get_bago
    return get_bago().bago_dir

def _models_dir() -> Path:
    d = _bago_dir() / "state" / "bagomodels"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── GET /api/tags ────────────────────────────────────────────────────────────

@router.get("/api/tags", response_model=TagsResponse)
async def tags():
    """Lista modelos disponibles: catalogo BAGO + instalados Ollama + custom BAGOMODELs."""
    from ..server import get_bago
    from bago.model_availability import available_model_routes
    from bago.providers import describe_model_source
    bago = get_bago()

    models = []

    # 1. Catalogo BAGO (model_catalog.py)
    for entry in bago.catalog():
        models.append(ModelInfo(
            name=entry.ollama_tag,
            model=entry.ollama_tag,
            provider=getattr(entry, "provider", "ollama-local"),
            service="ollama-native",
            route="ollama-native",
            best_for=entry.description if entry.description else "",
            installed=entry.installed,
            compat_level=entry.compat_level,
            size=int(entry.size_gb * 1024 * 1024 * 1024),
        ))

    # 2. BAGOMODELs custom
    models_dir = _models_dir()
    for mf in models_dir.glob("*.bagomodel"):
        bm = parse_bagomodel(mf.read_text(encoding="utf-8"), name=mf.stem)
        models.append(ModelInfo(
            name=bm.name,
            model=bm.from_model,
            provider="bago-custom",
            service="custom-modelfile",
            route="custom-modelfile",
            best_for=bm.best_for,
        ))

    # 3. Provider models (from model_providers.json)
    providers = bago.providers()
    for prov_name, prov_data in providers.items():
        seen = {
            (m.name, m.model, m.provider, m.service, m.route)
            for m in models
        }
        for rec in available_model_routes(prov_name, prov_data):
            mname = rec.get("model", "")
            wire = rec.get("wire_name", mname)
            key = (mname, wire, prov_name, rec.get("service", ""), rec.get("route", ""))
            if key in seen:
                continue
            seen.add(key)
            md = prov_data.get("models", {}).get(mname, {})
            models.append(ModelInfo(
                name=mname,
                model=wire,
                provider=prov_name,
                service=rec.get("service", "") or describe_model_source(
                    prov_name, mname, providers, wire_name=wire,
                    route=rec.get("route", ""), service=rec.get("service", ""),
                ).get("service", ""),
                route=rec.get("route", ""),
                best_for=rec.get("best_for", md.get("best_for", "")),
                size=int(md.get("size_mb", 0) * 1024 * 1024),
            ))

    return TagsResponse(models=models)


# ── POST /api/show ───────────────────────────────────────────────────────────

@router.post("/api/show", response_model=ShowResponse)
async def show(req: ShowRequest):
    """Detalles de un modelo: BAGOMODEL si existe, sino info del catalogo."""
    from ..server import get_bago
    bago = get_bago()
    req_model_id = normalize_local_model_id(req.model) or req.model

    # Check custom BAGOMODEL first
    models_dir = _models_dir()
    mf = models_dir / f"{req.model}.bagomodel"
    if mf.exists():
        bm = parse_bagomodel(mf.read_text(encoding="utf-8"), name=req.model)
        return ShowResponse(
            modelfile=bm.to_modelfile(),
            system=bm.system,
            template=bm.template,
            parameters=json.dumps(bm.parameters),
            provider="bago-custom",
            routing={"fallback": bm.fallback, "quality_guard": bm.quality_guard,
                     "context_escalation": bm.context_escalation},
            fallback=bm.fallback or "",
            quality_guard=bm.quality_guard,
        )

    # Check catalog
    for entry in bago.catalog():
        entry_id = normalize_local_model_id(entry.ollama_tag) or entry.ollama_tag
        if req_model_id in (entry_id, entry.ollama_tag, entry.label.lower()):
            return ShowResponse(
                provider="ollama-local",
                best_for=entry.description,
                catalog_entry={
                    "maker": entry.maker,
                    "specialty": entry.specialty,
                    "context_k": entry.context_k,
                    "benchmark": entry.benchmark,
                    "gem": entry.gem,
                },
            )

    # Check providers
    providers = bago.providers()
    for prov_name, prov_data in providers.items():
        for mname, mdata in prov_data.get("models", {}).items():
            wire = mdata.get("wire_name")
            if (
                mname == req.model
                or wire == req.model
                or normalize_local_model_id(mname) == req_model_id
                or normalize_local_model_id(wire) == req_model_id
            ):
                origin = describe_model_source(prov_name, mname, providers, wire_name=wire)
                return ShowResponse(
                    provider=prov_name,
                    details={**mdata, "service": origin.get("service", ""), "route": origin.get("route", "")},
                    routing={
                        "best_for": mdata.get("best_for", ""),
                        "service": origin.get("service", ""),
                        "route": origin.get("route", ""),
                    },
                )

    raise HTTPException(status_code=404, detail=f"Model '{req.model}' not found")


# ── POST /api/create ─────────────────────────────────────────────────────────

@router.post("/api/create", response_model=CreateResponse)
async def create(req: CreateRequest):
    """Crea un BAGOMODEL desde texto o archivo."""
    if not req.modelfile and not req.path:
        raise HTTPException(status_code=400, detail="Provide modelfile text or path")

    if req.path:
        src = Path(req.path)
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {req.path}")
        text = src.read_text(encoding="utf-8")
    else:
        text = req.modelfile

    bm = parse_bagomodel(text, name=req.name)
    if not bm.from_model:
        raise HTTPException(status_code=400, detail="BAGOMODEL must have a FROM directive")

    models_dir = _models_dir()
    save_bagomodel(bm, models_dir / f"{req.name}.bagomodel")
    return CreateResponse(status="success", name=req.name)


# ── POST /api/copy ───────────────────────────────────────────────────────────

@router.post("/api/copy", response_model=CopyResponse)
async def copy(req: CopyRequest):
    """Copia un BAGOMODEL existente."""
    models_dir = _models_dir()
    src = models_dir / f"{req.source}.bagomodel"
    if not src.exists():
        raise HTTPException(status_code=404, detail=f"Model '{req.source}' not found")

    dst = models_dir / f"{req.destination}.bagomodel"
    text = src.read_text(encoding="utf-8")
    bm = parse_bagomodel(text, name=req.destination)
    save_bagomodel(bm, dst)
    return CopyResponse(status="success")


# ── POST /api/pull ───────────────────────────────────────────────────────────

@router.post("/api/pull")
async def pull(req: PullRequest):
    """Instala un modelo desde el catalogo BAGO (envuelve ollama pull)."""
    import subprocess
    from ..server import get_bago
    bago = get_bago()
    req_model_id = normalize_local_model_id(req.model) or req.model

    # Find in catalog to get exact tag
    for entry in bago.catalog():
        entry_id = normalize_local_model_id(entry.ollama_tag) or entry.ollama_tag
        if req_model_id in (entry_id, entry.ollama_tag, entry.label.lower()):
            result = subprocess.run(
                ["ollama", "pull", entry.ollama_tag],
                capture_output=True, text=True, timeout=600,
            )
            return ProgressResponse(
                status="success" if result.returncode == 0 else f"error: {result.stderr}",
                digest=entry.ollama_tag,
            )

    # Not in catalog — try raw ollama pull
    result = subprocess.run(
        ["ollama", "pull", local_model_tag(req.model) or req.model],
        capture_output=True, text=True, timeout=600,
    )
    return ProgressResponse(
        status="success" if result.returncode == 0 else f"error: {result.stderr}",
    )


# ── DELETE /api/delete ───────────────────────────────────────────────────────

@router.delete("/api/delete")
async def delete(req: DeleteRequest):
    """Elimina un BAGOMODEL custom o un modelo Ollama local."""
    # Check custom first
    models_dir = _models_dir()
    mf = models_dir / f"{req.model}.bagomodel"
    if mf.exists():
        mf.unlink()
        return {"status": "success", "name": req.model}

    # Try Ollama delete
    import subprocess
    result = subprocess.run(
        ["ollama", "rm", req.model],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        return {"status": "success", "name": req.model}
    raise HTTPException(status_code=404, detail=f"Model '{req.model}' not found")
