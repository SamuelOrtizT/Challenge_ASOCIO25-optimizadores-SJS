# para ejecutar este código se debe instalar la libreria pyomo:
# en VSC, arriba a la izquierda seleccionar terminal --> new terminal
# y escribir pip install pyomo. Ejecutar al finalizar la descarga

import json
import os
import time
from pyomo.environ import *

text1 = "Ingrese el número del JSON que desea usar: "
text2 = "Ingrese el peso que desea darle a que los empleados asistan en sus días preferidos: "
text3 = "Ingrese el peso que desea darle a que los empleados usen el mismo escritorio todos los días que haga presencialidad: "
text4 = "Ingrese el peso que desea darle a que los empleados trabajen en el menor número de zonas: "
text5 = "Ingrese el peso que desea darle a que los empleados no queden aislados si el grupo de trabajo se reparte en distintas zonas: "
text6 = "Ingrese el tiempo límite en segundos para que el solver intente encontrar la mejor solución: "
text7 = "Ingrese que tanto puede la solución obtenida desviarse de la solución óptima (número en porcentaje %): "
num_instance = int(input(text1))
peso_dia_preferido = float(input(text2).replace(",", "."))
peso_mismo_escritorio = float(input(text3).replace(",", "."))
peso_zonas = float(input(text4).replace(",", "."))
peso_aislado = float(input(text5).replace(",", "."))
tiempo_limite = int(float((input(text6).replace(",", "."))))
gap = int(float((input(text7).replace(",", "."))))

#leer el json con los datos
ruta_json = os.path.join(".", "data", f"instance{num_instance}.json")
with open(ruta_json, 'r') as archivo:
    datos = json.load(archivo)

empleados = datos["Employees"]
escritorios = datos["Desks"]
dias = datos["Days"]
grupos = datos["Groups"]
zonas = datos["Zones"]
zonasXescritorios = dict(datos["Desks_Z"].items())
escritoriosXempleados = dict(datos['Desks_E'].items())
gruposXempleados = dict(datos["Employees_G"].items())
empleadosXdias = dict(datos['Days_E'].items())
escritorioXzona = {
    esc: zona
    for zona, escritorios in zonasXescritorios.items()
    for esc in escritorios
}

#Inicializar modelo
model = ConcreteModel()
model.I = RangeSet(0, len(empleados) - 1)
model.J = RangeSet(0, len(escritorios) - 1)
model.K = Set(initialize=dias)
model.G = Set(initialize=grupos)
model.x = Var(model.I, model.J, model.K, within=Binary)
model.y = Var([(i, j) for i in model.I for j in model.J if f"D{j}" in escritoriosXempleados[f"E{i}"]], domain=Binary)
model.g = Var(model.G, model.K, domain=Binary)
model.Z = Set(initialize=zonas)
model.z = Var(model.G, model.Z, domain=Binary)
model.miembros_en_zona = Var(model.G, model.Z, within=NonNegativeIntegers)
model.aislado = Var(model.G, model.Z, domain=Binary)

#Llenar diccionario con el peso de cada variable de decisión
C = {
    (int(emp[1:]), int(desk[1:]), day): (
        peso_dia_preferido if desk in escritoriosXempleados[emp] and day in empleadosXdias[emp]
        else 1
    )
    for emp in empleados
    for desk in escritoriosXempleados[emp]  # solo escritorios permitidos
    for day in dias
}
model.idxC = Set(initialize=C.keys())
#definir función objetivo
def funcion_objetivo(m):
    asignacion = sum(C[(i, j, k)] * m.x[i, j, k] for (i, j, k) in m.idxC)
    consistencia_escritorios = sum(m.y[i, j] for (i, j) in m.y.index_set())
    penalizacion_por_zonas = sum(m.z[g, z] for g in m.G for z in m.Z)
    penalizacion_aislamiento = sum(model.aislado[g, z] for g in model.G for z in model.Z)
    return asignacion - peso_mismo_escritorio * consistencia_escritorios - peso_zonas * penalizacion_por_zonas - peso_aislado * penalizacion_aislamiento

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

def un_dia_por_grupo(m, grupo):
    return sum(m.g[grupo, k] for k in m.K) == 1

model.restriccion_grupo_un_dia = Constraint(model.G, rule=un_dia_por_grupo)
model.restriccion_activar_y = Constraint(model.I, model.J, model.K, rule=activar_y)
model.restriccion_asignacion = Constraint(model.I, model.K, rule=un_escritorio_por_dia)
model.restriccion_ocupacion = Constraint(model.J, model.K, rule=un_empleado_por_escritorio)
model.restriccion_dias_min_max = Constraint(model.I, rule=dias_trabajados_por_empleado)
model.restriccion_asistencia_grupal = ConstraintList()
model.restriccion_zona_usada = ConstraintList()
model.restriccion_conteo_miembros = ConstraintList()
model.restriccion_aislamiento = ConstraintList()

for g in model.G:
    for z in model.Z:
        model.restriccion_aislamiento.add(model.miembros_en_zona[g, z] >= model.aislado[g, z])
        model.restriccion_aislamiento.add(model.miembros_en_zona[g, z] <= model.aislado[g, z] + (len(gruposXempleados[g]) - 1)*(1 - model.aislado[g, z]))


for grupo, empleados in gruposXempleados.items():
    for k in model.K:
        for e in empleados:
            i = int(e[1:])  # "E0" → 0
            model.restriccion_asistencia_grupal.add(
                sum(model.x[i, j, k] for j in model.J if f"D{j}" in escritoriosXempleados[f"E{i}"]) >= model.g[grupo, k]
            )

for grupo, empleados in gruposXempleados.items():
    for e in empleados:
        i = int(e[1:])
        escritorios_validos = escritoriosXempleados[f"E{i}"]
        for esc in escritorios_validos:
            j = int(esc[1:])
            zona = escritorioXzona[esc]
            for k in model.K:
                model.restriccion_zona_usada.add(
                    model.x[i, j, k] <= model.z[grupo, zona]
                )

for grupo, empleados in gruposXempleados.items():
    for zona in model.Z:
        sum_terms = []
        for e in empleados:
            i = int(e[1:])
            valid_escritorios = escritoriosXempleados.get(f"E{i}", [])
            for esc in valid_escritorios:
                if escritorioXzona[esc] != zona:
                    continue  # ignorar escritorios fuera de esta zona
                j = int(esc[1:])
                for k in model.K:
                    sum_terms.append(model.x[i, j, k])
        if sum_terms:
            model.restriccion_conteo_miembros.add(
                model.miembros_en_zona[grupo, zona] == sum(sum_terms)
            )
        else:
            model.restriccion_conteo_miembros.add(model.miembros_en_zona[grupo, zona] == 0)

# Resolver con cbc
cbc_path = os.path.join(os.path.dirname(__file__), "solvers", "cbc.exe")  # Ruta al ejecutable dentro del proyecto
solver = SolverFactory("cbc", executable=cbc_path)
start_time = time.time()
result = solver.solve(model, tee=False, options={'seconds': tiempo_limite, 'ratio': gap / 100})
end_time = time.time()

print(f"Tiempo total de resolución: {end_time - start_time:.2f} segundos")
print(f"Estado de la solución: {result.solver.status}")
print(f"Resultado objetivo: {value(model.obj)}")

# Mostrar asignaciones
for i in model.I:
    for j in model.J:
        for k in model.K:
            if value(model.x[i, j, k]) == 1:
                print(f"Empleado E{i} asignado al escritorio D{j} el día {k}")
