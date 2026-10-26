# Anexo Normativo: Guía de Cumplimiento en Protección de Datos (RGPD / LOPDGDD / EU AI Act)

**Aplicación:** Smart CV Filter  
**Destinatarios:** Departamentos de Recursos Humanos, Responsables de Tratamiento y Delegados de Protección de Datos (DPD).

---

## 1. Naturaleza de la Herramienta: Asistencia Técnica sin Decisión Automatizada Exclusiva

Smart CV Filter ha sido diseñada bajo el principio de **privacidad desde el diseño y por defecto (Art. 25 del RGPD)** como un sistema auxiliar de soporte al cribado curricular.

* **Supervisión humana obligatoria:** De conformidad con el **Artículo 22 del RGPD**, la herramienta no toma decisiones de contratación o rechazo definitivas de manera autónoma. Las puntuaciones e informes generados constituyen meras recomendaciones técnicas. La empresa responsable debe garantizar que la decisión final de exclusión o pase a entrevista sea adoptada de forma efectiva por personal cualificado del departamento de selección.
* **Auditabilidad y trazabilidad:** Los motivos de ponderación y scores quedan registrados localmente en un archivo estructurado (`resumen_proceso.csv`) para asegurar la trazabilidad del proceso ante auditorías internas o solicitudes de ejercicio de derechos.

---

## 2. Tratamiento y Transferencia Internacional de Datos (Uso de APIs)

El flujo del sistema aplica una fase previa de anonimización/seudonimización técnica local para retirar datos identificativos directos antes de remitir el perfil curricular a la API de inferencia.

Dado que la trayectoria profesional puede contener identificadores indirectos, la entidad responsable del tratamiento debe cumplir las siguientes garantías:

* **Contrato de Encargo de Tratamiento:** La empresa usuaria debe operar la herramienta mediante una cuenta comercial/empresarial propia en el proveedor de computación (**Google Cloud / Google AI Studio**) que incorpore el *Data Processing Addendum* (DPA) regulado por el **Artículo 28 del RGPD**, sustentado en el marco de privacidad UE-EE. UU. (*Data Privacy Framework*) o en las Cláusulas Contractuales Tipo (SCC).
* **Uso de claves corporativas:** Queda expresamente desaconsejado el uso de claves de acceso gratuitas o cuentas personales no reguladas en entornos corporativos de producción con datos reales de candidatos.

---

## 3. Deber de Información y Transparencia frente al Candidato

En cumplimiento de los **Artículos 13 y 14 del RGPD** y las directrices de la Agencia Española de Protección de Datos (AEPD) en materia de IA aplicada a Recursos Humanos, la empresa debe incorporar a sus canales de recepción (formularios, ofertas):

1. **Información explícita:** Informar a los aspirantes de que su candidatura será analizada mediante herramientas de asistencia algorítmica para contrastar competencias frente al puesto.
2. **Criterios objetivos:** Indicar de forma comprensible la lógica aplicada (años de experiencia, herramientas, cualificaciones objetivas).
3. **Derecho de impugnación e intervención humana:** Los candidatos deben poder solicitar la intervención de un evaluador humano, formular alegaciones o pedir una revisión del criterio aplicado.

---

## 4. Calificación Regulatoria y Evaluación de Impacto (EU AI Act y EIPD)

En el marco del **Reglamento Europeo de Inteligencia Artificial (AI Act)**, las soluciones orientadas al empleo, selección de personal y cribado curricular están clasificadas como **sistemas de Alto Riesgo**.

Por ello, se recomienda a la entidad implementadora:
* Realizar una **Evaluación de Impacto en la Protección de Datos (EIPD / DPIA)** previa a su integración en flujos recurrentes de contratación, evaluando posibles sesgos algorítmicos.
* Establecer **muestreos aleatorios periódicos** sobre candidatos clasificados en la carpeta `DESCARTADOS` para verificar que los filtros aplicados no inducen sesgos discriminatorios indirectos (por edad, género, procedencia o lagunas temporales formativas).