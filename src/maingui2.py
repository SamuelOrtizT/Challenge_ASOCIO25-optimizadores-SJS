import tkinter as tk
from tkinter import ttk, messagebox
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
        tk.Label(self.root, text="Bienvenido a la aplicación de optimización de horarios", font=("Helvetica", 16, "bold")).pack(pady=10)

        descripcion = ("Esta aplicación ha sido desarrollada para la participación del reto ASOCIO 2025 por Juan Sebastián Hoyos Castillo, Samuel Ortiz Toro "
            "y Jhon Edison Pinto Hincapié, bajo el nombre del equipo 'Optimizadores SJS'.\n\nEl propósito principal de esta aplicación es asignar de la mejor " 
            "manera posible los escritorios que serán utilizados por un grupo de empleados durante los días en que deben hacer presencialidad en su lugar de " 
            "trabajo.\n\nPara ello, la aplicación considera distintas preferencias y restricciones, tales como los días preferidos para hacer presencialidad " 
            "por cada empleado, el uso de un mismo escritorio toda la semana, y la distribución de los equipos de trabajo en diferentes zonas.\n\nEn la carpeta "
            "'data' ubicada en el mismo directorio que esta aplicación hay ejemplos en formato JSON de problemas a resolver. Para optimizar un nuevo problema, "
            "añada un nuevo JSON en la carpeta 'data' con la información correspondiente, titulandolo 'instanceXX' siendo XX el número del problema a resolver.")

        frame = tk.Frame(self.root)
        frame.pack(padx=20, pady=10, fill="both", expand=True)

        text_widget = tk.Text(frame, wrap="word", height=10)
        text_widget.insert("1.0", descripcion)
        text_widget.config(state="disabled")

        scrollbar = tk.Scrollbar(frame, command=text_widget.yview)
        text_widget.config(yscrollcommand=scrollbar.set)

        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Button(self.root, text="Ingresar al sistema", command=self.create_second_window).pack(pady=20)

    def create_second_window(self):
        self.clear_window()
        tk.Label(self.root, text="Parámetros del modelo", font=("Helvetica", 14)).pack(pady=10)

        self.params = []
        labels = ["Peso día preferido:", "Peso mismo escritorio:", "Peso uso de zonas:", "Peso aislamiento:", 
                  "Tiempo límite (segundos):", "Desviación del óptimo (%):"
        ]

        tooltips = ["Importancia dada a que los empleados trabajen los días que prefieren, ingrese un valor > 1.", 
                    "Importancia dada a que un empleado conserve el mismo escritorio toda la semana. Valor numérico", 
                    "Importancia dada a que un equipo se reparta en el menor número de zonas. Valor numérico", 
                    "Importancia dada a que un empleado no quede aislado del resto de su equipo si este se reparte en diferentes zonas. Valor numérico", 
                    "Tiempo máximo para resolver el problema.", 
                    "Permite soluciones aproximadas para ganar velocidad. Valor numérico"
        ]

        self.inputs = []
        self.check_vars = []

        tk.Label(
            self.root,
            text="Habilitar restricciones aumenta el tiempo de ejecución a cambio de mejor calidad de la solución.",
            fg="red"
        ).pack(pady=5)

        frame_combo = tk.Frame(self.root)
        frame_combo.pack(pady=5, anchor="w")
        tk.Label(frame_combo, text="Seleccione la instancia JSON:").grid(row=0, column=0, padx=5)
        self.json_var = tk.StringVar()
        self.json_combobox = ttk.Combobox(frame_combo, textvariable=self.json_var, state="readonly")
        self.json_combobox.grid(row=0, column=1, padx=5)

        archivos_json = [f for f in os.listdir("./data") if f.startswith("instance") and f.endswith(".json")]
        numeros_instancia = sorted([
            int(f.replace("instance", "").replace(".json", ""))
            for f in archivos_json
            if f.replace("instance", "").replace(".json", "").isdigit()
        ])
        self.json_combobox['values'] = [str(n) for n in numeros_instancia]
        self.json_var.trace_add("write", lambda *args: self.check_validity())

        for i, label in enumerate(labels):
            frame = tk.Frame(self.root)
            frame.pack(pady=3, anchor="w")

            lbl = tk.Label(frame, text=label, width=30, anchor="w")
            lbl.grid(row=0, column=0, padx=5)

            var = tk.StringVar()
            entry = tk.Entry(frame, textvariable=var, width=10)
            entry.grid(row=0, column=1, padx=5)
            self.inputs.append(var)

            btn = tk.Button(frame, text="?", width=2, command=lambda i=i: messagebox.showinfo("Explicación", tooltips[i]))
            btn.grid(row=0, column=2, padx=5)

            var_chk = tk.IntVar()
            if i > 0:
                entry.config(state="disabled")

                def toggle_entry(i=i, entry=entry, var=var, chk_var=var_chk):
                    if chk_var.get():
                        entry.config(state="normal")
                    else:
                        entry.config(state="disabled")
                        var.set("")  # Borrar contenido
                    self.check_validity()

                chk = tk.Checkbutton(frame, text="Habilitar", variable=var_chk, command=toggle_entry)
                chk.grid(row=0, column=3, padx=5)

            self.check_vars.append(var_chk)
            var.trace_add("write", lambda *args, v=var: self.check_validity())

        self.execute_button = tk.Button(self.root, text="Ejecutar modelo", command=self.run_model, state="disabled")
        self.execute_button.pack(pady=20)

    def check_validity(self):
        # Validar que se haya seleccionado un JSON válido
        if self.json_var.get() not in self.json_combobox['values']:
            self.execute_button.config(state="disabled")
            return

        # Validar que el campo "peso día preferido" (índice 0) tenga un número válido
        try:
            valor0 = self.inputs[0].get().strip().replace(",", ".")
            if float(valor0) < 0:
                self.execute_button.config(state="disabled")
                return
        except ValueError:
            self.execute_button.config(state="disabled")
            return

        # Validar que todos los campos habilitados tengan números válidos
        for i in range(1, len(self.inputs)):
            if self.check_vars[i].get():  # Solo si está habilitado
                valor = self.inputs[i].get().strip().replace(",", ".")
                try:
                    if float(valor) < 0:
                        self.execute_button.config(state="disabled")
                        return
                except ValueError:
                    self.execute_button.config(state="disabled")
                    return

        # Si todo está bien, habilitar el botón
        self.execute_button.config(state="normal")

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
            self.create_third_window(model,result)

        except Exception as e:
            messagebox.showerror("Error en la ejecución", str(e))

    def create_third_window(self, model, result):
        self.clear_window()
        tk.Label(self.root, text="Resultados del modelo", font=("Helvetica", 14)).pack(pady=10)

        self.sort_var = tk.StringVar(value="Empleado")
        options = ["Empleado", "Día", "Escritorio"]
        tk.Label(self.root, text="Ordenar por:").pack()
        sort_menu = ttk.Combobox(self.root, textvariable=self.sort_var, values=options, state="readonly")
        sort_menu.pack(pady=5)
        sort_menu.bind("<<ComboboxSelected>>", lambda e: self.show_results())

        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.result_area = tk.Text(frame, wrap="word")
        scrollbar = tk.Scrollbar(frame, command=self.result_area.yview)
        self.result_area.configure(yscrollcommand=scrollbar.set)
        self.result_area.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        asignaciones = []
        for i in model.I:
            for j in model.J:
                for k in model.K:
                    if value(model.x[i, j, k]) == 1:
                        asignaciones.append((f"E{i}", f"D{j}", k))

        self.resultados = asignaciones
        self.show_results()

        tk.Button(self.root, text="Volver al inicio", command=self.create_first_window).pack(pady=10)

    def show_results(self):
        criterio = self.sort_var.get()

        orden_dias = {"L": 0, "Ma": 1, "Mi": 2, "J": 3, "V": 4}
        def extraer_numero(texto):
            return int(''.join(filter(str.isdigit, texto)))

        orden = {"Empleado": lambda x: extraer_numero(x[0]), "Escritorio": lambda x: extraer_numero(x[1]), "Día": lambda x: orden_dias.get(x[2], 99)
        }

        try:
            sorted_result = sorted(self.resultados, key=orden[criterio])
        except Exception as e:
            messagebox.showerror("Error", f"Error ordenando resultados: {e}")
            return

        self.result_area.config(state="normal")
        self.result_area.delete("1.0", "end")

        for emp, desk, day in sorted_result:
            self.result_area.insert("end", f"Empleado {emp}\t→\tEscritorio {desk} el día {day}\n")

        self.result_area.config(state="disabled")

    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("700x450")
    app = SchedulerApp(root)
    root.mainloop()