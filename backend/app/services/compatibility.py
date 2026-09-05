import re
import unicodedata
from typing import Any


LOCALITIES = ("pica", "colchane", "camina", "huara", "la-tirana", "huayquique")


def normalize_text(value: Any) -> str:
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", str(value or ""))
        if not unicodedata.combining(character)
    ).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def locality_from_college(document: dict[str, Any]) -> str | None:
    haystack = " ".join(
        normalize_text(document.get(field))
        for field in ("localidad", "comuna", "nombre")
    )
    for locality in LOCALITIES:
        if normalize_text(locality) in haystack:
            return locality
    return None


def campaign_to_public(
    document: dict[str, Any],
    fallback_college_id: str | None = None,
) -> dict[str, Any]:
    """Normalize historical and current campaign fields in one place."""
    def date_value(value: Any) -> str | None:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    raw_state = normalize_text(document.get("estado"))
    state = raw_state if raw_state in {
        "planificada", "activa", "finalizada", "cancelada"
    } else "finalizada"
    history = document.get("historial_cambios") or []
    history = sorted(
        (item for item in history if isinstance(item, dict)),
        key=lambda item: str(item.get("fecha") or ""),
        reverse=True,
    )
    return {
        "_id": str(document.get("_id")),
        "colegio_id": str(document.get("colegio_id") or fallback_college_id or ""),
        "colegio": document.get("colegio") or "",
        "nombre": document.get("nombre") or "Campaña sin nombre",
        "cultivo": document.get("cultivo") or document.get("especie") or "sin especificar",
        "fecha_siembra": date_value(document.get("fecha_siembra") or document.get("desde")),
        "fecha_cosecha_estimada": date_value(document.get("fecha_cosecha_estimada") or document.get("hasta")),
        "fecha_cosecha_real": date_value(document.get("fecha_cosecha_real")),
        "fecha_cancelacion": date_value(document.get("fecha_cancelacion")),
        "estado": state,
        "observaciones": document.get("observaciones") or document.get("descripción") or document.get("descripcion") or "",
        "resultado_final": document.get("resultado_final") or "",
        "observaciones_finales": document.get("observaciones_finales") or "",
        "motivo_cancelacion": document.get("motivo_cancelacion") or "",
        "categoria_motivo": document.get("categoria_motivo"),
        "historial_cambios": history,
        "revision": int(document.get("revision") or 0),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }
