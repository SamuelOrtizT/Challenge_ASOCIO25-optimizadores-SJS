# para ejecutar este código se debe instalar la libreria pyomo:
# en VSC, arriba a la izquierda seleccionar terminal --> new terminal
# y escribir pip install pyomo. Ejecutar al finalizar la descarga

import json
import os
from pyomo.environ import *

text1 = "Ingrese el número del JSON que desea usar: "
text2 = "Ingrese el peso que desea darle a que los empleados asistan en sus días preferidos: "
text3 = "Ingrese el peso que desea darle a que los empleados usen el mismo escritorio todos los días que haga presencialidad: "
text4 = "Ingrese el tiempo límite en segundos para que el solver intente encontrar la mejor solución: "
num_instance = int(input(text1))
peso_dia_preferido = float(input(text2).replace(",", "."))
peso_mismo_escritorio = float(input(text3).replace(",", "."))
tiempo_limite = int(float((input(text4).replace(",", "."))))

#leer el json con los datos
ruta_json = os.path.join(".", "data", f"instance{num_instance}.json")
with open(ruta_json, 'r') as archivo:
    datos = json.load(archivo)

empleados = datos["Employees"]
escritorios = datos["Desks"]
dias = datos["Days"]
grupos = datos["Groups"]
zonas = datos["Zones"]
escritoriosXzonas = dict(datos["Desks_Z"].items())
escritoriosXempleados = dict(datos['Desks_E'].items())
gruposXempleados = dict(datos["Employees_G"].items())
empleadosXdias = dict(datos['Days_E'].items())

#Inicializar modelo
M = -99999
model = ConcreteModel()
model.I = RangeSet(0, len(empleados) - 1)
model.J = RangeSet(0, len(escritorios) - 1)
model.K = Set(initialize=dias)
model.x = Var(model.I, model.J, model.K, within=Binary)
model.y = Var([(i, j) for i in model.I for j in model.J if f"D{j}" in escritoriosXempleados[f"E{i}"]], domain=Binary)

#Llenar diccionario con el peso de cada variable de decisión
C = {
    (int(empleado[1:]), int(escritorio[1:]), dia): (
        peso_dia_preferido if escritorio in escritoriosXempleados[empleado] and dia in empleadosXdias[empleado]
        else 1 if escritorio in escritoriosXempleados[empleado]
        else M
    )
    for empleado in empleados
    for escritorio in escritorios
    for dia in dias
}

#definir función objetivo
def funcion_objetivo(m):
    asignacion = sum(C[(i, j, k)] * m.x[i, j, k] for i in m.I for j in m.J for k in m.K)
    consistencia_escritorios = sum(m.y[i, j] for (i, j) in m.y.index_set())
    return asignacion - peso_mismo_escritorio * consistencia_escritorios

model.obj = Objective(rule=funcion_objetivo, sense=maximize)

#restricciones
def un_escritorio_por_dia(m, i, k):
    return sum(m.x[i, j, k] for j in m.J) <= 1

def un_empleado_por_escritorio(m, j, k):
    return sum(m.x[i, j, k] for i in m.I) <= 1

def dias_trabajados_por_empleado(m, i):
    return inequality(2, sum(m.x[i, j, k] for j in m.J for k in m.K), 3)

# Relación entre x e y: si x[i,j,k] = 1 en algún k → y[i,j] = 1
def activar_y(m, i, j, k):
    if (i, j) in m.y.index_set():
        return m.x[i, j, k] <= m.y[i, j]
    return Constraint.Skip

model.restriccion_activar_y = Constraint(model.I, model.J, model.K, rule=activar_y)
model.restriccion_asignacion = Constraint(model.I, model.K, rule=un_escritorio_por_dia)
model.restriccion_ocupacion = Constraint(model.J, model.K, rule=un_empleado_por_escritorio)
model.restriccion_dias_min_max = Constraint(model.I, rule=dias_trabajados_por_empleado)


# Resolver con glpk
glpsol_path = os.path.join(os.path.dirname(__file__), "solvers", "glpsol.exe")  # Ruta al ejecutable dentro del proyecto

solver = SolverFactory("glpk", executable=glpsol_path)
result = solver.solve(model, tee=False, options={'tmlim': tiempo_limite})

print(f"Estado de la solución: {result.solver.status}")
print(f"Resultado objetivo: {value(model.obj)}")

# Mostrar asignaciones
for i in model.I:
    for j in model.J:
        for k in model.K:
            if value(model.x[i, j, k]) == 1:
                print(f"Empleado E{i} asignado al escritorio D{j} el día {k}")
