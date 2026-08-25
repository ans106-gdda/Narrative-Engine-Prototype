# PLAN — El Contrato de Vesper
### Virtual Dungeon Master con Narrative Consistency Agent

---

## 0. Resumen ejecutivo

Motor narrativo de 6 turnos donde un LLM narra una mansión vampírica, pero **nunca decide el estado del mundo**. El estado vive en un ledger JSON gobernado por Python determinista, y una cuarta llamada al modelo audita cada narración contra ese ledger antes de que llegue al jugador.

**Tesis del proyecto:** la consistencia no se le pide al modelo, se le impone desde fuera.
**Giro de diseño:** el mundo premia la coherencia (Vesper elige heredero por `coherence_score`), así que la mecánica de juego y la tesis técnica son la misma cosa.

**Los 4 agentes del pipeline:**

```
input del jugador
      ↓
[1] EXTRACTOR   texto libre → intent tipado          (solo si escribe libre)
      ↓
[2] LEDGER      aplica efectos en Python puro         ← NO hay LLM aquí
      ↓
[3] OPTIONER    intents legales → opciones redactadas
[3] NARRATOR    ledger completo → prosa del turno
      ↓
[4] AUDITOR     prosa vs ledger → ✅ / ❌ + violaciones  ← el consistency agent
      ↓
render + log
```

Si [4] rechaza, [3] se reintenta con las violaciones inyectadas (máx. 2). Cada rechazo queda en `contradiction_log` — evidencia auditable para el rubric.

---

## 1. Entorno (bloqueante primero)

| Item | Estado | Acción |
|---|---|---|
| Python | 3.9.6 (system) — **insuficiente** | venv con `~/.local/bin/python3.11` |
| SDK `anthropic` | no instalado | `pip install anthropic pydantic python-dotenv` |
| Credenciales | **ausentes** | ⚠️ ver abajo |

```bash
~/.local/bin/python3.11 -m venv .venv && ./.venv/bin/pip install anthropic pydantic python-dotenv rich
```

**⚠️ Único bloqueante:** no hay `ANTHROPIC_API_KEY` ni CLI `ant`. Necesito que exportes tu key o la pongas en `.env`. Puedo construir e importar todo el motor sin ella; solo la corrida real de 6 turnos y la demo A/B la requieren.

**Decisiones de API ya verificadas** (contra la doc actual, no de memoria):
- Modelo `claude-opus-5` en los 4 agentes.
- Extractor y Auditor usan `client.messages.parse(..., output_format=ModeloPydantic)` → `response.parsed_output` ya validado. Cero parseo de JSON a mano, cero regex sobre la salida.
- Narrator y Optioner: `messages.create` con `output_config={"effort": "medium"}` — prosa no necesita `high`.
- Auditor con `thinking={"type":"adaptive"}`, que es donde sí paga razonar.
- `max_tokens=16000`, sin streaming (turnos cortos).

---

## 2. Estructura de archivos

```
Narrative Engine Prototype/
├── README.md                 ← DELIVERABLE 2
├── PLAN.md                   ← este archivo
├── requirements.txt
├── .env.example
├── main.py                   ← CLI: interactivo | --script | --load
└── vesper/                   ← DELIVERABLE 1
    ├── world.py              canon, arquetipos, catálogo de intents
    ├── schema.py             Pydantic: Ledger, Candidate, Rumor, Thread, Patch, AuditResult
    ├── ledger.py             apply_patch · coherencia · rumores · poda · diff
    ├── llm.py                cliente + wrappers de las 4 llamadas
    ├── render.py             panel de terminal
    ├── engine.py             bucle del turno (orquesta 1→4)
    └── agents/
        ├── extractor.py
        ├── optioner.py
        ├── narrator.py
        └── auditor.py        ← el narrative consistency agent
├── fixtures/
│   ├── pact.json             estado tras ACEPTAR el pacto (campanada 2)
│   └── betrayal.json         estado tras DELATAR a Marrow
└── logs/
    └── session_<ts>.jsonl    un objeto por turno, ledger completo incluido
```

---

## 3. El mundo (para el README)

**Premisa.** Vesper Ashgrove lleva 1.100 años vivo y le quedan seis horas. Su sangre se apaga y debe legarla antes del alba. Ha convocado a cuatro candidatos a la Casa Ashgrove. Al amanecer uno hereda; los demás no salen.

**Reloj.** 6 campanadas hasta el alba. Público, visible, irreversible. **Poda opciones**: en la campanada ≥4 desaparece `build_trust` — ya no hay tiempo de hacer amigos; solo quedan `betray`, `bargain`, `confess`.

**Reparto.**

| Personaje | Arquetipo | Grieta |
|---|---|---|
| **Marrow** — ghoul, 40 años sirviendo la casa | leal, resentido, lo sabe todo | cree habérselo ganado; nadie lo ve como candidato |
| **Ilsabet Crane** — cazadora infiltrada | fría, competente, miente bien | vino a matar a Vesper y está dudando |
| **Tobias Vane** — 19 años, tuberculoso | desesperado, transparente | es el único que *necesita* ganar |
| **Vesper** — el legador | observa, no juzga por bondad | premia la coherencia, no la lealtad |

**Regla oculta.** Vesper no premia ser bueno ni cruel: premia **decidir y sostenerlo**. Un traidor consistente le impresiona más que un aliado titubeante. El jugador nunca ve su `coherence_score` hasta el final.

---

## 4. El ledger

```json
{
  "chime": 3, "chimes_until_dawn": 3,

  "player": {
    "standing_with_vesper": 2,
    "coherence_score": 0.83,
    "stated_positions": [
      {"claim": "no temo a la muerte", "chime": 1, "audience": ["vesper"]}
    ],
    "contradictions_committed": 0,
    "secrets_held": ["ilsabet_es_cazadora"]
  },

  "candidates": {
    "marrow": {
      "trust": 3,
      "emotional_state": {"mood": "hopeful", "cause": "lo respaldaste", "decays_at_chime": 5},
      "alive": true,
      "believes_about_player": ["me apoyará ante Vesper"],
      "knows_secrets": ["la sangre de Vesper ya falló una vez"]
    }
  },

  "rumor_network": [
    {"fact": "el jugador respaldó a Marrow", "true": true,
     "origin_chime": 2, "known_by": ["marrow","ilsabet"], "reaches_vesper_at": 4},
    {"fact": "el jugador teme a Vesper", "true": false,
     "spread_by": "ilsabet", "known_by": ["tobias"], "reaches_vesper_at": 5}
  ],

  "plot_threads": [
    {"id": "sangre_fallida", "state": "escalating", "revealed_to_player": true, "dormant_for": 0}
  ],

  "immutable_canon": ["Vesper muere al alba, sin excepción"],
  "contradiction_log": []
}
```

**Las cuatro piezas y por qué existen:**

| Campo | Función técnica |
|---|---|
| `rumor_network` | Información **falsa marcada como falsa**. Deja que el auditor distinga *desinformación rastreada* de *alucinación*. Es la pieza que define el proyecto. |
| `coherence_score` + `stated_positions` | Python detecta cuándo el **jugador** se contradice. El jugador es auditado por el mismo sistema que audita al LLM. |
| `believes_about_player` | Dos NPCs pueden tener modelos incompatibles de ti sin que nada esté roto. |
| `immutable_canon` | Hechos que jamás cambian. Prioridad máxima en la auditoría: separa "el mundo cambió" de "el modelo se contradijo". |

---

## 5. Fases de construcción

| # | Fase | Entregable | Depende de |
|---|---|---|---|
| **F1** | Entorno + `requirements.txt` + `.env.example` | venv listo | — |
| **F2** | `world.py` + `schema.py` | canon y modelos Pydantic; `Ledger` serializa/valida | F1 |
| **F3** | `ledger.py` | `apply_patch`, propagación de rumores, cálculo de coherencia, poda de intents, `diff()` | F2 |
| **F4** | `render.py` | panel de terminal | F3 |
| **F5** | `llm.py` + `agents/narrator.py` | primer turno narrado real | F3 + key |
| **F6** | `agents/optioner.py` + `extractor.py` | menú generado + input libre mapeado a intent | F5 |
| **F7** | `agents/auditor.py` | **el consistency agent**: veredicto + reintento + `contradiction_log` | F5 |
| **F8** | `engine.py` + `main.py` | bucle completo, logging JSONL | F4–F7 |
| **F9** | Corrida de 6 campanadas + fixtures A/B | `logs/` + `fixtures/*.json` poblados | F8 |
| **F10** | `README.md` | DELIVERABLE 2 | F9 |

F2–F4 no necesitan credenciales: puedo arrancar ya y dejar el motor entero probado con un LLM simulado antes de gastar un solo token.

---

## 6. Guion de las 6 campanadas

| # | Evento | Qué demuestra |
|---|---|---|
| 1 | **Entrevista.** Vesper pregunta a qué le temes. | Tu respuesta entra en `stated_positions` **y** en `immutable_canon`. Es la trampa que se cierra en la 5. |
| 2 | **El pacto de Marrow.** Te ofrece el secreto de la sangre a cambio de que lo respaldes. | ← **BIFURCACIÓN A/B** |
| 3 | **Ilsabet contraataca.** Actúa según su `believes_about_player` e inyecta un rumor **falso** sobre ti. | El ledger genera información que tú no escribiste |
| 4 | **El rumor llega a Vesper.** `standing_with_vesper` se mueve por algo que nunca dijiste. | Propagación autónoma de estado |
| 5 | **Tobias colapsa.** Ayudarlo o usarlo — y el motor comprueba contra la campanada 1. | `coherence_score` cae **en pantalla** |
| 6 | **El legado.** Vesper decide leyendo coherencia + standing + rumores. | Desenlace derivado del ledger, no del prompt |

---

## 7. La demo A/B

Bifurcación en la campanada 2, binaria y de alta propagación:

- **A — aceptas el pacto** → `marrow.trust +3`, ganas el secreto `sangre_fallida`, rumor "respaldó a Marrow" entra en la red
- **B — lo delatas ante Ilsabet** → `marrow.trust −4`, `ilsabet.trust +2`, Marrow deja de hablarte, rumor "traicionó a un aliado"

```bash
./.venv/bin/python main.py --load fixtures/pact.json     --chime 5 --input "Marrow, necesito la verdad sobre la sangre."
```
```bash
./.venv/bin/python main.py --load fixtures/betrayal.json --chime 5 --input "Marrow, necesito la verdad sobre la sangre."
```

Input idéntico, campanada idéntica, ledger distinto. El contraste tiene **tres capas**, no una:
1. la prosa cambia,
2. el **menú de opciones** cambia (`probe_secret` existe en A, está podada en B),
3. el **log muestra la razón** de la poda.

Eso cierra los 3 puntos de Reactive Dialogue sin margen de discusión.

---

## 8. Render del turno

```
╔═ CAMPANADA 4 ─────────────────── 2 hasta el alba ═╗
  VESPER  ██████░░░░  +2      COHERENCIA  ████████░░  0.83

  Marrow    ███████░░░  +3   hopeful    (decae en 5)
  Ilsabet   ███░░░░░░░  -2   cornered   (decae en 4)
  Tobias    █████░░░░░   0   fading     —

  RED DE RUMORES
   ✓ "respaldó a Marrow"      marrow, ilsabet  → Vesper AHORA
   ✗ "teme a Vesper"          tobias           → Vesper en 5

  OPCIONES PODADAS
   ✗ build_trust    · campanada > 3
   ✗ offer_alliance · ilsabet.trust -2 < 0

  AUDITORÍA  ✅ consistente (1 reintento)
╚═══════════════════════════════════════════════════╝
```

---

## 9. Mapeo al rubric

| Criterio | Pts | Cómo se gana |
|---|---|---|
| **State Tracking** | 4.0 | Ledger Pydantic mutado **solo** por `apply_patch` determinista. Panel por turno + `logs/*.jsonl` con ledger completo, patch y diff. Nunca se le pide al LLM que devuelva el estado — solo el delta. |
| **Reactive Dialogue** | 3.0 | Demo A/B de tres capas (§7). Poda determinista con razón logueada. `emotional_state` efímero separado de `trust` acumulado. |
| **Consistency** | 2.0 | Auditor dedicado sobre 6 turnos + `immutable_canon` + `contradiction_log` con los rechazos reales. La `rumor_network` prueba que distingues mentira rastreada de alucinación. |
| **ReadMe** | 1.0 | §10, con transcript real. |

---

## 10. Esqueleto del README (DELIVERABLE 2)

1. **El mundo** — premisa, reparto, el reloj, la regla oculta de Vesper *(~200 palabras)*
2. **Qué trackea el ledger** — las 4 capas de §4 con el JSON real de una partida, y por qué cada una existe
3. **Arquitectura** — el diagrama de 4 agentes, y la frase clave: *el LLM narra, Python decide*
4. **Un momento que me sorprendió** — de la corrida real de F9. Candidato más probable: la campanada 4, cuando el jugador es juzgado por una mentira que Ilsabet sembró y el narrador la trata como cierta *porque el ledger dice que Vesper la cree* — comportamiento correcto que nadie programó explícitamente.
5. **Cómo ejecutarlo** — venv, key, `main.py`, los dos comandos A/B
6. **Anexo** — la comparación A/B pegada lado a lado

> El momento sorpresa se captura **durante** F9, no se inventa después. Se nota.

---

## 11. Riesgos

| Riesgo | Mitigación |
|---|---|
| El auditor rechaza en bucle | Máx. 2 reintentos, luego acepta y **loguea la violación**. Un fallo registrado vale más que un cuelgue. |
| Coste de 4 llamadas/turno | Optioner y Narrator en una sola llamada con `output_config.format` si hace falta. 6 turnos × 2 fixtures es trivial de todos modos. |
| El narrador filtra `revealed_to_player: false` | Regla dura en el system prompt **y** chequeo explícito del auditor: es su primera comprobación. |
| Extractor malinterpreta input libre | Solo se invoca si el jugador escribe libre; el menú declara su efecto al generarse, así que la ruta principal no tiene extracción ambigua. |

---

## 12. Orden de ejecución propuesto

**Ahora, sin credenciales:** F1 → F2 → F3 → F4, más un `FakeLLM` que devuelva respuestas fijas para probar el bucle entero.
**Con tu key:** F5 → F6 → F7 → F8 → F9 → F10.

El primer commit útil es `schema.py` + `ledger.py`: de ahí cuelga todo lo demás.
