# flet_app/main.py
import sqlite3
import flet as ft
from datetime import datetime
import os

DB_PATH = os.path.join(os.getcwd(), "bank_app.db")

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS banks (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            bank_id INTEGER,
            balance REAL DEFAULT 0,
            FOREIGN KEY (bank_id) REFERENCES banks (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            bank_id INTEGER,
            amount REAL,
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (bank_id) REFERENCES banks (id)
        )
    ''')
    conn.commit()
    return conn

def seed_db(conn):
    c = conn.cursor()
    bank_names = ["paypal", "paysera", "moneco", "n26", "myfine", "bankera", "paypal_bus", "western", "remitly"]
    user_names = ["abdallah", "abir", "hamza", "safia", "aymen", "rania", "khadidja"]

    # Only seed if banks table is empty (avoid deleting data on each restart)
    c.execute('SELECT COUNT(*) FROM banks')
    if c.fetchone()[0] == 0:
        for bank_name in bank_names:
            c.execute('INSERT INTO banks (name) VALUES (?)', (bank_name,))
        # create users for each bank with an initial balance
        c.execute('SELECT id FROM banks')
        bank_ids = [row[0] for row in c.fetchall()]
        for bank_id in bank_ids:
            for user_name in user_names:
                c.execute('INSERT INTO users (name, bank_id, balance) VALUES (?, ?, ?)', (user_name, bank_id, 100.0))
        conn.commit()

# initialize
conn = init_db()
seed_db(conn)

def main(page: ft.Page):
    page.title = "E-Services Banque"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.padding = 20

    msg = ft.Text(value="", selectable=True)

    def reset_transactions():
        today = datetime.today()
        if today.day == 1:
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn_local:
                c = conn_local.cursor()
                c.execute('DELETE FROM transactions')
                conn_local.commit()

    def handle_withdraw(e):
        try:
            bank_name = bank_select.value
            user_name = user_select.value
            amount = float(amount_input.value)
        except Exception:
            msg.value = "Veuillez sélectionner banque/utilisateur et entrer un montant valide."
            page.update()
            return

        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn_local:
            c = conn_local.cursor()
            c.execute('SELECT id FROM banks WHERE name = ?', (bank_name,))
            row = c.fetchone()
            if not row:
                msg.value = "Banque introuvable."
                page.update()
                return
            bank_id = row[0]

            c.execute('SELECT id, balance FROM users WHERE name = ? AND bank_id = ?', (user_name, bank_id))
            user = c.fetchone()
            if user:
                user_id, balance = user
                new_balance = balance - amount
                c.execute('UPDATE users SET balance = ? WHERE id = ?', (new_balance, user_id))
                c.execute('INSERT INTO transactions (user_id, bank_id, amount, date) VALUES (?, ?, ?, ?)',
                          (user_id, bank_id, amount, datetime.now().isoformat()))
                conn_local.commit()

                c.execute('SELECT SUM(amount) FROM transactions WHERE user_id = ? AND bank_id = ?', (user_id, bank_id))
                total_withdrawn = c.fetchone()[0] or 0.0

                msg.value = (f"Vous avez retiré {amount:.2f} euros de la banque '{bank_name}'. "
                             f"Total retiré ce mois-ci: {total_withdrawn:.2f} euros. "
                             f"Nouveau solde: {new_balance:.2f} €")
            else:
                msg.value = "Utilisateur introuvable."

        page.update()

    # reset monthly transactions if day==1 (non-blocking)
    reset_transactions()

    # fetch banks and users for selects
    c = conn.cursor()
    c.execute('SELECT name FROM banks')
    bank_names = [row[0] for row in c.fetchall()]

    # For users, query users of selected bank dynamically; for simplicity keep static list here
    # (We will update user list when bank changes)
    user_names_all = ["abdallah", "abir", "hamza", "safia", "aymen", "rania", "khadidja"]

    bank_select = ft.Dropdown(
        label="Choisir la banque",
        options=[ft.dropdown.Option(name) for name in bank_names],
        width=300
    )

    user_select = ft.Dropdown(
        label="Choisir l'utilisateur",
        options=[ft.dropdown.Option(name) for name in user_names_all],
        width=300
    )

    amount_input = ft.TextField(label="Montant à retirer", width=200, value="0")
    withdraw_button = ft.ElevatedButton(text="Retirer", on_click=handle_withdraw)

    def on_bank_change(e):
        # Optional: if you want to dynamically load users for selected bank, implement here.
        pass

    bank_select.on_change = on_bank_change

    page.add(
        ft.Column([
            ft.Row([bank_select, user_select], alignment=ft.MainAxisAlignment.START),
            ft.Row([amount_input, withdraw_button], alignment=ft.MainAxisAlignment.START),
            msg,
            ft.Divider(),
            ft.Text("Transactions récentes (dernières 10):"),
        ])
    )

    # show last 10 transactions
    def load_transactions():
        with sqlite3.connect(DB_PATH, check_same_thread=False) as c_conn:
            cur = c_conn.cursor()
            cur.execute('''
                SELECT t.id, u.name, b.name, t.amount, t.date
                FROM transactions t
                JOIN users u ON u.id = t.user_id
                JOIN banks b ON b.id = t.bank_id
                ORDER BY t.date DESC LIMIT 10
            ''')
            rows = cur.fetchall()
        return rows

    trans_rows = load_transactions()
    for tr in trans_rows:
        tid, uname, bname, amt, date = tr
        page.add(ft.Text(f"{date} — {uname} @ {bname} — {amt:.2f} €"))

    page.update()

# Run Flet as web app (suitable for Render/Railway)
if __name__ == "__main__":
    ft.app(target=main, view=ft.WEB_BROWSER, port=int(os.environ.get("PORT", 8080)), host="0.0.0.0")
