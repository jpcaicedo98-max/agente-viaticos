import threading
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from google import genai

MODELO = "gemini-3.5-flash-lite"
RUTA_INSTRUCCIONES = Path(__file__).parent / "Prompts" / "sistema.md"
PUERTO = 8000
CARPETA_CONOCIMIENTO = Path(__file__).parent / "Conocimiento"
MAX_CARACTERES = 2000

load_dotenv()
client = genai.Client()
app = Flask(__name__, static_folder="static", static_url_path="/static")


def cargar_instrucciones():
    documentos = []
    for ruta in sorted(CARPETA_CONOCIMIENTO.iterdir()):
        if ruta.is_file():
            contenido = ruta.read_text(encoding="utf-8")
            documentos.append(f'<documento nombre="{ruta.name}">\n{contenido}\n</documento>')
    base = RUTA_INSTRUCCIONES.read_text(encoding="utf-8")
    return base + "\n\n" + "\n\n".join(documentos)


@app.get("/")
def inicio():
    return app.send_static_file("index.html")


@app.post("/api/chat")
def chat():
    datos = request.get_json(silent=True) or {}
    mensaje = str(datos.get("mensaje", "")).strip()
    if not mensaje:
        return jsonify(error="Escribe tu pregunta."), 400
    if len(mensaje) > MAX_CARACTERES:
        return jsonify(error=f"El mensaje supera los {MAX_CARACTERES} caracteres."), 400

    # Se lee en cada petición: si editas sistema.md o Conocimiento/, no hace falta reiniciar.
    instrucciones = cargar_instrucciones()
    try:
        interaccion = client.interactions.create(
            model=MODELO,
            system_instruction=instrucciones,
            input=mensaje,
            previous_interaction_id=datos.get("interaccion_id") or None,
        )
    except Exception as error:
        app.logger.exception("Falló la llamada a Gemini")
        return jsonify(error=f"No pude obtener respuesta ({type(error).__name__})."), 502

    return jsonify(respuesta=interaccion.output_text or "", interaccion_id=interaccion.id)


if __name__ == "__main__":
    threading.Timer(1, webbrowser.open, args=(f"http://127.0.0.1:{PUERTO}",)).start()
    app.run(host="127.0.0.1", port=PUERTO)
