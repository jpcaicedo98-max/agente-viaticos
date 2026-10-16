import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai

MODELO = "gemini-3.5-flash-lite"
RAIZ = Path(__file__).parent
RUTA_SISTEMA = RAIZ / "Prompts" / "sistema.md"
CARPETA_CONOCIMIENTO = RAIZ / "Conocimiento"


def cargar_documentos():
    documentos = []
    for ruta in sorted(CARPETA_CONOCIMIENTO.iterdir()):
        if ruta.is_file():
            contenido = ruta.read_text(encoding="utf-8")
            documentos.append(f'<documento nombre="{ruta.name}">\n{contenido}\n</documento>')
    return "\n\n".join(documentos)


INSTRUCCIONES = RUTA_SISTEMA.read_text(encoding="utf-8") + "\n\n" + cargar_documentos()

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
