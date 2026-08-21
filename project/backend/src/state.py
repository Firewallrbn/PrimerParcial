"""Representación canónica del estado físico del robot y el mundo.

s = ⟨ z, b, K, T, M, D, P, S ⟩ (ver design.md, sección "Estado").

K, T y M son funciones «objeto → localización», donde una localización es
una zona **o el propio robot** (constante ROBOT). Por eso no hay una
variable de carga aparte: llevar algo encima es, literalmente, que su
localización sea el robot — tal como se justifica en design.md.

Todos los campos usan frozenset, nunca listas: dos estados que describen el
mismo mundo físico deben ser == y tener el mismo hash sin importar el orden
en que se llegó a ellos (Caso 1 de validación, README.MD §6). Al ser un
dataclass congelado sobre solo tipos hashables e inmutables, la igualdad y
el hash de Python ya hacen ese trabajo.

`g(n)`, el padre y la acción que trajo aquí NO viven aquí — eso es
historial de búsqueda y pertenece al Nodo (ver search.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Localización especial: "encima del robot". Cualquier otra localización es
#: un id de zona del escenario.
ROBOT = "ROBOT"


@dataclass(frozen=True)
class State:
    zone: str
    battery: int

    keys: frozenset[tuple[str, str]]  # (key_id, loc)
    tools: frozenset[tuple[str, str]]  # (tool_id, loc)
    materials: frozenset[tuple[str, str, int]]  # (type, loc, count>0)

    doors_open: frozenset[str]
    panels_ok: frozenset[str]
    stations_online: frozenset[str]

    def carries_key(self, key_id: str) -> bool:
        return (key_id, ROBOT) in self.keys

    def carries_tool(self, tool_id: str) -> bool:
        return (tool_id, ROBOT) in self.tools

    def carried_material_count(self, material_type: str) -> int:
        return next(
            (c for t, loc, c in self.materials if t == material_type and loc == ROBOT),
            0,
        )

    def world_key(self) -> tuple[Any, ...]:
        """Identidad física del mundo SIN la batería.

        Es la clave de CLOSED que permite la dominancia de batería descrita
        en design.md ("Batería como recurso"): dos nodos con este mismo
        world_key describen el mismo mundo salvo el nivel de energía.
        """
        return (
            self.zone,
            self.keys,
            self.tools,
            self.materials,
            self.doors_open,
            self.panels_ok,
            self.stations_online,
        )


def initial_state(scenario: dict[str, Any]) -> State:
    for z in scenario["zones"]:
        if z["id"] == ROBOT:
            raise ValueError(
                f"El escenario usa '{ROBOT}' como id de zona, que colisiona con la "
                "localización reservada para la carga del robot."
            )
    return State(
        zone=scenario["robot"]["start"],
        battery=int(scenario["robot"]["battery_start"]),
        keys=frozenset((k["id"], k["zone"]) for k in scenario["keys"]),
        tools=frozenset((t["id"], t["zone"]) for t in scenario["tools"]),
        materials=frozenset(
            (m["type"], m["zone"], int(m["count"]))
            for m in scenario["materials"]
            if int(m["count"]) > 0
        ),
        doors_open=frozenset(d["id"] for d in scenario["doors"] if d["state"] == "OPEN"),
        panels_ok=frozenset(p["id"] for p in scenario["panels"] if p["state"] == "OK"),
        stations_online=frozenset(
            s["id"] for s in scenario["stations"] if s["state"] == "ONLINE"
        ),
    )
