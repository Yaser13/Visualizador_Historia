"""Initial curated draft with approximate modern reference locations."""

CHRONOLOGY = {
    "title": "Italian Peninsula, 1000 B.C.–1 A.D.",
    "creator": "The Metropolitan Museum of Art",
    "publication": "Heilbrunn Timeline of Art History, octubre de 2000",
    "url": "https://www.metmuseum.org/toah/ht/04/eust.html",
    "rights_note": "Derechos de reproducción no verificados; se enlaza la fuente.",
}


LOCATIONS = {
    "Roma": ([12.4923, 41.8902], "Centro histórico de Roma, referencia moderna aproximada; no representa la extensión de Roma antigua.", "https://whc.unesco.org/en/list/91/maps/", "Historic Centre of Rome, propiedad 91quater-001"),
    "Veyes": ([12.3896, 42.0236], "Referencia aproximada del yacimiento; no representa los límites de la ciudad antigua.", "https://www.mikoflohr.org/data/places/veii/", "Coordinates, Veii"),
    "Cartago": ([10.3233, 36.8528], "Referencia aproximada al área arqueológica de las colinas; no representa la extensión de Cartago ni de la provincia.", "https://whc.unesco.org/en/list/37/maps/", "The area of the hills, propiedad 37-001"),
}


def event(identifier, order, title, description, start, end, precision, label, place, locator):
    location = LOCATIONS.get(place)
    place_data = {"label": place, "coordinates": None, "precision": "unknown", "note": "Este acontecimiento abarca una región y no se representa mediante un punto.", "coordinate_source": None}
    if location:
        coordinates, note, url, source_locator = location
        place_data = {"label": place, "coordinates": coordinates, "precision": "approximate", "note": note, "coordinate_source": {"url": url, "locator": source_locator}}
    return {
        "id": identifier,
        "order": order,
        "title": title,
        "description": description,
        "date": {"start_year": start, "end_year": end, "precision": precision, "label": label},
        "place": place_data,
        "evidence_status": "under_review",
        "sources": [{**CHRONOLOGY, "locator": locator}],
    }


ROME = {
    "slug": "expansion-de-roma",
    "title": "La expansión de Roma",
    "summary": "Un recorrido inicial desde la República hasta el Principado. Contenido en revisión; los hitos no representan fronteras históricas.",
    "events": [
        event("republica", 1, "La República romana", "Se establece una república aristocrática en Roma.", -509, -509, "approximate", "c. 509 a. e. c.", "Roma", "Key Events, ca. 509 B.C."),
        event("veyes", 2, "La captura de Veyes", "Roma captura la ciudad etrusca de Veyes.", -396, -396, "year", "396 a. e. c.", "Veyes", "Key Events, 396 B.C."),
        event("sicilia", 3, "La primera guerra púnica", "Durante la guerra, gran parte de Sicilia pasa a ser la primera provincia romana.", -264, -241, "range", "264–241 a. e. c.", "Sicilia", "Key Events, 264–241 B.C."),
        event("cartago", 4, "La destrucción de Cartago", "Roma destruye Cartago y el territorio cartaginés pasa a ser provincia romana.", -146, -146, "year", "146 a. e. c.", "Cartago", "Key Events, 146 B.C."),
        event("augusto", 5, "El Principado de Augusto", "Se establece el Principado de Augusto, fecha convencional de inicio del periodo imperial.", -27, -27, "year", "27 a. e. c.", "Roma", "Overview; Key Events, 27 B.C.–14 A.D."),
    ],
}

