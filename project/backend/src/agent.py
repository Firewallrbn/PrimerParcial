"""Punto de entrada del agente real: state -> UCS -> traducción al contrato.

Reemplaza a demo_plan.build_demo_plan detrás de POST /api/solve. demo_plan.py
se conserva como referencia/comparación de costo (ver tests/test_agent.py).
"""
from __future__ import annotations

import time
from typing import Any

from scenario_index import ScenarioIndex
from search import ucs
from state import initial_state
from translate import to_contract


def solve(scenario: dict[str, Any]) -> dict[str, Any]:
    idx = ScenarioIndex.build(scenario)
    s0 = initial_state(scenario)

    # Condición necesaria de solubilidad: si un panel imprescindible no
    # puede repararse nunca (falta su herramienta o su material), la meta es
    # inalcanzable y se demuestra sin buscar. Evita responder FAILURE por
    # agotar el presupuesto de nodos cuando en realidad hay una razón
    # concreta (README.MD §6, Caso 4).
    blocked = idx.infeasible_reason(s0)
    if blocked is not None:
        return {
            "solution_found": False,
            "total_cost": 0,
            "steps": [],
            "message": f"FAILURE (meta inalcanzable): {blocked}.",
        }

    # TODO(perf): con el escenario demo, UCS necesita ~800k expansiones
    # (~2,5 min) para probar el óptimo — la dominancia de batería no colapsa
    # tanto como se esperaba en design.md. El límite se sube para que el
    # agente SÍ encuentre el plan en vez de fallar por presupuesto; sigue
    # pendiente optimizar el espacio de estados o el tiempo por nodo.
    t0 = time.perf_counter()
    outcome = ucs(s0, idx, idx.goal_stations, max_expansions=1_500_000)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    if not outcome.found:
        reason = "límite de nodos alcanzado" if outcome.limit_hit else "espacio de estados agotado"
        return {
            "solution_found": False,
            "total_cost": 0,
            "steps": [],
            "message": (
                f"FAILURE ({reason}): {outcome.generated} nodos generados, "
                f"{outcome.expanded} expandidos en {elapsed_ms:.1f} ms."
            ),
        }

    steps = to_contract(outcome.actions, idx)
    total = sum(int(s["cost"]) for s in steps)
    return {
        "solution_found": True,
        "total_cost": total,
        "steps": steps,
        "message": (
            f"UCS: {outcome.generated} nodos generados, {outcome.expanded} expandidos, "
            f"{elapsed_ms:.1f} ms, costo {total}."
        ),
    }
