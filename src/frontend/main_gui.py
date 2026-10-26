"""
================================================================================
SMART CV FILTER - CLOUD EDITION (GOOGLE GEMINI POWERED)
================================================================================
Author: Tebagl
Date: April 2026
Version: 2.0 (Cloud Migration)

DESCRIPTION:
An intelligent GUI-based recruitment tool that automates resume screening.
This version utilizes the Google Gemini API (gemini-3.1-flash-lite) for cloud 
inference, significantly reducing local RAM and CPU consumption.

KEY FEATURES:
- Multithreaded Processing: Keeps the UI responsive during API calls.
- Google Gemini Integration: Fast cloud CV analysis via Google AI Studio.
- X11 Force-Rendering: Bypasses Wayland/Linux segmentation faults.
- Dynamic Result Management: Real-time candidate scoring and CSV logging.

DEPENDENCIES:
- CustomTkinter: Modern GUI framework.
- Requests: API communication.
- Python-Dotenv: Secure API key management via conf.env.
- Subprocess: System-level PDF/Docx viewing.

USAGE:
Run with 'python3 src/frontend/main_gui.py'. 
Requires a valid GEMINI_API_KEY in the root conf.env file.
================================================================================
"""

# 1. Ajustes del Sistema Operativo
import os
os.environ["GDK_BACKEND"] = "x11"

# 2. Librerías Estándar de Python
import sys
import threading
import logging
import queue
import platform
import subprocess
from pathlib import Path
import time

# 3. Librerías de Interfaz Gráfica
import tkinter
import customtkinter as ctk


# --- Configuración de Rutas ---
def get_resource_path():
    """Ruta para archivos internos (código, iconos, etc.)"""
    if getattr(sys, 'frozen', False):
        # Estamos en el ejecutable
        return sys._MEIPASS
    
    # Estamos en desarrollo: subimos desde src/frontend/ a la raíz
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def get_executable_path():
    """Ruta donde reside el archivo .exe o el binario (para carpetas de salida)"""
    if getattr(sys, 'frozen', False):
        # Si es el ejecutable, queremos la carpeta donde está el archivo físico
        return os.path.dirname(sys.executable)
    # Si es modo desarrollo, usamos la raíz del proyecto
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Definimos las dos rutas críticas
resource_path = get_resource_path()    
executable_path = get_executable_path() # Para crear 'procesos_seleccion'

# Importante: los imports del backend deben buscarse en resource_path
sys.path.insert(0, resource_path)

# Importar el backend
from src.backend.cv_handler import CVHandler
from src.backend.analyzer import CVAnalyzer
from src.backend.process_manager import ProcessManager

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Carga Dinámica del Archivo de Configuración ---
from dotenv import load_dotenv

# Reutilizamos la ruta que calcula correctamente si estamos en desarrollo o empaquetados
dotenv_path = os.path.join(executable_path, 'conf.env')
load_dotenv(dotenv_path)

logger.info(f"Buscando configuración en: {dotenv_path}")

# Paleta del dashboard (grafito / índigo / esmeralda)
COLOR_BG = "#1e1e24"
COLOR_SURFACE = "#2b2b36"
COLOR_CARD = "#252530"
COLOR_ACCENT = "#4361ee"
COLOR_ACCENT_HOVER = "#3a86ff"
COLOR_SUCCESS = "#10b981"
COLOR_SUCCESS_HOVER = "#059669"
COLOR_AMBER = "#f59e0b"
COLOR_AMBER_HOVER = "#d97706"
COLOR_TEXT = "#e8e8ed"
COLOR_MUTED = "#9aa0ae"
COLOR_BORDER = "#3a3a48"
COLOR_LOG_BG = "#16161c"
RADIUS = 10
SECONDS_PER_CV = 11.5


class SmartCVFilterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()  # Evita que la ventana parpadee antes de configurar todo

        # 1. Configuración de la Ventana Principal (Establece la raíz de TK)
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=COLOR_BG)
        self.title("Smart CV Filter")
        self.geometry("1100x950")
        self.minsize(760, 560)
        self.resizable(True, True)
        

        # 2. INICIALIZACIÓN DE RUTAS Y VARIABLES (Obligatorio antes de widgets)
        self.default_dest_path = os.path.join(executable_path, "procesos_seleccion")
        if not os.path.exists(self.default_dest_path):
            os.makedirs(self.default_dest_path)
            
        self.input_folder = ctk.StringVar(value="")
        self.results_dir = ""
        self.shown_accepted = set()
        self.api_key = None
        self.log_queue = queue.Queue()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.analyzing = False
        self.paused = False
        self.pause_started_at = None
        self.pause_timer_job = None
        self._alert_win = None
        self._alert_after_id = None
        self._alert_generation = 0

        # 3. Inicialización de Backend y Estado
        self.analyzer = CVAnalyzer()
        # Reintentos HTTP (503/429/timeout): solo texto en el log, nunca alerta audiovisual.
        self.analyzer.status_callback = self._log_analyzer_status
        self.cv_handler = CVHandler(self.analyzer)
        self.process_manager = ProcessManager(executable_path, self.cv_handler)
        
        # 4. Creación de Interfaz (Dibuja los widgets antes de cualquier diálogo)
        self.create_widgets()
        self.update_idletasks()
        
        # Mostrar la ventana ya renderizada en negro
        self.deiconify()

        # 5. Iniciar consumidores de colas
        self.check_queues()

        # 6. Verificación de Configuración con retraso (SOLUCIÓN VENTANA DOBLE)
        self.after(200, self.verificar_configuracion_inicial)

    def verificar_configuracion_inicial(self):
        """Valida la API Key. Si no existe, fuerza su creación persistente en disco."""
        from dotenv import set_key

        # 1. Comprobar si el analizador ya leyó una clave válida del archivo conf.env
        if self.analyzer.api_key:
            self.api_key = self.analyzer.api_key
            self.log_mensaje("✅ API Key cargada automáticamente desde conf.env")
            return

        # 2. Si no hay clave, entramos en el bucle de solicitud inicial
        self.log_mensaje("⚠️ No se detectó API Key en conf.env. Solicitando configuración...")
        
        while True:
            api_key_usuario = self.solicitar_api_key()
            
            # Caso A: El usuario pulsó "Cancel" o dejó el cuadro vacío
            if not api_key_usuario or not api_key_usuario.strip():
                self.log_mensaje("🛑 Aplicación cerrada por falta de API Key válida.")
                self.destroy() # Cerramos la ventana de Tkinter inmediatamente
                return # Salimos de la función de forma segura
                
            # Limpiamos la clave de posibles espacios o saltos de línea (\n)
            api_key_usuario = api_key_usuario.strip()
            
            # Validamos un formato mínimo (longitud razonable, sin espacios internos)
            if len(api_key_usuario) > 20 and " " not in api_key_usuario:
                try:
                    # 💾 EL REMEDIO: Escribir físicamente el archivo conf.env en la ruta del ejecutable
                    set_key(dotenv_path, "GEMINI_API_KEY", api_key_usuario)
                    
                    self.api_key = api_key_usuario
                    self.analyzer.set_api_key(self.api_key)
                    
                    self.log_mensaje(f"💾 ¡Éxito! Archivo 'conf.env' generado en: {dotenv_path}")
                    break # Rompemos el bucle, la clave es correcta
                except Exception as e:
                    self.log_mensaje(f"❌ Error crítico escribiendo conf.env en disco: {e}")
                    break
            else:
                aviso = "La clave introducida no parece una API Key válida de Google Gemini."
                self.log_mensaje(f"❌ {aviso}")
                self.trigger_alert_notice("Error de Clave", aviso)

    def _habilitar_pegar_entry(self, dialog, entry):
        """Menú contextual (clic derecho) en el CTkEntry de la API Key."""
        widget = getattr(entry, "_entry", entry)
        menu_contextual = tkinter.Menu(
            dialog,
            tearoff=0,
            bg=COLOR_SURFACE,
            fg="white",
            activebackground=COLOR_ACCENT,
            bd=0,
        )

        def _texto_seleccionado():
            try:
                if widget.selection_present():
                    return widget.selection_get()
            except tkinter.TclError:
                pass
            return ""

        def pegar():
            try:
                texto = dialog.clipboard_get()
            except tkinter.TclError:
                return
            if not texto:
                return
            try:
                if widget.selection_present():
                    widget.delete("sel.first", "sel.last")
            except tkinter.TclError:
                pass
            widget.insert("insert", texto)

        def copiar():
            texto = _texto_seleccionado()
            if not texto:
                return
            dialog.clipboard_clear()
            dialog.clipboard_append(texto)

        def cortar():
            texto = _texto_seleccionado()
            if not texto:
                return
            dialog.clipboard_clear()
            dialog.clipboard_append(texto)
            try:
                widget.delete("sel.first", "sel.last")
            except tkinter.TclError:
                pass

        menu_contextual.add_command(label="Pegar", command=pegar)
        menu_contextual.add_command(label="Copiar", command=copiar)
        menu_contextual.add_command(label="Cortar", command=cortar)

        def mostrar_menu(event):
            entry.focus_set()
            try:
                menu_contextual.tk_popup(event.x_root + 2, event.y_root + 2)
            finally:
                menu_contextual.grab_release()
            return "break"

        # CTkEntry es un Frame: el clic derecho cae en el tk.Entry interno.
        for target in (entry, widget):
            target.bind("<Button-3>", mostrar_menu)
            target.bind("<Button-2>", mostrar_menu)

    def _dialogo_entrada_api_key(self, titulo, mensaje):
        """Ventana modal CustomTkinter para introducir la API Key. Devuelve el texto o None."""
        result = {"value": None}
        dialog = ctk.CTkToplevel(self)
        dialog.title(titulo)
        dialog.geometry("480x230")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.configure(fg_color=COLOR_CARD)

        ctk.CTkLabel(
            dialog,
            text=mensaje,
            font=("Segoe UI", 13, "bold"),
            text_color=COLOR_TEXT,
            wraplength=430,
            justify="left",
        ).pack(padx=22, pady=(22, 10), anchor="w")

        entry = ctk.CTkEntry(
            dialog,
            width=430,
            show="•",
            corner_radius=8,
            border_color=COLOR_BORDER,
            fg_color=COLOR_SURFACE,
            text_color=COLOR_TEXT,
        )
        entry.pack(padx=22)
        self._habilitar_pegar_entry(dialog, entry)

        def confirmar():
            result["value"] = entry.get()
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()

        def cancelar():
            result["value"] = None
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()

        botones = ctk.CTkFrame(dialog, fg_color="transparent")
        botones.pack(pady=22)
        ctk.CTkButton(
            botones, text="Guardar", width=120, corner_radius=8,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=confirmar,
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            botones, text="Cancelar", width=120, corner_radius=8,
            fg_color=COLOR_SURFACE, hover_color=COLOR_BORDER, command=cancelar,
        ).pack(side="left", padx=10)

        entry.bind("<Return>", lambda event: confirmar())
        entry.bind("<Escape>", lambda event: cancelar())
        dialog.protocol("WM_DELETE_WINDOW", cancelar)
        dialog.after(150, lambda: (dialog.grab_set(), entry.focus_set()))
        self.wait_window(dialog)
        return result["value"]

    def solicitar_api_key(self):
        """Diálogo inicial de API Key con CTkToplevel y la paleta oscura de la app."""
        return self._dialogo_entrada_api_key(
            "Configuración inicial",
            "Introduce tu Google Gemini API Key.\nEl archivo de configuración se creará automáticamente.",
        )

    def abrir_dialogo_api_key(self):
        """Diálogo para cambiar la API Key de Gemini en cualquier momento."""
        nueva_clave = self._dialogo_entrada_api_key(
            "Configurar API Key",
            "Introduce tu nueva API Key de Google Gemini:",
        )
        if not nueva_clave or not nueva_clave.strip():
            return
        nueva_clave = nueva_clave.strip()
        if len(nueva_clave) <= 20 or " " in nueva_clave:
            aviso = "La clave introducida no parece una API Key válida de Google Gemini."
            self.log_mensaje(f"❌ {aviso}")
            self.trigger_alert_notice("Error de Clave", aviso)
            return
        self.guardar_api_key(nueva_clave)

    def guardar_api_key(self, nueva_clave):
        """Persiste la clave en conf.env y la aplica al analizador sin reiniciar."""
        from dotenv import set_key
        try:
            set_key(dotenv_path, "GEMINI_API_KEY", nueva_clave)
        except Exception as e:
            self.log_mensaje(f"❌ Error guardando la API Key en conf.env: {e}")
            return False

        os.environ["GEMINI_API_KEY"] = nueva_clave
        self.api_key = nueva_clave
        if getattr(self, "analyzer", None):
            self.analyzer.set_api_key(nueva_clave)

        self.log_mensaje("🔑 API Key de Gemini guardada en conf.env y aplicada con éxito.")
        return True

    def log_mensaje(self, texto):
        """Método auxiliar para escribir en el log de la UI de forma segura"""
        if hasattr(self, 'log_text'):
            self.log_text.insert("end", f"{texto}\n")
            self.log_text.see("end")

    def _card(self, parent, **kwargs):
        opts = {
            "fg_color": COLOR_CARD,
            "corner_radius": RADIUS,
            "border_width": 1,
            "border_color": COLOR_BORDER,
        }
        opts.update(kwargs)
        return ctk.CTkFrame(parent, **opts)

    def _label(self, parent, text, muted=False, size=12, bold=True):
        return ctk.CTkLabel(
            parent,
            text=text,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            text_color=COLOR_MUTED if muted else COLOR_TEXT,
            anchor="w",
        )

    def _entry(self, parent, **kwargs):
        opts = {
            "corner_radius": 8,
            "border_color": COLOR_BORDER,
            "fg_color": COLOR_SURFACE,
            "text_color": COLOR_TEXT,
            "placeholder_text_color": COLOR_MUTED,
            "height": 34,
        }
        opts.update(kwargs)
        return ctk.CTkEntry(parent, **opts)

    def _secondary_button(self, parent, text, command, width=110):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=34,
            corner_radius=8,
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=("Segoe UI", 12),
        )

    def _path_row(self, parent, label, command, textvariable=None, initial=None, placeholder="Selecciona una carpeta..."):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))
        self._label(row, label, muted=True, size=11).pack(anchor="w", pady=(0, 4))

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x")
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=0)

        entry_kwargs = {"placeholder_text": placeholder, "width": 1}
        if textvariable is not None:
            entry_kwargs["textvariable"] = textvariable
        entry = self._entry(inner, **entry_kwargs)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._secondary_button(inner, "Explorar", command).grid(row=0, column=1, sticky="e")

        if initial:
            entry.insert(0, initial)
        return entry

    def create_widgets(self):
        from datetime import datetime

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(padx=18, pady=12, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=3)
        main_frame.grid_rowconfigure(2, weight=2)

        # --- HEADER ---
        header = self._card(main_frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w", padx=18, pady=10)
        ctk.CTkLabel(
            title_box,
            text="Smart CV Filter",
            font=("Segoe UI", 22, "bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box,
            text="Cribado semántico de currículums  ·  Gemini 3.1 Flash Lite",
            font=("Segoe UI", 12),
            text_color=COLOR_MUTED,
            anchor="w",
        ).pack(anchor="w")

        header_actions = ctk.CTkFrame(header, fg_color="transparent")
        header_actions.grid(row=0, column=1, sticky="e", padx=18, pady=10)

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        ctk.CTkLabel(
            header_actions,
            text=f"📅  {fecha_hoy}",
            font=("Segoe UI", 13),
            text_color=COLOR_MUTED,
        ).pack(side="left", padx=(0, 12))
        self._secondary_button(
            header_actions, "🔑  Configurar API Key", self.abrir_dialogo_api_key, width=180
        ).pack(side="left")

        # --- CUERPO: formulario izquierdo + candidatos ---
        body = ctk.CTkFrame(main_frame, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        body.columnconfigure(0, weight=6)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        left = self._card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_inner = ctk.CTkFrame(left, fg_color="transparent")
        left_inner.pack(fill="both", expand=True, padx=16, pady=14)
        left_inner.grid_columnconfigure(0, weight=1)
        left_inner.grid_rowconfigure(4, weight=1, minsize=72)

        self._label(left_inner, "Proceso de selección", size=14).grid(row=0, column=0, sticky="w", pady=(0, 8))

        form_row = ctk.CTkFrame(left_inner, fg_color="transparent")
        form_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        form_row.columnconfigure(0, weight=3)
        form_row.columnconfigure(1, weight=1)

        puesto_box = ctk.CTkFrame(form_row, fg_color="transparent")
        puesto_box.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._label(puesto_box, "Puesto", muted=True, size=11).pack(anchor="w", pady=(0, 4))
        self.entry_puesto = self._entry(puesto_box, placeholder_text="Ej: Senior Data Engineer")
        self.entry_puesto.pack(fill="x")

        fecha_box = ctk.CTkFrame(form_row, fg_color="transparent")
        fecha_box.grid(row=0, column=1, sticky="ew")
        self._label(fecha_box, "Fecha del proceso", muted=True, size=11).pack(anchor="w", pady=(0, 4))
        self.entry_fecha = self._entry(fecha_box, width=130)
        self.entry_fecha.insert(0, fecha_hoy)
        self.entry_fecha.configure(state="readonly")
        self.entry_fecha.pack(fill="x")

        entrada_box = ctk.CTkFrame(left_inner, fg_color="transparent")
        entrada_box.grid(row=2, column=0, sticky="ew")
        self.entry_input = self._path_row(
            entrada_box, "Carpeta de entrada", self.select_input_folder, textvariable=self.input_folder
        )

        destino_box = ctk.CTkFrame(left_inner, fg_color="transparent")
        destino_box.grid(row=3, column=0, sticky="ew")
        self.entry_destino = self._path_row(
            destino_box, "Carpeta de destino", self.select_destination_folder, initial=self.default_dest_path
        )

        jd_section = ctk.CTkFrame(left_inner, fg_color="transparent")
        jd_section.grid(row=4, column=0, sticky="nsew", pady=(0, 4))
        self._label(jd_section, "Descripción del puesto", muted=True, size=11).pack(anchor="w", pady=(0, 4))
        self.jd_textbox = ctk.CTkTextbox(
            jd_section,
            height=80,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER,
            fg_color=COLOR_SURFACE,
            text_color=COLOR_TEXT,
            font=("Segoe UI", 13),
            wrap="word",
        )
        self.jd_textbox.pack(fill="both", expand=True)
        self.menu_pegar = tkinter.Menu(self, tearoff=0, bg=COLOR_SURFACE, fg="white", activebackground=COLOR_ACCENT, bd=0)
        self.menu_pegar.add_command(label="  📋 Pegar Texto  ", command=self.pegar_texto)
        self.jd_textbox.bind("<Button-3>", self.mostrar_menu)

        btn_bar = ctk.CTkFrame(left_inner, fg_color="transparent")
        btn_bar.grid(row=5, column=0, sticky="ew", pady=(12, 8))
        self.btn_analyze = ctk.CTkButton(
            btn_bar,
            text="🚀  CLASIFICAR CVS",
            font=("Segoe UI", 14, "bold"),
            height=45,
            corner_radius=10,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#ffffff",
            command=self.run_analysis,
        )
        self.btn_analyze.pack(fill="x")

        right = self._card(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right_inner = ctk.CTkFrame(right, fg_color="transparent")
        right_inner.pack(fill="both", expand=True, padx=14, pady=14)

        self._label(right_inner, "CVs aceptados", size=14).pack(anchor="w")
        ctk.CTkLabel(
            right_inner,
            text="Pulsa una tarjeta para abrir el documento",
            font=("Segoe UI", 11),
            text_color=COLOR_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        self.candidates_list = ctk.CTkScrollableFrame(
            right_inner,
            fg_color=COLOR_SURFACE,
            corner_radius=8,
            border_width=0,
        )
        self.candidates_list.pack(fill="both", expand=True)

        # --- PIE: progreso + visor de eventos ---
        footer = self._card(main_frame)
        footer.grid(row=2, column=0, sticky="nsew")
        footer_inner = ctk.CTkFrame(footer, fg_color="transparent")
        footer_inner.pack(fill="both", expand=True, padx=16, pady=(8, 12))
        footer_inner.grid_columnconfigure(0, weight=1)
        footer_inner.grid_rowconfigure(4, weight=1)

        progress_row = ctk.CTkFrame(footer_inner, fg_color="transparent")
        progress_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self._label(progress_row, "Progreso del lote", muted=True, size=11).pack(side="left")
        self.progress_label = ctk.CTkLabel(
            progress_row,
            text="0 / 0  |  Tiempo est.: —",
            font=("Segoe UI", 11),
            text_color=COLOR_MUTED,
        )
        self.progress_label.pack(side="right")

        control_row = ctk.CTkFrame(footer_inner, fg_color="transparent")
        control_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.btn_pause = ctk.CTkButton(
            control_row,
            text="⏸️  Pausar análisis",
            width=180,
            height=32,
            corner_radius=8,
            fg_color=COLOR_AMBER,
            hover_color=COLOR_AMBER_HOVER,
            text_color="#1a1a1a",
            font=("Segoe UI", 12, "bold"),
            command=self.toggle_pause,
            state="disabled",
        )
        self.btn_pause.pack(side="left")
        self.pause_status_label = ctk.CTkLabel(
            control_row,
            text="",
            font=("Segoe UI", 12),
            text_color=COLOR_AMBER,
            anchor="w",
        )
        self.pause_status_label.pack(side="left", fill="x", expand=True, padx=(12, 0))

        self.progress_bar = ctk.CTkProgressBar(
            footer_inner,
            height=8,
            corner_radius=8,
            progress_color=COLOR_ACCENT,
            fg_color=COLOR_SURFACE,
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        self._label(footer_inner, "Eventos", muted=True, size=11).grid(row=3, column=0, sticky="w", pady=(0, 4))
        self.log_text = ctk.CTkTextbox(
            footer_inner,
            height=80,
            corner_radius=8,
            border_width=0,
            fg_color="#18181f",
            text_color="#e0e0e0",
            font=("Courier", 12),
            wrap="word",
        )
        self.log_text.grid(row=4, column=0, sticky="nsew")

    # --- Funciones de Soporte para Clic Derecho ---
    def mostrar_menu(self, event):
        """Muestra el menú con un pequeño margen para evitar clics accidentales"""
        try:
            # Añadimos +2 píxeles de margen en X e Y. 
            # Esto separa el cursor de la primera opción del menú.
            self.menu_pegar.tk_popup(event.x_root + 2, event.y_root + 2)
        finally:
            # Esto asegura que el menú libere el "foco" correctamente
            self.menu_pegar.grab_release()

    def pegar_texto(self):
        """Pega el texto asegurándose de limpiar el portapapeles de caracteres extra"""
        try:
            # Obtenemos el contenido del portapapeles
            texto = self.clipboard_get()
            if texto:
                # Insertamos en la posición actual del cursor ("insert")
                self.jd_textbox.insert("insert", texto)
                # Opcional: Desplazar la vista al final del texto pegado
                self.jd_textbox.see("end")
        except Exception as e:
            # Si el portapapeles no tiene texto (ej. una imagen), no hace nada
            pass
    

    def select_input_folder(self):
        from tkinter import filedialog
        import os
        
        # 1. Localizamos la ruta del Escritorio de forma dinámica
        # Esto funciona en Windows, macOS y Linux
        desktop_path = os.path.join(os.path.expanduser("~"), "Documents")
        
        # 2. Verificamos si existe (por si el SO tiene un nombre distinto)
        if not os.path.exists(desktop_path):
            desktop_path = os.path.expanduser("~") # Si no hay escritorio, abre su carpeta personal

        # 3. Abrimos el buscador empezando en el escritorio (initialdir)
        path = filedialog.askdirectory(
            initialdir=desktop_path,
            title="Selecciona la carpeta con los CVs"
        )
        
        if path:
            self.input_folder.set(path)


    def select_destination_folder(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(initialdir=self.default_dest_path, title="Seleccionar Proceso")
        
        if path:
            self.entry_destino.delete(0, "end")
            self.entry_destino.insert(0, path)
            
            # 1. 📂 Detectar si es un proceso existente (buscamos la carpeta RECLUTADOS)
            ruta_reclutados = os.path.join(path, "RECLUTADOS")
            if os.path.exists(ruta_reclutados):
                self.results_dir = ruta_reclutados
                
                # 2. 📅 Sincronizar FECHA y PUESTO desde el nombre de la carpeta
                nombre_folder = os.path.basename(path)
                if len(nombre_folder) >= 10 and "-" in nombre_folder:
                    fecha_orig = nombre_folder[:10]
                    # El puesto suele ser lo que va después del primer "_" (ej: 2026-04-10_Contable)
                    puesto_orig = nombre_folder[11:].replace("_", " ") if len(nombre_folder) > 11 else ""
                    
                    # Actualizar Fecha
                    self.entry_fecha.configure(state="normal")
                    self.entry_fecha.delete(0, "end")
                    self.entry_fecha.insert(0, fecha_orig)
                    self.entry_fecha.configure(state="readonly")
                    
                    # Actualizar Puesto
                    self.entry_puesto.delete(0, "end")
                    self.entry_puesto.insert(0, puesto_orig)

                # 3. 📝 Cargar DESCRIPCIÓN (JD) desde el archivo .txt
                ruta_jd = os.path.join(path, "descripcion_puesto.txt")
                if os.path.exists(ruta_jd):
                    try:
                        with open(ruta_jd, "r", encoding="utf-8") as f:
                            contenido_jd = f.read()
                        self.jd_textbox.delete("0.0", "end")
                        self.jd_textbox.insert("0.0", contenido_jd)
                    except Exception as e:
                        logger.error(f"Error al leer JD: {e}")

                # 4. ⭐ Cargar lista de CANDIDATOS
                self.update_top_candidates()
                self.log_text.insert("end", f"✅ Proceso '{puesto_orig}' cargado correctamente.\n")

    # --- Lógica de la Aplicación ---
    

    def update_top_candidates(self):
        """Carga inicial (una vez) de aceptados al abrir o reanudar un proceso."""
        for widget in self.candidates_list.winfo_children():
            widget.destroy()
        self.shown_accepted.clear()

        if not self.results_dir or not os.path.exists(self.results_dir):
            return

        try:
            archivos = [f for f in os.listdir(self.results_dir)
                       if f.lower().endswith(('.txt', '.pdf', '.docx'))]
            archivos.sort(reverse=True)
            for nombre in archivos:
                try:
                    score_val = int(nombre.split('_')[0])
                except (ValueError, IndexError):
                    score_val = 0
                if score_val >= 60:
                    self.agregar_tarjeta_cv_aceptado({
                        "dest_path": os.path.join(self.results_dir, nombre),
                        "nombre": nombre,
                        "score": score_val,
                    })
        except Exception as e:
            logger.error(f"Error actualizando lista visual: {e}")

    def agregar_tarjeta_cv_aceptado(self, datos_cv):
        """Añade una sola tarjeta al final, sin vaciar el contenedor."""
        ruta = datos_cv.get("dest_path") or ""
        nombre_archivo = os.path.basename(ruta) if ruta else str(datos_cv.get("nombre", ""))
        if not nombre_archivo or nombre_archivo in self.shown_accepted:
            return
        try:
            score_val = int(float(datos_cv.get("score", 0)))
        except (TypeError, ValueError):
            score_val = 0
        if score_val < 60:
            return
        display_name = nombre_archivo.split("_", 1)[1] if "_" in nombre_archivo else nombre_archivo
        self.shown_accepted.add(nombre_archivo)
        self._add_candidate_card(display_name, score_val, ruta)

    def _add_candidate_card(self, display_name, score_val, ruta_completa):
        badge_color = COLOR_SUCCESS if score_val >= 70 else COLOR_ACCENT
        card = ctk.CTkFrame(
            self.candidates_list,
            fg_color=COLOR_CARD,
            corner_radius=8,
            cursor="hand2",
        )
        card.pack(fill="x", pady=4, padx=4)

        name_label = ctk.CTkLabel(
            card,
            text=display_name,
            font=("Segoe UI", 12),
            text_color=COLOR_TEXT,
            anchor="w",
            justify="left",
        )
        name_label.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=10)

        badge = ctk.CTkLabel(
            card,
            text=f"{score_val}%",
            font=("Segoe UI", 12, "bold"),
            text_color="#ffffff",
            fg_color=badge_color,
            corner_radius=8,
            width=52,
            height=26,
        )
        badge.pack(side="right", padx=(0, 12), pady=8)

        def abrir(_event=None, r=ruta_completa):
            self.open_candidate_cv(r)

        for widget in (card, name_label, badge):
            widget.bind("<Button-1>", abrir)

    def _interruptible_sleep(self, seconds):
        """Espera entre CVs; si el usuario pausa, se detiene hasta reanudar."""
        remaining = seconds
        while remaining > 0:
            if not self.pause_event.is_set():
                self.pause_event.wait()
                return
            step = min(0.5, remaining)
            time.sleep(step)
            remaining -= step

    def _configure_pause_button(self, paused, enabled):
        if not hasattr(self, "btn_pause"):
            return
        if not enabled:
            self.btn_pause.configure(
                text="⏸️  Pausar análisis",
                fg_color=COLOR_AMBER,
                hover_color=COLOR_AMBER_HOVER,
                state="disabled",
            )
            return
        if paused:
            self.btn_pause.configure(
                text="▶️  Reanudar análisis",
                fg_color=COLOR_SUCCESS,
                hover_color=COLOR_SUCCESS_HOVER,
                text_color="#ffffff",
                state="normal",
            )
        else:
            self.btn_pause.configure(
                text="⏸️  Pausar análisis",
                fg_color=COLOR_AMBER,
                hover_color=COLOR_AMBER_HOVER,
                text_color="#1a1a1a",
                state="normal",
            )

    def _start_pause_timer(self):
        self.pause_started_at = time.time()
        self._tick_pause_timer()

    def _stop_pause_timer(self):
        if self.pause_timer_job is not None:
            try:
                self.after_cancel(self.pause_timer_job)
            except Exception:
                pass
            self.pause_timer_job = None
        self.pause_started_at = None
        if hasattr(self, "pause_status_label"):
            self.pause_status_label.configure(text="")

    def _tick_pause_timer(self):
        if not self.paused or self.pause_started_at is None:
            return
        elapsed = int(time.time() - self.pause_started_at)
        minutos, segundos = divmod(elapsed, 60)
        self.pause_status_label.configure(
            text=f"⏸️ En pausa — Tiempo transcurrido: {minutos:02d}:{segundos:02d} (Recomendado: 2-3 min)"
        )
        self.pause_timer_job = self.after(1000, self._tick_pause_timer)

    def _apply_paused_ui(self, auto=False):
        self.paused = True
        self._configure_pause_button(paused=True, enabled=True)
        self._start_pause_timer()
        if auto:
            self.log_mensaje("⚠️ Proceso pausado automáticamente por racha de saturación (503).")
        else:
            self.log_mensaje("⏸️ Análisis pausado. La petición en curso termina; el lote espera al siguiente CV.")

    def _apply_resumed_ui(self):
        self.paused = False
        self._stop_pause_timer()
        self._configure_pause_button(paused=False, enabled=True)
        self.log_mensaje("▶️ Análisis reanudado.")

    def toggle_pause(self):
        if not self.analyzing:
            return
        if self.paused:
            self.pause_event.set()
            self._apply_resumed_ui()
        else:
            self.pause_event.clear()
            self._apply_paused_ui(auto=False)

    def _format_eta(self, seconds):
        if seconds <= 0:
            return "~0 s"
        minutos = seconds / 60.0
        if minutos >= 1:
            return f"~{int(round(minutos))} min"
        return f"~{int(round(seconds))} s"

    def _set_progress(self, current, total):
        if not hasattr(self, "progress_bar"):
            return
        total = max(int(total), 0)
        current = max(int(current), 0)
        restantes = max(total - current, 0)
        eta = self._format_eta(restantes * SECONDS_PER_CV if current > 0 else total * SECONDS_PER_CV)
        if total == 0:
            self.progress_label.configure(text="0 / 0  |  Tiempo est.: —")
        else:
            self.progress_label.configure(text=f"{current} / {total}  |  Tiempo est.: {eta}")
        self.progress_bar.set(0 if total == 0 else min(current / total, 1.0))

    def _play_alert_sound(self):
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass
        sound = "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga"
        if os.path.exists(sound):
            try:
                subprocess.Popen(
                    ["paplay", sound],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def _log_analyzer_status(self, message):
        """Reintentos HTTP del analyzer: únicamente texto en el log de eventos."""
        if not message:
            return
        self.log_queue.put(message if isinstance(message, str) else str(message))

    def _close_alert_notice(self):
        if self._alert_after_id is not None:
            try:
                self.after_cancel(self._alert_after_id)
            except Exception:
                pass
            self._alert_after_id = None
        if self._alert_win is not None:
            win = self._alert_win
            self._alert_win = None
            try:
                win.withdraw()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

    def trigger_alert_notice(self, titulo, mensaje, icono_tipo="warning"):
        """Aviso audiovisual de 2 s: banner flotante CustomTkinter, no bloqueante."""
        self._close_alert_notice()
        self._play_alert_sound()
        self._alert_generation += 1
        generation = self._alert_generation

        width, height = 460, 180
        win = ctk.CTkToplevel(self)
        win.overrideredirect(True)
        win.configure(fg_color="#1e222d")
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        try:
            win.wm_attributes("-type", "notification")
        except Exception:
            pass

        self.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() // 2) - (width // 2)
        py = self.winfo_rooty() + (self.winfo_height() // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{max(px, 0)}+{max(py, 0)}")

        card = ctk.CTkFrame(
            win,
            fg_color="#1e222d",
            corner_radius=12,
            border_width=1,
            border_color="#3a3f4b",
        )
        card.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(card, text="⚠️", font=("Segoe UI", 32)).pack(pady=(16, 0))
        ctk.CTkLabel(
            card,
            text=titulo,
            font=("Segoe UI", 15, "bold"),
            text_color=COLOR_AMBER,
        ).pack(pady=(4, 2))
        ctk.CTkLabel(
            card,
            text=mensaje,
            font=("Segoe UI", 12),
            text_color="#ffffff",
            wraplength=400,
            justify="center",
        ).pack(padx=18, pady=(0, 16))

        self._alert_win = win

        def _cerrar_si_actual():
            if generation == self._alert_generation:
                self._close_alert_notice()

        self._alert_after_id = self.after(2000, _cerrar_si_actual)

    def open_candidate_cv(self, file_path):
        if not os.path.exists(file_path):
            self.log_text.insert("end", f"⚠️ Archivo no encontrado: {file_path}\n")
            return
        
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin": # macOS
                subprocess.call(("open", file_path))
            else: # 🐧 Linux (Aquí es donde estaba el problema)
                # 🛡️ "Limpiamos" las librerías internas antes de llamar al sistema
                env = dict(os.environ)
                # Eliminamos la ruta de librerías de PyInstaller para este proceso
                if "LD_LIBRARY_PATH" in env:
                    del env["LD_LIBRARY_PATH"]
                
                # Ejecutamos xdg-open con el entorno limpio
                subprocess.Popen(["xdg-open", file_path], env=env)
                
        except Exception as e:
            self.log_text.insert("end", f"❌ Error al abrir: {e}\n")


    
    def run_analysis(self):
        # Captura los datos de la interfaz
        puesto = self.entry_puesto.get().strip()
        ruta_destino_base = self.entry_destino.get().strip() 
        folder_path_entrada = self.input_folder.get().strip()
        user_description = self.jd_textbox.get("0.0", "end").strip()

        # Validaciones de UI (Si falta algo, sale)
        if not folder_path_entrada or not puesto or not user_description or not ruta_destino_base:
            self.log_text.insert("end", "⚠️ ERROR: Faltan datos (Entrada, Destino, Puesto o Descripción).\n")
            self.log_text.see("end")
            return
        
        self._set_progress(0, 0)
        self.log_text.insert("end", "⏳ Preparando entorno de análisis...\n")
        self.log_text.see("end")

        # El Manager crea o recupera la carpeta del proceso
        main_folder, self.results_dir = self.process_manager.configure_process(puesto, ruta_destino_base)

        # Sincronización visual de la fecha y la lista
        nombre_carpeta = os.path.basename(main_folder)
        
        # Actualiza la fecha en el cuadro (por si es un proceso antiguo)
        if len(nombre_carpeta) >= 10 and nombre_carpeta.count("-") >= 2:
            fecha_detectada = nombre_carpeta[:10]
            self.entry_fecha.configure(state="normal")
            self.entry_fecha.delete(0, "end")
            self.entry_fecha.insert(0, fecha_detectada)
            self.entry_fecha.configure(state="readonly")

        # Muestra los CVs que ya estaban en la carpeta (Memoria Visual)
        self.update_top_candidates()

        # Guarda descripción y lanza el análisis
        self.process_manager.save_job_description(main_folder, user_description)

        # Bloquear botón e iniciar hilo de trabajo
        self.btn_analyze.configure(state="disabled")
        self.pause_event.set()
        self.analyzing = True
        self.paused = False
        self._configure_pause_button(paused=False, enabled=True)
        threading.Thread(target=self.analysis_worker, args=(user_description,), daemon=True).start()
        

    def analysis_worker(self, user_job_desc):
        pendientes_cuota = 0
        pendientes_parseo = 0
        pendientes_timeout = 0
        pendientes_servidor = 0
        consecutive_server_errors = 0
        total_procesados = 0
        start_time = time.time()
        try:

            folder_path = Path(self.input_folder.get())
            extensiones = [".txt", ".pdf", ".docx"]
            files = [f for f in folder_path.iterdir() if f.suffix.lower() in extensiones]
           
            if not files:
                self.log_queue.put("⚠️ No se encontraron archivos (PDF, DOCX, TXT) en la carpeta seleccionada.")
                self.log_queue.put(("PROGRESS", 0, 0))
                self.log_queue.put("FIN")
                return

            self.log_queue.put(("PROGRESS", 0, len(files)))
            eta_inicial = self._format_eta(len(files) * SECONDS_PER_CV)
            self.log_queue.put(f"📑 Procesando {len(files)} candidatos...  |  Tiempo est.: {eta_inicial}")

            for index, file_path in enumerate(files, start=1):
                self.pause_event.wait()
                self.log_queue.put(f"🔍 Analizando: {file_path.name}")
                
                resultado = self.cv_handler.process_cv(str(file_path), user_job_desc)
                status = resultado.get("status")

                if status == "success":
                    consecutive_server_errors = 0
                    total_procesados += 1
                    # Usamos .get() con valores por defecto para evitar CRASHES
                    score = resultado.get("score", 0)
                    motivo = resultado.get("motivo", "No se proporcionó explicación")
                    nombre = resultado.get("nombre", "Archivo")
                    
                    # 🟢 Pintar en el log 
                    self.log_queue.put(f"✅ SCORE -> {score}%")
                    self.log_queue.put(f"   💡 MOTIVO: {motivo}") 
                    self.log_queue.put("-" * 45)
                    if resultado.get("decision") == "RECLUTADOS" and float(score) >= 60:
                        self.log_queue.put(("ADD_ACCEPTED", {
                            "dest_path": resultado.get("dest_path"),
                            "nombre": resultado.get("nombre"),
                            "score": score,
                        }))
                    
                
                elif status == "api_error":
                    pendientes_cuota += 1
                    self.log_queue.put(f"⚠️ {file_path.name}: Límite de cuota. El archivo permanece en la carpeta de entrada.")
                elif status == "timeout_error":
                    consecutive_server_errors += 1
                    pendientes_timeout += 1
                    self.log_queue.put(f"⏳ {file_path.name}: CV marcado como pendiente por agotamiento de timeouts. El archivo permanece en la carpeta de entrada.")
                elif status == "server_busy":
                    consecutive_server_errors += 1
                    pendientes_servidor += 1
                    self.log_queue.put(f"⏳ {file_path.name}: Servidor de Gemini saturado. El archivo permanece en la carpeta de entrada.")
                    # Aviso audiovisual solo al agotar los 5 reintentos de este CV (nunca en el bucle HTTP).
                    self.log_queue.put((
                        "ALERT",
                        "ALTA DEMANDA / PAUSA DETECTADA",
                        f"{file_path.name}: Gemini respondió 503 (servidor saturado). El archivo permanece en la carpeta de entrada.",
                    ))
                elif status == "parse_error":
                    pendientes_parseo += 1
                    self.log_queue.put(f"⚠️ {file_path.name}: Error en respuesta de la IA. El archivo permanece en la carpeta de entrada.")
                else:
                    error_msg = resultado.get("reason", "Error desconocido")
                    self.log_queue.put(f"❌ Error en {file_path.name}: {error_msg}")

                if consecutive_server_errors >= 5:
                    consecutive_server_errors = 0
                    self.log_queue.put("⚠️ Alta demanda en los servidores de Google: 5 fallos consecutivos. El proceso se pausa automáticamente.")
                    self.log_queue.put(("AUTO_PAUSE",))
                    self.pause_event.clear()
                    self.pause_event.wait()
                
                self.log_queue.put(("PROGRESS", index, len(files)))
                self.log_queue.put("⏳ Pausa entre análisis (4.5s)...")
                self.log_queue.put("-" * 40) # Una línea separadora un poco más larga
                self._interruptible_sleep(4.5)

            elapsed_seconds = round(time.time() - start_time, 1)
            minutos = int(elapsed_seconds // 60)
            segundos = round(elapsed_seconds % 60, 1)
            tiempo_fmt = f"{minutos}m {segundos}s" if minutos > 0 else f"{segundos}s"

            if pendientes_cuota > 0 or pendientes_timeout > 0 or pendientes_servidor > 0:
                total = pendientes_cuota + pendientes_timeout + pendientes_parseo + pendientes_servidor
                causas = [
                    (n, causa) for n, causa in (
                        (pendientes_cuota, "CUOTA DE API"),
                        (pendientes_timeout, "TIEMPO DE ESPERA AGOTADO"),
                        (pendientes_servidor, "SERVIDOR SATURADO"),
                        (pendientes_parseo, "FORMATO DE RESPUESTA"),
                    ) if n > 0
                ]
                self.log_queue.put("\n" + "="*55)
                if len(causas) > 1:
                    partes = [f"{n} POR {causa}" for n, causa in causas]
                    desglose = ", ".join(partes[:-1]) + " Y " + partes[-1]
                    self.log_queue.put(f"⚠️  ATENCIÓN: {total} CV(S) PENDIENTES ({desglose})")
                else:
                    self.log_queue.put(f"⚠️  ATENCIÓN: {total} CV(S) PENDIENTES POR {causas[0][1]}")
                self.log_queue.put("="*55)
                self.log_queue.put("💡 No se han movido de la carpeta de entrada.")
                self.log_queue.put("👉 Espera 1-2 minutos y vuelve a pulsar 'CLASIFICAR CVS'.")
                self.log_queue.put("="*55 + "\n")
            elif pendientes_parseo > 0:
                self.log_queue.put("\n" + "="*55)
                self.log_queue.put(f"⚠️  ATENCIÓN: {pendientes_parseo} CV(S) PENDIENTES POR RESPUESTA INCOMPLETA DE LA IA")
                self.log_queue.put("="*55)
                self.log_queue.put("💡 La IA devolvió un formato incompleto. No se han movido de la carpeta de entrada.")
                self.log_queue.put("👉 Vuelve a pulsar 'CLASIFICAR CVS' para procesarlos de nuevo.")
                self.log_queue.put("="*55 + "\n")
            else:
                self.log_queue.put("\n🎊 ¡Clasificación terminada con éxito!")
                self.log_queue.put(f"⏱️ Tiempo total: {tiempo_fmt} | 📄 Candidatos analizados: {total_procesados}")
            self.log_queue.put("FIN")

            if pendientes_cuota > 0 or pendientes_timeout > 0 or pendientes_servidor > 0:
                total = pendientes_cuota + pendientes_timeout + pendientes_parseo + pendientes_servidor
                partes = [
                    f"{n} por {causa}" for n, causa in (
                        (pendientes_cuota, "cuota"),
                        (pendientes_timeout, "tiempo de espera agotado"),
                        (pendientes_servidor, "servidor saturado"),
                        (pendientes_parseo, "formato de respuesta"),
                    ) if n > 0
                ]
                if len(partes) > 1:
                    detalle = f"Han quedado {total} CV(s) pendientes: {', '.join(partes[:-1])} y {partes[-1]}."
                else:
                    detalle = f"Han quedado {total} CV(s) pendientes en la carpeta de entrada."
                if pendientes_cuota > 0:
                    titulo = "Límite de Cuota Alcanzado"
                    causa = "Se ha alcanzado el límite por minuto de la cuenta gratuita de Gemini."
                elif pendientes_servidor > 0:
                    titulo = "Servidor de Gemini Saturado"
                    causa = "El servidor de Gemini no estuvo disponible tras varios intentos (error 503)."
                else:
                    titulo = "Tiempo de Espera Agotado"
                    causa = "Gemini no respondió a tiempo tras varios intentos."
                self.log_queue.put((
                    "ALERT",
                    titulo,
                    f"{causa} {detalle} Espera 1-2 min y vuelve a pulsar CLASIFICAR CVS.",
                ))
            elif pendientes_parseo > 0:
                self.log_queue.put((
                    "ALERT",
                    "Respuesta Incompleta de la IA",
                    f"Han quedado {pendientes_parseo} CV(s) pendientes por formato incompleto. Vuelve a pulsar CLASIFICAR CVS.",
                ))

        except Exception as e:
            self.log_queue.put(f"❌ Error crítico: {e}")
            self.log_queue.put("FIN")


    def check_queues(self):
        pending_alert = None
        auto_pause_alert = False
        try:
            while not self.log_queue.empty():
                msg = self.log_queue.get_nowait()
                if isinstance(msg, tuple) and msg[0] == "AUTO_PAUSE":
                    if not self.paused:
                        self._apply_paused_ui(auto=True)
                    auto_pause_alert = True
                elif isinstance(msg, tuple) and msg[0] == "ALERT":
                    pending_alert = (msg[1], msg[2])
                elif isinstance(msg, tuple) and msg[0] == "PROGRESS":
                    self._set_progress(msg[1], msg[2])
                elif isinstance(msg, tuple) and msg[0] == "ADD_ACCEPTED":
                    self.agregar_tarjeta_cv_aceptado(msg[1])
                elif msg == "UPDATE_LIST":
                    self.update_top_candidates()
                elif msg == "FIN":
                    self.analyzing = False
                    self.paused = False
                    self.pause_event.set()
                    self._stop_pause_timer()
                    self._configure_pause_button(paused=False, enabled=False)
                    self.btn_analyze.configure(state="normal")
                else:
                    self.log_text.insert("end", f"{msg}\n")
                    self.log_text.see("end")
        except:
            pass
        # Un solo banner por ciclo: la pausa automática tiene prioridad sobre el aviso de un CV.
        if auto_pause_alert:
            self.trigger_alert_notice(
                "ALTA DEMANDA / PAUSA DETECTADA",
                "Se han encadenado 5 fallos por saturación (503). El proceso se ha pausado. Espera 2-3 min y pulsa 'Reanudar análisis'.",
            )
        elif pending_alert:
            self.trigger_alert_notice(pending_alert[0], pending_alert[1])
        self.after(100, self.check_queues)


if __name__ == "__main__":
    ctk.set_widget_scaling(1.0)  # Fuerza escala 1:1
    app = SmartCVFilterApp()
    # En lugar de fijarlo a lo bruto, usamos after para esperar 200ms
    # Esto suele evitar el Segmentation Fault en Linux
    app.after(200, lambda: ctk.set_appearance_mode("dark"))
    app.mainloop()