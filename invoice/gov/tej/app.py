import tkinter as tk
from tkinter import filedialog, messagebox
import os 
from excel_val import load_excel,split_valid_invalid_rows
from builder import build_xml_from_dataframe

def run_pipeline():
    if not excel_path.get():
        messagebox.showerror("Error", "Please select an Excel file")
        return

    try:
        base_dir = os.path.dirname(excel_path.get())

        df = load_excel(excel_path.get())
        valid_df, error_df = split_valid_invalid_rows(df)

        if not error_df.empty:
            error_df.to_excel(os.path.join(base_dir, "errors.xlsx"), index=False)

        if valid_df.empty:
            messagebox.showerror("Error", "No valid rows found")
            return

        build_xml_from_dataframe(valid_df, os.path.join(base_dir, "output.xml"))

        messagebox.showinfo(
            "Success",
            "XML generated successfully.\n"
            + ("Errors file created." if not error_df.empty else "No errors found.")
        )

    except Exception as e:
        messagebox.showerror("Failure", str(e))


def browse_file():
    file = filedialog.askopenfilename(
        filetypes=[("Excel files", "*.xlsx")]
    )
    if file:
        excel_path.set(file)

# ================= UI =================

root = tk.Tk()
root.title("RS Excel → XML Generator")
root.geometry("500x180")
root.resizable(False, False)

excel_path = tk.StringVar()

tk.Label(root, text="Excel file:").pack(pady=10)
tk.Entry(root, textvariable=excel_path, width=60).pack()
tk.Button(root, text="Browse", command=browse_file).pack(pady=5)
tk.Button(root, text="Generate XML", command=run_pipeline).pack(pady=15)

root.mainloop()