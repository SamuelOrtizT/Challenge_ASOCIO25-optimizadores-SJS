import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
import json
from pyomo.environ import *

class SchedulerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Optimizador de Turnos")
        self.create_first_window()

    def create_first_window(self):
        self.clear_window()
        tk.Label(self.root, text="Presentación del equipo", font=("Helvetica", 16)).pack(pady=10)

        integrantes = [("Juan Sebastián Hoyos Castillo", "foto1.png"), ("Samuel Ortiz Toro", "foto2.png"), ("Jhon Edison Pinto Hincapié", "foto3.png")]
        for nombre, foto in integrantes:
            frame = tk.Frame(self.root)
            frame.pack()
            try:
                imagen = Image.open(foto).resize((80, 80))
                img = ImageTk.PhotoImage(imagen)
                tk.Label(frame, image=img).pack(side="left", padx=5)
                tk.Label(frame, text=nombre, font=("Helvetica", 12)).pack(side="left")
                frame.image = img
            except:
                tk.Label(frame, text=f"{nombre} (sin foto)").pack()

        tk.Button(self.root, text="Ingresar al sistema", command=self.create_second_window).pack(pady=20)

    def create_second_window(self):
        self.clear_window()
        tk.Label(self.root, text="Parámetros del modelo", font=("Helvetica", 14)).pack(pady=10)

        self.params = []
        labels = [
            "Peso día preferido:",
            "Peso mismo escritorio:",
            "Peso uso de zonas:",
            "Peso aislamiento:",
            "Tiempo límite (segundos):",
            "Desviación del óptimo (%):"
        ]

        self.inputs = []
        self.valid = [False] * len(labels)

        # Combobox para selección del número de instancia
        tk.Label(self.root, text="Seleccione la instancia JSON:").pack()
        self.json_var = tk.StringVar()
        self.json_combobox = ttk.Combobox(self.root, textvariable=self.json_var, state="readonly")
        self.json_combobox.pack(pady=5)

        archivos_json = [f for f in os.listdir("./data") if f.startswith("instance") and f.endswith(".json")]
        numeros_instancia = sorted([
            f.replace("instance", "").replace(".json", "")
            for f in archivos_json
            if f.replace("instance", "").replace(".json", "").isdigit()
        ])
        self.json_combobox['values'] = numeros_instancia

        def validate_json_selection(*args):
            self.valid[0] = self.json_var.get() in numeros_instancia
            self.check_validity()

        self.json_var.trace_add("write", validate_json_selection)

        # Entradas restantes
        for i, label in enumerate(labels):
            frame = tk.Frame(self.root)
            frame.pack(pady=3)
            tk.Label(frame, text=label).pack(side="left")
            var = tk.StringVar()
            entry = tk.Entry(frame, textvariable=var)
            entry.pack(side="left")

            def validate(i=i, v=var):
                def inner(*args):
                    try:
                        val = float(v.get().replace(",", "."))
                        self.valid[i] = val >= 0
                    except:
                        self.valid[i] = False
                    self.check_validity()
                return inner

            var.trace_add("write", validate())
            self.inputs.append(var)

        self.execute_button = tk.Button(self.root, text="Ejecutar modelo", command=self.run_model, state="disabled")
        self.execute_button.pack(pady=20)

    def check_validity(self):
        if all(self.valid):
            self.execute_button.config(state="normal")
        else:
            self.execute_button.config(state="disabled")

    def run_model(self):
        try:
            num_instance = self.json_var.get()
            nombre_archivo = f"instance{num_instance}.json"
            ruta_json = os.path.join(".", "data", nombre_archivo)
            peso_dia_preferido = float(self.inputs[0].get().replace(",", "."))
            peso_mismo_escritorio = float(self.inputs[1].get().replace(",", "."))
            peso_zonas = float(self.inputs[2].get().replace(",", "."))
            peso_aislado = float(self.inputs[3].get().replace(",", "."))
            tiempo_limite = int(float(self.inputs[4].get().replace(",", ".")))
            gap = float(self.inputs[5].get().replace(",", "."))

            if not os.path.exists(ruta_json):
                messagebox.showerror("Error", "El archivo JSON no existe.")
                return

            with open(ruta_json, 'r') as archivo:
                datos = json.load(archivo)

            empleados = datos["Employees"]
            escritorios = datos["Desks"]
            dias = datos["Days"]
            grupos = datos["Groups"]
            zonas = datos["Zones"]
            zonasXescritorios = datos["Desks_Z"]
            escritoriosXempleados = datos['Desks_E']
            gruposXempleados = datos["Employees_G"]
            empleadosXdias = datos['Days_E']

            escritorioXzona = {
                esc: zona
                for zona, escritorios in zonasXescritorios.items()
                for esc in escritorios
            }

            M = -99999
            model = ConcreteModel()
            model.I = RangeSet(0, len(empleados) - 1)
            model.J = RangeSet(0, len(escritorios) - 1)
            model.K = Set(initialize=dias)
            model.G = Set(initialize=grupos)
            model.Z = Set(initialize=zonas)
            model.x = Var(model.I, model.J, model.K, within=Binary)
            model.y = Var([(i, j) for i in model.I for j in model.J if f"D{j}" in escritoriosXempleados[f"E{i}"]], domain=Binary)
            model.g = Var(model.G, model.K, domain=Binary)
            model.z = Var(model.G, model.Z, domain=Binary)
            model.miembros_en_zona = Var(model.G, model.Z, within=NonNegativeIntegers)
            model.aislado = Var(model.G, model.Z, domain=Binary)

            C = {
                (int(emp[1:]), int(desk[1:]), day): (
                    peso_dia_preferido if desk in escritoriosXempleados[emp] and day in empleadosXdias[emp]
                    else 1 if desk in escritoriosXempleados[emp]
                    else M
                )
                for emp in empleados
                for desk in escritorios
                for day in dias
            }

            def objetivo(m):
                a = sum(C[(i, j, k)] * m.x[i, j, k] for i in m.I for j in m.J for k in m.K)
                b = sum(m.y[i, j] for (i, j) in m.y.index_set())
                c = sum(m.z[g, z] for g in m.G for z in m.Z)
                d = sum(m.aislado[g, z] for g in m.G for z in m.Z)
                return a - peso_mismo_escritorio * b - peso_zonas * c - peso_aislado * d

            model.obj = Objective(rule=objetivo, sense=maximize)

            model.restriccion_activar_y = Constraint(model.I, model.J, model.K, rule=lambda m, i, j, k: m.x[i, j, k] <= m.y[i, j] if (i, j) in m.y.index_set() else Constraint.Skip)
            model.restriccion_asignacion = Constraint(model.I, model.K, rule=lambda m, i, k: sum(m.x[i, j, k] for j in m.J) <= 1)
            model.restriccion_ocupacion = Constraint(model.J, model.K, rule=lambda m, j, k: sum(m.x[i, j, k] for i in m.I) <= 1)
            model.restriccion_dias = Constraint(model.I, rule=lambda m, i: inequality(2, sum(m.x[i, j, k] for j in m.J for k in m.K), 3))
            model.restriccion_grupo = Constraint(model.G, rule=lambda m, g: sum(m.g[g, k] for k in m.K) == 1)
            model.restriccion_asistencia_grupal = ConstraintList()
            model.restriccion_zona_usada = ConstraintList()
            model.restriccion_conteo_miembros = ConstraintList()
            model.restriccion_aislamiento = ConstraintList()

            for g in model.G:
                for z in model.Z:
                    model.restriccion_aislamiento.add(model.miembros_en_zona[g, z] >= model.aislado[g, z])
                    model.restriccion_aislamiento.add(model.miembros_en_zona[g, z] <= model.aislado[g, z] + (len(gruposXempleados[g]) - 1)*(1 - model.aislado[g, z]))

            for g, emps in gruposXempleados.items():
                for k in model.K:
                    for e in emps:
                        i = int(e[1:])
                        model.restriccion_asistencia_grupal.add(sum(model.x[i, j, k] for j in model.J if f"D{j}" in escritoriosXempleados[f"E{i}"]) >= model.g[g, k])

            for g, emps in gruposXempleados.items():
                for e in emps:
                    i = int(e[1:])
                    for esc in escritoriosXempleados[f"E{i}"]:
                        j = int(esc[1:])
                        zona = escritorioXzona[esc]
                        for k in model.K:
                            model.restriccion_zona_usada.add(model.x[i, j, k] <= model.z[g, zona])

            for g, emps in gruposXempleados.items():
                for z in model.Z:
                    terms = []
                    for e in emps:
                        i = int(e[1:])
                        for esc in escritoriosXempleados[f"E{i}"]:
                            if escritorioXzona[esc] == z:
                                j = int(esc[1:])
                                for k in model.K:
                                    terms.append(model.x[i, j, k])
                    model.restriccion_conteo_miembros.add(model.miembros_en_zona[g, z] == sum(terms) if terms else 0)

            cbc_path = os.path.join(os.path.dirname(__file__), "solvers", "cbc.exe")
            solver = SolverFactory("cbc", executable=cbc_path)
            result = solver.solve(model, tee=False, options={'seconds': tiempo_limite, 'ratio': gap / 100})

            self.create_third_window(model, result)

        except Exception as e:
            messagebox.showerror("Error en la ejecución", str(e))

    def create_third_window(self, model, result):
        self.clear_window()
        tk.Label(self.root, text="Resultados del modelo", font=("Helvetica", 14)).pack(pady=10)

        output = f"Estado: {result.solver.status}\n"
        output += f"Valor objetivo: {value(model.obj)}\n\nAsignaciones:\n"

        asignaciones = []
        for i in model.I:
            for j in model.J:
                for k in model.K:
                    if value(model.x[i, j, k]) == 1:
                        asignaciones.append(f"Empleado E{i} → Escritorio D{j} el día {k}")

        output += "\n".join(asignaciones)

        # Contenedor para Text con scrollbar
        frame = tk.Frame(self.root)
        frame.pack(expand=True, fill="both", padx=10, pady=10)

        text_area = tk.Text(frame, wrap="word", height=25, width=80)
        scrollbar = tk.Scrollbar(frame, command=text_area.yview)
        text_area.configure(yscrollcommand=scrollbar.set)

        text_area.insert("1.0", output)
        text_area.config(state="disabled")

        text_area.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Button(self.root, text="Volver al inicio", command=self.create_first_window).pack(pady=10)

    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("600x700")
    app = SchedulerApp(root)
    root.mainloop()
