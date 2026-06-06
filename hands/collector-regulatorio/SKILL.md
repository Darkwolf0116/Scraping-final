---
domain: regulacion-salud-colombia
version: "1.0"
sources:
  - "MinSalud — Normatividad"
  - "Supersalud — Normativa y circulares"
  - "Invima — Alertas sanitarias / tecnovigilancia / farmacovigilancia"
  - "INS — Vigilancia en salud pública"
---

# Regulación de salud en Colombia — Conocimiento del dominio

Referencia experta para evaluar y resumir normativa relevante a una IPS de alta
complejidad (Fundación Valle del Lili). Es conocimiento de apoyo, no instrucciones:
las instrucciones están en el playbook (el `system_prompt` dentro de HAND.toml).
Mantenlo breve para no inflar el contexto (costo de tokens).

## Entidades y qué emiten
- **MinSalud (Ministerio de Salud y Protección Social):** Decretos y Resoluciones.
  Marco general: habilitación, SOGCS, talento humano, aseguramiento.
- **Supersalud (Superintendencia Nacional de Salud):** Circulares externas;
  inspección, vigilancia y control; reportes obligatorios.
- **Invima:** Alertas sanitarias, farmacovigilancia, tecnovigilancia, registros
  sanitarios de medicamentos y dispositivos.
- **INS (Instituto Nacional de Salud):** Vigilancia epidemiológica (Sivigila),
  lineamientos y alertas en salud pública.

## Tipos de norma (jerarquía)
Ley > Decreto > Resolución > Circular. Las **alertas** (Invima/INS) no son norma
pero exigen acción operativa inmediata. Identifica siempre si una norma **deroga**,
**modifica** o **adiciona** otra (clave para la vigencia).

## Temas de alto impacto para una IPS (usar para puntuar relevancia)
- **Habilitación y SOGCS:** condiciones para prestar servicios de salud.
- **Seguridad del paciente** y eventos adversos.
- **Facturación y RIPS:** facturación electrónica en salud, glosas, reportes.
- **Talento humano en salud:** registro (ReTHUS), condiciones laborales.
- **Farmacovigilancia / tecnovigilancia:** medicamentos y dispositivos médicos.
- **Datos sensibles de salud:** historia clínica, habeas data, interoperabilidad.
- **Aseguramiento y convenios EPS:** pertinente al área administrativa.

## Marco fundacional (suele ser el "ancla" de muchas normas)
- **Decreto 780 de 2016** — Decreto Único Reglamentario del Sector Salud.
- **Resolución 3100 de 2019** — inscripción de prestadores y habilitación de servicios.
- **Resolución 1995 de 1999** — normas de historia clínica.
Cuando una norma nueva modifica alguna de estas, la relevancia es alta.

## Cómo leer la vigencia
- Busca el artículo de "vigencia y derogatorias" al final del texto oficial.
- Una norma puede estar publicada pero con entrada en vigor diferida (transición).
- Ante ambigüedad, marca `vigencia: "verificar en fuente oficial"`.

## Errores a evitar
- No confundir un **proyecto/borrador** publicado para comentarios con una norma en firme.
- No inventar números ni fechas: si no están en la fuente oficial, omitir la norma.
- Distinguir alertas de Invima (acción operativa) de cambios normativos estructurales.
