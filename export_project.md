# Export Project

Este archivo acompana a export_project.ps1 y se incluye en cada ZIP de exportacion.

## Restauracion rapida

1. Extraer el ZIP en una carpeta de trabajo.
2. Crear y activar un entorno virtual de Python.
3. Instalar dependencias:
   - `python -m pip install -r requirements.txt`
4. Ejecutar el proceso necesario del proyecto (por ejemplo, scripts .py o .bat).

## Notas

- El ZIP se genera con exclusiones de caches, entornos virtuales y artefactos temporales.
- Este archivo es obligatorio porque el exportador valida su presencia antes de comprimir.
