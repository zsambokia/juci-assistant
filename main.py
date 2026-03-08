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
    window_type: Literal[
        "normal",
        "roof",
        "skylight",
        "winter_garden",
        "storefront",
        "other"
    ]
    glass_type: Literal[
        "single",
        "double",
        "double_low_e",
        "triple_low_e",
        "unknown"
    ]
    install_side: Literal[
        "inside",
        "outside",
        "both",
        "unknown"
    ]

    width_cm: int = Field(ge=1, le=500)
    height_cm: Optional[int] = Field(default=None, ge=1, le=500)

    main_goal: Literal[
        "heat",
        "heat_privacy",
        "privacy",
        "heat_safety",
        "winter_insulation",
        "surface_protection"
    ]

    reflectivity_tolerance: Literal[
        "mirror_ok",
        "slightly",
        "not_mirror",
        "almost_invisible"
    ]

    brightness_preference: Literal[
        "very_bright",
        "medium",
        "darker_ok"
    ]

    privacy_level: Literal[
        "none",
        "daytime",
        "day_night",
        "decor"
    ]

    safety_need: Literal[
        "none",
        "shatter",
        "anti_burglary",
        "anti_graffiti",
        "heat_safety"
    ]


    allow_diy: bool = True
    interior_reflection_sensitive: bool = False


class WizardLeadRequest(BaseModel):
    session_id: str
    email: EmailStr
    name: Optional[str] = None


# -------------------------
# HELPERS
# -------------------------

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


def human_summary(data: WizardRequest, result_count: int) -> str:
    surface_map = {
        "glass": "üvegfelületre",
        "polycarbonate": "polikarbonát vagy plexi felületre",
    }
    window_map = {
        "normal": "normál függőleges ablakra",
        "roof": "tetőtéri ablakra",
        "skylight": "felülvilágítóra vagy üvegtetőre",
        "winter_garden": "télikertre",
        "storefront": "üvegfalra vagy kirakatra",
        "other": "egyéb üvegfelületre",
    }
    goal_map = {
        "heat": "elsősorban hővédelmet",
        "heat_privacy": "hővédelmet és belátásvédelmet",
        "privacy": "elsősorban belátásvédelmet",
        "heat_safety": "hővédelmet és extra védelmet",
        "winter_insulation": "téli komfortjavítást",
        "surface_protection": "felületvédelmet",
    }
    reflect_map = {
        "mirror_ok": "a tükrösség nem zavar",
        "slightly": "legfeljebb enyhén tükrös megoldást szeretnél",
        "not_mirror": "nem szeretnél tükrös hatást",
        "almost_invisible": "szinte láthatatlan megjelenést szeretnél",
    }
    light_map = {
        "very_bright": "fontos, hogy minél világosabb maradjon",
        "medium": "közepes sötétítés még rendben van",
        "darker_ok": "az erősebb sötétítés is belefér",
    }
    privacy_map = {
        "none": "nem kértél külön belátásvédelmet",
        "daytime": "nappali belátásvédelmet szeretnél",
        "day_night": "erősebb, egész napos takarást keresel",
        "decor": "részleges vagy dekor jellegű takarást is elfogadsz",
    }

    return (
        f"A válaszaid alapján {surface_map[data.surface]} keresel fóliát, "
        f"{window_map[data.window_type]}. A fő célod {goal_map[data.main_goal]}, "
        f"emellett {reflect_map[data.reflectivity_tolerance]}, és {light_map[data.brightness_preference]}. "
        f"Belátásvédelem szempontjából az látszik, hogy {privacy_map[data.privacy_level]}. "
        f"A megadott méret alapján {result_count} ajánlható fóliát találtunk."
    )


def insert_wizard_session(row: dict) -> None:
    errors = bq.insert_rows_json(WIZARD_SESSIONS_TABLE, [row])
    if errors:
        raise RuntimeError(f"BigQuery insert error: {errors}")


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


@app.get("/wizard-ui")
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
    session_id = str(uuid.uuid4())
    merge_wizard_session(WizardSessionUpsert(session_id=session_id))
    return {"session_id": session_id}


@app.post("/wizard/session/save")
def wizard_session_save(data: WizardSessionUpsert):
    merge_wizard_session(data)
    return {"ok": True, "session_id": data.session_id}


@app.post("/wizard")
def wizard(data: WizardRequest):
    session_id = data.session_id or str(uuid.uuid4())

    priorities = build_priorities(data)
    reflectivity_preference = build_reflectivity_preference(data)
    privacy_required = (
        data.privacy_level in {"daytime", "day_night", "decor"}
        or data.safety_need in {"shatter", "anti_burglary", "heat_safety"}
    )

    query = load_query()

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("surface", "STRING", normalize_surface(data.surface)),
            bigquery.ScalarQueryParameter("glass_type", "STRING", data.glass_type),
            bigquery.ScalarQueryParameter("install_side", "STRING", data.install_side),
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
        result.append({
            "sku": r.sku,
            "name": r.name,
            "brand": r.brand,
            "family": r.family,
            "image": r.image_url,
            "url": r.product_url,
            "score": float(r.final_score),
        })

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

    return {
        "session_id": session_id,
        "summary": human_summary(data, len(result)),
        "answers": data.model_dump(),
        "results": result,
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