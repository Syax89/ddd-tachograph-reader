import customtkinter as ctk
from tkinter import filedialog, messagebox
import json
import os
from main import parse_ddd

# Impostazioni tema
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DDD Tachograph Reader ✨")
        self.geometry("800x600")

        # Layout Grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="DDD Reader", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.open_button = ctk.CTkButton(self.sidebar_frame, text="Apri File .ddd", command=self.open_file)
        self.open_button.grid(row=1, column=0, padx=20, pady=10)

        self.save_button = ctk.CTkButton(self.sidebar_frame, text="Salva JSON", command=self.save_json, state="disabled")
        self.save_button.grid(row=2, column=0, padx=20, pady=10)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Tema:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 20))
        self.appearance_mode_optionemenu.set("Dark")

        # Main Content Area
        self.textbox = ctk.CTkTextbox(self, width=600)
        self.textbox.grid(row=0, column=1, padx=(20, 20), pady=(20, 20), sticky="nsew")
        self.textbox.insert("0.0", "Benvenuto!\n\nSeleziona un file .ddd dalla barra laterale per iniziare il parsing.")

        self.current_data = None

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("DDD Files", "*.ddd"), ("All Files", "*.*")])
        if file_path:
            try:
                data = parse_ddd(file_path)
                if data:
                    self.current_data = data
                    self.textbox.delete("0.0", "end")
                    self.textbox.insert("0.0", json.dumps(data, indent=4))
                    self.save_button.configure(state="normal")
                    messagebox.showinfo("Successo", f"File {os.path.basename(file_path)} caricato con successo!")
                else:
                    messagebox.showerror("Errore", "Impossibile leggere il file DDD.")
            except Exception as e:
                messagebox.showerror("Errore", f"Si è verificato un errore: {str(e)}")

    def save_json(self):
        if self.current_data:
            file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
            if file_path:
                with open(file_path, 'w') as f:
                    json.dump(self.current_data, f, indent=4)
                messagebox.showinfo("Successo", f"Dati salvati in {file_path}")

if __name__ == "__main__":
    app = App()
    app.mainloop()
