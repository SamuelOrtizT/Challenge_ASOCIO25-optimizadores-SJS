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
empleadosXdias = dict(datos['Days_E'].items())
escritoriosXempleados = dict(datos['Desks_E'].items())

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

def funcion_objetivo(m):
    return sum(C[(i, j, k)] * m.x[i, j, k] for i in m.I for j in m.J for k in m.K)

model.obj = Objective(rule=funcion_objetivo, sense=maximize)
print(check_available_solvers())
"""
# Resolver con glpk
solver = SolverFactory('glpk')
result = solver.solve(model, tee=False)
"""
