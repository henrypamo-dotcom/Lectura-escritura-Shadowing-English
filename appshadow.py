import streamlit as st
import whisper
import tempfile
import json
import os
import base64 # Importamos esto explícitamente para el reproductor
import PyPDF2
from docx import Document

st.set_page_config(page_title="AppShadow", layout="wide")

# --- 1. CARGA DE MODELO ---
@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()

# --- 2. FUNCIONES DE UTILIDAD ---
def leer_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def leer_docx(file):
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

# Función para obtener audios de la carpeta "audios"
def listar_audios_biblioteca():
    carpeta = "audios"
    if not os.path.exists(carpeta):
        os.makedirs(carpeta) # Crea la carpeta si no existe para evitar errores
        return []
    # Filtra solo archivos mp3 o wav
    archivos = [f for f in os.listdir(carpeta) if f.endswith(('.mp3', '.wav'))]
    return archivos

# --- 3. INTERFAZ ---
st.title("🇬🇧 AppShadow: British Training")

# Barra lateral para elegir el MODO
modo = st.sidebar.radio("Fuente del Audio:", ["📂 Biblioteca de Lecciones", "⬆️ Subir mi propio audio"])

archivo_a_procesar = None
ruta_audio_final = None # Variable para guardar dónde está el archivo físicamente

# --- LÓGICA DE SELECCIÓN ---
if modo == "📂 Biblioteca de Lecciones":
    st.info("Selecciona una lección pre-cargada desde GitHub:")
    lista_audios = listar_audios_biblioteca()
    
    if lista_audios:
        seleccion = st.selectbox("Elige la lección:", lista_audios)
        # La ruta es directa a la carpeta
        ruta_audio_final = os.path.join("audios", seleccion)
        st.audio(ruta_audio_final) # Reproductor simple de vista previa
    else:
        st.warning("No hay audios en la carpeta 'audios' de GitHub todavía.")

else: # Modo "Subir mi propio audio"
    uploaded_file = st.file_uploader("Sube tu archivo (mp3, wav)", type=["mp3", "wav"])
    if uploaded_file is not None:
        # Guardar temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(uploaded_file.read())
            ruta_audio_final = tmp.name

# --- 4. ZONA DE GUION (Opcional) ---
with st.expander("📄 Cargar Guion / Texto de apoyo (Opcional)", expanded=False):
    text_file = st.file_uploader("Sube el texto", type=["txt", "pdf", "docx"])
    if text_file:
        # (Lógica de lectura de texto igual que antes...)
        if text_file.name.endswith('.pdf'):
            contenido = leer_pdf(text_file)
        elif text_file.name.endswith('.docx'):
            contenido = leer_docx(text_file)
        else:
            contenido = text_file.read().decode("utf-8")
        st.text_area("Guion:", contenido, height=200)

# --- 5. PROCESAMIENTO Y KARAOKE ---
if ruta_audio_final and st.button("🚀 Iniciar Shadowing"):
    
    with st.spinner("Analizando audio con IA..."):
        # Transcribir usando la ruta definida arriba
        result = model.transcribe(ruta_audio_final, word_timestamps=True)
        
        # Preparar JSON
        word_data = []
        for segment in result["segments"]:
            for word in segment["words"]:
                word_data.append({
                    "word": word["word"],
                    "start": word["start"],
                    "end": word["end"]
                })
        json_data = json.dumps(word_data)

        # Leer los bytes del archivo para el reproductor HTML
        # (Necesitamos leerlo de nuevo para pasarlo a base64 al navegador)
        with open(ruta_audio_final, "rb") as f:
            audio_bytes = f.read()
            b64_audio = base64.b64encode(audio_bytes).decode()

        # HTML/JS Player (Versión Compacta)
        html_code = f"""
        <style>
            .transcript {{ font-family: sans-serif; font-size: 18px; line-height: 1.6; max-height: 400px; overflow-y: auto; padding: 10px; background: #f9f9f9; border: 1px solid #ddd; }}
            .word {{ padding: 2px 4px; border-radius: 4px; cursor: pointer; transition: 0.2s; }}
            .highlight {{ background-color: #ff4b4b; color: white; font-weight: bold; transform: scale(1.1); display: inline-block; }}
        </style>
        <audio id="player" controls style="width: 100%; margin-bottom: 10px;">
            <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
        </audio>
        <div id="text-container" class="transcript"></div>
        <script>
            const data = {json_data};
            const container = document.getElementById('text-container');
            const player = document.getElementById('player');
            
            data.forEach((d, i) => {{
                const s = document.createElement('span');
                s.innerText = d.word + " ";
                s.className = 'word';
                s.id = 'w-' + i;
                s.onclick = () => {{ player.currentTime = d.start; player.play(); }};
                container.appendChild(s);
            }});

            player.ontimeupdate = () => {{
                const t = player.currentTime;
                data.forEach((d, i) => {{
                    const el = document.getElementById('w-' + i);
                    if (t >= d.start && t <= d.end) {{
                        el.classList.add('highlight');
                        el.scrollIntoView({{behavior: "smooth", block: "center"}});
                    }} else {{ el.classList.remove('highlight'); }}
                }});
            }};
        </script>
        """
        st.components.v1.html(html_code, height=450)

    # Limpieza solo si fue un archivo temporal (subido por usuario)
    # Si viene de "audios/" no lo borramos
    if modo == "⬆️ Subir mi propio audio" and os.path.exists(ruta_audio_final):
        os.remove(ruta_audio_final)
