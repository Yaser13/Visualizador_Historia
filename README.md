# Observatorio geopolítico

Aplicación en desarrollo para explorar noticias geopolíticas sobre un globo, con hechos atribuidos, análisis identificado y fuentes. La primera noticia es una instantánea de la COP31 en Antalya, consultada el 15 de noviembre de 2026; **no se actualiza automáticamente**.

## Inicio local

En PowerShell, desde la raíz del proyecto:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\manage.py migrate
python backend\manage.py seed_cop31
python backend\manage.py runserver
```

En otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

Abre la dirección indicada por Vite. Su proxy de desarrollo necesita Django en `127.0.0.1:8000`. La API inicial de la noticia está en `http://127.0.0.1:8000/api/stories/geopolitica/`; el contenido anterior de Roma se conserva.

Para verificar: `python backend\manage.py test stories` desde la raíz y `npm run build` dentro de `frontend/`.

La noticia se guarda en la base de datos local como registros relacionados; no es un servicio de noticias en vivo. La búsqueda automática de fuentes y la ingesta de noticias aportadas por el usuario siguen pendientes. El punto del mapa representa una ubicación aproximada de la ciudad, no el recinto exacto ni zonas de influencia. Fuentes y limitaciones: [documentación de la noticia](docs/geopolitica/COP31_FUENTES.md). La configuración de Django y el proxy son para desarrollo local.


La base de datos permite examinar y editar registros relacionados mediante el administrador Django (`/admin/`). Para entrar se necesita una cuenta administrativa local, que se puede crear con `python backend\manage.py createsuperuser`. Las búsquedas de fuentes, extracción y publicación con revisión humana todavía no están automatizadas; editar directamente con ORM no aplica necesariamente todas las validaciones entre registros. El plan y las limitaciones están en [PLAN_OBSERVATORIO.md](docs/geopolitica/PLAN_OBSERVATORIO.md).
