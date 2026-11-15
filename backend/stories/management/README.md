# Carga de la instantánea COP31

Con la dependencia Django instalada y en un entorno local de desarrollo, desde la raíz:

```powershell
.\.venv\Scripts\Activate.ps1
python backend\manage.py migrate
python backend\manage.py seed_cop31
python backend\manage.py test stories
```

La operación crea la instantánea inicial dentro de una transacción. Si el evento ya existe, el comando termina sin añadir ni modificar registros: no restaura automáticamente afirmaciones editadas o eliminadas ni completa cargas parciales. Estas situaciones requieren revisión editorial explícita. No descarga fuentes ni actualiza la noticia. La fecha de corte es 15 de noviembre de 2026. La API `/api/stories/geopolitica/` lee registros revisados y afirmaciones respaldadas con evidencia; si no hay contenido utilizable devuelve 404 JSON. Antes de migrar una base que contenga información valiosa, respáldala. `full_clean()` se aplica en esta carga; las escrituras directas con ORM pueden evadir validaciones de integridad cruzada. El endpoint de Roma se conserva.

