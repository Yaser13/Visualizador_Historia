"""Instantánea documental de una noticia; no se actualiza automáticamente."""

GEOPOLITICS = {
    "slug": "geopolitica",
    "title": "La COP31 abre sus negociaciones en Antalya",
    "summary": "Instantánea documental consultada el 15 de noviembre de 2026. No se actualiza automáticamente.",
    "events": [
        {
            "id": "cop31-apertura",
            "order": 1,
            "category": "clima",
            "title": "Comienza la COP31",
            "description": "La conferencia climática de la ONU comenzó el 9 de noviembre en Antalya, Turquía. Su programa incluye adaptación y financiación climática; está prevista hasta el 20 de noviembre.",
            "analysis": "Associated Press informó de desacuerdos sobre financiación climática. Según un asesor de negociadores africanos citado por AP, propuestas del Grupo Africano recibieron apoyo de numerosos países en desarrollo y fueron cuestionadas por países de la Unión Europea y Canadá. En términos geopolíticos, estas diferencias ilustran la dificultad de conciliar prioridades financieras en la negociación; su evolución y el resultado final siguen abiertos.",
            "published_at": "2026-11-09",
            "as_of": "2026-11-15",
            "date": {"start_year": 2026, "end_year": 2026, "precision": "range", "label": "9–20 noviembre 2026"},
            "place": {
                "label": "Antalya, Turquía",
                "coordinates": [30.6897, 36.9125],
                "precision": "approximate",
                "note": "Punto de referencia de la ciudad de Antalya, no la ubicación exacta del recinto de la conferencia.",
                "coordinate_source": {"url": "https://ungegn.un.org/dashboard/cities/details?id=2881", "locator": "City Details — Antalya, coordenadas NGA GEOnet Names Server"},
            },
            "evidence_status": "supported",
            "sources": [
                {
                    "title": "UN climate summit kicks off in Turkey after a disastrous year of extreme weather",
                    "creator": "Suzan Fraser y Sibi Arasu",
                    "publication": "Associated Press · 9 de noviembre de 2026",
                    "published_at": "2026-11-09",
                    "url": "https://apnews.com/article/turkey-cop31-summit-climate-change-edd587ab19f3b57848b50f9dc724ba82",
                    "locator": "Apertura y sección sobre el inicio de las conversaciones climáticas",
                    "rights_note": "Derechos reservados; se enlaza y resume, sin reproducir imágenes ni texto extenso.",
                },
                {
                    "title": "COP31 Agenda as Adopted",
                    "creator": "Convención Marco de las Naciones Unidas sobre el Cambio Climático",
                    "publication": "UNFCCC · agenda aprobada el 9 de noviembre de 2026",
                    "published_at": None,
                    "url": "https://unfccc.int/sites/default/files/resource/COP%2031%20agenda%20as%20adopted.pdf",
                    "locator": "Páginas 1–2, agenda y nota 1",
                    "rights_note": "Se enlaza el documento; condiciones de reproducción no verificadas.",
                },
            ],
        }
    ],
}
