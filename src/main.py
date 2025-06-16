# para ejecutar este código se debe instalar la libreria pyomo:
# en VSC, arriba a la izquierda seleccionar terminal --> new terminal
# y escribir pip install pyomo. Ejecutar al finalizar la descarga

import json
import os
from pyomo.environ import *
from pyomo.opt import check_available_solvers

text1 = "Ingrese el número del JSON que desea usar: "
text2 = "Ingrese el peso que desea darle a que los empleados asistan en sus días preferidos: "
num_instance = int(input(text1))
peso_dia_preferido = float(input(text2).replace(",", "."))

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
    return sum(C[(i, j, k)] * m.x[i, j, k] for i in m.I for j in m.J for k in m.K)

model.obj = Objective(rule=funcion_objetivo, sense=maximize)

#restricciones
def un_escritorio_por_dia(m, i, k):
    return sum(m.x[i, j, k] for j in m.J) <= 1
model.restriccion_asignacion = Constraint(model.I, model.K, rule=un_escritorio_por_dia)


# Resolver con glpk
glpsol_path = os.path.join(os.path.dirname(__file__), "solvers", "glpsol.exe")  # Ruta al ejecutable dentro del proyecto

solver = SolverFactory("glpk", executable=glpsol_path)
result = solver.solve(model, tee=False)

print(f"Estado de la solución: {result.solver.status}")
print(f"Resultado objetivo: {value(model.obj)}")

# Mostrar asignaciones
for i in model.I:
    for j in model.J:
        for k in model.K:
            if value(model.x[i, j, k]) == 1:
                print(f"Empleado E{i} asignado al escritorio D{j} el día {k}")
