"""Constantes derivadas del escenario — lo que design.md llama "qué se
deriva y NO se almacena": grafo de corredores, costos oficiales, pesos,
capacidad, batería máxima y qué paneles/estaciones hacen falta para la
meta. Nada de esto cambia entre estados, así que vive aquí, no en `State`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScenarioIndex:
    battery_max: int
    cargo_capacity: int

    corridors_from: dict[str, tuple[dict[str, Any], ...]]
    corridor_cost: dict[tuple[str, str], int]

    doors: dict[str, dict[str, Any]]
    key_to_door: dict[str, str]

    key_weight: dict[str, int]
    tool_weight: dict[str, int]
    material_weight: dict[str, int]

    panels: dict[str, dict[str, Any]]
    stations: dict[str, dict[str, Any]]
    chargers_by_zone: dict[str, str]

    action_costs: dict[str, int]

    goal_stations: frozenset[str]
    needed_stations: frozenset[str]
    needed_panels: frozenset[str]

    @staticmethod
    def build(scenario: dict[str, Any]) -> "ScenarioIndex":
        corridors_from: dict[str, list[dict[str, Any]]] = {}
        corridor_cost: dict[tuple[str, str], int] = {}
        for c in scenario["corridors"]:
            corridors_from.setdefault(c["from"], []).append(c)
            corridor_cost[(c["from"], c["to"])] = int(c["cost"])

        doors = {d["id"]: d for d in scenario["doors"]}
        key_to_door = {d["key"]: d["id"] for d in scenario["doors"]}

        stations = {s["id"]: s for s in scenario["stations"]}
        goal_stations = frozenset(scenario["goal"]["stations_online"])

        # Cierre transitivo de dependencias: qué estaciones hacen falta de
        # verdad para alcanzar la meta (design.md: "no activo estaciones que
        # no están en la meta ni son prerrequisito de una que sí lo esté").
        needed_stations: set[str] = set(goal_stations)
        stack = list(goal_stations)
        while stack:
            sid = stack.pop()
            for pre in stations[sid]["requires"].get("stations_online", []):
                if pre not in needed_stations:
                    needed_stations.add(pre)
                    stack.append(pre)

        panels = {p["id"]: p for p in scenario["panels"]}
        needed_panels = frozenset(
            pid
            for sid in needed_stations
            for pid in stations[sid]["requires"].get("panels_ok", [])
        )

        return ScenarioIndex(
            battery_max=int(scenario["robot"]["battery_max"]),
            cargo_capacity=int(scenario["robot"]["cargo_capacity"]),
            corridors_from={k: tuple(v) for k, v in corridors_from.items()},
            corridor_cost=corridor_cost,
            doors=doors,
            key_to_door=key_to_door,
            key_weight={k["id"]: int(k["weight"]) for k in scenario["keys"]},
            tool_weight={t["id"]: int(t["weight"]) for t in scenario["tools"]},
            material_weight={m["type"]: int(m["weight"]) for m in scenario["materials"]},
            panels=panels,
            stations=stations,
            chargers_by_zone={c["zone"]: c["id"] for c in scenario["chargers"]},
            action_costs={k: int(v) for k, v in scenario["action_costs"].items()},
            goal_stations=goal_stations,
            needed_stations=frozenset(needed_stations),
            needed_panels=needed_panels,
        )

    def is_key_relevant(self, key_id: str, state: "Any") -> bool:
        """Una llave cuya puerta ya está OPEN nunca vuelve a servir
        (design.md, "Relevancia: objetos que ya no cambian el futuro")."""
        door_id = self.key_to_door.get(key_id)
        return door_id is not None and door_id not in state.doors_open

    def is_tool_relevant(self, tool_id: str, state: "Any") -> bool:
        """Relevante si algún panel que todavía hace falta reparar la
        necesita (design.md: "T es necesaria porque REPAIR exige...")."""
        return any(
            pid not in state.panels_ok and self.panels[pid]["requires"]["tool"] == tool_id
            for pid in self.needed_panels
        )

    def is_material_relevant(self, material_type: str, state: "Any") -> bool:
        """Relevante si aún faltan más unidades de este tipo en el payload
        de las que los paneles pendientes van a consumir (design.md: "M
        exige tener material... puede llegar a 0"). Sin el conteo, el
        agente recogería unidades sobrantes del mismo tipo sin necesidad
        (ej. la segunda FUSE cuando solo un panel la requiere), inflando el
        espacio de estados sin ningún beneficio."""
        remaining_need = sum(
            1
            for pid in self.needed_panels
            if pid not in state.panels_ok and self.panels[pid]["requires"]["material"] == material_type
        )
        return state.carried_material_count(material_type) < remaining_need

    def infeasible_reason(self, state: "Any") -> "str | None":
        """Condición **necesaria** de solubilidad, comprobada antes de buscar.

        Los materiales se consumen al reparar y nunca se crean; las
        herramientas no se gastan pero tampoco aparecen de la nada. Así que
        si un panel imprescindible exige una herramienta que no existe en el
        mundo, o si quedan menos unidades de un material de las que los
        paneles pendientes van a consumir, ningún plan puede repararlos: la
        meta es inalcanzable y sobra registrar la búsqueda.

        Es sound porque solo descarta instancias donde la meta es imposible
        con certeza — nunca puede rechazar una instancia resoluble. Sirve
        para que el agente distinga "demostré que no hay solución" de "me
        quedé sin presupuesto de nodos", que es lo que exige README.MD §6,
        Caso 4.
        """
        tools_available = {tool_id for tool_id, _loc in state.tools}
        pending = [pid for pid in self.needed_panels if pid not in state.panels_ok]

        needed_material_units: dict[str, int] = {}
        for pid in pending:
            requires = self.panels[pid]["requires"]
            if requires["tool"] not in tools_available:
                return (
                    f"el panel {pid} exige la herramienta {requires['tool']}, "
                    "que no existe en el escenario"
                )
            mat = requires["material"]
            needed_material_units[mat] = needed_material_units.get(mat, 0) + 1

        for mat, needed in needed_material_units.items():
            available = sum(c for t, _loc, c in state.materials if t == mat)
            if available < needed:
                return (
                    f"quedan {available} unidades de {mat} y los paneles pendientes "
                    f"consumen {needed}"
                )
        return None

    def is_material_payload_dead(self, material_type: str, state: "Any") -> bool:
        """Un material que ya lleva encima y que ningún panel pendiente
        consume: soltarlo no le quita nada al plan."""
        return not any(
            pid not in state.panels_ok and self.panels[pid]["requires"]["material"] == material_type
            for pid in self.needed_panels
        )
