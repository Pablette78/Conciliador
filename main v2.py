"""
Conciliador Bancario - Aplicación de escritorio
Soporta múltiples extractos (de uno o varios meses / bancos) y uno o varios mayores.
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading
from datetime import datetime

from core.models import Movimiento, DatosExtracto
from core.parsers.santander import SantanderParser
from core.factory import FabricaParsers
from core.engine import MotorConciliacion
from core.utils import combinar_extractos, combinar_mayores
from parser_excel import parsear_excel
from generador_excel import generar_excel
import re

# Parsers legados (en proceso de refactorización)
from parser_banco_ciudad import parsear_pdf as parsear_ciudad
from parser_comafi import parsear_pdf as parsear_comafi
from parser_icbc import parsear_pdf as parsear_icbc
from parser_provincia import parsear_pdf as parsear_provincia
from detector_banco import detectar_banco_con_confianza

PARSERS_BANCO = {
    "Banco Ciudad":    parsear_ciudad,
    "Banco Comafi":    parsear_comafi,
    "Banco ICBC":      parsear_icbc,
    "Banco Provincia": parsear_provincia,
    "Banco Santander": None, # Se maneja vía FabricaParsers (refactorizado)
    "Banco Galicia":   None, # Se maneja vía FabricaParsers (refactorizado)
}

COLOR_FONDO   = '#f0f4f8'
COLOR_HEADER  = '#2F5496'
COLOR_VERDE   = '#2E7D32'
COLOR_ROJO    = '#C62828'
COLOR_NARANJA = '#E65100'


class ListaArchivos(tk.Frame):
    """Widget reutilizable: lista de archivos con botones Agregar / Quitar."""

    def __init__(self, parent, titulo, filetypes, on_agregar=None, **kwargs):
        super().__init__(parent, bg=COLOR_FONDO, **kwargs)
        self.filetypes = filetypes
        self.on_agregar = on_agregar
        self._archivos = []  # list of (ruta, etiqueta)

        # Encabezado con botones
        row_top = tk.Frame(self, bg=COLOR_FONDO)
        row_top.pack(fill='x')
        tk.Label(row_top, text=titulo, font=('Arial', 10, 'bold'),
                 bg=COLOR_FONDO, anchor='w').pack(side='left')
        tk.Button(row_top, text="＋ Agregar", command=self._agregar,
                  font=('Arial', 9), bg=COLOR_HEADER, fg='white',
                  relief='flat', padx=8, cursor='hand2').pack(side='right', padx=(4, 0))
        tk.Button(row_top, text="✕ Quitar", command=self._quitar,
                  font=('Arial', 9), bg=COLOR_ROJO, fg='white',
                  relief='flat', padx=8, cursor='hand2').pack(side='right')

        # Listbox
        frame_lb = tk.Frame(self, bg=COLOR_FONDO)
        frame_lb.pack(fill='both', expand=True, pady=(4, 0))
        self.lb = tk.Listbox(frame_lb, font=('Consolas', 9),
                             height=4, selectmode='extended',
                             activestyle='none', relief='solid', bd=1,
                             bg='white', selectbackground='#c5d8f5')
        scroll = tk.Scrollbar(frame_lb, orient='vertical', command=self.lb.yview)
        self.lb.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.lb.pack(side='left', fill='both', expand=True)

    def _agregar(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar archivo(s)",
            filetypes=self.filetypes
        )
        for path in paths:
            if path not in [a[0] for a in self._archivos]:
                etiqueta = os.path.basename(path)
                self._archivos.append((path, etiqueta))
                self.lb.insert('end', etiqueta)
                if self.on_agregar:
                    self.on_agregar(path)

    def _quitar(self):
        seleccion = list(self.lb.curselection())
        for i in reversed(seleccion):
            self.lb.delete(i)
            self._archivos.pop(i)

    def rutas(self):
        return [a[0] for a in self._archivos]

    def vacia(self):
        return len(self._archivos) == 0

    def limpiar(self):
        self.lb.delete(0, 'end')
        self._archivos.clear()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Conciliador Bancario")
        self.root.geometry("720x680")
        self.root.resizable(False, False)
        self.root.configure(bg=COLOR_FONDO)
        self._crear_interfaz()

    # ─── Interfaz ─────────────────────────────────────────────────────────────

    def _crear_interfaz(self):
        # Header
        hdr = tk.Frame(self.root, bg=COLOR_HEADER, height=60)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🏦  Conciliador Bancario",
                 font=('Arial', 18, 'bold'), fg='white', bg=COLOR_HEADER).pack(pady=14)

        main = tk.Frame(self.root, bg=COLOR_FONDO, padx=24, pady=16)
        main.pack(fill='both', expand=True)

        # ── Extractos bancarios ───────────────────────────────────────────────
        self.lista_extractos = ListaArchivos(
            main,
            titulo="Extractos bancarios  (PDF o Excel — uno o varios meses, uno o varios bancos)",
            filetypes=[("Extracto bancario", "*.pdf *.xlsx *.xls"),
                       ("PDF", "*.pdf"), ("Excel", "*.xlsx *.xls"), ("Todos", "*.*")],
            on_agregar=self._autodetectar_banco,
        )
        self.lista_extractos.pack(fill='x', pady=(0, 12))

        # ── Banco (fallback si no se detecta) ────────────────────────────────
        frame_banco = tk.Frame(main, bg=COLOR_FONDO)
        frame_banco.pack(fill='x', pady=(0, 12))
        tk.Label(frame_banco, text="Banco (si no se detecta automáticamente):",
                 font=('Arial', 9), bg=COLOR_FONDO, fg='#555').pack(side='left', padx=(0, 8))
        self.banco_var = tk.StringVar(value="— auto —")
        self.combo_banco = ttk.Combobox(
            frame_banco, textvariable=self.banco_var,
            values=["— auto —"] + list(PARSERS_BANCO.keys()),
            state='readonly', font=('Arial', 10), width=22)
        self.combo_banco.pack(side='left')

        self.lista_mayores = ListaArchivos(
            main,
            titulo="Mayor contable  (Excel — uno o varios)",
            filetypes=[("Excel", "*.xls *.xlsx *.xlsm"), ("Todos", "*.*")],
        )
        self.lista_mayores.pack(fill='x', pady=(0, 12))

        ttk.Separator(main, orient='horizontal').pack(fill='x', pady=6)

        # ── Botón conciliar ───────────────────────────────────────────────────
        self.btn = tk.Button(
            main, text="  CONCILIAR  ", command=self._conciliar,
            font=('Arial', 13, 'bold'), bg=COLOR_VERDE, fg='white',
            relief='flat', padx=20, pady=9, cursor='hand2',
            activebackground='#1B5E20')
        self.btn.pack(pady=(4, 8))

        self.progress = ttk.Progressbar(main, mode='indeterminate')
        self.progress.pack(fill='x')

        # ── Log ───────────────────────────────────────────────────────────────
        self.log = tk.Text(main, height=9, font=('Consolas', 8),
                           bg='#1e1e1e', fg='#d4d4d4',
                           state='disabled', relief='flat', padx=8, pady=6)
        self.log.pack(fill='x', pady=(10, 0))

        # Colores de log
        self.log.tag_config('ok',    foreground='#89d185')
        self.log.tag_config('warn',  foreground='#f5c842')
        self.log.tag_config('error', foreground='#f48771')
        self.log.tag_config('info',  foreground='#9cdcfe')

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _log(self, msg, tag=None):
        self.log.configure(state='normal')
        self.log.insert('end', msg + '\n', tag or '')
        self.log.see('end')
        self.log.configure(state='disabled')
        self.root.update_idletasks()

    def _autodetectar_banco(self, ruta):
        banco, confianza = detectar_banco_con_confianza(ruta)
        nombre = os.path.basename(ruta)
        if banco:
            sufijo = "" if confianza == "alta" else " (probable)"
            self._log(f"均衡 {nombre} → {banco}{sufijo}", 'info')
            # Si el combo está en "auto" o vacío, pre-seleccionar
            if self.banco_var.get() in ("— auto —", ""):
                self.banco_var.set(banco)
        else:
            self._log(f"❓ {nombre} → banco no detectado, seleccioná manualmente", 'warn')

    def _convertir_datos_legados(self, datos_raw, nombre_banco) -> DatosExtracto:
        """Convierte el diccionario de los parsers antiguos a DatosExtracto."""
        movs = []
        for m in datos_raw.get('movimientos', []):
            movs.append(Movimiento(
                fecha=m['fecha'],
                concepto=m['concepto'],
                debito=m.get('debito', 0.0),
                credito=m.get('credito', 0.0),
                descripcion=m.get('descripcion', ''),
                tipo=m.get('tipo', 'OTRO')
            ))
        return DatosExtracto(
            banco=nombre_banco,
            titular=datos_raw.get('titular', ''),
            movimientos=movs,
            saldo_anterior=datos_raw.get('saldo_anterior', 0.0),
            saldo_final=datos_raw.get('saldo_final', 0.0)
        )

    # ─── Conciliación ─────────────────────────────────────────────────────────

    def _conciliar(self):
        if self.lista_extractos.vacia():
            messagebox.showwarning("Atención", "Agregá al menos un extracto bancario.")
            return
        if self.lista_mayores.vacia():
            messagebox.showwarning("Atención", "Agregá al menos un mayor contable.")
            return

        self.btn.configure(state='disabled')
        self.progress.start(10)
        thread = threading.Thread(target=self._proceso, daemon=True)
        thread.start()

    def _proceso(self):
        try:
            # ── 1. Leer todos los extractos ───────────────────────────────────
            self._log("─" * 55)
            self._log("📂 Leyendo extractos bancarios...", 'info')
            lista_datos_banco = []

            banco_lote = None
            for ruta in self.lista_extractos.rutas():
                b_det, _ = detectar_banco_con_confianza(ruta)
                if b_det:
                    banco_lote = b_det
                    break

            for ruta in self.lista_extractos.rutas():
                nombre = os.path.basename(ruta)
                
                # 1. Detectar banco
                banco_detectado = detectar_banco_con_confianza(ruta)[0]
                banco_final = banco_detectado or banco_lote or self.banco_var.get()
                
                if banco_final == "— auto —":
                    self._log(f"   {nombre} -> No se pudo determinar el banco. Saltando.", 'error')
                    continue

                # 2. Intentar obtener parser refactorizado (Factory)
                parser = FabricaParsers.obtener_parser(banco_final)
                
                if parser:
                    datos = parser.parse(ruta)
                elif banco_final == "Banco Santander":
                    # Si no hay parser en factory pero es Santander, algo falló en factory
                    # pero lo intentamos instanciar directo como última opción
                    datos = SantanderParser().parse(ruta)
                else:
                    # 3. Fallback a parsers legados
                    parse_func = PARSERS_BANCO.get(banco_final)
                    if parse_func:
                        self._log(f"   {nombre} -> Usando parser legado para {banco_final}", 'warn')
                        datos_raw = parse_func(ruta)
                        datos = self._convertir_datos_legados(datos_raw, banco_final)
                    else:
                        self._log(f"   {nombre} -> No hay parser disponible para {banco_final}", 'error')
                        continue
                
                self._log(
                    f"   {nombre}  [{datos.banco}]  "
                    f"→ {len(datos.movimientos)} movs  "
                    f"SA: ${datos.saldo_anterior:,.2f}  "
                    f"SF: ${datos.saldo_final:,.2f}")
                lista_datos_banco.append(datos)

            # Combinar todos los extractos en uno solo
            datos_combinados = combinar_extractos(lista_datos_banco)
            total_movs_banco = len(datos_combinados.movimientos)
            self._log(f"   Total combinado: {total_movs_banco} movimientos", 'ok')

            # ── 2. Leer todos los mayores ─────────────────────────────────────
            self._log("📊 Leyendo mayores contables...", 'info')
            lista_movs_sistema = []

            for ruta in self.lista_mayores.rutas():
                nombre = os.path.basename(ruta)
                movs = parsear_excel(ruta)
                self._log(f"   {nombre}  → {len(movs)} movimientos")
                lista_movs_sistema.append(movs)

            movs_sistema = combinar_mayores(lista_movs_sistema)
            self._log(f"   Total combinado: {len(movs_sistema)} movimientos", 'ok')

            # ── 3. Conciliar ──────────────────────────────────────────────────
            self._log(f"🔄 Conciliando (Multipasada Automática)...", 'info')
            motor = MotorConciliacion()
            resultado = motor.conciliar(
                datos_combinados,
                movs_sistema,
            )

            # Resumen
            conc      = resultado.conciliados
            n_conc    = len(conc)
            n_diff    = sum(1 for c in conc if c.estado == 'CON_DIFERENCIA')
            
            # Contar diferencias de días significativas
            n_dias = 0
            for c in conc:
                if c.banco and c.sistema:
                    diff_dias = abs((c.banco.fecha - c.sistema.fecha).days)
                    if diff_dias > 15:
                        n_dias += 1

            n_banco   = len(resultado.solo_banco)
            n_sist    = len(resultado.solo_sistema)
            n_gastos  = len(resultado.gastos_por_categoria)

            self._log(f"   ✅ {n_conc} pares conciliados", 'ok')
            if n_dias:
                self._log(f"   ⏱  {n_dias} cruzados con >15 días de diferencia (cheques diferidos / registración tardía)", 'warn')
            if n_diff:
                self._log(f"   ⚠  {n_diff} con diferencia de monto", 'warn')
            if n_banco:
                self._log(f"   ⚠  {n_banco} solo en banco (sin contrapartida en sistema)", 'warn')
            if n_sist:
                self._log(f"   ⚠  {n_sist} solo en sistema (sin contrapartida en banco)", 'warn')
            self._log(f"   📋 {n_gastos} tipos de gastos bancarios discriminados")

            # Desglose de pasadas
            resumen_pasadas = getattr(resultado, 'resumen_pasadas', {})
            for pasada, cant in resumen_pasadas.items():
                self._log(f"      {pasada}: {cant} items")

            # ── 4. Guardar ────────────────────────────────────────────────────
            movs_banco = datos_combinados.movimientos
            if movs_banco:
                meses_es = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                            'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
                fechas = sorted(m.fecha for m in movs_banco)
                f0, f1 = fechas[0], fechas[-1]
                if f0.month == f1.month and f0.year == f1.year:
                    periodo = f"{meses_es[f0.month]}{f0.year}"
                else:
                    periodo = f"{meses_es[f1.month]}{f1.year}" # Simplificado
            else:
                periodo = "SinFecha"

            banco_label = (datos_combinados.titular or 
                           self.banco_var.get().replace(' ', '').replace('—', ''))
            
            # Limpiar caracteres inválidos para Windows
            banco_label = re.sub(r'[\\/*?:"<>|]', '_', banco_label)
            periodo = re.sub(r'[\\/*?:"<>|]', '_', periodo)
            
            nombre_sug = f"Conciliacion_{banco_label}_{periodo}.xlsx"
            dir_ini = os.path.dirname(self.lista_extractos.rutas()[0])

            self._resultado_temp = {
                'resultado':           resultado,
                'datos_banco':         datos_combinados,
                'movs_sistema':        movs_sistema,
                'periodo':             periodo,
                'nombre_sugerido':     nombre_sug,
                'directorio_inicial':  dir_ini,
                'n_conc': n_conc, 'n_diff': n_diff,
                'n_banco': n_banco, 'n_sist': n_sist, 'n_gastos': n_gastos,
            }
            self.root.after(0, self._pedir_guardar)

        except Exception as e:
            import traceback
            self._log(f"❌ {e}", 'error')
            self._log(traceback.format_exc(), 'error')
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, self._finalizar)

    def _pedir_guardar(self):
        t = self._resultado_temp
        ruta = filedialog.asksaveasfilename(
            title="Guardar conciliación",
            initialdir=t['directorio_inicial'],
            initialfile=t['nombre_sugerido'],
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")]
        )
        if not ruta:
            self._log("⚠ Guardado cancelado", 'warn')
            self._finalizar()
            return
        try:
            generar_excel(
                t['resultado'],
                t['datos_banco'],
                ruta,
                t['periodo'],
                t['movs_sistema'],
            )
            self._log(f"✅ Guardado: {os.path.basename(ruta)}", 'ok')
            self._log("─" * 55)

            messagebox.showinfo(
                "Conciliación exitosa",
                f"Archivo guardado:\n{ruta}\n\n"
                f"• {t['n_conc']} pares conciliados\n"
                f"• {t['n_gastos']} tipos de gastos\n"
                f"• {t['n_diff']} diferencias de monto\n"
                f"• {t['n_banco']} solo en banco / {t['n_sist']} solo en sistema"
            )
            if os.name == 'nt':
                os.startfile(os.path.dirname(ruta))
        except Exception as e:
            self._log(f"❌ Error al guardar: {e}", 'error')
            messagebox.showerror("Error", str(e))
        finally:
            self._finalizar()

    def _finalizar(self):
        self.progress.stop()
        self.btn.configure(state='normal')


if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()
