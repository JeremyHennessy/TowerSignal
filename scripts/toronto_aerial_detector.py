from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import numpy as np
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, balanced_accuracy_score

from toronto_market_common import as_float, read_json, request_bytes, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MAPSERVER = "https://gis.toronto.ca/arcgis/rest/services/basemap/cot_ortho_2025_color_8cm/MapServer/export"


def mercator(lon: float, lat: float) -> tuple[float, float]:
    origin = 20037508.342789244
    x = lon * origin / 180.0
    lat = max(min(lat, 85.05112878), -85.05112878)
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) / (math.pi / 180.0)
    y = y * origin / 180.0
    return x, y


def crop_url(lon: float, lat: float, half_size_m: float = 70.0, pixels: int = 384) -> str:
    x, y = mercator(lon, lat)
    bbox = f"{x-half_size_m},{y-half_size_m},{x+half_size_m},{y+half_size_m}"
    params = {
        "bbox": bbox, "bboxSR": 3857, "imageSR": 3857,
        "size": f"{pixels},{pixels}", "format": "png32",
        "transparent": "false", "f": "image",
    }
    return f"{MAPSERVER}?{urlencode(params)}"


def image_features(data: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(data)).convert("RGB").resize((128, 128))
    arr = np.asarray(image, dtype=np.float32) / 255.0
    gray = arr.mean(axis=2)
    feats: list[float] = []
    for channel in range(3):
        hist, _ = np.histogram(arr[:, :, channel], bins=12, range=(0, 1), density=True)
        feats.extend(hist.tolist())
        feats.extend([float(arr[:, :, channel].mean()), float(arr[:, :, channel].std())])
    gx = np.diff(gray, axis=1)
    gy = np.diff(gray, axis=0)
    grad = np.sqrt(gx[:-1, :] ** 2 + gy[:, :-1] ** 2)
    feats.extend([
        float(gray.mean()), float(gray.std()),
        float(np.mean(np.abs(gx))), float(np.mean(np.abs(gy))),
        float(grad.mean()), float(grad.std()),
        float(np.quantile(grad, 0.75)), float(np.quantile(grad, 0.90)), float(np.quantile(grad, 0.98)),
    ])
    for y0 in range(0, 128, 32):
        for x0 in range(0, 128, 32):
            patch = gray[y0:y0+32, x0:x0+32]
            feats.extend([float(patch.mean()), float(patch.std())])
    return np.asarray(feats, dtype=np.float32)


def fetch_property(prop: dict[str, Any]) -> tuple[np.ndarray, bytes, str] | None:
    lon = as_float(prop.get("longitude"))
    lat = as_float(prop.get("latitude"))
    if lon is None or lat is None:
        return None
    url = crop_url(lon, lat)
    data = request_bytes(url, timeout=90, max_bytes=8_000_000)
    return image_features(data), data, url


def is_confirmed(prop: dict[str, Any]) -> bool:
    return "CONFIRMED" in set(prop.get("poc_tower_statuses") or [])


def is_weak_control(prop: dict[str, Any]) -> bool:
    return bool(prop.get("is_original_poc_property")) and not is_confirmed(prop)


def build(market: Path, max_score: int, save_review: int) -> dict[str, Any]:
    spine = read_json(market / "property_spine.json") or {}
    props = [p for p in spine.get("properties", []) if isinstance(p, dict)]
    positives = [p for p in props if is_confirmed(p)]
    controls = [p for p in props if is_weak_control(p)]
    controls = sorted(controls, key=lambda p: p.get("property_id") or "")[:max(len(positives) * 2, 60)]
    train_props = positives + controls

    X: list[np.ndarray] = []
    y: list[int] = []
    usable_props: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, str]] = []
    review_dir = market / "work" / "aerial_review"
    review_dir.mkdir(parents=True, exist_ok=True)

    for prop in train_props:
        try:
            fetched = fetch_property(prop)
            if not fetched:
                continue
            feat, data, url = fetched
            X.append(feat)
            y.append(1 if is_confirmed(prop) else 0)
            usable_props.append(prop)
            if is_confirmed(prop):
                (review_dir / f"confirmed_{prop['geo_id']}.png").write_bytes(data)
        except Exception as exc:
            fetch_errors.append({"property_id": prop.get("property_id"), "error": f"{type(exc).__name__}: {exc}"})

    report: dict[str, Any] = {
        "schema_version": "toronto-aerial-weak-label-0.1",
        "generated_at": utc_now(),
        "source": "City of Toronto 2025 8 cm aerial imagery",
        "mapserver": MAPSERVER.rsplit("/export", 1)[0],
        "label_contract": {
            "positive": "Existing documentary CONFIRMED cooling-tower property, not pixel-verified current tower.",
            "control": "Original POC property without confirmed tower evidence; absence of evidence is not a true negative.",
            "interpretation": "Scores measure visual similarity to weak documentary labels and MUST NOT create or upgrade tower confirmation.",
            "imagery_date": "2025 imagery can post-date or pre-date individual construction/removal events.",
        },
        "training": {
            "requested_positive_properties": len(positives),
            "requested_weak_controls": len(controls),
            "usable_images": len(X),
            "fetch_errors": fetch_errors,
        },
    }

    if len(X) < 20 or len(set(y)) < 2 or min(sum(y), len(y)-sum(y)) < 5:
        report["status"] = "INSUFFICIENT_WEAK_LABEL_IMAGES"
        report["candidates"] = []
        write_json(market / "aerial_model_report.json", report)
        print(json.dumps(report["training"], indent=2))
        return report

    Xn = np.vstack(X)
    yn = np.asarray(y)
    model = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=17)
    folds = min(5, int(min(yn.sum(), len(yn) - yn.sum())))
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=17)
    probabilities = cross_val_predict(model, Xn, yn, cv=cv, method="predict_proba")[:, 1]
    model.fit(Xn, yn)
    report["status"] = "WEAK_LABEL_MODEL_FIT"
    report["weak_label_validation"] = {
        "folds": folds,
        "roc_auc_vs_weak_labels": float(roc_auc_score(yn, probabilities)),
        "balanced_accuracy_at_0_5_vs_weak_labels": float(balanced_accuracy_score(yn, probabilities >= 0.5)),
        "warning": "These are discrimination metrics against weak documentary labels, not validated cooling-tower detection accuracy.",
    }

    train_ids = {p["property_id"] for p in usable_props}
    score_props = sorted(
        [p for p in props if p.get("property_id") not in train_ids],
        key=lambda p: (not bool(p.get("is_original_poc_property")), p.get("property_id") or ""),
    )[:max_score]
    candidates: list[dict[str, Any]] = []
    scored_images: list[tuple[float, dict[str, Any], bytes]] = []
    for prop in score_props:
        try:
            fetched = fetch_property(prop)
            if not fetched:
                continue
            feat, data, url = fetched
            score = float(model.predict_proba(feat.reshape(1, -1))[0, 1])
            entry = {
                "property_id": prop.get("property_id"),
                "geo_id": prop.get("geo_id"),
                "address": prop.get("display_address"),
                "aerial_visual_similarity_score": round(score, 6),
                "review_state": "UNREVIEWED_WEAK_MODEL",
                "imagery_request": url,
            }
            candidates.append(entry)
            scored_images.append((score, prop, data))
        except Exception as exc:
            fetch_errors.append({"property_id": prop.get("property_id"), "error": f"{type(exc).__name__}: {exc}"})

    candidates.sort(key=lambda c: c["aerial_visual_similarity_score"], reverse=True)
    for score, prop, data in sorted(scored_images, key=lambda item: item[0], reverse=True)[:save_review]:
        (review_dir / f"candidate_{score:.4f}_{prop['geo_id']}.png").write_bytes(data)

    report["training"]["fetch_errors"] = fetch_errors
    report["scoring"] = {
        "candidate_properties_requested": len(score_props),
        "candidate_properties_scored": len(candidates),
        "review_images_saved_artifact_only": min(save_review, len(scored_images)),
    }
    report["candidates"] = candidates
    write_json(market / "aerial_model_report.json", report)
    write_json(market / "aerial_candidates.json", {
        "metadata": {k: v for k, v in report.items() if k != "candidates"},
        "candidates": candidates,
    })
    print(json.dumps({"status": report["status"], **report["weak_label_validation"], **report["scoring"]}, indent=2))
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--market", type=Path, default=ROOT / "data/toronto/market/current")
    p.add_argument("--max-score", type=int, default=1200)
    p.add_argument("--save-review", type=int, default=50)
    args = p.parse_args()
    build(args.market, args.max_score, args.save_review)


if __name__ == "__main__":
    main()
