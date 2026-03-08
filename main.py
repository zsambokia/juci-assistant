from fastapi import FastAPI
from pydantic import BaseModel
from google.cloud import bigquery

app = FastAPI()

bq = bigquery.Client()

QUERY_FILE = "wizard_query.sql"


class WizardInput(BaseModel):

    surface: str
    glass_type: str
    install_side: str
    window_type: str

    window_width_cm: int

    heat_priority: int
    privacy_priority: int
    light_priority: int

    allow_diy: bool
    reflectivity_preference: str


from openai import OpenAI

client = OpenAI()

def explain_product(product):

    response = client.responses.create(

        prompt={
            "id": "pmpt_69adad1be28881958e88071b815518d2019bf30b94065abd",
            "version": "1"
        },

        input={
            "name": product["name"],
            "family": product["family"],
            "heat_score": product["heat_score"],
            "privacy_score": product["privacy_score"],
            "light_score": product["light_score"]
        }

    )

    return response.output_text

def load_query():
    with open(QUERY_FILE, "r") as f:
        return f.read()


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/wizard")
def wizard(data: WizardInput):

    query = load_query()

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("surface", "STRING", data.surface),
            bigquery.ScalarQueryParameter("glass_type", "STRING", data.glass_type),
            bigquery.ScalarQueryParameter("install_side", "STRING", data.install_side),
            bigquery.ScalarQueryParameter("window_type", "STRING", data.window_type),
            bigquery.ScalarQueryParameter("window_width_cm", "INT64", data.window_width_cm),

            bigquery.ScalarQueryParameter("heat_priority", "INT64", data.heat_priority),
            bigquery.ScalarQueryParameter("privacy_priority", "INT64", data.privacy_priority),
            bigquery.ScalarQueryParameter("light_priority", "INT64", data.light_priority),

            bigquery.ScalarQueryParameter("allow_diy", "BOOL", data.allow_diy),
            bigquery.ScalarQueryParameter("reflectivity_preference", "STRING", data.reflectivity_preference),
        ]
    )

    job = bq.query(query, job_config=job_config)

    rows = job.result()

    result = []

    for r in rows:
        product = {
            "name": r.name,
            "family": r.family,
            "heat_score": r.heat_comfort_score,
            "privacy_score": r.privacy_score,
            "light_score": r.natural_light_score
        }

        explanation = explain_product(product)

        result.append({
            "sku": r.sku,
            "name": r.name,
            "brand": r.brand,
            "family": r.family,
            "image": r.image_url,
            "url": r.product_url,
            "score": round(r.final_score,2),
            "explanation": explanation
        })

    return {"results": result}