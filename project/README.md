# Proyecto — Emergency Control

El diseño interno de la IA lo escribe usted en [`design.md`](design.md) **antes**
de implementar. Ese archivo ya trae las subsecciones que debe completar
(estado, acciones, `DROP`, batería, tamaño del espacio). El enunciado está en
el `README.MD` de la raíz; las reglas del mundo, en [`../CONTRATO.md`](../CONTRATO.md).

## Estructura

```text
project/
├── frontend/          # React + R3F — simulación 3D voxel
├── backend/           # FastAPI — POST /api/solve (agente UCS)
├── scenarios/         # scenario.json — fuente de verdad
├── design.md          # diseño del agente (entregable 1)
└── README.md
```

### Módulos del agente y su correspondencia con `design.md`

Cada módulo implementa una sección del diseño, para poder contrastar el
modelo matemático con el código:

| Módulo (`backend/src/`) | Sección de `design.md` |
|---|---|
| `state.py` | Estado: la tupla `s = ⟨z, b, K, T, M, D, P, S⟩` y su forma canónica |
| `scenario_index.py` | «Qué información se deriva y NO se almacena» (constantes del escenario) |
| `actions.py` | Acciones: costo y modelo de transición `Result(s, a)` |
| `successors.py` | «`Applicable` interno vs legalidad del contrato»: las podas y su soundness |
| `search.py` | Estrategia de búsqueda: UCS + Graph Search + dominancia de batería |
| `translate.py` | Traducción de acciones internas a las 4 operaciones de `CONTRATO.md` |
| `agent.py` | Orquestación y respuesta de `/api/solve` |

`simulator.py` y `demo_plan.py` vienen con el repositorio base y no forman
parte del agente: el primero se usa como oráculo de legalidad en los tests
y el segundo se conserva como plan artesanal de referencia para comparar
costos.

## Cómo levantar (tú)

Abre **dos terminales**.

### Terminal 1 — Backend

```bash
cd project/backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --app-dir src --port 8000
```

Comprobar: http://127.0.0.1:8000/api/health

### Terminal 2 — Frontend

```bash
cd project/frontend
npm install
npm run dev
```

Abrir: http://localhost:5173

Pulsa **EXECUTE PLAN**. El frontend llama a `/api/solve` (proxy Vite → puerto 8000) y reproduce el plan casilla a casilla.

`/api/solve` ejecuta el agente UCS real (`backend/src/agent.py`), no el plan
artesanal: la ruta que verás es la que encontró la búsqueda.

> ### ⏱️ La primera respuesta tarda ~2-3 minutos
>
> **Esto es normal, no está colgado.** Sobre `scenario.json` la búsqueda
> expande unos 800 000 nodos antes de poder *demostrar* que el plan que
> devuelve es el de menor costo. Durante ese rato el log se queda en
> `[---] Requesting plan from /api/solve ...` y no se mueve nada en pantalla;
> en las DevTools verás la petición `solve` en estado `Pending`.
>
> Cuando termina, el log continúa solo con `[---] Plan received — ...` y
> arranca la animación. En instancias más pequeñas la respuesta es
> instantánea (milisegundos).

### Cómo interpretar el resultado

La respuesta sigue el formato de `../CONTRATO.md` §2:

```json
{ "solution_found": true, "total_cost": 80, "steps": [ ... ], "message": "UCS: ..." }
```

- **`total_cost`** es la suma de los costos oficiales del escenario (no el
  número de pasos). El agente encuentra un plan de **costo 80**; el plan
  artesanal de `demo_plan.py` cuesta 99, así que la búsqueda mejora la
  referencia en 19 unidades de energía. El contador `ENERGY COST` del
  frontend debe coincidir con ese valor al terminar la simulación.
- **`message`** trae la instrumentación de la búsqueda: nodos generados,
  nodos expandidos y tiempo. Sirve para comprobar el comportamiento real de
  UCS (factor de ramificación ≈ 3,4 sobre el escenario demo) en vez de
  confiar en la predicción de `design.md`.
- **`solution_found: false`** con `steps: []` es el `FAILURE` del enunciado.
  El `message` distingue dos situaciones muy distintas:
  - *«meta inalcanzable»* — se demostró **sin buscar** que ningún plan puede
    existir (por ejemplo, falta el material que un panel obligatorio
    consume). Es una conclusión, no una rendición.
  - *«espacio de estados agotado»* — se exploraron todos los estados
    alcanzables y ninguno satisface la meta.
  - *«límite de nodos alcanzado»* — red de seguridad para no bloquear la
    revisión indefinidamente; indica que la búsqueda se detuvo por
    presupuesto, no que la misión sea imposible.

El log del frontend re-ejecuta cada paso contra su propio simulador, así que
si algún paso violara una regla del mundo aparecería en rojo con el motivo
exacto. Un plan que llega a `MISSION COMPLETE` es un plan legal.

### Tests

```bash
cd project/backend
.\.venv\Scripts\activate

python tests/test_agent.py       # agente UCS — los 5 casos del entregable 3
python tests/test_demo_plan.py   # plan artesanal del repositorio base
```

`test_agent.py` cubre los cinco casos exigidos por el enunciado (§6):
estados equivalentes, información relevante, menos pasos ≠ menor costo,
`FAILURE` sin quedar atrapado, y rutas alternativas conservando la más
barata. Además comprueba de punta a punta que el plan emitido es legal
contra `simulator.py` y alcanza la meta.

Tarda varios minutos: dos de los casos resuelven el escenario completo.

## Contrato visual vs agente (importante)

La versión oficial y completa de este contrato (esquema JSON, acciones de `INTERACT`, reglas del mundo y costos) está en `../CONTRATO.md`, que forma parte del enunciado.

El enunciado fija **4 operaciones visuales** que el frontend entiende:

```text
MOVE | PICKUP | DROP | INTERACT
```

`REPAIR`, `ACTIVATE`, `OPEN_DOOR`, `RECHARGE` **no son ops del plan de alto nivel**: son el campo `action` dentro de un paso `INTERACT`.

Ejemplo de lo que debe devolver `/api/solve`:

```json
{ "op": "INTERACT", "target": "PANEL_A", "action": "REPAIR", "consumes": "FUSE", "cost": 2 }
```

- **Agente (estudiante):** puede modelar acciones internas (`REPAIR_PANEL_A`, etc.) y luego **traducirlas** a `MOVE`/`PICKUP`/`DROP`/`INTERACT`.
- **Frontend / banco de pruebas:** solo ejecuta esas 4 ops. El log muestra `INTERACT REPAIR ...` para dejar claro el `op` + el `action`.

Así no hay contradicción: la capa visual no define la IA; solo anima el plan ya traducido.
