# DEVELOPMENT_LOG

## Estado del Proyecto
Fase actual: Optimización de Inferencia y Distribución (Módulo 7)

## Especificaciones Técnicas
- **Motor de Inferencia Híbrido/Nube**: Uso de la **API de Google Gemini** (`gemini-3.1-flash-lite`, endpoint compatible con OpenAI de Google AI Studio) para el procesamiento de lenguaje natural y el análisis semántico.
- **Arquitectura de Bajo Consumo**: Eliminación de la dependencia de modelos locales pesados (Gemma/PyTorch), reduciendo el consumo de RAM de >2GB a <200MB y el tamaño del ejecutable en un 95%.
- **Privacidad y Anonimización (GDPR)**: El contenido sigue siendo anonimizado localmente antes de cualquier envío a la API de Gemini para garantizar la protección de datos personales.

## Registro de Cambios (Changelog)

- [2026-03-20] Documento DEVELOPMENT_LOG.md inicializado.
- [2026-03-20] Módulo 1: UniversalExtractor completado y validado.
- [2026-03-20] Módulo 2: LocalAnonymizer completado.
- [2026-03-23] Módulo 4: Interfaz de Usuario de Escritorio (v0.6) con `customtkinter`.
- [2026-03-26] **Hito: Transición a Arquitectura de IA 100% Local**. Uso temporal de modelos embebidos en RAM para pruebas de privacidad total.
- [2026-03-27] Implementación de Clasificación Física de Archivos y persistencia en DB.
- [2026-04-08] Módulo 5: Motor de Análisis Blindado y Gestión por Proyectos (v1.0). Parche de negaciones implementado.
- [2026-04-10] Módulo 6: Trazabilidad, Persistencia y Estabilidad (v1.1). Implementación de `ProcessManager` y reportes CSV.
- [2026-04-14] **Hito: Migración a Inferencia Groq (v2.0)**:
    * **Cambio de Motor IA**: Sustitución de Gemma 2 (Local) por la API de **Groq**. 
    * **Optimización de Peso**: El ejecutable `.exe` se reduce de ~2.5GB a ~120MB al eliminar las librerías de Deep Learning pesadas.
    * **Soporte ODT descartado**: El soporte para archivos `.odt` fue evaluado y descartado por inestabilidad en el parsing y en el empaquetado. El foco queda exclusivamente en `.pdf`, `.docx` y `.txt`.
    * **Estabilización en Wine**: Compilación validada en entorno Wine 6.0.3 para Windows 10.
- [2026-10-23] **Hito: Migración a Google Gemini (v2.1)**:
    * **Cambio de Proveedor IA**: Sustitución de Groq por la API de **Google Gemini** (`gemini-2.5-flash`) para evitar la saturación de cuota. La clave se guarda como `GEMINI_API_KEY` en `conf.env`.
    * **Reintentos ante 429**: Backoff exponencial (Retry-After o esperas de 10s y 20s, hasta 3 intentos).
    * **Archivos Pendientes**: Los fallos de cuota o de JSON ya no puntúan 0 ni mueven el archivo; se registran como `PENDIENTE_ERROR_API` o `PENDIENTE_ERROR_PARSEO` en el CSV.
- [2026-10-23] **Ajuste: Robustez ante Cuota 429 (v2.1.1)**:
    * **Más Reintentos**: Se amplían los intentos ante 429 de 3 a 5 antes de dejar el CV como pendiente.
    * **Backoff Progresivo**: Si la respuesta no trae `Retry-After`, las esperas pasan a ser de 10s, 20s, 35s y 50s.
    * **Avisos en la GUI**: Los mensajes de espera por 429 se muestran también en el log de la interfaz, no solo en la terminal.
    * **Pausa entre CVs**: La pausa fija entre análisis sube de 2s a 4.5s para acompasar el consumo con la regeneración de la cuota por minuto.
- [2026-10-23] **Hito: Validación en Producción de gemini-3.1-flash-lite (v2.1.2)**:
    * **Modelo Definitivo**: `gemini-3.1-flash-lite` queda validado como motor de inferencia activo.
    * **Timeouts Recuperables**: `timeout=(10, 60)` y hasta 5 reintentos ante `ReadTimeout`; el CV queda `PENDIENTE_TIMEOUT` sin moverse ni puntuar 0.
    * **Prueba de Carga**: 80 CVs consecutivos registrados en CSV sin errores fatales (~15 min de lote).
- [2026-10-23] **Hito: Resiliencia UX, Alertas y Control de Saturación (v2.2.0)**:
    * **Estimación temporal métrica**: El lote muestra tiempo total y restante con la métrica real validada de **11.5 s/CV** (barra de progreso + etiqueta `Tiempo est.`).
    * **Sistema de alertas efímero**: `trigger_alert_notice` abre un `CTkToplevel` flotante en tema oscuro (`fg_color="#1e222d"`, `corner_radius=12`, `overrideredirect(True)`), con icono ⚠️, tipografía ámbar/blanca, autocierre a **2 s** (`self.after(2000, ...)`) y aviso acústico del sistema. No bloquea el hilo de la GUI. Si hay un banner abierto, se cierra antes de abrir el siguiente.
    * **Control de saturación (503 / timeout)**: Los reintentos HTTP 1–4 son silenciosos (solo texto en el log de Eventos). `trigger_alert_notice` se dispara únicamente (a) cuando un CV agota los 5 intentos y queda `server_busy`, o (b) al encadenar 5 CVs fallidos consecutivos y activar la **pausa automática** del lote (aviso + cronómetro de pausa). Pausa/reanudación cooperativa con `threading.Event`.
    * **Panel de CVs aceptados incremental**: Se elimina el vaciado destructivo (`winfo_children().destroy()`). Las tarjetas se añaden una a una, solo `RECLUTADOS` con **score ≥ 60**, con control de duplicados en memoria (`shown_accepted`).
    * **Layout y estética**: Altura mínima útil del `CTkTextbox` de descripción del puesto; grid responsive para no aplastar CLASIFICAR / destino / log. Erradicación total de `tkinter.messagebox` (incluidos avisos de lote pendiente y error de API Key). Diálogos de clave y alertas son `CTkToplevel` con `CTkLabel` / `CTkEntry` / `CTkButton`. Se mantiene `filedialog.askdirectory()` para Explorar.
    * **Suite de pruebas (Src-Layout)**: `tests/test_alertas_gui.py` aísla 503 con mocks de `requests.post` y `time.sleep`. El resto de tests se consolida en la carpeta raíz `tests/` (eliminada `src/test/`).

#### Resultados de rendimiento y estabilidad (v2.1.2)
Prueba real de producción tras la migración a `gemini-3.1-flash-lite`:

* **Volumen procesado**: 80 CVs analizados y registrados en CSV consecutivamente, sin errores fatales.
* **Tiempo total**: ~15 minutos (~11,25 s por CV: ~6,2 s de inferencia + 4,5 s de pausa de seguridad + extracción local).
* **Estabilidad de cuota**: Cero errores 429 durante toda la ráfaga, gracias al ajuste de pausas preventivas.
* **Resiliencia ante latencia**: Tras 80 archivos, la primera demora de red disparó el sistema de reintentos por Timeout (`timeout=60s` + captura de `ReadTimeout` con 5 intentos). Actuó de forma autónoma, sin abortar el lote ni descartar el archivo.
* **Conclusión**: `gemini-3.1-flash-lite` queda validado con éxito como motor definitivo por su equilibrio entre velocidad, cuota y estabilidad operativa.

## Detalles de Implementación de GUI
- **Framework**: `customtkinter` para diseño moderno (tema oscuro). Sin `tkinter.messagebox`.
- **Arquitectura**: Separación de responsabilidades. La GUI captura datos y delega la lógica de rutas al `CVHandler`.
- **Alertas (v2.2.0)**: Banner no bloqueante `trigger_alert_notice` + log en el panel de Eventos. Reintentos HTTP no abren ventana.
- **Novedades v2.0**:
    * Validación de API Key (entonces Groq) en archivo `conf.env`.
    * Latencia de respuesta casi instantánea (<1s por CV) en el proveedor original.
    * Logging detallado del motivo técnico devuelto por el LLM en la nube.

## Próximos Pasos
- **Optimización de prompts**: Ajuste fino de instrucciones y tokens para reducir parseos incompletos.
- **Gestión avanzada de cuotas**: Políticas de ritmo por minuto y reanudación asistida tras 429 persistentes.
- **Exportación de reportes**: Ampliar `resumen_proceso.csv` y valorar exportación adicional (p. ej. filtros o columnas técnicas).
- **Empaquetado Final**: Configurar `PyInstaller` para incluir el archivo `conf.env` base.

---

### 📝 Registro de Calibración Final (Módulo 7)
**Fecha:** 2026-04-14  
**Estado:** Validado y Calibrado para Producción

> **[2026-04-14] Salto a la Nube con Groq:**
> Se confirma el éxito de la migración. El sistema ya no requiere hardware potente para funcionar, permitiendo su ejecución en ordenadores de oficina estándar. La precisión semántica se mantiene (o mejora) gracias al uso de modelos Llama 3 de mayor escala vía API.

#### Resumen de Calibración de Inferencia:
* **Modelo Utilizado**: Llama-3-70B (vía Groq API).
* **Latencia Promedio**: 0.4s por CV.
* **Tamaño del Binario**: ~120MB (Ejecutable único).
* **Dependencias Clave**: `groq`, `customtkinter`, `PyMuPDF`.