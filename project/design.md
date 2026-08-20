# Diseño del agente

Este documento debe completarse **antes** de la implementación principal del agente.

Use sus propias palabras y notación. No reemplace este archivo por una transcripción
del enunciado. Las subsecciones existen para que no se le olvide una decisión;
usted decide el contenido.

El entorno, según las propiedades vistas en clase, es totalmente observable,
determinista, secuencial, estático, discreto y de agente único. Bajo esas
condiciones la solución es un **plan completo** y el marco correcto es la
búsqueda clásica. Justifique cada componente con ese marco (AIMA, cap. 3).

- Antes de nada quiero entender y dejar en claro el marco en el que voy a trabajar y cómo va a funcionar el mundo, porque de ahí sale todo lo demás. El entorno es totalmente observable porque recibo el escenario completo y no hay nada oculto, es determinista porque cada acción legal produce exactamente un sucesor, no hay azar ni fallos, es secuencial porque recoger la herramienta equivocada me gasta capacidad y batería y condiciona todo lo que venga después. También se puede decir que el mundo es estático porque solo cambia cuando yo actúo, es discreto porque las zonas, los objetos y la batería son conjuntos finitos, y es de agente único porque nadie más toca el mundo. Como se cumplen las cuatro suposiciones de la búsqueda clásica (observable, determinista, conocido y estático), la solución es un plan completo, una secuencia fija de acciones que calculo antes de mover cualquier cosa.

---

## Estado

### Definición formal

Escriba la tupla de estado. Cada componente debe ser una variable que el robot
necesita para saber qué podrá hacer después.

```text
s = ⟨ z, b, K, T, M, D, P, S ⟩
```

* z: representa la zona en la que está el robot. 
* b: representa la batería restante del robot. 
* K: representa la localización de cada llave (una zona, o el propio robot si la lleva encima).
* T: representa la localización de cada herramienta. Mismo dominio que K.
* M: representa la cantidad de cada tipo de material en cada localización.
* D: representa el conjunto de puertas abiertas.
* P: representa el conjunto de paneles reparados.
* S: representa el conjunto de estaciones online.

- No usé una variable de carga aparte, puesto que puedo usar al robot como localización.

### Por qué cada variable es necesaria

Criterio de clase (`Applicable`): una variable pertenece al estado **si y solo si**
dos configuraciones que difieran en ella pueden diferir en las acciones legales
futuras o en su resultado.

Pase ese filtro con cada variable. En particular:

- La **batería** forma parte de la situación física (§2.1 del enunciado).
- La **posición de los objetos** no se deduce del escenario inicial si el robot
  puede soltarlos (`DROP`).
- Los cambios permanentes (puertas, paneles, estaciones) condicionan el futuro.
- La zona **z** es fundamental ya que todas las acciones, excluyendo `DROP`, tienen una precondición de zona. Es fundamental para hacer las acciones: no puedo estar en z = Z1 y reparar un panel en Z4. Y aunque `DROP` no tenga precondición de zona, su resultado sí depende de ella, porque el objeto queda tirado justo donde estoy.
- La batería **b** es fundamental ya que todas las acciones requieren de batería, además de que esta abre muchos caminos indicando si son legales o no dependiendo de su estado y de si es posible recargar o no.
- La localización de cada llave **K** es importante porque su posición determina dónde puedo recogerla y, a su vez, necesito la llave (tenerla en mi inventario en ese momento) para abrir una puerta.
- **T** es necesaria porque REPAIR exige que la herramienta del panel esté en la carga en ese momento, y porque si la solté en otra zona, el PICKUP para recuperarla solo es legal allí.
- **M** exige tener material y lo consume, o sea que el conteo baja y puede llegar a 0, lo cual haría imposible la reparación.
- **D** es importante para la movilidad del robot, un corredor con una puerta cerrada es inaccesible.
- **P** es importante porque no se pueden activar estaciones si no se han reparado los paneles. También sirve para distinguir por qué un panel puede estar reparado sin que su estación esté activada todavía: reparar y activar son dos acciones distintas, y el agente tiene que saberlo para hacer un movimiento legal.
- **S** es importante porque una estación puede requerir que otra esté ONLINE, y es literalmente la meta.

### Qué información se deriva y NO se almacena

Peso de la carga, grafo de corredores, costos, capacidad, batería máxima, etc.
Si se puede calcular a partir del estado y de las constantes del escenario, no
es una variable de estado.

- Aquí hay que identificar qué son constantes y qué datos son derivables de información que conoce el agente por su estado.
- El grafo de corredores y la puerta de cada corredor son constantes del escenario y no cambian a lo largo de la búsqueda.
- La batería máxima, la capacidad de carga, los pesos y el costo de cada acción también son constantes.
- Los requires de paneles y estaciones y el goal son constantes: las reglas no van a cambiar durante la búsqueda.
- El contenido de la carga, el peso de la carga, si puedo recargar aquí y las estaciones que me faltan son todos derivables del estado más las constantes.
- El layout completo celdas y eso.
- La energía gastada no es una variable de estado porque no afecta la legalidad de las acciones ni el objetivo final, solo es un acumulador de historial.

### Qué pertenece al historial de búsqueda y no al estado físico

`g(n)`, el padre y la acción que trajo aquí describen *cómo llegó*, no *dónde
está*. Viven en el **Nodo**. Si se meten en el estado, CLOSED no puede reconocer
la misma situación física alcanzada por dos rutas.

- Complementando la afirmación de arriba diría que sí: `g(n)`, `parent`, `action`, `depth` y `energy_spent` describen la forma en cómo llegué, no cómo está el mundo. Todo eso vive en el Nodo, y varios nodos distintos pueden apuntar al mismo estado.

- El ejemplo más claro es este: estando en Z2, si hago PICKUP FUSE y luego PICKUP CHIP, o al revés, PICKUP CHIP y luego PICKUP FUSE, llego exactamente al mismo estado físico. Misma zona, misma carga, misma batería (gasté 1+1 en los dos casos), todo igual. Lo único que cambia es la historia. Si el orden en que recogí las cosas acabara dentro del estado, serían dos estados distintos y CLOSED no reconocería que es el mismo mundo.

### Cuándo dos configuraciones son el mismo estado

Materiales equivalentes por tipo (§2.2): no les ponga ids artificiales.
Estructuras canónicas (conjuntos, contadores) para que `==` y el hash coincidan
con la equivalencia física. Sin eso Graph Search explota.

- Dos estados son iguales cuando describen el mismo mundo. Para que Python lo vea igual que yo, cada mundo tiene que tener una sola escritura posible: los materiales por tipo y cantidad (no por id), la carga derivada de un mapa objeto→sitio (no una lista con orden), y conjuntos inmutables para lo que ya cambió.

### Relevancia: objetos que ya no cambian el futuro

Los cambios del entorno son **monótonos** (una puerta abierta no se cierra).
Pregúntese: una llave cuya puerta ya está abierta, o una herramienta cuyo panel
ya está reparado, ¿sigue distinguiendo estados si solo cambia dónde está en
el suelo? Si no habilita ninguna acción futura, incluirla multiplica el espacio
con permutaciones de objetos muertos. Justifique si las ignora y por qué eso
no pierde el óptimo.

- El mundo es monótono, es decir, las puertas no se cierran ni los paneles se rompen, es por eso que un objeto puede volverse inútil de forma permanente. Una llave cuyas puertas están todas abiertas nunca vuelve a servir, porque OPEN_DOOR exige que la puerta esté cerrada y eso ya no puede volver a pasar. 

- Lo mismo pasa con una herramienta cuyo panel ya fue reparado. También hay que decir que cuando un objeto muere, dejo de rastrear en qué zona quedó y lo colapso a un solo valor (⊥), salvo si está en la carga: ahí sigue ocupando peso y por tanto sigue cambiando qué puedo recoger, así que lo dejo como ROBOT y el robot tiene que pagar un DROP si quiere deshacerse de él. No pierdo el óptimo porque cualquier plan que recoja un objeto muerto se puede acortar borrando ese paso.

---

## Acciones

Defina las acciones **internas** del agente (nombres libres). Para cada una:
precondiciones, efectos, costo. Toda acción del mundo exige además
`batería ≥ costo`.

Puede usar una tabla:


| Acción | Precondiciones | Efectos | Costo |
|---|---|---|---|
| **`MOVE`**<br>*caminar a la zona de al lado* | Hay un corredor que va de donde estoy a la zona destino (solo zonas vecinas, un salto a la vez), y si ese corredor tiene puerta, la puerta ya está abierta. | El robot pasa a la zona destino, con lo que lleve encima. Todo lo demás queda igual. | Lo que valga el corredor. **El precio no depende de lo que cargue.** |
| **`PICKUP`**<br>*recoger algo del suelo* | El objeto está tirado **en mi zona** (no se recoge a distancia) y me cabe: lo que ya llevo más el objeto no pasa de mi capacidad. | El objeto pasa del suelo a la carga. Si es material, la pila de ese tipo baja en uno (y desaparece si llega a cero). | `action_costs.pickup`, igual para todo. |
| **`DROP`**<br>*dejar algo en el suelo* | El objeto está encima del robot. **Y ya está**: ninguna otra restricción. | El objeto pasa de la carga al suelo de mi zona, y puede recogerse después. Los materiales se suman a la pila que hubiera. | `action_costs.drop`. |
| **`OPEN_DOOR`**<br>*abrir una puerta* | Estoy en **una de las dos zonas** que conecta (da igual cuál), la puerta está cerrada, y tengo la llave **encima en ese momento** — no basta haberla tenido antes ni que esté tirada ahí. | La puerta queda abierta **para siempre**; el corredor queda libre para todos los `MOVE` futuros. La llave **no se gasta**. | `action_costs.interact`. |
| **`REPAIR`**<br>*arreglar un panel* | Estoy en la zona del panel, sigue dañado, y llevo **a la vez** su herramienta **y** su material. El material declarado debe ser exactamente el que pide. | El panel queda reparado, permanentemente. **El material se destruye**; **la herramienta no se gasta** y sirve para otros paneles. | `action_costs.interact`. |
| **`ACTIVATE`**<br>*encender una estación* | Estoy en su zona, está apagada, **todos** sus paneles ya están reparados y **todas** las estaciones de las que depende ya están encendidas. | La estación queda encendida, permanentemente. No consume nada ni requiere llevar nada. | `action_costs.interact`. |
| **`RECHARGE`**<br>*recargar la batería* | Hay cargador en mi zona, la batería **no** está llena (recargar al máximo es ilegal), y me alcanza para pagar la propia recarga. | La batería sube al máximo. Nada más. | `action_costs.recharge`, **pagado antes** de recargar. |




### `Applicable` interno vs legalidad del contrato

El simulador dice cuándo un paso es **legal**. Su generador de sucesores dice
qué acciones son **relevantes para buscar**. No tienen que ser el mismo conjunto.

El contrato **permite** `DROP` en cualquier zona si el objeto está en la carga.
Si su agente genera ese `DROP` en cada estado con carga, el espacio deja de ser
«5 zonas y unas tareas» y pasa a ser «en cuál de las 5 zonas quedó cada objeto».
Eso no se arregla cambiando `cargo_capacity` ni apagando la batería: el escenario
es la fuente de verdad y el profesor probará otras instancias.

Usted puede (y se espera que) restrinja `DROP` —y cualquier otra acción— a los
casos que un plan **óptimo** podría necesitar. Justifique que ningún plan de
costo mínimo usa una acción que usted dejó de generar.

- El contrato me deja soltar en cualquier sitio, pero yo genero DROP solo cuando tengo delante un objeto que necesito y no me cabe. El argumento es que el MOVE cuesta lo mismo vaya cargado o vacío, así que llevar cosas es gratis; si es gratis, soltar solo sirve para hacer hueco; y hacer hueco solo hace falta en el PICKUP. Como soltar cuesta igual ahora que después, retrasar cada DROP hasta ese momento da un plan del mismo precio así que el óptimo sigue estando en mi espacio. Sin esa restricción, el problema deja de ser "cinco zonas y tres estaciones" y pasa a ser "dónde quedó cada uno de los diez objetos": sesenta millones de repartos.

- Restrinjo también las demás acciones, con el mismo tipo de argumento: no recojo objetos que ya no sirven, no cargo más unidades de un material de las que quedan por consumir, no reparo paneles que ninguna estación pendiente necesita y no activo estaciones que no están en la meta ni son prerrequisito de una que sí lo esté. En todos los casos, si un plan hiciera eso, borro ese paso y me queda un plan legal de costo menor o igual.


- Y hay una poda que no hice que fue limitar RECHARGE a solo si la batería baja de cierto umbral. Es tentador, pero no es sound: el umbral correcto depende del resto del plan, y me devolvería FAILURE en misiones que sí tenían solución.

---

## Modelo de transición

```text
s  --a-->  s'     solo si a ∈ Applicable(s)
```

`Result` es determinista y parcial. Qué puede cambiar: zona, carga/suelo,
batería, entorno persistente. Qué se preserva. Si canonicaliza el estado tras
una acción, dígalo aquí.

- Result(s, a) es determinista (una acción, un único sucesor, por eso puedo planificar el plan entero offline) y parcial: solo está definida si a ∈ Applicable(s), así que evalúo las precondiciones antes, nunca capturo excepciones. Cambian la zona (solo MOVE), la batería (todas), la posición de los objetos (PICKUP/DROP, y REPAIR que destruye el material pero no la herramienta) y los conjuntos persistentes de puertas, paneles y estaciones, que solo crecen. Se preservan las constantes del escenario y el hecho de que cada objeto está en exactamente un sitio. Y sí: Result devuelve el estado ya canonicalizado (conteos en cero eliminados, M ordenada, objetos muertos colapsados) porque hacerlo al construir cuesta una vez por sucesor y hacerlo al comparar costaría una vez por consulta a CLOSED.

---

## Prueba de meta

```text
Goal(s) ⟺ goal.stations_online ⊆ S
```

La misión se verifica sobre el **estado final del mundo**, no sobre haber
ejecutado una lista de tareas. ¿Las puertas y los paneles son parte de la meta
o solo medios?

- Como no llevo una lista de cosas que tengo que hacer, sino más bien veo el estado y me pregunto si ya alcancé la meta, Goal(s) es cierto cuando todas las estaciones de la lista están en el conjunto S del estado. Se evalúa sobre el mundo, no sobre el camino, como ya había comentado antes; las puertas y los paneles no son parte de la meta, son un medio: un plan que abra todo y repare todo pero no encienda las estaciones no me sirve de nada, en cambio un plan que deje todas las puertas cerradas y encienda las estaciones sí.

---

## Función de costo

```text
g(n) = suma de los costos oficiales de todas las acciones del camino desde s₀ hasta n
```

Debe ser la suma de los **costos oficiales** del escenario (no el número de
pasos). Explique por qué minimizar pasos no es lo mismo que minimizar costo
en este mundo (hay corredores baratos y caros).

- g(n) es la suma de los costos oficiales del escenario a lo largo del camino: el cost de cada corredor para los MOVE, y los action_costs para el resto. Representa la energía que gasta el robot, que es la medida de rendimiento de la misión. Minimizar pasos no es lo mismo que minimizar costo, porque los corredores valen entre 3 y 12 mientras las acciones valen entre 1 y 3: en el propio demo, y suponiendo DOOR1 ya abierta, ir de Z4 a Z5 en 5 acciones cuesta 16 (bajar a Z3 por KEY3, volver, abrir DOOR3 y cruzar) y hacerlo en 3 acciones cuesta 24 (dar la vuelta por Z1 y Z2). BFS elegiría el de 3 y gastaría un 50% más. Por eso hace falta UCS, que ordena por costo acumulado y no por profundidad. Y g es aditivo y no negativo —de hecho en esta instancia todos los costos son ≥ 1, que es la condición ε > 0 del teorema—, que es justo lo que hace válida la optimalidad de UCS.

---

## Estrategia de búsqueda

Elija una estrategia **vista en clase** y justifíquela con las propiedades
reales del problema (costos heterogéneos, plan de menor costo, espacio finito).

Discuta:

- completitud
- optimalidad (¿la prueba de meta se hace al extraer o al generar?)
- costo de camino
- tiempo y espacio (el `b` peligroso no es el grado del mapa: es cuántos
  `DROP`/`PICKUP` genera por estado)
- cuándo se rompen las garantías (costos 0 o negativos, estados mal
  canonicalizados, OPEN que no se vacía)

Graph Search exige una lista CLOSED sobre estados **canónicos**. Explique cómo
evita reexplorar la misma situación física.

- El elemento más importante y en el cual baso mi decisión es que los costos de este mundo no son uniformes, hay corredores de 3 a 12 frente a acciones de 1 a 3, y se pide explícitamente el plan de menor costo; es por eso que elijo UCS con Graph Search. Descarto BFS e IDS, que solo son óptimos si todos los pasos cuestan igual, y descarto DFS, que aunque es completo en Graph Search no garantiza optimalidad. Lo que distingue a UCS es la estructura de OPEN: una cola de prioridad ordenada por g(n), así que expande anillos concéntricos de costo en vez de profundidad.

- Es completo porque el espacio de estados es finito y CLOSED impide reexpandir, y óptimo porque los costos son no negativos —en esta instancia todos ≥ 1, que es la condición ε > 0 del teorema— y porque respeto los dos conceptos críticos de UCS: la prueba de meta al extraer, no al generar (si la hiciera al generar podría devolver un camino de 90 mientras uno de 78 sigue esperando en la cola), y el parent discarding: cuando genero un sucesor a un estado que ya está en OPEN con un g mayor, no lo ignoro, lo reemplazo por la versión más barata.

- Su punto débil es el espacio, y por eso lo que de verdad importa es quién es b: el factor de ramificación peligroso no es el grado del mapa, que es 2 o 3, sino cuántos DROP y PICKUP genero por estado. Con un Applicable ingenuo b se me va por encima de 10 (es lo de soltar objetos en sitios donde no hay nada que recoger) y el árbol se vuelve inmanejable; con las restricciones justificadas espero un b del orden de 5. Voy a instrumentar el solver con un contador de nodos generados y expandidos y con el tiempo de búsqueda, y a devolverlos en el campo `message`, para poder enseñar el número medido y no solo la predicción. Y CLOSED guarda estados canónicos, no nodos: es lo único que impide que el ciclo Z1→Z4→Z1 genere nodos para siempre.

- Las garantías se rompen en cuatro casos. Con costos negativos se pierde la optimalidad, porque un camino ya cerrado podría abaratarse después; el contrato los prohíbe. Con costos 0 en ciclos el orden de extracción se vuelve arbitrario, aunque con CLOSED y espacio finito sigue terminando. Si pruebo la meta al generar en vez de al extraer, devuelvo el primer camino que llega y no el más barato. Y el fallo real de este parcial es tener estados mal canonicalizados: si el mismo mundo físico produce dos tuplas distintas, CLOSED no lo detecta, Graph Search degenera en Tree Search y con ciclos no termina. Si veo que OPEN no se vacía, ese es el síntoma — la causa está en Applicable o en la canonicalización, nunca en el algoritmo.

### Batería como recurso

La batería **sí** va en el estado (§2.1). Eso no implica explorar todos los
paseos que solo gastan energía. Si dos caminos llegan a la **misma**
configuración del mundo (zona, carga, suelo, entorno) y uno trae **más batería
residual** a un **costo menor o igual**, el otro no puede mejorar ningún plan
futuro: está dominado. Tratar cada nivel de batería como un mundo distinto,
sin esa observación, hace que UCS recorra detours inútiles hasta agotar
memoria. Justifique cómo CLOSED aprovecha (o no) esta dominancia.

- La batería va en el estado porque cambia qué acciones son legales: con 2 no cruzo un corredor de 4, y con la batería llena RECHARGE es ilegal. El problema es que multiplica el espacio por todos los valores que pueda tener la batería y hace que UCS explore paseos que solo queman energía. Lo resuelvo con dominancia: si dos caminos llegan al mismo mundo y uno trae más batería habiendo gastado menos, el otro no puede ganar en ninguna circunstancia y se descarta. En CLOSED la llave es el mundo sin la batería, y guardo la mejor batería con la que ya expandí ese mundo; como UCS extrae en orden de costo creciente, con eso basta. En esta instancia eso colapsa los 101 niveles de batería a uno o dos por mundo. El único caso delicado es RECHARGE, que exige batería no llena: tener más batería puede hacer una acción ilegal. No rompe la dominancia porque, si ya estoy lleno, no necesito recargar; basta con omitir ese paso del plan, que además lo abarata.

---

## Formulación y tamaño del espacio (obligatorio)

El mapa visible es pequeño. El espacio de estados **no** lo es, si se formula
mal. Responda con sus palabras:

1. ¿Por qué «5 zonas, ~10 objetos, capacidad 3» puede generar millones de nodos
   en un UCS ingenuo?
2. ¿Qué papel tiene `DROP` en esa explosión?
3. ¿Qué podas o abstracciones aplicó y por qué **no pierden el óptimo**
   (*sound*)?
4. ¿Por qué **no** es solución subir la capacidad, bajar las estaciones o
   ignorar la batería?

---

1. Porque el espacio de estados no es el mapa, es una multiplicación: un estado no es la posición del robot, es todo el mundo a la vez, y cada variable multiplica a las demás.  Y la culpa está muy concentrada: las posiciones de los objetos aportan un factor de unos 35 millones y la batería un factor de 101, mientras que el robot, las puertas, los paneles y las estaciones juntos aportan apenas 2560. O sea que casi todo el espacio son las posiciones de los objetos y la batería, que no por casualidad son las dos únicas cosas reversibles de este mundo: todo lo demás solo avanza y nunca retrocede.

2. Como ya lo hemos discutido antes al hablar de Applicable, se debe a que DROP es lo que convierte la posición de los objetos en una variable en lugar de una constante. Si DROP no existiera, cada objeto solo podría estar en dos sitios: donde empezó o lo tiene el robot; pero como bien lo dice el contrato uno lo puede soltar en cualquier lado, lo que genera que UCS los visite de verdad, uno por uno, explorando sistemáticamente todas las formas de repartir la basura por el suelo antes de llegar a la profundidad donde está la solución.

3. Apliqué algunas podas: que solo genero un DROP cuando hay un objeto útil en mi zona que no me cabe es sound porque el costo de MOVE no depende de lo que lleve encima, así que cargar es gratis; otra es que no recojo objetos que ya no sirven, y esto se aplica a otras áreas, como por ejemplo que no reparo ni activo cosas innecesarias, no rastreo objetos muertos y aplico dominancia de batería en CLOSED. Todas comparten la misma forma de argumento: dado cualquier plan óptimo que use la acción que yo no genero, construyo otro plan legal de costo menor o igual que no la usa, luego siempre queda un plan óptimo dentro de mi espacio reducido. Para los objetos inútiles: si un plan recoge algo que nunca usa, borro ese PICKUP; sigue siendo legal porque ninguna precondición exige que un objeto no esté en el suelo, ahorro el costo y libero una ranura.

4. Porque los tres atajos cambian el problema para que quepa en mi solución, en vez de arreglar la solución. Subir la capacidad de carga es el más tentador, ya que no tendría que soltar nada nunca, y así con los demás ejemplos. Además, en la vida real nosotros no podemos cambiar el mundo a nuestro antojo para que quepa en nuestras soluciones, y otra gran razón es porque el profesor lo testeará en entornos retadores y mi solución no funcionaría.
