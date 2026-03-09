#main.py

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from google.cloud import bigquery

app = FastAPI(title="Juci Assistant Wizard")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
QUERY_FILE = BASE_DIR / "wizard_query.sql"

bq = bigquery.Client()

PROJECT_ID = "folias-juci"
DATASET_ID = "assistant"
WIZARD_SESSIONS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.wizard_sessions"
WIZARD_LEADS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.wizard_leads"


# -------------------------
# MODELS
# -------------------------

class WizardSessionUpsert(BaseModel):
    session_id: str

    surface: Optional[str] = None
    window_type: Optional[str] = None
    glass_type: Optional[str] = None
    install_side: Optional[str] = None

    width_cm: Optional[int] = None
    height_cm: Optional[int] = None

    privacy_required: Optional[bool] = None
    reflectivity_preference: Optional[str] = None
    result_count: Optional[int] = None

class WizardRequest(BaseModel):
    session_id: Optional[str] = None

    surface: Literal["glass", "polycarbonate"]

    window_type: Optional[Literal[
        "normal",
        "roof",
        "skylight",
        "winter_garden",
        "storefront",
        "other"
    ]] = "normal"

    glass_type: Optional[Literal[
        "single",
        "double",
        "double_low_e",
        "triple_low_e",
        "unknown"
    ]] = "unknown"

    install_side: Optional[Literal[
        "inside",
        "outside",
        "both",
        "unknown"
    ]] = "unknown"

    width_cm: int = Field(ge=1, le=500)
    height_cm: Optional[int] = Field(default=None, ge=1, le=500)

    main_goal: Optional[Literal[
        "heat",
        "heat_privacy",
        "privacy",
        "heat_safety",
        "winter_insulation",
        "surface_protection"
    ]] = "heat"

    reflectivity_tolerance: Optional[Literal[
        "mirror_ok",
        "slightly",
        "not_mirror",
        "almost_invisible"
    ]] = "not_mirror"

    brightness_preference: Optional[Literal[
        "very_bright",
        "medium",
        "darker_ok"
    ]] = "medium"

    privacy_level: Optional[Literal[
        "none",
        "daytime",
        "day_night",
        "decor"
    ]] = "none"

    safety_need: Optional[Literal[
        "none",
        "shatter",
        "anti_burglary",
        "anti_graffiti",
        "heat_safety"
    ]] = None

    allow_diy: bool = True
    interior_reflection_sensitive: Optional[bool] = False

class WizardLeadRequest(BaseModel):
    session_id: str
    email: EmailStr
    name: Optional[str] = None


# -------------------------
# HELPERS
# -------------------------


def polycarbonate_summary(result_count: int, width_cm: int, height_cm: Optional[int]) -> str:
    size_text = f"{width_cm} cm széles"
    if height_cm:
        size_text += f", kb. {height_cm} cm magas"

    return f"""
<div class="wizard-summary">
<h3>A megadott igényed</h3>
<ul class="wizard-summary-list">
<li><strong>📐 Felület:</strong> Polikarbonát vagy plexi felület</li>
<li><strong>📏 Méret:</strong> {size_text}</li>
</ul>

<h3>🎯 Az eredmény</h3>
<p>
<strong>{result_count}</strong> polikarbonáthoz ajánlható fóliát találtunk.
</p>
</div>
"""

def get_polycarbonate_products(width_cm: int):
    query = f"""
    SELECT
      p.product_id,
      p.sku,
      p.name,
      p.brand,
      p.family,
      p.image_url,
      p.product_url,
      p.roll_width_cm,
      ps.tsers AS tser,
      ps.visible_light_transmission,
      ps.visible_light_reflection_ext,
      ps.visible_light_reflection_int
    FROM `{PROJECT_ID}.{DATASET_ID}.products` p
    LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.product_specs` ps
      ON p.film_type = ps.product_id
    WHERE
      'polycarbonate' IN UNNEST(p.film_features)
      AND p.roll_width_cm >= @width_cm
    ORDER BY p.roll_width_cm ASC, p.name
    """

    job = bq.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("width_cm", "INT64", width_cm),
            ]
        )
    )

    rows = list(job.result())
    result = []

    for i, r in enumerate(rows):
        result.append({
            "sku": r.sku,
            "name": r.name,
            "brand": r.brand,
            "family": r.family,
            "image": r.image_url,
            "url": r.product_url,
            "score": 100 - i,
            "tser": r.tser,
            "vlt": r.visible_light_transmission,
            "reflect_ext": r.visible_light_reflection_ext,
            "reflect_int": r.visible_light_reflection_int,
            "heat_stars": heat_match(r.tser) if r.tser is not None else 4,
            "light_stars": light_match(r.visible_light_transmission, "medium") if r.visible_light_transmission is not None else 4,
            "privacy_stars": privacy_match(r.visible_light_reflection_ext) if r.visible_light_reflection_ext is not None else 1,
            "exact_match": True,
            "match_type": "perfect",
            "badges": [
                {"ok": True, "label": "Polikarbonáthoz ajánlott"},
                {"ok": True, "label": "Hővédő megoldás"},
            ],
            "is_recommended": i == 0,
        })

    return result

def load_query() -> str:
    return QUERY_FILE.read_text(encoding="utf-8")


def utcnow():
    return datetime.now(timezone.utc)


def normalize_surface(surface: str) -> str:
    return "glass" if surface == "glass" else "polycarbonate"


def normalize_window_type(window_type: str) -> str:
    mapping = {
        "normal": "normal",
        "roof": "roof",
        "skylight": "roof",
        "winter_garden": "winter_garden",
        "storefront": "storefront",
        "other": "other",
    }
    return mapping.get(window_type, "normal")


def build_priorities(data: WizardRequest) -> dict:
    heat_priority = 5
    privacy_priority = 1
    light_priority = 3

    if data.main_goal == "heat":
        heat_priority = 5
        privacy_priority = 1
        light_priority = 4
    elif data.main_goal == "heat_privacy":
        heat_priority = 5
        privacy_priority = 4
        light_priority = 3
    elif data.main_goal == "privacy":
        heat_priority = 2
        privacy_priority = 5
        light_priority = 2
    elif data.main_goal == "heat_safety":
        heat_priority = 5
        privacy_priority = 2
        light_priority = 3
    elif data.main_goal == "surface_protection":
        heat_priority = 2
        privacy_priority = 1
        light_priority = 3

    if data.privacy_level == "daytime":
        privacy_priority = max(privacy_priority, 3)
    elif data.privacy_level == "day_night":
        privacy_priority = max(privacy_priority, 5)
    elif data.privacy_level == "decor":
        privacy_priority = max(privacy_priority, 2)

    if data.brightness_preference == "very_bright":
        light_priority = 5
    elif data.brightness_preference == "medium":
        light_priority = max(light_priority, 3)
    elif data.brightness_preference == "darker_ok":
        light_priority = 1

    return {
        "heat_priority": heat_priority,
        "privacy_priority": privacy_priority,
        "light_priority": light_priority,
    }


def build_reflectivity_preference(data: WizardRequest) -> str:
    mapping = {
        "mirror_ok": "mirror",
        "slightly": "neutral",
        "not_mirror": "neutral",
        "almost_invisible": "neutral",
    }
    return mapping[data.reflectivity_tolerance]

def light_match(vlt, preference):

    if preference == "very_bright":
        if vlt >= 60:
            return 5
        elif vlt >= 45:
            return 4
        elif vlt >= 30:
            return 3
        elif vlt >= 20:
            return 2
        else:
            return 1

    if preference == "medium":
        if vlt >= 45:
            return 5
        elif vlt >= 30:
            return 4
        elif vlt >= 20:
            return 3
        else:
            return 2

    if preference == "darker_ok":
        if vlt >= 20:
            return 5
        elif vlt >= 10:
            return 4
        else:
            return 3

def heat_match(tser):

    if tser >= 80:
        return 5
    if tser >= 70:
        return 4
    if tser >= 60:
        return 3
    if tser >= 50:
        return 2
    return 1

def privacy_match(reflection_ext):

    if reflection_ext >= 50:
        return 5
    if reflection_ext >= 35:
        return 4
    if reflection_ext >= 20:
        return 3
    if reflection_ext >= 10:
        return 2
    return 1

def human_summary(data: WizardRequest, result_count: int) -> str:

    surface_map = {
        "glass": "Üvegfelület",
        "polycarbonate": "Polikarbonát vagy plexi felület",
    }

    window_map = {
        "normal": "Normál függőleges ablak",
        "roof": "Tetőtéri ablak",
        "skylight": "Felülvilágító vagy üvegtető",
        "winter_garden": "Télikert",
        "storefront": "Üvegfal vagy kirakat",
        "other": "Egyéb üvegfelület",
    }

    goal_map = {
        "heat": "Hővédelem",
        "heat_privacy": "Hővédelem + belátásvédelem",
        "privacy": "Belátásvédelem",
        "heat_safety": "Hővédelem + extra védelem",
        "winter_insulation": "Téli komfortjavítás",
        "surface_protection": "Felületvédelem",
    }

    reflect_map = {
        "mirror_ok": "A tükrös hatás nem zavar",
        "slightly": "Legfeljebb enyhén tükrös lehet",
        "not_mirror": "Nem szeretnél tükrös hatást",
        "almost_invisible": "Szinte láthatatlan megjelenést szeretnél",
    }

    light_map = {
        "very_bright": "Fontos, hogy nagyon világos maradjon",
        "medium": "Közepes sötétítés még rendben van",
        "darker_ok": "Az erősebb sötétítés is belefér",
    }

    privacy_map = {
        "none": "Nem szükséges belátásvédelem",
        "daytime": "Nappali belátásvédelem",
        "day_night": "Erős, egész napos belátásvédelem",
        "decor": "Dekor vagy részleges takarás",
    }

    return f"""
<div class="wizard-summary">

<h3>A megadott igényeid</h3>

<ul class="wizard-summary-list">
<li><strong>📐 Felület:</strong> {surface_map.get(data.surface)}</li>
<li><strong>⊞  Ablak típusa:</strong> {window_map.get(data.window_type)}</li>
<li><strong>🎯 Fő cél:</strong> {goal_map.get(data.main_goal)}</li>
<li><strong>✨ Tükrösség:</strong> {reflect_map.get(data.reflectivity_tolerance)}</li>
<li><strong>☀️ Fényáteresztés:</strong> {light_map.get(data.brightness_preference)}</li>
<li><strong>👀 Belátásvédelem:</strong> {privacy_map.get(data.privacy_level)}</li>
</ul>

<h3>🎯 Az eredmény</h3>

<p>
<strong>{result_count}</strong> ajánlható fóliát találtunk a megadott feltételek alapján.
</p>

</div>
"""


def merge_wizard_session(payload: WizardSessionUpsert) -> None:
    query = f"""
    MERGE `{WIZARD_SESSIONS_TABLE}` T
    USING (
      SELECT
        @session_id AS session_id,
        @created_at AS created_at,
        @surface AS surface,
        @window_type AS window_type,
        @glass_type AS glass_type,
        @install_side AS install_side,
        @width_cm AS width_cm,
        @height_cm AS height_cm,
        @privacy_required AS privacy_required,
        @reflectivity_preference AS reflectivity_preference,
        @result_count AS result_count
    ) S
    ON T.session_id = S.session_id
    WHEN MATCHED THEN
      UPDATE SET
        surface = COALESCE(S.surface, T.surface),
        window_type = COALESCE(S.window_type, T.window_type),
        glass_type = COALESCE(S.glass_type, T.glass_type),
        install_side = COALESCE(S.install_side, T.install_side),
        width_cm = COALESCE(S.width_cm, T.width_cm),
        height_cm = COALESCE(S.height_cm, T.height_cm),
        privacy_required = COALESCE(S.privacy_required, T.privacy_required),
        reflectivity_preference = COALESCE(S.reflectivity_preference, T.reflectivity_preference),
        result_count = COALESCE(S.result_count, T.result_count)
    WHEN NOT MATCHED THEN
      INSERT (
        session_id, created_at, surface, window_type, glass_type, install_side,
        width_cm, height_cm, privacy_required, reflectivity_preference, result_count
      )
      VALUES (
        S.session_id, S.created_at, S.surface, S.window_type, S.glass_type, S.install_side,
        S.width_cm, S.height_cm, S.privacy_required, S.reflectivity_preference, S.result_count
      )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("session_id", "STRING", payload.session_id),
            bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", utcnow().isoformat()),
            bigquery.ScalarQueryParameter("surface", "STRING", payload.surface),
            bigquery.ScalarQueryParameter("window_type", "STRING", payload.window_type),
            bigquery.ScalarQueryParameter("glass_type", "STRING", payload.glass_type),
            bigquery.ScalarQueryParameter("install_side", "STRING", payload.install_side),
            bigquery.ScalarQueryParameter("width_cm", "INT64", payload.width_cm),
            bigquery.ScalarQueryParameter("height_cm", "INT64", payload.height_cm),
            bigquery.ScalarQueryParameter("privacy_required", "BOOL", payload.privacy_required),
            bigquery.ScalarQueryParameter("reflectivity_preference", "STRING", payload.reflectivity_preference),
            bigquery.ScalarQueryParameter("result_count", "INT64", payload.result_count),
        ]
    )
    bq.query(query, job_config=job_config).result()


# -------------------------
# ROUTES
# -------------------------

@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/hovedo")
def wizard_ui():
    return FileResponse(STATIC_DIR / "wizard.html")


@app.get("/static/{filename}")
def static_files(filename: str):
    file_path = STATIC_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.post("/wizard/session/start")
def wizard_session_start():
    return {"session_id": str(uuid.uuid4())}


@app.post("/wizard/session/save")
def wizard_session_save(data: WizardSessionUpsert):
    merge_wizard_session(data)
    return {"ok": True, "session_id": data.session_id}




@app.post("/wizard")
def wizard(data: WizardRequest):
    session_id = data.session_id or str(uuid.uuid4())

    if data.surface == "polycarbonate":
        result = get_polycarbonate_products(data.width_cm)
        summary = polycarbonate_summary(len(result), data.width_cm, data.height_cm)

        merge_wizard_session(
            WizardSessionUpsert(
                session_id=session_id,
                surface=data.surface,
                window_type="other",
                glass_type="unknown",
                install_side="unknown",
                width_cm=data.width_cm,
                height_cm=data.height_cm,
                privacy_required=False,
                reflectivity_preference="polycarbonate",
                result_count=len(result),
            )
        )

    bq.query(
        f"""
        MERGE `{WIZARD_SESSIONS_TABLE}` T
        USING (
            SELECT
                @session_id AS session_id,
                @answers AS answers_json,
                @results AS results_json,
                @summary AS summary
        ) S
        ON T.session_id = S.session_id

        WHEN MATCHED THEN
            UPDATE SET
                answers_json = S.answers_json,
                results_json = S.results_json,
                summary = S.summary

        WHEN NOT MATCHED THEN
            INSERT (session_id, answers_json, results_json, summary, created_at)
            VALUES (S.session_id, S.answers_json, S.results_json, S.summary, CURRENT_TIMESTAMP())
        """,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "answers", "STRING", json.dumps(data.model_dump())
                ),
                bigquery.ScalarQueryParameter(
                    "results", "STRING", json.dumps(result, ensure_ascii=False)
                ),
                bigquery.ScalarQueryParameter(
                    "summary", "STRING", summary
                ),
                bigquery.ScalarQueryParameter(
                    "session_id", "STRING", session_id
                ),
            ]
        ),
    ).result()

    failure_reason = None
    if len(result) == 0:
        failure_reason = "Jelenleg nincs olyan polikarbonát fólia, amely megfelelő szélességben elérhető."

    return {
        "session_id": session_id,
        "summary": summary,
        "answers": data.model_dump(),
        "results": result,
        "failure_reason": failure_reason,
    }

    
    priorities = build_priorities(data)
    reflectivity_preference = build_reflectivity_preference(data)
    privacy_required = (
        data.privacy_level in {"daytime", "day_night", "decor"}
        or data.safety_need in {"shatter", "anti_burglary", "heat_safety"}
    )

    safety_required = data.main_goal == "heat_safety"

    query = load_query()

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("surface", "STRING", normalize_surface(data.surface)),
            bigquery.ScalarQueryParameter("glass_type", "STRING", data.glass_type),
            bigquery.ScalarQueryParameter(
                "install_side",
                "STRING",
                {
                    "inside": "interior",
                    "outside": "exterior",
                    "both": "both",
                    "unknown": "both"
                }.get(data.install_side, "both")
            ),
            bigquery.ScalarQueryParameter(
                "safety_required",
                "BOOL",
                safety_required
            ),
            bigquery.ScalarQueryParameter("window_type", "STRING", normalize_window_type(data.window_type)),
            bigquery.ScalarQueryParameter("window_width_cm", "INT64", data.width_cm),

            bigquery.ScalarQueryParameter("heat_priority", "INT64", priorities["heat_priority"]),
            bigquery.ScalarQueryParameter("privacy_priority", "INT64", priorities["privacy_priority"]),
            bigquery.ScalarQueryParameter("light_priority", "INT64", priorities["light_priority"]),

            bigquery.ScalarQueryParameter("allow_diy", "BOOL", data.allow_diy),
            bigquery.ScalarQueryParameter("reflectivity_preference", "STRING", reflectivity_preference),
            bigquery.ScalarQueryParameter("privacy_required", "BOOL", privacy_required),
        ]
    )
    
    rows = bq.query(query, job_config=job_config).result()

    result = []

    for r in rows:

        badges = []

        if r.heat_rating in ["⭐⭐⭐⭐⭐ Kiváló","⭐⭐⭐⭐ Nagyon jó","⭐⭐⭐ Jó"]:
            badges.append({
                "ok": True,
                "label": "Erős hővédelem"
            })

        if r.privacy_level != "Nincs":
            badges.append({
                "ok": True,
                "label": "Belátásvédelem"
            })
        else:
            badges.append({
                "ok": False,
                "label": "Gyengébb belátásvédelem"
            })

        result.append({
            "sku": r.sku,
            "name": r.name,
            "brand": r.brand,
            "family": r.family,
            "image": r.image_url,
            "url": r.product_url,
            "score": float(r.final_score or 0),

            "tser": r.tser,
            "vlt": r.visible_light_transmission,
            "reflect_ext": r.visible_light_reflection_ext,
            "reflect_int": r.visible_light_reflection_int,

            "heat_stars": heat_match(r.tser),
            "light_stars": light_match(r.visible_light_transmission, data.brightness_preference),
            "privacy_stars": privacy_match(r.visible_light_reflection_ext),

            "exact_match": bool(r.exact_match),
            "match_type": r.match_type,

            "badges": badges
        })

    # ⭐ itt jelöljük a legjobbat
    if result:
        best = max(result, key=lambda x: x["score"])
        best["is_recommended"] = True

    merge_wizard_session(
        WizardSessionUpsert(
            session_id=session_id,
            surface=data.surface,
            window_type=data.window_type,
            glass_type=data.glass_type,
            install_side=data.install_side,
            width_cm=data.width_cm,
            height_cm=data.height_cm,
            privacy_required=privacy_required,
            reflectivity_preference=reflectivity_preference,
            result_count=len(result),
        )
    )

    summary = human_summary(data, len(result))

    bq.query(
        f"""
        MERGE `{WIZARD_SESSIONS_TABLE}` T
        USING (
            SELECT
                @session_id AS session_id,
                @answers AS answers_json,
                @results AS results_json,
                @summary AS summary
        ) S
        ON T.session_id = S.session_id

        WHEN MATCHED THEN
            UPDATE SET
                answers_json = S.answers_json,
                results_json = S.results_json,
                summary = S.summary

        WHEN NOT MATCHED THEN
            INSERT (session_id, answers_json, results_json, summary, created_at)
            VALUES (S.session_id, S.answers_json, S.results_json, S.summary, CURRENT_TIMESTAMP())
        """,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "answers", "STRING", json.dumps(data.model_dump())
                ),
                bigquery.ScalarQueryParameter(
                    "results", "STRING", json.dumps(result, ensure_ascii=False)
                ),
                bigquery.ScalarQueryParameter(
                    "summary", "STRING", summary
                ),
                bigquery.ScalarQueryParameter(
                    "session_id", "STRING", session_id
                ),
            ]
        ),
    ).result()

    failure_reason = None

    if len(result) == 0:

        if data.glass_type == "triple_low_e":
            failure_reason = "A háromrétegű Low-E üveg miatt a legtöbb fólia nem telepíthető belülről."

        elif data.brightness_preference == "very_bright":
            failure_reason = "A nagyon világos megjelenés mellett nehéz erős hővédelmet és belátásvédelmet elérni."

        elif data.privacy_level == "daytime":
            failure_reason = "A nappali belátásvédelem általában sötétebb vagy tükrösebb fóliát igényel."

        else:
            failure_reason = "A megadott feltételek együtt túl szűk szűrést eredményeztek."

    return {
        "session_id": session_id,
        "summary": summary,
        "answers": data.model_dump(),
        "results": result,
        "failure_reason": failure_reason,
    }


@app.post("/wizard/lead")
def wizard_lead(data: WizardLeadRequest):
    row = {
        "session_id": data.session_id,
        "created_at": utcnow().isoformat(),
        "email": data.email,
        "name": data.name,
    }
    errors = bq.insert_rows_json(WIZARD_LEADS_TABLE, [row])
    if errors:
        raise HTTPException(status_code=500, detail=str(errors))

    return {"ok": True}

@app.get("/hovedo/eredmeny")
def wizard_result_page():
    return FileResponse(STATIC_DIR / "wizard-result.html")

@app.get("/wizard/result")
def wizard_result(session: str):

    query = f"""
    SELECT
        results_json,
        summary,
        answers_json
    FROM `{WIZARD_SESSIONS_TABLE}`
    WHERE session_id = @session
    LIMIT 1
    """

    job = bq.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("session", "STRING", session)
            ]
        )
    )

    rows = list(job.result())

    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")

    row = rows[0]

    return {
        "session_id": session,
        "summary": row.summary,
        "answers": json.loads(row.answers_json) if row.answers_json else {},
        "results": json.loads(row.results_json) if row.results_json else []
    }