import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# =========================================================
# CONFIGURAZIONE DATABASE
# =========================================================
DB_NAME = "db_magazzino.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS farmaci (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            principio_attivo TEXT,
            quantita INTEGER DEFAULT 0,
            data_scadenza TEXT,
            posologia TEXT,
            giorni_durata INTEGER,
            note TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS prescrizioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paziente TEXT NOT NULL,
            farmaco_id INTEGER,
            data_prescrizione TEXT,
            piano_terapeutico TEXT,
            FOREIGN KEY (farmaco_id) REFERENCES farmaci(id)
        )
    """)
    conn.commit()
    conn.close()

def run_query(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def fetch_query(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# =========================================================
# FUNZIONI GESTIONALI
# =========================================================
def aggiungi_farmaco():
    st.header("➕ Aggiungi nuovo farmaco")
    nome = st.text_input("Nome commerciale *")
    principio = st.text_input("Principio attivo")
    quantita = st.number_input("Quantità disponibile", min_value=0, step=1)
    data_scadenza = st.date_input("Data di scadenza")
    posologia = st.text_input("Posologia (es. 2 volte al giorno)")
    giorni_durata = st.number_input("Durata trattamento (giorni)", min_value=0, step=1)
    note = st.text_area("Note (facoltative)")

    if st.button("Salva farmaco"):
        if nome:
            run_query(
                "INSERT INTO farmaci (nome, principio_attivo, quantita, data_scadenza, posologia, giorni_durata, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (nome, principio, quantita, str(data_scadenza), posologia, giorni_durata, note),
            )
            st.success(f"✅ Farmaco '{nome}' aggiunto correttamente!")
        else:
            st.error("❌ Inserisci almeno il nome del farmaco.")

def elenco_farmaci():
    st.header("📦 Elenco farmaci in magazzino")
    df = fetch_query("SELECT * FROM farmaci ORDER BY nome")
    if df.empty:
        st.info("Nessun farmaco presente.")
    else:
        # Avvisi scadenza
        oggi = datetime.now().date()
        df["Scadenza"] = pd.to_datetime(df["data_scadenza"]).dt.date
        df["Giorni alla scadenza"] = (df["Scadenza"] - oggi).dt.days
        df["⚠️ Avviso"] = df["Giorni alla scadenza"].apply(
            lambda x: "🟥 Scaduto" if x < 0 else ("🟧 In scadenza" if x <= 30 else "🟩 OK")
        )

        st.dataframe(df[["nome", "principio_attivo", "quantita", "Scadenza", "⚠️ Avviso", "posologia", "note"]])

def registra_prescrizione():
    st.header("📋 Registra consegna / prescrizione")
    df_farmaci = fetch_query("SELECT id, nome FROM farmaci WHERE quantita > 0")
    if df_farmaci.empty:
        st.warning("⚠️ Nessun farmaco disponibile.")
        return

    paziente = st.text_input("Nome paziente *")
    farmaco = st.selectbox("Farmaco *", df_farmaci["nome"])
    piano = st.text_area("Prescrizione o piano terapeutico *")
    data = datetime.now().strftime("%Y-%m-%d")

    if st.button("Registra consegna"):
        if paziente and piano:
            id_farmaco = df_farmaci.loc[df_farmaci["nome"] == farmaco, "id"].values[0]
            run_query(
                "INSERT INTO prescrizioni (paziente, farmaco_id, data_prescrizione, piano_terapeutico) VALUES (?, ?, ?, ?)",
                (paziente, id_farmaco, data, piano),
            )
            # Diminuisci quantità
            run_query("UPDATE farmaci SET quantita = quantita - 1 WHERE id = ?", (id_farmaco,))
            st.success(f"💊 Farmaco '{farmaco}' consegnato a {paziente}")
        else:
            st.error("Compila tutti i campi obbligatori.")

def avvisi_scadenza():
    st.header("⏰ Avvisi scadenza e riordino")
    df = fetch_query("SELECT * FROM farmaci")
    if df.empty:
        st.info("Nessun farmaco registrato.")
    else:
        oggi = datetime.now().date()
        df["Scadenza"] = pd.to_datetime(df["data_scadenza"]).dt.date
        scaduti = df[df["Scadenza"] < oggi]
        in_scadenza = df[(df["Scadenza"] >= oggi) & (df["Scadenza"] <= oggi + timedelta(days=30))]
        bassi = df[df["quantita"] <= 2]

        if not scaduti.empty:
            st.error("⚠️ Farmaci scaduti:")
            st.table(scaduti[["nome", "quantita", "data_scadenza"]])

        if not in_scadenza.empty:
            st.warning("⚠️ Farmaci in scadenza entro 30 giorni:")
            st.table(in_scadenza[["nome", "quantita", "data_scadenza"]])

        if not bassi.empty:
            st.info("ℹ️ Farmaci con scorte basse (≤2):")
            st.table(bassi[["nome", "quantita"]])

# =========================================================
# INTERFACCIA PRINCIPALE
# =========================================================
def main():
    st.set_page_config(page_title="Magazzino Farmaceutico AFIR", page_icon="💊", layout="wide")
    st.title("💊 Magazzino Farmaceutico AFIR")

    init_db()

    menu = st.sidebar.radio("Naviga", ["🏠 Home", "➕ Aggiungi farmaco", "📋 Prescrizioni", "📦 Elenco farmaci", "⏰ Avvisi"])

    if menu == "🏠 Home":
        st.write("""
        Benvenuto nel gestionale **AFIR Magazzino Farmaceutico**.
        - Registra i farmaci con posologia e scadenze  
        - Controlla le prescrizioni e i piani terapeutici  
        - Ricevi avvisi su scadenze e riordini automatici
        """)
    elif menu == "➕ Aggiungi farmaco":
        aggiungi_farmaco()
    elif menu == "📋 Prescrizioni":
        registra_prescrizione()
    elif menu == "📦 Elenco farmaci":
        elenco_farmaci()
    elif menu == "⏰ Avvisi":
        avvisi_scadenza()

if __name__ == "__main__":
    main()

    
