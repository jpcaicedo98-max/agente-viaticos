"""Valida una legalización de gastos de viaje contra la política de viáticos.

Uso:
    python validar.py <ruta_del_csv>

Lee el CSV (UTF-8), decide el veredicto de cada gasto según
referencia/politica_viaticos.md, calcula el total a reembolsar e imprime el
informe llenando plantilla_informe.md. Solo usa la biblioteca estándar.

Orden de decisión de cada gasto (el primero que aplica gana):
  1. Dato faltante o no válido (valor, fecha, categoría)  -> Devuelto
  2. Gasto no reembolsable (sección 6)                    -> Rechazado
  3. Supera el tope de su categoría (secciones 2 y 4)     -> Rechazado
  4. Mayor a $30.000 COP sin factura (sección 5)          -> Devuelto
  5. Supera $1.500.000 COP, falta el director (sección 3) -> Devuelto
  6. Cumple                                               -> Aprobado
"""

import csv
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ_SKILL / "plantilla_informe.md"

COLUMNAS = {
    "legalizacion", "empleado", "ciudad", "salida", "regreso",
    "id", "fecha", "categoria", "descripcion", "factura", "valor_cop",
}

# Política, sección 2.
CIUDADES_GRUPO_A = {"bogota", "medellin", "cartagena"}
TOPE_ALIMENTACION = 95_000          # por día
TOPE_HOSPEDAJE = {"A": 320_000, "B": 240_000}  # por noche
TOPE_TRANSPORTE = 60_000            # por día

# Política, secciones 3 y 5.
LIMITE_SIN_FACTURA = 30_000
LIMITE_SIN_DIRECTOR = 1_500_000

# Política, sección 6: palabras que delatan un gasto no reembolsable.
NO_REEMBOLSABLES = [
    ("minibar", "consumo de minibar"),
    ("alcohol", "bebidas alcohólicas"),
    ("licor", "bebidas alcohólicas"),
    ("cerveza", "bebidas alcohólicas"),
    ("vino", "bebidas alcohólicas"),
    ("aguardiente", "bebidas alcohólicas"),
    ("propina", "propinas"),
    ("multa", "multas de tránsito"),
    ("comparendo", "multas de tránsito"),
    ("cine", "entretenimiento personal"),
    ("concierto", "entretenimiento personal"),
    ("tour", "entretenimiento personal"),
    ("acompanante", "gastos de acompañantes"),
]


def sin_tildes(texto):
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn").lower().strip()


def tipo_categoria(categoria):
    """Clasifica la categoría del CSV; devuelve None si no la reconoce."""
    c = sin_tildes(categoria)
    if c.startswith("tiquete") or c.startswith("pasaje"):
        return "tiquete"
    for tipo in ("alimentacion", "hospedaje", "transporte", "otros"):
        if c.startswith(tipo):
            return tipo
    return None


def parsear_valor(texto):
    texto = (texto or "").strip()
    if not re.fullmatch(r"\d+", texto):
        return None
    valor = int(texto)
    return valor if valor > 0 else None


def parsear_fecha(texto):
    try:
        return date.fromisoformat((texto or "").strip())
    except ValueError:
        return None


def pesos(valor):
    return f"${valor:,}".replace(",", ".") + " COP"


def leer_gastos(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        faltan = COLUMNAS - set(lector.fieldnames or [])
        if faltan:
            raise ValueError("Faltan columnas en el CSV: " + ", ".join(sorted(faltan)))
        filas = [fila for fila in lector if any((v or "").strip() for v in fila.values())]
    if not filas:
        raise ValueError("El CSV no tiene gastos.")
    for campo in ("legalizacion", "empleado", "ciudad", "salida", "regreso"):
        if len({fila[campo].strip() for fila in filas}) > 1:
            raise ValueError(f"El CSV mezcla varios valores de '{campo}'; revisa una legalización por archivo.")
    return filas


def decidir(filas):
    """Devuelve (grupo, resultados); cada resultado es (fila, veredicto, motivo, valor)."""
    cabecera = filas[0]
    grupo = "A" if sin_tildes(cabecera["ciudad"]) in CIUDADES_GRUPO_A else "B"
    salida = parsear_fecha(cabecera["salida"])
    regreso = parsear_fecha(cabecera["regreso"])
    noches = (regreso - salida).days if salida and regreso else None

    # Primera pasada: datos y gastos no reembolsables; acumula por categoría y fecha.
    previo = []
    acumulado = defaultdict(int)
    for fila in filas:
        valor = parsear_valor(fila["valor_cop"])
        fecha = parsear_fecha(fila["fecha"])
        tipo = tipo_categoria(fila["categoria"])
        if valor is None:
            previo.append(("Devuelto", "Sección 5: el valor falta o no es válido.", None, None, None))
            continue
        if fecha is None:
            previo.append(("Devuelto", "Sección 5: la fecha falta o no es válida.", valor, None, None))
            continue
        if tipo is None:
            previo.append(("Devuelto", "Sección 2: categoría no reconocida.", valor, None, None))
            continue
        texto = sin_tildes(fila["categoria"] + " " + fila["descripcion"])
        motivo = next((m for palabra, m in NO_REEMBOLSABLES
                       if re.search(r"\b" + palabra, texto)), None)
        if motivo is None and "lavanderia" in texto and (noches is None or noches < 5):
            motivo = "lavandería en viajes de menos de 5 noches"
        if motivo:
            previo.append(("Rechazado", f"Sección 6: {motivo}.", valor, fecha, tipo))
            continue
        previo.append((None, "", valor, fecha, tipo))
        if tipo in ("alimentacion", "hospedaje", "transporte"):
            acumulado[(tipo, fecha)] += valor

    # Segunda pasada: topes, factura y aprobación del director.
    resultados = []
    for fila, (veredicto, motivo, valor, fecha, tipo) in zip(filas, previo):
        if veredicto is None:
            veredicto, motivo = "Aprobado", ""
            tope = {
                "alimentacion": TOPE_ALIMENTACION,
                "hospedaje": TOPE_HOSPEDAJE[grupo],
                "transporte": TOPE_TRANSPORTE,
            }.get(tipo)
            if tope is not None and acumulado[(tipo, fecha)] > tope:
                unidad = "noche" if tipo == "hospedaje" else "día"
                veredicto = "Rechazado"
                motivo = (f"Secciones 2 y 4: supera el tope de {pesos(tope)} por {unidad} "
                          f"(total del {fecha}: {pesos(acumulado[(tipo, fecha)])}).")
            elif valor > LIMITE_SIN_FACTURA and not fila["factura"].strip():
                veredicto = "Devuelto"
                motivo = "Sección 5: falta la factura electrónica."
            elif valor > LIMITE_SIN_DIRECTOR:
                veredicto = "Devuelto"
                motivo = "Sección 3: requiere aprobación del director del área."
        resultados.append((fila, veredicto, motivo, valor))
    return grupo, resultados


def construir_informe(filas, grupo, resultados):
    cabecera = filas[0]
    lineas = []
    for fila, veredicto, motivo, valor in resultados:
        mostrado = pesos(valor) if valor is not None else fila["valor_cop"].strip()
        celdas = [fila["id"].strip(), fila["fecha"].strip(), fila["categoria"].strip(),
                  mostrado, veredicto, motivo]
        lineas.append("| " + " | ".join(celdas) + " |")

    def cuenta(nombre):
        return sum(1 for r in resultados if r[1] == nombre)

    total = sum(r[3] for r in resultados if r[1] == "Aprobado")
    datos = {
        "legalizacion": cabecera["legalizacion"].strip(),
        "empleado": cabecera["empleado"].strip(),
        "ciudad": cabecera["ciudad"].strip(),
        "grupo": grupo,
        "salida": cabecera["salida"].strip(),
        "regreso": cabecera["regreso"].strip(),
        "filas": "\n".join(lineas),
        "presentados": str(len(resultados)),
        "aprobados": str(cuenta("Aprobado")),
        "rechazados": str(cuenta("Rechazado")),
        "devueltos": str(cuenta("Devuelto")),
        "total": pesos(total),
    }
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    return re.sub(r"\{(\w+)\}", lambda m: datos[m.group(1)], plantilla)


def main(argv):
    if len(argv) != 2:
        print("Uso: python validar.py <ruta_del_csv>", file=sys.stderr)
        return 2
    try:
        filas = leer_gastos(argv[1])
        grupo, resultados = decidir(filas)
        informe = construir_informe(filas, grupo, resultados)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    sys.stdout.reconfigure(encoding="utf-8")
    print(informe, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
