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
valid_x = [(int(emp[1:]), int(desk[1:]), day)
           for emp in empleados
           for desk in escritoriosXempleados[emp]
           for day in dias]
valid_y = [(int(emp[1:]), int(desk[1:]))
           for emp in empleados
           for desk in escritoriosXempleados[emp]]

#Inicializar modelo
model = ConcreteModel()
model.I = RangeSet(0, len(empleados) - 1)
model.J = RangeSet(0, len(escritorios) - 1)
model.K = Set(initialize=dias)
model.G = Set(initialize=grupos)
model.Z = Set(initialize=zonas)
model.idxC = Set(initialize=valid_x, dimen=3)
model.x = Var(model.idxC, within=Binary)
model.y = Var(valid_y, domain=Binary)
model.g = Var(model.G, model.K, domain=Binary)
model.z = Var(model.G, model.Z, domain=Binary)
model.miembros_en_zona = Var(model.G, model.Z, within=NonNegativeIntegers)
model.aislado = Var(model.G, model.Z, domain=Binary)

# --- Coeficientes para la función objetivo ---
C = {
    (int(emp[1:]), int(desk[1:]), day): peso_dia_preferido
    for emp in empleados
    for desk in escritoriosXempleados[emp]
    for day in dias
}

# --- Objetivo ---
def funcion_objetivo(m):
    asignacion = sum(C[idx] * m.x[idx] for idx in m.idxC)
    consistencia = sum(m.y[i, j] for (i, j) in valid_y)
    zonas_usadas = sum(m.z[g, z] for g in m.G for z in m.Z)
    aislamiento = sum(m.aislado[g, z] for g in m.G for z in m.Z)
    return asignacion - peso_mismo_escritorio * consistencia - peso_zonas * zonas_usadas - peso_aislado * aislamiento

model.obj = Objective(rule=funcion_objetivo, sense=maximize)

# --- Restricciones ---
def un_escritorio_por_dia(m, i, k):
    return sum(m.x[i2, j, k2] for (i2, j, k2) in m.idxC if i2 == i and k2 == k) <= 1

def un_empleado_por_escritorio(m, j, k):
    return sum(m.x[i, j2, k2] for (i, j2, k2) in m.idxC if j2 == j and k2 == k) <= 1

def dias_trabajados(m, i):
    return inequality(2, sum(m.x[i2, j, k] for (i2, j, k) in m.idxC if i2 == i), 3)

def un_dia_por_grupo(m, g):
    return sum(m.g[g, k] for k in m.K) == 1

model.restriccion_asignacion = Constraint(model.I, model.K, rule=un_escritorio_por_dia)
model.restriccion_ocupacion = Constraint(model.J, model.K, rule=un_empleado_por_escritorio)
model.restriccion_dias = Constraint(model.I, rule=dias_trabajados)
model.restriccion_y = ConstraintList()
for (i, j, k) in valid_x:
    model.restriccion_y.add(model.x[i, j, k] <= model.y[i, j])
model.restriccion_dia_grupo = Constraint(model.G, rule=un_dia_por_grupo)

model.restriccion_asistencia = ConstraintList()
model.restriccion_zona = ConstraintList()
model.restriccion_miembros = ConstraintList()
model.restriccion_aislamiento = ConstraintList()

for g in model.G:
    empleados_grupo = gruposXempleados[g]
    for k in dias:
        for e in empleados_grupo:
            i = int(e[1:])
            valid = [(i2, j, k2) for (i2, j, k2) in valid_x if i2 == i and k2 == k]
            if valid:
                model.restriccion_asistencia.add(
                    sum(model.x[idx] for idx in valid) >= model.g[g, k]
                )

    for z in model.Z:
        model.restriccion_aislamiento.add(model.miembros_en_zona[g, z] >= model.aislado[g, z])
        model.restriccion_aislamiento.add(model.miembros_en_zona[g, z] <= model.aislado[g, z] + (len(empleados_grupo) - 1)*(1 - model.aislado[g, z]))

        sum_terms = []
        for e in empleados_grupo:
            i = int(e[1:])
            for esc in escritoriosXempleados[e]:
                if escritorioXzona[esc] == z:
                    j = int(esc[1:])
                    for k in empleadosXdias[e]:
                        idx = (i, j, k)
                        if idx in model.idxC:
                            sum_terms.append(model.x[idx])
                            model.restriccion_zona.add(model.x[idx] <= model.z[g, z])
        model.restriccion_miembros.add(model.miembros_en_zona[g, z] == sum(sum_terms) if sum_terms else 0)

# --- Warm-start ---
for idx in model.idxC:
    model.x[idx].value = 0  # asignación inicial factible trivial (sin asignaciones)

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
for idx in model.idxC:
    if value(model.x[idx]) == 1:
        print(f"Empleado E{idx[0]} asignado al escritorio D{idx[1]} el día {idx[2]}")
