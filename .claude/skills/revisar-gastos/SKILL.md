---
name: revisar-gastos
description: Revisa una legalización de gastos de viaje (archivo CSV) contra la política de viáticos y entrega un informe con el veredicto de cada gasto y el total a reembolsar. Úsala cuando pidan revisar, validar o calcular el reembolso de una legalización. No la uses para consultar topes ni para crear datos de ejemplo.
---

# Revisar una legalización de gastos de viaje

## Cuándo usarla

Cuando pidan revisar, validar o calcular el reembolso de una legalización en CSV. Si no dicen cuál archivo, búscalo en `datos/` y, si hay duda, pregunta.

## Pasos

1. Ejecuta el script con la ruta del CSV:

   ```
   python .claude/skills/revisar-gastos/scripts/validar.py datos/legalizacion_L-2031.csv
   ```

   Si `python` no está en el PATH, usa el del entorno del proyecto (`.venv/Scripts/python.exe`).
2. Muestra el informe que imprime el script **sin cambiar ninguna cifra**: ni veredictos, ni valores, ni el total. No recalcules a mano. Si el script falla, informa el error tal cual.
3. Después del informe, agrega una sección **Notas del revisor** con lo que el script no puede juzgar y que sea relevante para esa legalización. Son observaciones: no cambian el informe. Por ejemplo:
   - Plazo de legalización de 5 días hábiles desde el regreso (sección 5).
   - Tiquetes: clase económica, agencia de la empresa y 7 días de anticipación (sección 2).
   - Hospedaje en hotel de máximo 4 estrellas (sección 2).
   - Si hay una autorización del director emitida antes del viaje para un exceso rechazado (sección 4).
   - Si los "otros gastos" se relacionan con el motivo del viaje, y si alguna comida incluye acompañantes (secciones 2 y 6).
   - Facturas a nombre de Altiplano S.A.S. (sección 5).

## Archivos

- `scripts/validar.py`: decide los veredictos y calcula el total.
- `plantilla_informe.md`: formato del informe que llena el script.
- `referencia/politica_viaticos.md`: política de viáticos, versión 2.0, para consultar ante cualquier duda.
