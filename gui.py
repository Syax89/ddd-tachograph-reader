import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import json
import os
from ddd_parser import TachoParser

# Impostazioni Tema Aurora ✨
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Aurora DDD Reader ✨ - Tachograph Analytics")
        self.geometry("1000x700")

        # Configurazione Grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="DDD READER", font=ctk.CTkFont(size=22, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        self.open_button = ctk.CTkButton(self.sidebar_frame, text="Carica File .ddd", command=self.open_file, height=40)
        self.open_button.grid(row=1, column=0, padx=20, pady=10)

        self.export_button = ctk.CTkButton(self.sidebar_frame, text="Esporta JSON", command=self.export_json, state="disabled", fg_color="transparent", border_width=1)
        self.export_button.grid(row=2, column=0, padx=20, pady=10)

        self.info_box = ctk.CTkTextbox(self.sidebar_frame, width=180, height=200, font=ctk.CTkFont(size=12))
        self.info_box.grid(row=3, column=0, padx=20, pady=20)
        self.info_box.insert("0.0", "INFO MEZZO:\n\nIn attesa di file...")

        # --- Main View ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(self.main_frame, text="Cronologia Viaggi Rilevati", font=ctk.CTkFont(size=18, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Tabella (Treeview)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.map("Treeview", background=[('selected', '#1f538d')])

        self.tree = ttk.Treeview(self.main_frame, columns=("Data", "Inizio", "Fine", "Targa", "KM Inizio", "KM Fine", "Distanza"), show='headings')
        self.tree.heading("Data", text="Data")
        self.tree.heading("Inizio", text="Inizio")
        self.tree.heading("Fine", text="Fine")
        self.tree.heading("Targa", text="Targa")
        self.tree.heading("KM Inizio", text="KM Inizio")
        self.tree.heading("KM Fine", text="KM Fine")
        self.tree.heading("Distanza", text="KM Totali")
        
        for col in self.tree["columns"]:
            self.tree.column(col, width=120, anchor="center")

        self.tree.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")
        
        self.current_data = None

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("DDD Files", "*.ddd"), ("All Files", "*.*")])
        if path:
            parser = TachoParser(path)
            data = parser.parse()
            if data:
                self.current_data = data
                self.update_ui(data)
                messagebox.showinfo("Completato", f"Analisi di {os.path.basename(path)} completata!")
            else:
                messagebox.showerror("Errore", "Impossibile leggere il file.")

    def update_ui(self, data):
        # Update Info Box
        self.info_box.delete("0.0", "end")
        info_text = f"GENERAZIONE: {data['metadata']['generation']}\n"
        info_text += f"VIN: {data['vehicle']['vin']}\n"
        info_text += f"TARGA: {data['vehicle']['plate']}\n"
        info_text += f"CARTA: {data['driver']['card_number']}\n"
        self.info_box.insert("0.0", info_text)

        # Clear and Update Table
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for trip in data['trips']:
            self.tree.insert("", "end", values=(
                trip['data'], trip['inizio'], trip['fine'], 
                trip['targa'], trip['km_inizio'], trip['km_fine'], 
                f"{trip['distanza']} km"
            ))
        
        self.export_button.configure(state="normal")

    def export_json(self):
        if self.current_data:
            path = filedialog.asksaveasfilename(defaultextension=".json")
            if path:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_data, f, indent=4, ensure_ascii=False)
                messagebox.showinfo("Esportazione", "File salvato correttamente!")

if __name__ == "__main__":
    app = App()
    app.mainloop()
