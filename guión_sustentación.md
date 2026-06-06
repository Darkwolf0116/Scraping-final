# Guión de sustentación — Agent OS (OpenFang) · Fundación Valle del Lili

**Duración total:** 15 minutos · **Integrantes:** Mateo · Fong · Jhonatan · Nicolás
**Proyecto:** RUTA B — Sistema Operativo Agéntico con OpenFang + Gemini + RAG + Telegram

> **Cómo usar este guión:** cada integrante tiene su bloque con (a) el **guión hablado**
> (lo que dice, en primera persona), (b) **qué mostrar en pantalla** y (c) la **transición**
> al siguiente. Los textos en *cursiva* son notas para el orador (no se leen). Al final hay
> una **batería de preguntas y respuestas** para preparar la ronda del jurado.

---

## Distribución y tiempos

| # | Integrante | Tema | Tiempo |
|---|-----------|------|--------|
| 1 | **Mateo** | Apertura, el problema y la arquitectura del Agent OS | 0:00 – 3:30 |
| 2 | **Fong** | El conocimiento de la empresa → memoria del OS (RAG: scraping, embeddings, Vector + KV Store) | 3:30 – 7:00 |
| 3 | **Jhonatan** | El cerebro en acción: agente, MCP, tool-calling y **demo en vivo** por Telegram | 7:00 – 10:45 |
| 4 | **Nicolás** | Autonomía (Hands System + HITL), economía de tokens, retos de ingeniería y cierre | 10:45 – 14:30 |
| — | **Los 4** | Conclusión + preguntas | 14:30 – 15:00 |

**Hilo narrativo:** *problema → cómo la empresa se "vuelve" el agente → cómo responde en vivo
→ cómo trabaja solo y por qué es robusto y barato.*

---

## 1 · MATEO — Apertura y arquitectura (0:00 – 3:30)

**Objetivo:** enganchar al jurado, plantear el problema y dar el mapa mental del sistema.

### Guión hablado

"Buenos días. Somos [nombres del equipo] y hoy les presentamos la **RUTA B** de nuestro
proyecto: un **Sistema Operativo Agéntico** para la Fundación Valle del Lili.

Partamos del problema. Una institución de salud tiene muchísima información dispersa —cientos
de especialistas, decenas de servicios, sedes, chequeos, normativa— y atender al usuario con
eso es costoso y lento. La idea ingenua sería conectar un ChatGPT, pero eso tiene dos
problemas graves: **inventa datos** (y en salud eso es inaceptable) y **expone la información
de la empresa** a un tercero.

Nuestra solución es distinta: en lugar de un chatbot, montamos un **Sistema Operativo para
agentes** llamado **OpenFang** —un kernel agéntico escrito en Rust— que corre **localmente**
y orquesta todo: recibe mensajes, administra la memoria del agente, ejecuta herramientas y
hasta tareas autónomas. Como modelo de lenguaje usamos **Google Gemini**, y para que **nunca
invente**, aplicamos **RAG**: *Retrieval-Augmented Generation*. Es decir: primero **buscamos**
la respuesta en una base de conocimiento construida con la información real de la Fundación, y
solo entonces el modelo **redacta** usando ese contexto. La regla de oro de todo el sistema es:
*el modelo no inventa, solo redacta lo que las herramientas le entregan.*

A vista de pájaro, el sistema tiene cuatro grandes piezas —que son justamente los cuatro
módulos de la ruta—:
1. **El entorno**: OpenFang + Gemini.
2. **El conocimiento**: convertimos el sitio web de la empresa en la memoria del agente.
3. **La autonomía**: 'Hands', operaciones que el agente ejecuta solo.
4. **El canal**: el usuario habla con el agente por **Telegram**.

En los próximos minutos, Fong les contará cómo inyectamos el conocimiento, Jhonatan les hará
una demostración en vivo de cómo responde, y Nicolás cerrará con la parte autónoma y los retos
de ingeniería que resolvimos."

### Qué mostrar
- Portada con el título y los 4 nombres.
- **Diagrama de arquitectura** (el del `explicación.md`): Telegram → OpenFang → agente →
  herramientas (MCP) → RAG (Vector + KV) → Gemini.

### Transición
"Pero un agente sin conocimiento es una cáscara vacía. Fong, ¿cómo logramos que la Fundación
**se convierta** en el agente?"

---

## 2 · FONG — El conocimiento → memoria del OS (3:30 – 7:00)

**Objetivo:** explicar el pipeline de datos: del sitio web a la memoria semántica + estructurada.

### Guión hablado

"Gracias, Mateo. El corazón de que el agente *sepa* de la Fundación es la **ingesta del
conocimiento**, y tiene dos capas de memoria.

Primero, **conseguimos el contenido**. Construimos un *web scraper* que lee el **sitemap** del
sitio oficial y descarga todas las páginas —especialistas, servicios, sedes, chequeos— en
paralelo, con reintentos y capacidad de *reanudar*. Cada página se limpia y se convierte en
**Markdown** con metadatos (título, sección, URL). Hay lógica especial para los **perfiles de
médicos**: extraemos nombre, especialidades y hasta la extensión telefónica, incluso de bloques
ocultos del HTML. Terminamos con cerca de **1.500 fragmentos** de conocimiento, de los cuales
unos **650 son perfiles de especialistas**.

Segundo, y aquí está la magia, convertimos ese texto en **memoria semántica**. Usamos
**embeddings**: cada fragmento se transforma en un **vector de 3.072 dimensiones** con el
modelo de Gemini. ¿Por qué? Porque un vector captura el *significado*: textos parecidos quedan
'cerca' en el espacio. Así, cuando alguien pregunta '¿quién me ve el corazón?', el sistema
encuentra 'cardiología' aunque no use esa palabra. Todo eso se guarda en un **Vector Store**
—una base SQLite—, y la búsqueda se hace por **similitud de coseno**: rankeamos por cercanía
de vectores.

Pero no todo es semántico. Los datos **administrativos** —sedes, horarios, teléfonos, EPS en
convenio— los guardamos como **memoria estructurada**, en el **Key-Value Store nativo de
OpenFang**. Cada sección es una entrada exacta. Esto le da al agente una 'identidad base'
permanente dentro del sistema operativo.

Entonces tenemos dos memorias complementarias: la **semántica** (Vector Store) para 'qué hace
este servicio' o 'qué médicos hay', y la **estructurada** (KV Store) para 'cuál es la dirección
de la sede principal'. El agente elige cuál usar según la pregunta."

### Qué mostrar
- Un `.md` scrapeado de un especialista (con su frontmatter).
- El diagrama: `output/*.md → chunking → embeddings (3072-d) → SQLite` + el `institucional.json` → KV.
- *Opcional:* una línea del `data/rag_index.sqlite` o el conteo por sección.

### Transición
"Ya tenemos memoria. Jhonatan, muéstrales cómo el agente la usa para responderle a una persona
real… en vivo."

---

## 3 · JHONATAN — El cerebro en acción + DEMO (7:00 – 10:45)

**Objetivo:** explicar tool-calling/MCP y **demostrar** una respuesta real por Telegram.

### Guión hablado (antes de la demo)

"Gracias, Fong. Ya con la memoria lista, veamos **cómo razona** el agente.

Cuando alguien escribe por Telegram, **OpenFang** entrega el mensaje al agente. El agente corre
sobre Gemini, pero no responde de una: tiene **herramientas**. Las exponemos con un estándar
llamado **MCP** —Model Context Protocol—: levantamos un pequeño servidor que ofrece tres
herramientas de búsqueda. La principal, `buscar_institucional`, busca médicos, especialidades y
servicios; `consultar_datos_corporativos` trae sedes y horarios; y `buscar_regulatorio` consulta
normativa.

Lo potente es el **tool-calling**: Gemini, en medio de su razonamiento, *decide* llamar la
herramienta correcta, recibe el resultado de nuestro RAG, y **redacta la respuesta con esos
datos**. Por ejemplo, si preguntan por un médico, nuestro prompt obliga al agente a usar
`buscar_institucional` filtrando por la sección de especialistas, y a **listar siempre los
nombres** que le devuelve la herramienta. Nunca improvisa.

Veámoslo en vivo."

### DEMO EN VIVO (guion del demo)

*Tener Telegram abierto y el bot `@Valle_lilibot` corriendo (daemon `make start` ya levantado).*

1. **Pregunta de especialistas:** escribir *"¿Qué cardiólogos atienden en la Fundación?"*
   → mostrar que responde con **lista de nombres + especialidad + extensión**.
   - Decir: *"Aquí el agente llamó a `buscar_institucional`, recuperó los perfiles por
     similitud y Gemini los listó. Todo con datos reales del scraping, sin inventar."*
2. **Pregunta de datos corporativos:** *"¿Cuáles son las sedes y sus direcciones?"*
   → muestra que usa la otra herramienta (KV) y da direcciones exactas.
3. **(Opcional) Flujo síntoma → cita:** *"Me duele el pecho, ¿qué hago?"* → el agente sugiere
   la especialidad, lista doctores y da el contacto de citas.
4. **Prueba de honestidad:** *"¿Quién ganó el mundial 2022?"* → el agente responde que solo
   ayuda con información institucional. *"Esto demuestra la regla de oro: no inventa."*

*Plan B si falla el internet/Telegram:* tener **capturas** de las cuatro respuestas y el
**dashboard** de OpenFang (`http://127.0.0.1:4200`) listos.

### Qué mostrar
- Telegram con el bot respondiendo en vivo.
- *Opcional:* el dashboard de OpenFang mostrando el agente y las herramientas conectadas.

### Transición
"Lo que vieron fue el agente **reactivo**: responde cuando le escriben. Pero OpenFang también
permite que el agente **trabaje solo**. Nicolás les cuenta esa parte y cómo lo hicimos robusto
y barato."

---

## 4 · NICOLÁS — Autonomía, costos, retos y cierre (10:45 – 14:30)

**Objetivo:** mostrar el Hands System (lo más avanzado), la economía de tokens, los retos
técnicos resueltos y cerrar con fuerza.

### Guión hablado

"Gracias, Jhonatan. Hasta aquí, un asistente que responde. Pero el verdadero diferencial de un
*Agent OS* es la **autonomía**: lo que OpenFang llama **Hands**.

Una **Hand** es una capacidad que **corre sola**, en un horario, sin que nadie le escriba.
Nosotros configuramos una Hand de **inteligencia regulatoria**: vigila de forma autónoma la
normativa de salud colombiana —MinSalud, Supersalud, Invima— detecta normas nuevas relevantes
para una IPS, las resume y deja **borradores**. Y aquí aplicamos un principio serio:
**Human-In-The-Loop**. La Hand no publica nada por su cuenta; un humano **aprueba** cada
borrador antes de que entre a la base que consulta el personal interno. Automatización con
control humano.

Segundo punto: **el costo**. Gemini cobra por token, así que optimizamos agresivamente.
Usamos el modelo más económico con soporte de herramientas, **desactivamos el modo
'pensamiento'**, y —un detalle clave— **suprimimos los 61 'skills' que OpenFang inyecta por
defecto**, que costaban unos **20.000 tokens por mensaje**. Resultado: cada respuesta cuesta
fracciones de centavo.

Tercero, y quiero ser honesto porque aquí estuvo la ingeniería de verdad: **los retos**.
Hacerlo funcionar de punta a punta nos enseñó cuatro cosas no obvias:
- El **modelo** debe existir en el catálogo de OpenFang; un nombre equivocado hacía que el
  agente **no usara las herramientas** y respondiera evasivo.
- OpenFang ejecuta las herramientas en un **sandbox que limpia el entorno**; tuvimos que
  lanzarlas con el intérprete correcto y reenviar la clave de API explícitamente.
- En la búsqueda, había que **filtrar por sección dentro del ranking**, o los servicios
  'tapaban' a los médicos.
- Y descubrimos el efecto de la **sesión 'envenenada'**: si el agente alguna vez respondió mal,
  se mantenía consistente con ese error; lo corregimos con un prompt más firme y limpiando el
  historial.

Cada uno de esos bugs lo diagnosticamos **inspeccionando el daemon en vivo** —su API, sus
logs, su catálogo de modelos—, no a ciegas.

Para cerrar: construimos un **sistema operativo agéntico completo** que convierte el
conocimiento de la Fundación en un asistente que atiende por Telegram, no inventa, trabaja
también de forma autónoma y todo a un costo mínimo y con los datos bajo control. Como trabajo
futuro: activar más Hands —por ejemplo un perfil comercial de generación de *leads*— y conectar
WhatsApp. Muchas gracias."

### Qué mostrar
- El `HAND.toml` y el dashboard mostrando la Hand `collector-regulatorio` activa.
- Una diapositiva de **'Retos resueltos'** (los 4 puntos) — suele impresionar al jurado.
- Slide de cierre: logros + trabajo futuro.

---

## Cierre conjunto (14:30 – 15:00)

"En resumen: **OpenFang** como orquestador, **Gemini** como cerebro, **RAG** para no inventar,
**MCP** para las herramientas, **Hands** para la autonomía y **Telegram** como canal. Quedamos
atentos a sus preguntas."

---

## Batería de preguntas del jurado (preparación)

> Repártanse quién responde cada tema según su bloque. Respuestas cortas y seguras.

**¿Por qué OpenFang y no un chatbot normal?**
Porque es un *sistema operativo* de agentes: orquesta memoria, herramientas, multicanal y
tareas autónomas (Hands), corre local (soberanía de datos) y es de bajo consumo. Un chatbot
sería solo la capa reactiva; aquí tenemos también autonomía e infraestructura.

**¿Cómo evitan que el modelo invente (alucinaciones)?**
Con RAG: el agente *debe* llamar herramientas y responder **solo** con lo que devuelven; el
prompt lo prohíbe explícitamente inventar nombres, teléfonos o normas. Si no hay datos, lo dice.

**¿Qué es exactamente un embedding y por qué 3072 dimensiones?**
Es un vector que representa el significado del texto; lo da el modelo de embeddings de Gemini
(3072 dimensiones es su salida). Permite buscar por *significado* (coseno), no por palabras exactas.

**¿Dónde viven los datos? ¿Es seguro?**
El conocimiento (índices) vive **local** en el repositorio. A Gemini solo viaja la consulta y
el contexto recuperado para redactar. Las claves van en un `.env` que **no** se sube al repo.

**¿Por qué Gemini y no un modelo local (Ollama)?**
Por requerimiento del proyecto y por calidad/costo: `gemini-2.5-flash-lite` soporta
*tool-calling*, es muy barato y no exige hardware. El diseño deja la puerta abierta a cambiar
de modelo fácilmente.

**¿Cómo controlan el costo?**
Modelo 'lite', 'thinking' apagado, supresión de skills (~20K tokens/mensaje), contexto
acotado y Hands con tope de ejecuciones. Medimos tokens y costo por consulta con un *smoke test*.

**¿Qué es una Hand y en qué se diferencia del agente?**
El agente es **reactivo** (responde cuando le escriben). La Hand es **autónoma**: corre en un
horario, construye conocimiento y reporta al dashboard. La nuestra vigila normativa con
aprobación humana (HITL).

**¿Qué es MCP?**
Un estándar para exponer herramientas a un modelo. Nuestro servidor MCP ofrece las búsquedas;
el agente las 'llama' mediante *tool-calling*.

**¿Qué pasa si una herramienta falla?**
El agente lo informa con honestidad y sugiere contactar a la Fundación; no se inventa la
respuesta. Diseñamos el sistema para degradar con gracia.

**¿Escala a más canales o empresas?**
Sí: el mismo cerebro RAG sirve para WhatsApp (puerto nativo de OpenFang) y el pipeline de
ingesta se reusa para cualquier sitio; solo cambia el corpus.

---

## Tips de presentación

- **Ensayen con cronómetro**: ~3:30 cada uno. Si se alargan, recorten la teoría, **no la demo**.
- **Demo a prueba de fallos**: tengan el bot ya corriendo antes de empezar y **capturas de
  respaldo** por si falla la red.
- **Lenguaje**: traduzcan cada término técnico la primera vez (RAG, embedding, MCP, Hand).
- **Transiciones**: usen las frases puente; que se note que es un solo relato, no cuatro charlas.
- **Cierre fuerte**: el bloque de 'retos resueltos' demuestra dominio real; no lo salten.
```

