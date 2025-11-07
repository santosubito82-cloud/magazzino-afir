import sqlite3

conn = sqlite3.connect("db_magazzino.db")
c = conn.cursor()
c.execute("ALTER TABLE farmaci ADD COLUMN note TEXT")
conn.commit()
conn.close()

print("Colonna 'note' aggiunta con successo.")
