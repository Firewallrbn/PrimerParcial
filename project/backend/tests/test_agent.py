"""Tests del agente real (UCS): los 5 casos exigidos por README.MD §6,
más una prueba de legalidad de punta a punta contra el simulador de
referencia (el mismo patrón que test_demo_plan.py, pero para el agente que
sí busca)."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from actions import Action, result  # noqa: E402
from agent import solve  # noqa: E402
from demo_plan import build_demo_plan  # noqa: E402
from scenario_index import ScenarioIndex  # noqa: E402
from simulator import goal_satisfied, load_scenario, simulate  # noqa: E402
from state import initial_state  # noqa: E402


# --- Caso 1: estados equivalentes ------------------------------------------------


def test_caso1_pickup_en_distinto_orden_llega_al_mismo_estado() -> None:
    """PICKUP FUSE luego CHIP, o al revés desde el mismo punto, deben
    producir el mismo estado físico (mismo == y mismo hash), aunque las
    historias que los generaron sean distintas."""
    scenario = load_scenario()
    idx = ScenarioIndex.build(scenario)
    s_z2 = replace(initial_state(scenario), zone="Z2")

    pickup_fuse = Action("PICKUP", item="FUSE", item_kind="material")
    pickup_chip = Action("PICKUP", item="CHIP", item_kind="material")

    order_a = result(pickup_chip, result(pickup_fuse, s_z2, idx), idx)
    order_b = result(pickup_fuse, result(pickup_chip, s_z2, idx), idx)

    assert order_a == order_b
    assert hash(order_a) == hash(order_b)


# --- Caso 2: información relevante -----------------------------------------------


def test_caso2_bateria_distinta_es_estado_distinto() -> None:
    """Dos configuraciones iguales en todo salvo la batería son estados
    físicos distintos: `b` sí pertenece a `s` (design.md, §2.1 del
    enunciado)."""
    scenario = load_scenario()
    s0 = initial_state(scenario)
    s_full = replace(s0, battery=50)
    s_low = replace(s0, battery=10)

    assert s_full.world_key() == s_low.world_key()  # mismo mundo físico...
    assert s_full != s_low  # ...pero distinto estado, por la batería.


def test_caso2_zona_distinta_es_estado_distinto() -> None:
    scenario = load_scenario()
    s0 = initial_state(scenario)
    assert replace(s0, zone="Z1") != replace(s0, zone="Z2")


# --- Caso 3: costos diferentes ---------------------------------------------------


def test_caso3_menos_pasos_no_es_menor_costo() -> None:
    """Ejemplo verificado en design.md (sección Función de costo): ir de
    Z4 a Z5 en 5 acciones (bajar a Z3 por KEY3, volver, abrir DOOR3, cruzar)
    cuesta 16; hacerlo en 3 acciones dando la vuelta por Z1/Z2 cuesta 24.
    El plan de menor costo no es el de menos pasos."""
    scenario = load_scenario()
    idx = ScenarioIndex.build(scenario)

    ruta_corta_cara = (
        idx.corridor_cost[("Z4", "Z1")]
        + idx.corridor_cost[("Z1", "Z2")]
        + idx.corridor_cost[("Z2", "Z5")]
    )
    ruta_larga_barata = (
        idx.corridor_cost[("Z4", "Z3")]
        + idx.action_costs["pickup"]
        + idx.corridor_cost[("Z3", "Z4")]
        + idx.action_costs["interact"]
        + idx.corridor_cost[("Z4", "Z5")]
    )

    assert ruta_corta_cara == 24
    assert ruta_larga_barata == 16
    assert ruta_larga_barata < ruta_corta_cara


# --- Caso 4: sin solución ---------------------------------------------------------


def test_caso4_sin_solucion_retorna_failure_sin_colgarse() -> None:
    """Z2 sellada: sin KEY1 la DOOR1 nunca abre, y sin el corredor Z2<->Z5
    (que no tiene puerta) no queda ninguna otra vía de entrada. Todos los
    materiales viven en Z2, así que ningún panel puede repararse y la meta
    es inalcanzable.

    Ojo con el detalle que hace válido este caso: NO basta con quitar KEY1.
    El mapa permite rodear por Z1->Z4->Z3->(KEY3)->Z5->Z2, así que quitar
    solo la llave deja la misión perfectamente resoluble.

    Lo que se exige aquí (README.MD §6, Caso 4) es que el agente termine
    correctamente, no que se rinda: por eso se comprueba que el FAILURE
    viene de haber agotado el espacio de estados y no de haber tocado el
    límite de expansiones, que sería una rendición disfrazada de respuesta.
    """
    scenario = load_scenario()
    scenario["keys"] = [k for k in scenario["keys"] if k["id"] != "KEY1"]
    scenario["corridors"] = [
        c for c in scenario["corridors"] if {c["from"], c["to"]} != {"Z2", "Z5"}
    ]

    response = solve(scenario)

    assert response["solution_found"] is False
    assert response["steps"] == []
    assert response["total_cost"] == 0
    assert "espacio de estados agotado" in response["message"], response["message"]


def test_caso4_material_faltante_se_demuestra_sin_buscar() -> None:
    """Sin CABLE, PANEL_C no puede repararse nunca y ARTILLERY jamás enciende.

    Antes esto devolvía FAILURE solo tras agotar 1,5 millones de nodos
    (~3 min): la respuesta era correcta pero por rendición, no por
    demostración. El precheck de factibilidad lo resuelve al instante y con
    una razón concreta.
    """
    scenario = load_scenario()
    scenario["materials"] = [m for m in scenario["materials"] if m["type"] != "CABLE"]

    response = solve(scenario)

    assert response["solution_found"] is False
    assert response["steps"] == []
    assert "meta inalcanzable" in response["message"], response["message"]
    assert "CABLE" in response["message"], response["message"]


def test_precheck_no_rechaza_el_escenario_resoluble() -> None:
    """El precheck solo puede descartar instancias imposibles: sobre el
    escenario original no debe disparar."""
    scenario = load_scenario()
    idx = ScenarioIndex.build(scenario)
    assert idx.infeasible_reason(initial_state(scenario)) is None


# --- Caso 5: rutas alternativas ----------------------------------------------------


def test_caso5_agente_real_mejora_el_plan_artesanal() -> None:
    """demo_plan.py es legal pero no óptimo (usa el corredor caro Z2<->Z5
    dos veces y recarga sin necesidad — ver project/README.md). Hay más de
    una ruta física hacia la misma meta; el agente real, con UCS, debe
    quedarse con la de menor costo acumulado."""
    scenario = load_scenario()
    demo = build_demo_plan(scenario)
    real = solve(scenario)

    assert real["solution_found"] is True
    assert real["total_cost"] < demo["total_cost"]


# --- Extremo a extremo: legalidad contra el simulador de referencia --------------


def test_agente_real_resuelve_el_escenario_demo_y_es_legal() -> None:
    scenario = load_scenario()
    response = solve(scenario)

    assert response["solution_found"] is True
    assert response["total_cost"] == sum(s["cost"] for s in response["steps"])

    final = simulate(scenario, response["steps"])
    assert goal_satisfied(scenario, final), final["stations"]
    assert final["energy_spent"] == response["total_cost"]


if __name__ == "__main__":
    test_caso1_pickup_en_distinto_orden_llega_al_mismo_estado()
    test_caso2_bateria_distinta_es_estado_distinto()
    test_caso2_zona_distinta_es_estado_distinto()
    test_caso3_menos_pasos_no_es_menor_costo()
    test_caso4_sin_solucion_retorna_failure_sin_colgarse()
    test_caso4_material_faltante_se_demuestra_sin_buscar()
    test_precheck_no_rechaza_el_escenario_resoluble()
    test_caso5_agente_real_mejora_el_plan_artesanal()
    test_agente_real_resuelve_el_escenario_demo_y_es_legal()
    print("All agent tests passed.")
