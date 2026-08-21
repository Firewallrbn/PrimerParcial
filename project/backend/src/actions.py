"""Acciones internas del agente: costo y transición (Result).

`result()` asume que la acción ya pasó el filtro de legalidad de
successors.py: es determinista y parcial, tal como se describe en
design.md ("Modelo de transición") — nunca se invoca sobre una acción no
aplicable, así que aquí no se re-evalúan precondiciones ni se capturan
excepciones.

Recoger y soltar no son más que cambiar la localización de un objeto entre
una zona y ROBOT: con K, T y M definidas como «objeto → localización», no
hace falta mover nada entre dos estructuras distintas.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from scenario_index import ScenarioIndex
from state import ROBOT, State


@dataclass(frozen=True)
class Action:
    kind: str  # MOVE | PICKUP | DROP | OPEN_DOOR | REPAIR | ACTIVATE | RECHARGE
    frm: Optional[str] = None
    to: Optional[str] = None
    item: Optional[str] = None  # id (key/tool) o type (material)
    item_kind: Optional[str] = None  # "key" | "tool" | "material"
    target: Optional[str] = None  # door/panel/station/charger id
    consumes: Optional[str] = None  # material type, solo para REPAIR


def cost(action: Action, idx: ScenarioIndex) -> int:
    """Siempre el costo oficial leído del escenario (CONTRATO.md §5) —
    nunca un valor fijo en el código, porque el profesor prueba con otras
    instancias."""
    if action.kind == "MOVE":
        return idx.corridor_cost[(action.frm, action.to)]
    if action.kind == "PICKUP":
        return idx.action_costs["pickup"]
    if action.kind == "DROP":
        return idx.action_costs["drop"]
    if action.kind == "RECHARGE":
        return idx.action_costs["recharge"]
    return idx.action_costs["interact"]  # OPEN_DOOR, REPAIR, ACTIVATE


def result(action: Action, state: State, idx: ScenarioIndex) -> State:
    battery = state.battery - cost(action, idx)

    if action.kind == "MOVE":
        return replace(state, zone=action.to, battery=battery)

    if action.kind == "PICKUP":
        return _relocate(state, battery, action, frm=state.zone, to=ROBOT, idx=idx)

    if action.kind == "DROP":
        # Soltar un objeto muerto lo hace desaparecer del estado (⊥) en vez
        # de dejarlo rastreado en una zona para siempre (design.md,
        # "Relevancia: objetos que ya no cambian el futuro"). Sin este
        # colapso, cada combinación de "dónde quedó cada objeto ya inútil"
        # produce un mundo distinto y explota el espacio de estados.
        destination = state.zone if _still_useful(action, state, idx) else None
        return _relocate(state, battery, action, frm=ROBOT, to=destination, idx=idx)

    if action.kind == "OPEN_DOOR":
        # La llave no se consume (CONTRATO.md §4, Puertas): sigue encima.
        return replace(state, battery=battery, doors_open=state.doors_open | {action.target})

    if action.kind == "REPAIR":
        assert action.consumes is not None
        # El material se destruye; la herramienta no se gasta.
        return replace(
            state,
            battery=battery,
            materials=_move_material(state.materials, action.consumes, ROBOT, None),
            panels_ok=state.panels_ok | {action.target},
        )

    if action.kind == "ACTIVATE":
        return replace(
            state, battery=battery, stations_online=state.stations_online | {action.target}
        )

    if action.kind == "RECHARGE":
        # El costo ya se descontó arriba (hace falta batería suficiente
        # para pagarlo); el efecto neto es subir al máximo, tal como lo
        # implementa el simulador de referencia (CONTRATO.md §4, Batería).
        return replace(state, battery=idx.battery_max)

    raise ValueError(f"Unknown action kind: {action.kind}")


def _still_useful(action: Action, state: State, idx: ScenarioIndex) -> bool:
    if action.item_kind == "key":
        return idx.is_key_relevant(action.item, state)
    if action.item_kind == "tool":
        return idx.is_tool_relevant(action.item, state)
    return not idx.is_material_payload_dead(action.item, state)


def _relocate(
    state: State,
    battery: int,
    action: Action,
    frm: str,
    to: Optional[str],
    idx: ScenarioIndex,
) -> State:
    """Mueve un objeto de una localización a otra. `to=None` lo elimina del
    estado (objeto muerto colapsado a ⊥)."""
    assert action.item is not None

    if action.item_kind == "material":
        return replace(
            state,
            battery=battery,
            materials=_move_material(state.materials, action.item, frm, to),
        )

    field = "keys" if action.item_kind == "key" else "tools"
    current: frozenset[tuple[str, str]] = getattr(state, field)
    updated = frozenset(pair for pair in current if pair != (action.item, frm))
    if to is not None:
        updated = updated | {(action.item, to)}
    return replace(state, battery=battery, **{field: updated})


def _move_material(
    materials: frozenset[tuple[str, str, int]],
    mtype: str,
    frm: str,
    to: Optional[str],
) -> frozenset[tuple[str, str, int]]:
    """Mueve una unidad de material entre localizaciones, manteniendo la
    forma canónica: nunca se guarda un contador en cero."""
    counts = {(t, loc): c for t, loc, c in materials}
    counts[(mtype, frm)] -= 1
    if counts[(mtype, frm)] <= 0:
        del counts[(mtype, frm)]
    if to is not None:
        counts[(mtype, to)] = counts.get((mtype, to), 0) + 1
    return frozenset((t, loc, c) for (t, loc), c in counts.items())
