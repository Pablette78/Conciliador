"""
Conciliador Bancario v10 — Interfaz gráfica moderna con CustomTkinter
Soporta múltiples extractos (PDF/Excel) y múltiples mayores contables.
"""
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinter import filedialog, messagebox
import os
import threading
import re
from datetime import datetime

from core.models import DatosExtracto
from core.factory import FabricaParsers
from core.engine import MotorConciliacion
from core.utils import combinar_extractos, combinar_mayores
from parser_excel import parsear_excel
from generador_excel import generar_excel
from detector_banco import detectar_banco_con_confianza

# ─── Tema ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BLUE_MAIN = "#3B82F6"
BLUE_DARK = "#1E40AF"
GREEN_OK  = "#22C55E"
RED_ERR   = "#EF4444"
YELLOW_W  = "#F59E0B"
BG_DARK   = "#0F172A"
BG_PANEL  = "#1E293B"
BG_CARD   = "#334155"
TEXT_MAIN = "#F1F5F9"
TEXT_MUTED= "#94A3B8"

BANCOS = [
    "— auto —", "Banco Santander", "Banco Galicia", "Banco BBVA", "Banco Bancor",
    "Banco Provincia", "Banco Nación", "Banco Credicoop", "Banco HSBC",
    "Banco ICBC", "Banco Macro", "Banco Ciudad", "Banco Comafi", "ARCA-Mis Retenciones"
]


# ─── Widget: Zona de Drop ─────────────────────────────────────────────────────
class DropZone(ctk.CTkFrame):
    """Area de carga con soporte drag-and-drop y botón explorador."""

    def __init__(self, master, titulo, extensiones, on_agregar=None, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=14,
                         border_width=2, border_color=BLUE_MAIN, **kw)
        self._archivos: list[str] = []
        self._extensiones = extensiones
        self._on_agregar = on_agregar

        # ─ Título
        ctk.CTkLabel(self, text=titulo, font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=TEXT_MAIN).pack(pady=(14, 4))

        # ─ Icono + hint
        ctk.CTkLabel(self, text="📂  Arrastrá archivos aquí  ·  o",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT_MUTED).pack()

        # ─ Botón explorador
        ctk.CTkButton(self, text="Seleccionar archivos", width=170,
                      fg_color=BLUE_MAIN, hover_color=BLUE_DARK,
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=self._explorar).pack(pady=(6, 8))

        # ─ Lista compacta
        self._lista = ctk.CTkScrollableFrame(self, height=80, fg_color=BG_PANEL,
                                             corner_radius=8)
        self._lista.pack(fill="x", padx=14, pady=(0, 8))
        self._actualizar_lista()

        # ─ Quitar selección
        ctk.CTkButton(self, text="✕ Quitar seleccionados", width=170, height=26,
                      fg_color="transparent", border_width=1,
                      border_color=RED_ERR, text_color=RED_ERR,
                      hover_color="#3B1212",
                      font=ctk.CTkFont("Segoe UI", 10),
                      command=self._quitar).pack(pady=(0, 12))

        # ─ Activar DnD
        try:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self._on_drop)
        except Exception:
            pass

    # ── Drag & Drop ──────────────────────────────────────────────────────────

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        for p in paths:
            self._agregar_ruta(p.strip('{}'))

    # ── Explorador ───────────────────────────────────────────────────────────

    def _explorar(self):
        ft = [("Archivos soportados", " ".join(f"*.{e}" for e in self._extensiones))]
        rutas = filedialog.askopenfilenames(title="Seleccionar archivos", filetypes=ft)
        for r in rutas:
            self._agregar_ruta(r)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _agregar_ruta(self, ruta: str):
        if ruta and ruta not in self._archivos:
            self._archivos.append(ruta)
            self._actualizar_lista()
            if self._on_agregar:
                self._on_agregar(ruta)

    def _quitar(self):
        if self._archivos:
            self._archivos.pop()
            self._actualizar_lista()

    def _actualizar_lista(self):
        for w in self._lista.winfo_children():
            w.destroy()
        if not self._archivos:
            ctk.CTkLabel(self._lista, text="Sin archivos cargados",
                         text_color=TEXT_MUTED,
                         font=ctk.CTkFont("Segoe UI", 10)).pack(pady=6)
        for ruta in self._archivos:
            ctk.CTkLabel(self._lista, text=f"✓  {os.path.basename(ruta)}",
                         text_color=GREEN_OK,
                         font=ctk.CTkFont("Segoe UI", 10),
                         anchor="w").pack(fill="x", padx=8, pady=2)

    def rutas(self) -> list[str]:
        return self._archivos.copy()

    def vacia(self) -> bool:
        return len(self._archivos) == 0


# ─── Widget: Métrica circular ─────────────────────────────────────────────────
class MetricCard(ctk.CTkFrame):
    """Card con valor grande, emoji y etiqueta."""

    def __init__(self, master, emoji: str, etiqueta: str, color: str, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, **kw)
        self._var = ctk.StringVar(value="—")
        ctk.CTkLabel(self, text=emoji, font=ctk.CTkFont("Segoe UI", 28)).pack(pady=(16, 0))
        ctk.CTkLabel(self, textvariable=self._var,
                     font=ctk.CTkFont("Segoe UI", 26, "bold"),
                     text_color=color).pack()
        ctk.CTkLabel(self, text=etiqueta,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=TEXT_MUTED).pack(pady=(0, 14))

    def set(self, valor):
        self._var.set(str(valor))


# ─── Ventana principal ────────────────────────────────────────────────────────
class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Conciliador Bancario v10")
        self.geometry("1000x760")
        self.minsize(900, 680)
        self.configure(bg=BG_DARK)

        # Estado
        self._resultado_temp = None

        self._construir_ui()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _construir_ui(self):
        # ─ Sidebar
        sidebar = ctk.CTkFrame(self, width=200, fg_color=BG_PANEL, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._construir_sidebar(sidebar)

        # ─ Main area
        self._main = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self._main.pack(side="left", fill="both", expand=True)

        # Mostramos pantalla de inicio
        self._mostrar_home()

    def _construir_sidebar(self, parent):
        # Logo
        ctk.CTkLabel(parent, text="🏦", font=ctk.CTkFont("Segoe UI", 36)).pack(pady=(30, 4))
        ctk.CTkLabel(parent, text="Conciliador\nBancario",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=TEXT_MAIN, justify="center").pack()
        ctk.CTkLabel(parent, text="v10",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=BLUE_MAIN).pack(pady=(0, 24))

        ctk.CTkFrame(parent, height=1, fg_color=BG_CARD, corner_radius=0).pack(fill="x", padx=20, pady=8)

        # Botones de navegación
        nav = [
            ("🔄  Nueva Conciliación", self._mostrar_home),
            ("📊  Resultados",         self._mostrar_resultados),
        ]
        for texto, cmd in nav:
            ctk.CTkButton(parent, text=texto, anchor="w", width=160,
                          fg_color="transparent", hover_color=BG_CARD,
                          text_color=TEXT_MAIN,
                          font=ctk.CTkFont("Segoe UI", 12),
                          command=cmd).pack(pady=4, padx=16)

        # Separador inferior + versión
        ctk.CTkFrame(parent, height=1, fg_color=BG_CARD, corner_radius=0).pack(fill="x", padx=20, pady=4, side="bottom")
        ctk.CTkLabel(parent, text="© 2026 Conciliador",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=TEXT_MUTED).pack(side="bottom", pady=4)

    # ── Pantalla: Nueva Conciliación ─────────────────────────────────────────

    def _mostrar_home(self):
        self._limpiar_main()

        scroll = ctk.CTkScrollableFrame(self._main, fg_color=BG_DARK)
        scroll.pack(fill="both", expand=True, padx=24, pady=20)

        # Título
        ctk.CTkLabel(scroll, text="Nueva Conciliación",
                     font=ctk.CTkFont("Segoe UI", 22, "bold"),
                     text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(scroll, text="Cargá los extractos bancarios y el mayor contable para comenzar.",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 20))

        # Drop zones lado a lado
        zonas = ctk.CTkFrame(scroll, fg_color="transparent")
        zonas.pack(fill="x", pady=(0, 16))
        zonas.columnconfigure((0, 1), weight=1)

        self._zona_extractos = DropZone(
            zonas, "📄  Extractos Bancarios",
            extensiones=["pdf", "xlsx", "xls"],
            on_agregar=self._autodetectar_banco)
        self._zona_extractos.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        self._zona_mayores = DropZone(
            zonas, "📊  Mayor Contable",
            extensiones=["xls", "xlsx", "xlsm"])
        self._zona_mayores.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        # Selector de banco
        banco_row = ctk.CTkFrame(scroll, fg_color="transparent")
        banco_row.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(banco_row, text="Banco (si no se detecta automáticamente):",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 12))
        self._banco_var = ctk.StringVar(value="— auto —")
        ctk.CTkComboBox(banco_row, values=BANCOS,
                        variable=self._banco_var,
                        width=220,
                        button_color=BLUE_MAIN,
                        border_color=BLUE_MAIN).pack(side="left")

        # Botón CONCILIAR
        self._btn_conciliar = ctk.CTkButton(
            scroll, text="  ⚡  CONCILIAR  ", width=260, height=52,
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            fg_color=BLUE_MAIN, hover_color=BLUE_DARK,
            corner_radius=14,
            command=self._conciliar)
        self._btn_conciliar.pack(pady=(0, 12))

        self._progress = ctk.CTkProgressBar(scroll, mode="indeterminate",
                                            width=400, height=8,
                                            progress_color=BLUE_MAIN)
        self._progress.pack(pady=(0, 16))
        self._progress.set(0)

        # Log
        ctk.CTkLabel(scroll, text="Registro de actividad",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=TEXT_MUTED).pack(anchor="w")
        self._log_box = ctk.CTkTextbox(
            scroll, height=200,
            font=ctk.CTkFont("Consolas", 10),
            fg_color="#0D1117", text_color="#c9d1d9",
            corner_radius=10)
        self._log_box.pack(fill="x", pady=(4, 0))
        self._log_box.configure(state="disabled")

    # ── Pantalla: Resultados ─────────────────────────────────────────────────

    def _mostrar_resultados(self):
        self._limpiar_main()

        scroll = ctk.CTkScrollableFrame(self._main, fg_color=BG_DARK)
        scroll.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(scroll, text="Panel de Resultados",
                     font=ctk.CTkFont("Segoe UI", 22, "bold"),
                     text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 4))

        if not self._resultado_temp:
            ctk.CTkLabel(scroll, text="Aún no hay resultados. Ejecutá una conciliación primero.",
                         font=ctk.CTkFont("Segoe UI", 13),
                         text_color=TEXT_MUTED).pack(pady=40)
            return

        t = self._resultado_temp

        # ─ Cards de métricas
        cards_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(8, 20))
        for i in range(5):
            cards_frame.columnconfigure(i, weight=1)

        datos_cards = [
            ("✅", "Conciliados",   GREEN_OK,  t["n_conc"]),
            ("⚖",  "Dif. Monto",   YELLOW_W,  t["n_diff"]),
            ("🏦", "Solo Banco",    BLUE_MAIN, t["n_banco"]),
            ("📋", "Solo Sistema",  YELLOW_W,  t["n_sist"]),
            ("💰", "Tipos Gastos",  TEXT_MUTED,t["n_gastos"]),
        ]
        for col, (emoji, lbl, color, val) in enumerate(datos_cards):
            card = MetricCard(cards_frame, emoji, lbl, color)
            card.set(val)
            card.grid(row=0, column=col, padx=6, sticky="nsew")

        # Barra de éxito
        total = t["n_conc"] + t["n_banco"] + t["n_sist"]
        pct = t["n_conc"] / total if total > 0 else 0
        pct_txt = f"{pct*100:.1f}% conciliado"
        ctk.CTkLabel(scroll, text=pct_txt,
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=GREEN_OK if pct >= 0.8 else YELLOW_W).pack(anchor="w", pady=(0, 4))
        bar = ctk.CTkProgressBar(scroll, height=14, progress_color=GREEN_OK if pct >= 0.8 else YELLOW_W)
        bar.pack(fill="x", pady=(0, 20))
        bar.set(pct)

        # Botón guardar
        ctk.CTkButton(scroll, text="💾  Guardar Excel",
                      width=220, height=46,
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      fg_color=GREEN_OK, hover_color="#15803D",
                      command=self._pedir_guardar).pack(pady=(0, 16))

        # Log de pasadas
        if t.get("resumen_pasadas"):
            ctk.CTkLabel(scroll, text="Detalle por pasadas de conciliación:",
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=TEXT_MUTED).pack(anchor="w")
            for pasada, cant in t["resumen_pasadas"].items():
                ctk.CTkLabel(scroll, text=f"  • {pasada}: {cant} items",
                             font=ctk.CTkFont("Consolas", 10),
                             text_color=TEXT_MAIN).pack(anchor="w")

    # ── Lógica ───────────────────────────────────────────────────────────────

    def _limpiar_main(self):
        for w in self._main.winfo_children():
            w.destroy()

    def _log(self, msg: str, color: str = TEXT_MAIN):
        try:
            self._log_box.configure(state="normal")
            self._log_box.insert("end", msg + "\n")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        except Exception:
            pass

    def _autodetectar_banco(self, ruta: str):
        banco, confianza = detectar_banco_con_confianza(ruta)
        if banco:
            sufijo = "" if confianza == "alta" else " (probable)"
            self._log(f"🔍  {os.path.basename(ruta)} → {banco}{sufijo}")
            if self._banco_var.get() == "— auto —":
                self._banco_var.set(banco)
        else:
            self._log(f"❓  {os.path.basename(ruta)} → no detectado, seleccioná el banco manualmente")

    def _conciliar(self):
        if self._zona_extractos.vacia():
            messagebox.showwarning("Atención", "Agregá al menos un extracto bancario.")
            return
        if self._zona_mayores.vacia():
            messagebox.showwarning("Atención", "Agregá al menos un mayor contable.")
            return
        self._btn_conciliar.configure(state="disabled")
        self._progress.start()
        threading.Thread(target=self._proceso, daemon=True).start()

    def _proceso(self):
        try:
            self._log("─" * 55)
            self._log("📂  Leyendo extractos bancarios...")
            lista_datos = []

            banco_lote = None
            for ruta in self._zona_extractos.rutas():
                b, _ = detectar_banco_con_confianza(ruta)
                if b:
                    banco_lote = b
                    break

            for ruta in self._zona_extractos.rutas():
                nombre = os.path.basename(ruta)
                banco_det = detectar_banco_con_confianza(ruta)[0]
                banco_fin = banco_det or banco_lote or self._banco_var.get()

                if banco_fin == "— auto —":
                    self._log(f"   ✗  {nombre} → banco desconocido, saltando")
                    continue

                parser = FabricaParsers.obtener_parser(banco_fin)
                if not parser:
                    self._log(f"   ✗  {nombre} → sin parser para {banco_fin}")
                    continue

                datos = parser.parse(ruta)
                self._log(f"   ✓  {nombre}  [{datos.banco}]  → {len(datos.movimientos)} movs")
                lista_datos.append(datos)

            datos_comb = combinar_extractos(lista_datos)
            self._log(f"   Total banco: {len(datos_comb.movimientos)} movimientos")

            self._log("📊  Leyendo mayores contables...")
            lista_sistema = []
            for ruta in self._zona_mayores.rutas():
                movs = parsear_excel(ruta)
                self._log(f"   ✓  {os.path.basename(ruta)} → {len(movs)} movimientos")
                lista_sistema.append(movs)
            movs_sis = combinar_mayores(lista_sistema)

            self._log("🔄  Conciliando...")
            resultado = MotorConciliacion().conciliar(datos_comb, movs_sis)

            conc   = resultado.conciliados
            n_conc = len(conc)
            n_diff = sum(1 for c in conc if c.estado == "CON_DIFERENCIA")
            n_banco  = len(resultado.solo_banco)
            n_sist   = len(resultado.solo_sistema)
            n_gastos = len(resultado.gastos_por_categoria)

            self._log(f"   ✅  {n_conc} pares conciliados")
            if n_diff:  self._log(f"   ⚠  {n_diff} diferencias de monto")
            if n_banco: self._log(f"   🏦  {n_banco} solo en banco")
            if n_sist:  self._log(f"   📋  {n_sist} solo en sistema")
            self._log(f"   💰  {n_gastos} tipos de gastos discriminados")

            movs_banco = datos_comb.movimientos
            if movs_banco:
                meses = ['','Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
                fechas = sorted(m.fecha for m in movs_banco)
                f0, f1 = fechas[0], fechas[-1]
                periodo = f"{meses[f0.month]}{f0.year}" if f0.month == f1.month and f0.year == f1.year else f"{meses[f1.month]}{f1.year}"
            else:
                periodo = "SinFecha"

            banco_label = re.sub(r'[\\/*?:"<>|]', '_',
                datos_comb.titular or self._banco_var.get().replace(' ', '').replace('—', ''))
            periodo = re.sub(r'[\\/*?:"<>|]', '_', periodo)

            self._resultado_temp = {
                "resultado": resultado,
                "datos_banco": datos_comb,
                "movs_sistema": movs_sis,
                "periodo": periodo,
                "nombre_sugerido": f"Conciliacion_{banco_label}_{periodo}.xlsx",
                "directorio_inicial": os.path.dirname(self._zona_extractos.rutas()[0]),
                "n_conc": n_conc, "n_diff": n_diff,
                "n_banco": n_banco, "n_sist": n_sist, "n_gastos": n_gastos,
                "resumen_pasadas": getattr(resultado, "resumen_pasadas", {}),
            }
            self._log("─" * 55)
            self._log("✅  ¡Conciliación completada! Ir a Panel de Resultados.")
            self.after(0, self._mostrar_resultados)

        except Exception as e:
            import traceback
            self._log(f"❌  Error: {e}")
            self._log(traceback.format_exc())
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, self._finalizar)

    def _pedir_guardar(self):
        if not self._resultado_temp:
            return
        t = self._resultado_temp
        ruta = filedialog.asksaveasfilename(
            title="Guardar conciliación",
            initialdir=t["directorio_inicial"],
            initialfile=t["nombre_sugerido"],
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if not ruta:
            return
        try:
            generar_excel(t["resultado"], t["datos_banco"], ruta, t["periodo"], t["movs_sistema"])
            messagebox.showinfo("Guardado", f"Archivo guardado:\n{ruta}\n\n"
                                f"• {t['n_conc']} pares conciliados\n"
                                f"• {t['n_diff']} diferencias de monto\n"
                                f"• {t['n_banco']} solo banco  /  {t['n_sist']} solo sistema")
            if os.name == "nt":
                os.startfile(os.path.dirname(ruta))
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))

    def _finalizar(self):
        self._progress.stop()
        self._progress.set(0)
        try:
            self._btn_conciliar.configure(state="normal")
        except Exception:
            pass


# ─── Punto de entrada ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
