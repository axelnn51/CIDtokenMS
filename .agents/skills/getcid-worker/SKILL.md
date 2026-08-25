---
name: getcid-worker
description: "SYSTEM SPECIFICATION & ARCHITECTURE: GETCID — Microsoft Operation Worker. Lee esta skill siempre que vayas a trabajar en el proyecto GETCID para recordar las reglas arquitectónicas, los contratos de Redis y el flujo de estados."
---

# SYSTEM SPECIFICATION & ARCHITECTURE: GETCID — Microsoft Operation Worker

## 0. CONTEXTO DEL PROYECTO Y OBJETIVO
Este es un sistema distribuido y asíncrono en Python para automatizar la extracción de **Tokens de Autenticación (JWT, Bearer, MSAL)** desde portales de Microsoft (como `visualstudio.com`).

**El cambio de paradigma central:** Este sistema está diseñado para iniciar una sesión de navegador real (Chromium), superar barreras de seguridad de forma humana/automatizada y capturar los tokens interceptando las peticiones de red o inspeccionando el `localStorage`/Cookies. El Worker devuelve el token extraído al backend para su uso externo.

El sistema debe ser resiliente, observable y capaz de recuperarse ante errores de red, expiración de sesión, cambios del DOM y desafíos de autenticación (CAPTCHAs).

---

## 1. ARQUITECTURA GENERAL
El sistema se compone de 3 piezas estrictamente separadas que se comunican vía Redis:

1. **FastAPI (REST API):** Orquestador. Recibe el `Installation ID`, crea un Job en Redis y devuelve un `job_id` (HTTP 202). No sabe nada de navegadores, autenticación ni Playwright.
2. **Redis (Broker/State):** Maneja la cola de trabajos (Streams), el estado de los jobs, los resultados con TTL y los *locks* de concurrencia. No se usarán archivos compartidos.
3. **Microsoft Operation Worker (Python):** Consume la cola, levanta Chromium mediante Playwright, ejecuta la operación y guarda el resultado.

---

## 2. REGLAS INQUEBRANTABLES (HARD RULES)
- **Extracción Sigilosa:** El objetivo principal es obtener el token sin ser detectado.
- **Cero MITM (Proxies):** Prohibido usar proxies interceptores externos (ej. `selenium-wire`). La intercepción de red debe hacerse con la API nativa de Playwright (`page.on('request')`). CDP solo si la API nativa es insuficiente.
- **Concurrencia Estricta (1 Worker = 1 Job):** Inicialmente, solo 1 Worker ejecutará 1 Job a la vez, usando un perfil de navegador persistente. Debe usar un sistema de *Leasing/Lock* atómico en Redis con un hilo de *heartbeat* para mantener exclusividad.
- **Garantía de Cleanup (try...finally):** Ninguna excepción, timeout o crash debe dejar un Chromium zombie o un *lock* huérfano. Todo debe cerrarse de forma segura.
- **Autonomía al 100% (con fallback manual):** El sistema intentará resolver los desafíos (CAPTCHA/Azure WAF) de manera **100% automática** (por ejemplo, mediante proveedores de resolución u otras técnicas autónomas). Si el desafío no se puede resolver automáticamente, o si el usuario envía un comando explícito para intervención, el sistema pasará a `CHALLENGE_REQUIRED`, pausará de forma segura y esperará intervención manual vía VNC/SSH.
- **UNKNOWN_STATE:** Si el DOM cambia o no coincide con los selectores esperados, no se improvisa. Se transiciona a `UNKNOWN_STATE`, se guarda diagnóstico (URL, screenshot) y se detiene.

---

## 3. CONTRATOS DE REDIS (DATA MODEL)
- `jobs:stream` -> Redis Stream (Consumer Groups). Evita que los jobs desaparezcan si el Worker muere antes del ACK.
- `jobs:data:{job_id}` -> Hash/JSON. Modelo estricto (Pydantic): `status`, `installation_id`, `metrics`, `result`, `retry_count`. TTL de 24 horas.
- `locks:microsoft_worker` -> String con lease de 30s. La renovación/eliminación debe validar atómicamente (Lua script) que el dueño (`worker_id`) sigue siendo el mismo.
- `workers:{worker_id}` -> Hash/JSON. Heartbeat periódico del worker (`status`, `job_id`, `heartbeat`).

---

## 4. MÁQUINA DE ESTADOS DEL JOB
Transiciones controladas mediante una función centralizada. No se permiten transiciones arbitrarias.

- `PENDING`: Job en cola.
- `STARTING_BROWSER`: Worker asignado, preparando perfil Chromium.
- `AUTHENTICATING`: Validando estado de sesión con Microsoft.
- `EXECUTING`: Sesión válida, inyectando `Installation ID`.
- `CHALLENGE_REQUIRED`: CAPTCHA/WAF detectado que no pudo resolverse autónomamente (o se forzó manual). Espera intervención humana.
- `VALIDATING_RESULT`: Resultado obtenido, verificando su integridad.
- `UNKNOWN_STATE`: Estado irreconocible del sitio. **Detiene la ejecución**.
- `RETRYABLE_ERROR`: Fallo de red/timeout recuperable.
- `FAILED_PERMANENTLY`: Error no reintentable.
- `COMPLETED`: CID obtenido y validado con éxito.

---

## 5. ESTRUCTURA DEL PROYECTO (WORKER)
Respeta esta arquitectura de directorios con responsabilidades aisladas:

```text
worker/
├── main.py                 # Main loop
├── jobs/
│   ├── consumer.py         # Consumo del Stream (ACK) y garantía try...finally
│   ├── state_manager.py    # Transiciones de estado y validación
│   └── lock.py             # WorkerLease (Lock atómico en Redis + Heartbeat)
├── browser/
│   ├── chromium.py         # Config Playwright y argumentos
│   └── lifecycle.py        # Context Manager (Setup/Teardown limpio)
├── microsoft/
│   ├── authentication.py   # Lógica de detección de sesión
│   ├── navigation.py       # Navegación
│   └── operation.py        # Inyección y extracción (solo selectores/DOM)
└── diagnostics/
    ├── logger.py           # Logging estructurado (NUNCA loguear secretos)
    └── vnc_notifier.py     # Diagnóstico y capturas ante UNKNOWN_STATE
```
