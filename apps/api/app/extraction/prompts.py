"""Central, page-aware extraction prompt construction."""

from app.database.models import DocumentPage

EXTRACTION_INSTRUCTIONS = """You extract untrusted structured candidates from document text.
Extract only facts explicitly supported by the supplied text. Never diagnose, infer missing values,
invent units, invent dates, or provide medical advice. Preserve uncertainty and use null whenever a
field is unknown. Every candidate must include a short verbatim evidence passage and the numeric
source page from its nearest [PAGE N] marker. Confidence is extraction confidence, not medical
certainty.

Classification rules:
- A named diagnosis or a line labelled "Known condition" is a condition.
- A drug name, dose, or a line labelled "Medication" is a medication, never a measurement.
- A named laboratory test and result, such as HbA1c or glucose, is a lab.
- A patient-reported complaint or a line labelled "Reported symptom" is a symptom.
- A vital sign or body measurement, such as weight, blood pressure, pulse, or temperature, is a
  measurement. Do not put medications or lab results in measurements.
- For a numeric result, put the number in value_number and its unit in unit. Do not repeat the unit
  in value_text. Use value_text only when the result is genuinely non-numeric.
- Encode every date as YYYY-MM-DD and every datetime as ISO 8601. Never return written-out dates.
- Set medication active_status only when active/inactive status is explicit; otherwise use unknown.

Return JSON only and conform exactly to the supplied schema. Do not add facts from general
knowledge."""


def build_extraction_prompt(pages: list[DocumentPage], fallback_text: str | None = None) -> str:
    page_text = "\n\n".join(f"[PAGE {page.page_number}]\n{page.text}" for page in pages)
    if not page_text and fallback_text:
        page_text = f"[PAGE UNAVAILABLE]\n{fallback_text}"
    return f"{EXTRACTION_INSTRUCTIONS}\n\nDOCUMENT TEXT\n{page_text}"
