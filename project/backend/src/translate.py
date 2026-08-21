"""Traduce el plan interno (lista de Action) al formato cerrado de
CONTRATO.md — la capa que separa el modelo interno de IA de la
representación visual (README.MD §5). El agente nunca construye un paso
del contrato en ningún otro lugar."""
from __future__ import annotations

from typing import Any

from actions import Action, cost
from scenario_index import ScenarioIndex


def to_contract(plan: list[Action], idx: ScenarioIndex) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for a in plan:
        c = cost(a, idx)
        if a.kind == "MOVE":
            steps.append({"op": "MOVE", "from": a.frm, "to": a.to, "cost": c})
        elif a.kind == "PICKUP":
            steps.append({"op": "PICKUP", "item": a.item, "cost": c})
        elif a.kind == "DROP":
            steps.append({"op": "DROP", "item": a.item, "cost": c})
        elif a.kind == "OPEN_DOOR":
            steps.append({"op": "INTERACT", "target": a.target, "action": "OPEN_DOOR", "cost": c})
        elif a.kind == "REPAIR":
            steps.append(
                {
                    "op": "INTERACT",
                    "target": a.target,
                    "action": "REPAIR",
                    "consumes": a.consumes,
                    "cost": c,
                }
            )
        elif a.kind == "ACTIVATE":
            steps.append({"op": "INTERACT", "target": a.target, "action": "ACTIVATE", "cost": c})
        elif a.kind == "RECHARGE":
            steps.append({"op": "INTERACT", "target": a.target, "action": "RECHARGE", "cost": c})
        else:
            raise ValueError(f"Unknown action kind: {a.kind}")
    return steps
