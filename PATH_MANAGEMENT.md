# 📂 PATH MANAGEMENT - Smart CV Filter

## 📍 Ubicación de Componentes Clave

### 🏗️ Carpeta Maestra (Root de Proyectos)
- **Ruta**: `procesos_seleccion/`
- **Descripción**: Directorio principal autogenerado al mismo nivel que el ejecutable que agrupa todos los procesos de filtrado cronológicamente.

### 🗄️ Sistema de Persistencia (Híbrido)
- **Reporte de Auditoría (`resumen_proceso.csv`)**: 
  - **Ubicación**: Carpeta raíz de cada proceso específico.
  - **Función**: Registro permanente en formato *append* de cada análisis. Almacena: Nombre, Score, Decisión y Motivo técnico de la IA.
- **Respaldo de Requisitos (`descripcion_puesto.txt`)**: 
  - **Ubicación**: Carpeta raíz de cada proceso.
  - **Función**: Persistencia de la *Job Description*. Permite al sistema reanudar sesiones y recalibrar el contexto de la IA.

### 📁 Organización de Salida (Output)
Los archivos se clasifican físicamente para facilitar la navegación mediante el explorador de archivos:
- **RECLUTADOS/**: Candidatos aptos. Archivos renombrados con prefijo de nota (ej. `95_CV_Juan.pdf`).
- **DUDAS/**: Candidatos con puntuación intermedia para revisión manual.
- **DESCARTADOS/**: Candidatos no aptos o con 0 coincidencias técnicas.

### 🧠 Gestión de IA y Credenciales
- **Inferencia (Google Gemini API)**: Ya no se almacenan pesos de modelos pesados (Gemma/Llama) en local. La lógica reside en la nube de Google Gemini.
- **Configuración (`conf.env`)**:
  - **Ubicación**: Raíz del proyecto / Junto al ejecutable.
  - **Función**: Contiene la `GEMINI_API_KEY`. Es fundamental para la comunicación con el motor de análisis.
- **NLP Local (spaCy)**: Los modelos de anonimización ligera se cargan desde el entorno de ejecución para garantizar el cumplimiento de la GDPR antes del envío de datos.

### ⚙️ Resolución de Rutas
- **Pathlib**: El sistema utiliza rutas absolutas dinámicas calculadas en tiempo de ejecución (`executable_path`), garantizando que el programa funcione correctamente al ser movido en unidades USB o carpetas de red en Windows.