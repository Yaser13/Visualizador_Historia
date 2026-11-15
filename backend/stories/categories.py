"""Event categories accepted by the backend.

Single backend source for docs/api/CONTRATO_CRONOLOGIAS.md section 3. It must
stay in sync with ``CATEGORIES`` in ``frontend/src/icons.tsx``. Categories are
event-type conventions; they never represent forces, fronts, routes or
territorial control.
"""

EVENT_CATEGORIES = (
    'conflicto',
    'ataque',
    'humanitario',
    'desplazamiento',
    'negociacion',
    'acuerdo',
    'politica',
    'vencimiento',
    'clima',
)


def is_valid_category(value):
    return value in EVENT_CATEGORIES
