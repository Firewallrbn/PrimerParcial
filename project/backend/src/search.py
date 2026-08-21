"""UCS con Graph Search y dominancia de batería en CLOSED.

Ver design.md, "Estrategia de búsqueda": prueba de meta al extraer (no al
generar), CLOSED sobre estados canónicos, y la observación de dominancia de
"Batería como recurso" para no tratar cada nivel de batería como un mundo
distinto.
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass
from typing import Optional

from actions import Action, cost, result
from scenario_index import ScenarioIndex
from state import State
from successors import generate


@dataclass
class Node:
    state: State
    parent: Optional["Node"]
    action: Optional[Action]
    g: int


@dataclass
class SearchResult:
    found: bool
    actions: list[Action]
    total_cost: int
    generated: int
    expanded: int
    limit_hit: bool = False


def _reconstruct(node: Node) -> list[Action]:
    plan: list[Action] = []
    while node.parent is not None:
        assert node.action is not None
        plan.append(node.action)
        node = node.parent
    plan.reverse()
    return plan


def ucs(
    initial: State,
    idx: ScenarioIndex,
    goal_stations: frozenset[str],
    max_expansions: int = 200_000,
) -> SearchResult:
    counter = itertools.count()
    root = Node(initial, None, None, 0)
    open_heap: list[tuple[int, int, Node]] = [(0, next(counter), root)]

    # CLOSED: mundo físico SIN batería -> mejor batería con la que ya se
    # expandió ese mundo. Es la dominancia de design.md: si dos caminos
    # llegan al mismo mundo y uno trae más batería a costo menor o igual
    # (UCS extrae en orden no decreciente de g), el otro está dominado.
    closed: dict[tuple, int] = {}

    generated = 1
    expanded = 0

    while open_heap:
        g, _, node = heapq.heappop(open_heap)

        # Prueba de meta AL EXTRAER, no al generar — condición de
        # optimalidad de UCS (design.md, "Estrategia de búsqueda").
        if goal_stations <= node.state.stations_online:
            return SearchResult(True, _reconstruct(node), g, generated, expanded)

        world_key = node.state.world_key()
        best_battery = closed.get(world_key)
        if best_battery is not None and best_battery >= node.state.battery:
            # Dominado: mismo mundo, batería igual o menor, costo mayor o
            # igual. Se descarta sin expandir. heapq no soporta
            # decrease-key, así que esto logra el mismo efecto que el
            # "parent discarding" descrito en design.md pero aplicado de
            # forma perezosa al extraer, en vez de al insertar.
            continue
        closed[world_key] = node.state.battery

        expanded += 1
        if expanded > max_expansions:
            return SearchResult(False, [], 0, generated, expanded, limit_hit=True)

        for action in generate(node.state, idx):
            child_state = result(action, node.state, idx)
            # Poda temprana: si CLOSED ya cerró este mismo mundo con
            # batería igual o mayor, este hijo está dominado y nunca se
            # expandirá (se descartaría al extraerlo igual). No encolarlo
            # ahorra memoria y trabajo del heap en un espacio con muchas
            # variantes de batería para el mismo mundo físico.
            child_best = closed.get(child_state.world_key())
            if child_best is not None and child_best >= child_state.battery:
                generated += 1
                continue
            g2 = g + cost(action, idx)
            generated += 1
            heapq.heappush(open_heap, (g2, next(counter), Node(child_state, node, action, g2)))

    return SearchResult(False, [], 0, generated, expanded)
