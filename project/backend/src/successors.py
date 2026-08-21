"""Generador de sucesores restringido — el `Applicable` interno del agente.

A propósito más estricto que el simulador/contrato: implementa las podas
justificadas en design.md ("Applicable interno vs legalidad del contrato" y
"Formulación y tamaño del espacio") para mantener acotado el factor de
ramificación de UCS. Cada poda de aquí tiene su argumento de soundness
escrito en design.md — este módulo es donde ese argumento se vuelve código.
"""
from __future__ import annotations

from actions import Action, cost
from scenario_index import ScenarioIndex
from state import ROBOT, State


def payload_weight(state: State, idx: ScenarioIndex) -> int:
    """El peso de la carga se deriva del estado: es la suma de los pesos de
    los objetos cuya localización es el robot (design.md, "Qué información
    se deriva y NO se almacena")."""
    total = sum(idx.key_weight[k] for k, loc in state.keys if loc == ROBOT)
    total += sum(idx.tool_weight[t] for t, loc in state.tools if loc == ROBOT)
    total += sum(
        idx.material_weight[t] * c for t, loc, c in state.materials if loc == ROBOT
    )
    return total


def generate(state: State, idx: ScenarioIndex) -> list[Action]:
    actions: list[Action] = []

    # MOVE: cualquier corredor desde la zona actual cuya puerta (si tiene)
    # esté abierta.
    for corridor in idx.corridors_from.get(state.zone, ()):
        door = corridor.get("door")
        if door is None or door in state.doors_open:
            actions.append(Action("MOVE", frm=state.zone, to=corridor["to"]))

    weight_now = payload_weight(state, idx)
    cap = idx.cargo_capacity

    # Objetos relevantes en el suelo de la zona actual.
    ground_here: list[tuple[str, str, int]] = []  # (kind, id_o_tipo, peso)
    for key_id, loc in state.keys:
        if loc == state.zone and idx.is_key_relevant(key_id, state):
            ground_here.append(("key", key_id, idx.key_weight[key_id]))
    for tool_id, loc in state.tools:
        if loc == state.zone and idx.is_tool_relevant(tool_id, state):
            ground_here.append(("tool", tool_id, idx.tool_weight[tool_id]))
    for mtype, loc, count in state.materials:
        if loc == state.zone and count > 0 and idx.is_material_relevant(mtype, state):
            ground_here.append(("material", mtype, idx.material_weight[mtype]))

    # PICKUP: solo objetos relevantes que además caben.
    blocked = False
    for kind, ident, w in ground_here:
        if weight_now + w <= cap:
            actions.append(Action("PICKUP", item=ident, item_kind=kind))
        else:
            blocked = True

    # DROP: solo cuando hay presión de carga real (algo útil aquí que no
    # cabe). No se genera DROP en cada estado con carga — eso es justo la
    # explosión combinatoria que design.md descarta.
    #
    # Si además hay algún objeto muerto encima (ya no sirve para nada),
    # soltar ESE domina soltar uno vivo: libera el mismo espacio al mismo
    # costo y no obliga a recogerlo de nuevo más adelante. Por eso, cuando
    # hay al menos un muerto, solo se ofrecen esos como candidatos.
    if blocked:
        carried_keys = [k for k, loc in state.keys if loc == ROBOT]
        carried_tools = [t for t, loc in state.tools if loc == ROBOT]
        carried_materials = [t for t, loc, _c in state.materials if loc == ROBOT]

        dead_keys = [k for k in carried_keys if not idx.is_key_relevant(k, state)]
        dead_tools = [t for t in carried_tools if not idx.is_tool_relevant(t, state)]
        dead_materials = [
            t for t in carried_materials if idx.is_material_payload_dead(t, state)
        ]

        if dead_keys or dead_tools or dead_materials:
            carried_keys, carried_tools, carried_materials = (
                dead_keys,
                dead_tools,
                dead_materials,
            )

        for key_id in carried_keys:
            actions.append(Action("DROP", item=key_id, item_kind="key"))
        for tool_id in carried_tools:
            actions.append(Action("DROP", item=tool_id, item_kind="tool"))
        for mtype in carried_materials:
            actions.append(Action("DROP", item=mtype, item_kind="material"))

    # OPEN_DOOR
    for door_id, door in idx.doors.items():
        if (
            state.zone in door["between"]
            and door_id not in state.doors_open
            and state.carries_key(door["key"])
        ):
            actions.append(Action("OPEN_DOOR", target=door_id))

    # REPAIR: solo paneles que de verdad hacen falta para la meta.
    for panel_id in idx.needed_panels:
        if panel_id in state.panels_ok:
            continue
        panel = idx.panels[panel_id]
        if panel["zone"] != state.zone:
            continue
        req_tool = panel["requires"]["tool"]
        req_mat = panel["requires"]["material"]
        if state.carries_tool(req_tool) and state.carried_material_count(req_mat) > 0:
            actions.append(Action("REPAIR", target=panel_id, consumes=req_mat))

    # ACTIVATE: solo estaciones que hacen falta para la meta (directa o
    # transitivamente).
    for station_id in idx.needed_stations:
        if station_id in state.stations_online:
            continue
        station = idx.stations[station_id]
        if station["zone"] != state.zone:
            continue
        reqs = station["requires"]
        if all(p in state.panels_ok for p in reqs.get("panels_ok", [])) and all(
            s in state.stations_online for s in reqs.get("stations_online", [])
        ):
            actions.append(Action("ACTIVATE", target=station_id))

    # RECHARGE: se genera siempre que sea legal. design.md descarta a
    # propósito la poda por umbral de batería por no ser sound.
    charger_id = idx.chargers_by_zone.get(state.zone)
    if charger_id and state.battery < idx.battery_max:
        actions.append(Action("RECHARGE", target=charger_id))

    return [a for a in actions if state.battery >= cost(a, idx)]
