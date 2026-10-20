import csv
import json
import sys
import unicodedata
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from google import genai

MODELO = "gemini-3.5-flash-lite"
RAIZ = Path(__file__).parent
RUTA_SISTEMA = RAIZ / "Prompts" / "sistema.md"
CARPETA_CONOCIMIENTO = RAIZ / "Conocimiento"
RUTA_GASTOS = CARPETA_CONOCIMIENTO / "gastos.csv"
RUTA_SOLICITUDES = RAIZ / "solicitudes.csv"
CAMPOS_SOLICITUD = [
    "radicado", "fecha_registro", "empleado", "ciudad",
    "fecha_salida", "noches", "motivo", "estado",
]
ESTADO_SOLICITUD = "Pendiente de aprobación del jefe inmediato"
MAX_VUELTAS = 5


def cargar_documentos():
    documentos = []
    for ruta in sorted(CARPETA_CONOCIMIENTO.glob("*.md")):
        contenido = ruta.read_text(encoding="utf-8")
        documentos.append(f'<documento nombre="{ruta.name}">\n{contenido}\n</documento>')
    return "\n\n".join(documentos)


def normalizar(texto):
    sin_tildes = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).casefold().strip()


def sumar_gastos(area=None, estado=None):
    filas = 0
    total = 0
    with open(RUTA_GASTOS, encoding="utf-8", newline="") as archivo:
        for gasto in csv.DictReader(archivo):
            if area and normalizar(gasto["area"]) != normalizar(area):
                continue
            if estado and normalizar(gasto["estado"]) != normalizar(estado):
                continue
            filas += 1
            total += int(gasto["valor_cop"])
    return {"filas": filas, "total_cop": total}


def registrar_solicitud(empleado, ciudad, fecha_salida, noches, motivo):
    existe = RUTA_SOLICITUDES.exists()
    consecutivo = 1
    if existe:
        with open(RUTA_SOLICITUDES, encoding="utf-8", newline="") as archivo:
            consecutivo += sum(1 for _ in csv.DictReader(archivo))
    radicado = f"S-{consecutivo:03d}"
    with open(RUTA_SOLICITUDES, "a", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS_SOLICITUD)
        if not existe:
            escritor.writeheader()
        escritor.writerow({
            "radicado": radicado,
            "fecha_registro": date.today().isoformat(),
            "empleado": empleado,
            "ciudad": ciudad,
            "fecha_salida": fecha_salida,
            "noches": noches,
            "motivo": motivo,
            "estado": ESTADO_SOLICITUD,
        })
    return {"radicado": radicado}


FUNCIONES = {
    "sumar_gastos": sumar_gastos,
    "registrar_solicitud": registrar_solicitud,
}

HERRAMIENTAS = [
    {
        "type": "function",
        "name": "sumar_gastos",
        "description": (
            "Cuenta y suma los gastos de viaje registrados en gastos.csv. Úsala siempre que "
            "pregunten cuántos gastos hay o cuánto suman, en total o filtrando por área y/o "
            "estado. Devuelve el número de filas y el total en COP."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "area": {
                    "type": "string",
                    "description": (
                        "Área del empleado, por ejemplo Ventas, Operaciones, Tecnología, "
                        "Mercadeo o Gestión Humana. Omítelo para incluir todas las áreas."
                    ),
                },
                "estado": {
                    "type": "string",
                    "description": (
                        "Estado del gasto: Aprobado, Pendiente o Rechazado. "
                        "Omítelo para incluir todos los estados."
                    ),
                },
            },
        },
    },
    {
        "type": "function",
        "name": "registrar_solicitud",
        "description": (
            "Registra una solicitud de viaje y devuelve su número de radicado. Úsala solo "
            "cuando el usuario pida registrar o radicar una solicitud y ya tengas los cinco "
            "datos; si falta alguno, pídelo antes de llamarla."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "empleado": {"type": "string", "description": "Nombre completo del empleado."},
                "ciudad": {"type": "string", "description": "Ciudad de destino del viaje."},
                "fecha_salida": {
                    "type": "string",
                    "description": "Fecha de salida del viaje, en formato AAAA-MM-DD.",
                },
                "noches": {"type": "integer", "description": "Número de noches del viaje."},
                "motivo": {"type": "string", "description": "Motivo del viaje de trabajo."},
            },
            "required": ["empleado", "ciudad", "fecha_salida", "noches", "motivo"],
        },
    },
]

def cargar_instrucciones():
    return RUTA_SISTEMA.read_text(encoding="utf-8") + "\n\n" + cargar_documentos()


def llamadas_pendientes(interaccion):
    return [paso for paso in interaccion.steps or [] if paso.type == "function_call"]


def ejecutar_herramientas(client, interaccion, instrucciones):
    for _ in range(MAX_VUELTAS):
        llamadas = llamadas_pendientes(interaccion)
        if not llamadas:
            return interaccion

        resultados = []
        for llamada in llamadas:
            try:
                resultado = FUNCIONES[llamada.name](**llamada.arguments)
            except Exception as error:
                resultado = {"error": f"{type(error).__name__}: {error}"}
            print(f"[herramienta] {llamada.name}({llamada.arguments}) -> {resultado}")
            resultados.append({
                "type": "function_result",
                "name": llamada.name,
                "call_id": llamada.id,
                "result": [{"type": "text", "text": json.dumps(resultado, ensure_ascii=False)}],
            })

        interaccion = client.interactions.create(
            model=MODELO,
            system_instruction=instrucciones,
            input=resultados,
            tools=HERRAMIENTAS,
            previous_interaction_id=interaccion.id,
        )

    if llamadas_pendientes(interaccion):
        print(f"[aviso] Se alcanzó el máximo de {MAX_VUELTAS} vueltas con herramientas.")
    return interaccion


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python agente.py "tu pregunta"')

    load_dotenv()
    client = genai.Client()
    instrucciones = cargar_instrucciones()

    interaccion = client.interactions.create(
        model=MODELO,
        system_instruction=instrucciones,
        input=" ".join(sys.argv[1:]),
        tools=HERRAMIENTAS,
    )
    interaccion = ejecutar_herramientas(client, interaccion, instrucciones)

    if interaccion.output_text:
        print(interaccion.output_text)
    else:
        pasos = [paso.type for paso in interaccion.steps or []]
        print(f"[aviso] El modelo no devolvió texto (estado: {interaccion.status}, pasos: {pasos}).")


if __name__ == "__main__":
    main()
