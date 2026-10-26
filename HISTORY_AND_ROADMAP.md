# 📑 Smart CV Filter - Historia y Hoja de Ruta

## 🎯 Visión General
Sistema profesional de filtrado y evaluación semántica de CVs. Evolucionado de un modelo 100% local a una **arquitectura de inferencia en la nube (Google Gemini)**, manteniendo la **privacidad por diseño** mediante anonimización previa en el cliente.

---

## 🕒 Historial de Desarrollo y Log de Versiones

### **Fase 1: Cimientos y Extracción (v0.1 - v0.3)**
* **v0.1 - UniversalExtractor**: Soporte para PDF (pdfplumber), DOCX y TXT.
* **v0.2 - LocalAnonymizer**: Anonimización local mediante spaCy (NER).
* **v0.3 - Calidad**: Suite de tests unitarios y validación de extracción.

### **Fase 2: Orquestación y Transición a la Nube (v0.4 - v0.6)**
* **v0.4 - Orchestrator**: Primer flujo completo de análisis.
* **v0.5 - Era Gemini**: Integración temporal con Google Gemini API.
* **v0.6 - Utilidades**: Scripts de limpieza de entorno y gestión de SQL.

### **Fase 3: IA Local y Gestión de Procesos (v0.7 - v1.4.0)**
* **v1.1.0 - Privacy & Local Update**: Integración de `MiniLM-L12-v2` (100% Local).
* **v1.2.0 - The Organizer Update**: Clasificación física automatizada en carpetas.
* **v1.3.0 - The Precision Update**: Parche de negaciones regex y organización por proyectos.
* **v1.4.0 - Persistence Update**: Generación de `resumen_proceso.csv` y arquitectura `ProcessManager`.

### **Fase 4: Inferencia Ultrarrápida y Optimización Cloud (v2.0.0)**
* **v2.0.0 - The Groq Speed Update**:
    * **Inferencia en la Nube (Groq)**: Migración a la API de Groq (Llama 3) para reducir el tiempo de análisis de minutos a milisegundos.
    * **Optimización de Binarios**: Reducción del ejecutable de 2.5GB a ~120MB al eliminar dependencias pesadas de PyTorch/Transformers.
    * **Compilación Wine**: Estabilización del entorno de empaquetado para Windows 10 desde Linux.

### **Fase 5: Migración a Google Gemini y Robustez ante Cuotas (v2.1.0)**
* **v2.1.0 - The Gemini Update**:
    * **Inferencia en la Nube (Gemini)**: Migración a la API de Google Gemini (`gemini-2.5-flash`) mediante el endpoint compatible con OpenAI de Google AI Studio, para evitar la saturación de cuota.
    * **Reintentos con Backoff Exponencial**: Gestión automática de respuestas 429 (Retry-After o esperas de 10s y 20s).
    * **Archivos Pendientes**: Los CVs con fallo de cuota o de formato JSON no se puntúan ni se mueven; quedan en la carpeta de entrada para reintentarse.
* **v2.1.1 - Quota Resilience Update**:
    * **Reintentos Ampliados**: Hasta 5 intentos ante 429, con esperas de 10s, 20s, 35s y 50s si no hay `Retry-After`.
    * **Avisos en la GUI**: Las esperas por cuota se muestran en el log de la interfaz.
    * **Pausa entre CVs**: Sube de 2s a 4.5s para reducir la frecuencia de respuestas 429.
* **v2.1.2 - Production Validation**:
    * **Modelo activo**: `gemini-3.1-flash-lite` validado en lote real (~80 CVs, ~11.5 s/CV).
    * **Timeouts recuperables**: el archivo queda pendiente; el lote no se aborta.

### **Fase 6: Resiliencia UX y Control de Saturación (v2.2.0) [ESTADO ACTUAL]**
* **v2.2.0 - The UX Resilience Update (2026-10-23)**:
    * **UX/UI**: Dashboard CustomTkinter estable (descripción de puesto con altura mínima, CLASIFICAR visible, log de Eventos). Alertas efímeras no bloqueantes; erradicación de `tkinter.messagebox`.
    * **Fiabilidad Gemini**: Reintentos 503/timeout silenciosos en log; un aviso por CV agotado (`server_busy`); pausa automática + cronómetro tras 5 fallos consecutivos; pausa/reanudación cooperativa.
    * **Estabilidad de datos**: Lista de aceptados incremental (sin parpadeo), filtro `RECLUTADOS` y score ≥ 60, duplicados controlados en memoria. ETA de lote a 11.5 s/CV.
    * **Pruebas**: Suite unificada en `/tests` (Src-Layout), incluido `tests/test_alertas_gui.py` con mocks de red y sleeps.

---

## 🏗️ Arquitectura del Sistema (Pipeline)
1.  **Ingestión**: Selección de CVs y detección de formatos (PDF, DOCX, TXT).
2.  **Anonimización Local**: Sustitución de datos sensibles antes de salir del equipo.
3.  **Inferencia Gemini**: Envío de texto anonimizado a la API de Google Gemini para evaluación semántica profunda.
4.  **Logística**: 
    * Clasificación física en `RECLUTADOS/`, `DUDAS/` o `DESCARTADOS/`.
    * Renombrado de archivos por score invertido para ordenamiento automático.
5.  **Trazabilidad**: Actualización del CSV de auditoría y base de datos local.

---

## 🚀 Hoja de Ruta Futura (Roadmap)

### **Completado en v2.2.0**
- [x] **Validación Dinámica de API Key**: Interfaz en la GUI para introducir/validar la Key de Gemini sin editar el `conf.env`.
- [x] **Gestión de Reintentos**: Lógica de *exponential backoff* para manejar límites de ratio en la API.
- [x] **Pausa/reanudación cooperativa** en segundo plano (`threading.Event`, cronómetro de pausa).
- [x] **Alertas no bloqueantes** ante saturación de API (`trigger_alert_notice`, sin `messagebox`).
- [x] **Estimación de tiempos de procesamiento** (11.5 s/CV, total y restante).
- [x] **Prevención de parpadeos** en el panel de candidatos clasificados (render incremental).
- [x] **Migración completa a CustomTkinter**: eliminación de `tkinter.messagebox` heredados.

### **Próximos Hitos (v2.3)**
- [ ] **Optimización de prompts**: reducir respuestas incompletas y tokens de salida.
- [ ] **Gestión avanzada de cuotas**: ritmo adaptativo y guía de reanudación tras 429 persistentes.
- [ ] **Exportación de reportes**: ampliar el CSV de auditoría y formatos de salida.
- [ ] **Dashboard de Estadísticas**: gráficos de distribución de candidatos integrados en CustomTkinter.

### **Objetivos a Largo Plazo**
- [ ] **Soporte Multi-idioma**: Adaptar el motor de análisis para CVs en inglés, francés y alemán.
- [ ] **Feedback Loop**: Permitir que el reclutador ajuste los umbrales de puntuación en tiempo real desde la GUI.
- [ ] **Pre-visualización**: Integrar un visor de documentos interno para abrir archivos directamente desde la lista de resultados.

---

## 🛠️ Stack Tecnológico Actual
* **Lenguaje**: Python 3.10+ (Entorno Wine para .exe).
* **GUI**: CustomTkinter (Modern Dark Theme).
* **NLP/IA**: Google Gemini API vía `requests` (Inferencia), spaCy (Anonimización local).
* **Formatos**: PyMuPDF, python-docx.
* **Persistencia**: CSV (Append), SQLite, Pathlib.

---

## 📝 Principios de Diseño
* **Eficiencia**: Ejecución instantánea sin necesidad de hardware potente (GPU).
* **Privacidad**: Anonimización local garantizada antes de usar servicios de terceros.
* **Portabilidad**: Ejecutable ligero de fácil distribución mediante USB o red.