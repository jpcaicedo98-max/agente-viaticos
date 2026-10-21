import threading
import webbrowser

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from google import genai

from agente import HERRAMIENTAS, MODELO, armar_respuesta, cargar_instrucciones, ejecutar_herramientas

PUERTO = 8000
MAX_CARACTERES = 2000

load_dotenv()
client = genai.Client()
app = Flask(__name__, static_folder="static", static_url_path="/static")


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
            tools=HERRAMIENTAS,
            previous_interaction_id=datos.get("interaccion_id") or None,
        )
        informes, pasos = [], []
        interaccion = ejecutar_herramientas(client, interaccion, instrucciones, informes, pasos)
    except Exception as error:
        app.logger.exception("Falló la llamada a Gemini")
        return jsonify(error=f"No pude obtener respuesta ({type(error).__name__})."), 502

    return jsonify(
        respuesta=armar_respuesta(interaccion, informes),
        pasos=pasos,
        interaccion_id=interaccion.id,
    )


if __name__ == "__main__":
    threading.Timer(1, webbrowser.open, args=(f"http://127.0.0.1:{PUERTO}",)).start()
    app.run(host="127.0.0.1", port=PUERTO)
