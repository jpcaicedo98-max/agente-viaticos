import sys

from dotenv import load_dotenv
from google import genai

MODELO = "gemini-3.5-flash-lite"
INSTRUCCIONES = "Responde como cavernicola."

load_dotenv()
client = genai.Client()

if len(sys.argv) < 2:
    sys.exit('Uso: python agente.py "tu pregunta"')

pregunta = " ".join(sys.argv[1:])

interaccion = client.interactions.create(
    model=MODELO,
    system_instruction=INSTRUCCIONES,
    input=pregunta,
)

print(interaccion.output_text)
