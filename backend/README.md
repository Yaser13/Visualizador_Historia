# Backend Django

API inicial de lectura para desarrollo local. Desde la raíz del repositorio en PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\manage.py migrate
python backend\manage.py runserver
```

Visita http://127.0.0.1:8000/api/stories/expansion-de-roma/ para ver el JSON. Para ejecutar las comprobaciones:

```powershell
python backend\manage.py check
python backend\manage.py test stories
```

Los cinco hitos están en `stories/data.py` como contenido inicial en revisión, con enlaces y localizadores. Aún no se guardan en modelos ni incluyen coordenadas verificadas; no se muestran fronteras. La API no está conectada al frontend y todavía no existe una especificación OpenAPI formal. La configuración generada es exclusivamente para desarrollo local y debe revisarse antes de cualquier despliegue. SQLite se usa para las aplicaciones integradas de Django.
