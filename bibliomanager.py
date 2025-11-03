
import sqlite3
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

db = sqlite3.connect("bibliomanager.db")
db.execute("PRAGMA foreign_keys = ON")

db.execute("""
CREATE TABLE IF NOT EXISTS Books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    total_copies INTEGER NOT NULL CHECK(total_copies >= 0),
    available_copies INTEGER NOT NULL CHECK(available_copies >= 0)
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS Members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS Loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    loan_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    return_date TEXT,
    FOREIGN KEY(book_id) REFERENCES Books(id),
    FOREIGN KEY(member_id) REFERENCES Members(id)
)
""")
db.commit()

# =========================
# Fonctions de manipulation
# =========================
# --- Livres ---
def add_book(title, author, total):
    total = int(total)
    if total < 0:
        raise ValueError("total_copies doit être ≥ 0")
    db.execute("INSERT INTO Books(title, author, total_copies, available_copies) VALUES(?,?,?,?)",
               (title.strip(), author.strip(), total, total))
    db.commit()

def update_book(book_id, title, author, total):
    total = int(total)
    cur = db.execute("SELECT available_copies FROM Books WHERE id=?", (book_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError("Livre introuvable")
    available = row[0]
    if total < available:
        available = total  # garder la cohérence
    db.execute("UPDATE Books SET title=?, author=?, total_copies=?, available_copies=? WHERE id=?",
               (title.strip(), author.strip(), total, available, book_id))
    db.commit()

def delete_book(book_id):
    cur = db.execute("SELECT COUNT(*) FROM Loans WHERE book_id=? AND return_date IS NULL", (book_id,))
    if cur.fetchone()[0] > 0:
        raise ValueError("Impossible: livre référencé par un prêt en cours.")
    db.execute("DELETE FROM Books WHERE id=?", (book_id,))
    db.commit()

def list_books(search=""):
    like = f"%{(search or '').strip()}%"
    cur = db.execute(
        "SELECT id, title, author, total_copies, available_copies "
        "FROM Books WHERE title LIKE ? OR author LIKE ? ORDER BY id DESC",
        (like, like)
    )
    return cur.fetchall()

# --- Membres ---
def add_member(name, phone):
    name = name.strip()
    phone = (phone or "").strip()
    if not name:
        raise ValueError("Nom obligatoire.")
    db.execute("INSERT INTO Members(name, phone) VALUES(?,?)", (name, phone))
    db.commit()

def update_member(member_id, name, phone):
    db.execute("UPDATE Members SET name=?, phone=? WHERE id=?", (name.strip(), (phone or "").strip(), member_id))
    db.commit()

def delete_member(member_id):
    cur = db.execute("SELECT COUNT(*) FROM Loans WHERE member_id=? AND return_date IS NULL", (member_id,))
    if cur.fetchone()[0] > 0:
        raise ValueError("Impossible: membre avec prêt en cours.")
    db.execute("DELETE FROM Members WHERE id=?", (member_id,))
    db.commit()

def list_members(search=""):
    like = f"%{(search or '').strip()}%"
    cur = db.execute(
        "SELECT id, name, phone FROM Members "
        "WHERE name LIKE ? OR IFNULL(phone,'') LIKE ? ORDER BY id DESC",
        (like, like)
    )
    return cur.fetchall()

# --- Prêts ---
def loan(book_id, member_id, days=14):
    days = int(days)
    cur = db.execute("SELECT available_copies FROM Books WHERE id=?", (book_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError("Livre introuvable")
    available = row[0]
    if available <= 0:
        raise ValueError("Aucun exemplaire disponible.")
    loan_date = datetime.now()
    due_date = loan_date + timedelta(days=days)
    db.execute("INSERT INTO Loans(book_id, member_id, loan_date, due_date, return_date) VALUES(?,?,?,?,NULL)",
               (book_id, member_id, loan_date.isoformat(), due_date.isoformat()))
    db.execute("UPDATE Books SET available_copies = available_copies - 1 WHERE id=?", (book_id,))
    db.commit()

def return_loan(loan_id):
    cur = db.execute("SELECT book_id, return_date FROM Loans WHERE id=?", (loan_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError("Prêt introuvable")
    book_id, ret = row
    if ret is not None:
        raise ValueError("Ce prêt est déjà retourné.")
    now = datetime.now().isoformat()
    db.execute("UPDATE Loans SET return_date=? WHERE id=?", (now, loan_id))
    db.execute("UPDATE Books SET available_copies = available_copies + 1 WHERE id=?", (book_id,))
    db.commit()

def list_open_loans():
    cur = db.execute(
        "SELECT L.id, B.title, M.name, L.loan_date, L.due_date "
        "FROM Loans L JOIN Books B ON B.id=L.book_id JOIN Members M ON M.id=L.member_id "
        "WHERE L.return_date IS NULL ORDER BY L.id DESC"
    )
    return cur.fetchall()

# =========================
# Interface Tkinter (3 onglets)
# =========================
def center(win, w=960, h=600):
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x, y = (sw - w) // 2, (sh - h) // 3
    win.geometry(f"{w}x{h}+{x}+{y}")

class BooksTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.title_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.total_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self._build()

    def _build(self):
        form = ttk.Frame(self); form.pack(fill="x", pady=6)
        ttk.Label(form, text="Titre").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.title_var, width=28).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Auteur").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.author_var, width=24).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Total").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.total_var, width=6).grid(row=0, column=5, padx=4)
        ttk.Button(form, text="Ajouter", command=self.add_book).grid(row=0, column=6, padx=4)
        ttk.Button(form, text="Modifier", command=self.update_selected).grid(row=0, column=7, padx=4)
        ttk.Button(form, text="Supprimer", command=self.delete_selected).grid(row=0, column=8, padx=4)

        search = ttk.Frame(self); search.pack(fill="x", pady=4)
        ttk.Label(search, text="Recherche (titre/auteur):").pack(side="left")
        ttk.Entry(search, textvariable=self.search_var, width=30).pack(side="left", padx=4)
        ttk.Button(search, text="Rechercher", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(search, text="Tout", command=self.clear_search).pack(side="left")

        cols = ("id", "title", "author", "total", "available")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for c, t in zip(cols, ("ID", "Titre", "Auteur", "Total", "Dispo")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=150 if c in ("id","total","available") else 220, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.refresh()

    def clear_search(self):
        self.search_var.set("")
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in list_books(self.search_var.get()):
            self.tree.insert("", "end", values=row)

    def _read_inputs(self):
        title = self.title_var.get().strip()
        author = self.author_var.get().strip()
        total = self.total_var.get().strip() or "0"
        if not title or not author:
            raise ValueError("Titre et Auteur obligatoires.")
        int(total)  # validation
        return title, author, total

    def add_book(self):
        try:
            title, author, total = self._read_inputs()
            add_book(title, author, total)
            self.title_var.set(""); self.author_var.set(""); self.total_var.set("")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def update_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sélection", "Choisissez un livre."); return
        book_id = int(self.tree.item(sel[0], "values")[0])
        try:
            title, author, total = self._read_inputs()
            update_book(book_id, title, author, total)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sélection", "Choisissez un livre."); return
        book_id = int(self.tree.item(sel[0], "values")[0])
        if not messagebox.askyesno("Confirmer", "Supprimer ce livre ?"): return
        try:
            delete_book(book_id); self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

class MembersTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.name_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self._build()

    def _build(self):
        form = ttk.Frame(self); form.pack(fill="x", pady=6)
        ttk.Label(form, text="Nom").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.name_var, width=28).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Téléphone").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.phone_var, width=20).grid(row=0, column=3, padx=4)
        ttk.Button(form, text="Ajouter", command=self.add_member).grid(row=0, column=4, padx=4)
        ttk.Button(form, text="Modifier", command=self.update_selected).grid(row=0, column=5, padx=4)
        ttk.Button(form, text="Supprimer", command=self.delete_selected).grid(row=0, column=6, padx=4)

        search = ttk.Frame(self); search.pack(fill="x", pady=4)
        ttk.Label(search, text="Recherche (nom/téléphone):").pack(side="left")
        ttk.Entry(search, textvariable=self.search_var, width=30).pack(side="left", padx=4)
        ttk.Button(search, text="Rechercher", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(search, text="Tout", command=self.clear_search).pack(side="left")

        cols = ("id", "name", "phone")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for c, t in zip(cols, ("ID", "Nom", "Téléphone")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=160 if c != "name" else 240, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.refresh()

    def clear_search(self):
        self.search_var.set("")
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in list_members(self.search_var.get()):
            self.tree.insert("", "end", values=row)

    def _read_inputs(self):
        name = self.name_var.get().strip()
        phone = self.phone_var.get().strip()
        if not name:
            raise ValueError("Nom obligatoire.")
        return name, phone

    def add_member(self):
        try:
            name, phone = self._read_inputs()
            add_member(name, phone)
            self.name_var.set(""); self.phone_var.set("")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def update_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sélection", "Choisissez un membre."); return
        member_id = int(self.tree.item(sel[0], "values")[0])
        try:
            name, phone = self._read_inputs()
            update_member(member_id, name, phone)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sélection", "Choisissez un membre."); return
        member_id = int(self.tree.item(sel[0], "values")[0])
        if not messagebox.askyesno("Confirmer", "Supprimer ce membre ?"): return
        try:
            delete_member(member_id); self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

class LoansTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.book_id_var = tk.StringVar()
        self.member_id_var = tk.StringVar()
        self.days_var = tk.StringVar(value="14")
        self._build()

    def _build(self):
        top = ttk.Frame(self); top.pack(fill="x", pady=6)
        ttk.Label(top, text="Livre (ID)").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.book_id_var, width=8).grid(row=0, column=1, padx=4)
        ttk.Label(top, text="Membre (ID)").grid(row=0, column=2, sticky="w")
        ttk.Entry(top, textvariable=self.member_id_var, width=8).grid(row=0, column=3, padx=4)
        ttk.Label(top, text="Jours").grid(row=0, column=4, sticky="w")
        ttk.Entry(top, textvariable=self.days_var, width=6).grid(row=0, column=5, padx=4)
        ttk.Button(top, text="Emprunter", command=self.make_loan).grid(row=0, column=6, padx=6)
        ttk.Button(top, text="Retourner", command=self.return_selected).grid(row=0, column=7, padx=6)
        ttk.Button(top, text="Rafraîchir", command=self.refresh).grid(row=0, column=8, padx=6)

        ttk.Label(self, text="Astuce : regardez les onglets Livres/Membres pour trouver les IDs.").pack(fill="x", pady=2)

        cols = ("id","title","member","loan_date","due_date")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for c, t in zip(cols, ("ID Prêt", "Livre", "Membre", "Date prêt", "Échéance")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=170 if c!="title" else 240, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in list_open_loans():
            self.tree.insert("", "end", values=row)

    def make_loan(self):
        try:
            book_id = int(self.book_id_var.get())
            member_id = int(self.member_id_var.get())
            days = int(self.days_var.get() or "14")
            loan(book_id, member_id, days)
            self.book_id_var.set(""); self.member_id_var.set("")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def return_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sélection", "Choisissez un prêt."); return
        loan_id = int(self.tree.item(sel[0], "values")[0])
        if not messagebox.askyesno("Confirmer", "Marquer ce prêt comme retourné ?"): return
        try:
            return_loan(loan_id); self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

# ==============
# Lancement UI
# ==============
def on_close(root):
    try:
        db.close()
    finally:
        root.destroy()

def main():
    root = tk.Tk()
    root.title("Biblio Simple — Tkinter + SQLite")
    center(root, 1000, 620)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    nb.add(BooksTab(nb), text="Livres")
    nb.add(MembersTab(nb), text="Membres")
    nb.add(LoansTab(nb), text="Prêts")

    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))
    root.mainloop()

if __name__ == "__main__":
    main()
