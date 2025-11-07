import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# ============================================================
# CONFIGURAZIONE APP
# ============================================================
st.set_page_config(page_title="Magazzino Farmaceutico AFIR", page_icon="💊", layout="wide")
st.title("💊 Magazzino Farmaceutico AFIR")
st.markdown("Benvenuto nel gestionale **AFIR Magazzino Farmaceutico**. "
            "Registra i farmaci con posologia e scadenze, controlla le prescrizioni e ricevi avvisi su scadenze e riordini.")

# ============================================================
# DATABASE SETUP
# ============================================================
def init_db():
    conn = sqlite3.connect("db_magazzino.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS farmaci (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT,
                    quantita INTEGER,
                    scadenza TEXT,
                    posologia TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS prescrizioni (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paziente TEXT,
                    farmaco TEXT,
                    dose TEXT,
                    frequenza TEXT,
                    data_prescrizione TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

# ============================================================
# FUNZIONI DI UTILITÀ
# ============================================================
def carica_farmaci():
    conn = sqlite3.connect("db_magazzino.db")
    df = pd.read_sql_query("SELECT * FROM farmaci", conn)
    conn.close()
    return df

def salva_farmaco(nome, quantita, scadenza, posologia):
    conn = sqlite3.connect("db_magazzino.db")
    c = conn.cursor()
    c.execute("INSERT INTO farmaci (nome, quantita, scadenza, posologia) VALUES (?, ?, ?, ?)",
              (nome, quantita, scadenza, posologia))
    conn.commit()
    conn.close()

def salva_prescrizione(paziente, farmaco, dose, frequenza, data_prescrizione):
    conn = sqlite3.connect("db_magazzino.db")
    c = conn.cursor()
    c.execute("INSERT INTO prescrizioni (paziente, farmaco, dose, frequenza, data_prescrizione) VALUES (?, ?, ?, ?, ?)",
              (paziente, farmaco, dose, frequenza, data_prescrizione))
    conn.commit()
    conn.close()

def carica_prescrizioni():
    conn = sqlite3.connect("db_magazzino.db")
    df = pd.read_sql_query("SELECT * FROM prescrizioni", conn)
    conn.close()
    return df

# ============================================================
# PAGINE DELL'APP
# ============================================================
def home():
    st.subheader("🏠 Home")
    st.info("Usa il menu a sinistra per navigare tra le funzioni dell’app.")

def aggiungi_farmaco():
    st.subheader("➕ Aggiungi Farmaco")
    with st.form("aggiungi_farmaco_form"):
        nome = st.text_input("Nome farmaco")
        quantita = st.number_input("Quantità disponibile", min_value=0, step=1)
        scadenza = st.date_input("Data di scadenza", format="DD/MM/YYYY")
        posologia = st.text_area("Posologia (es. 1 compressa ogni 8 ore)")
        submitted = st.form_submit_button("Salva farmaco")
        if submitted:
            scadenza_str = scadenza.strftime("%d/%m/%Y")
            salva_farmaco(nome, quantita, scadenza_str, posologia)
            st.success(f"✅ Farmaco '{nome}' aggiunto correttamente!")

def prescrizioni():
    st.subheader("📋 Prescrizioni")
    with st.form("prescrizione_form"):
        paziente = st.text_input("Nome paziente")
        farmaco = st.text_input("Farmaco prescritto")
        dose = st.text_input("Dose (es. 500 mg)")
        frequenza = st.text_input("Frequenza (es. 2 volte al giorno)")
        data_prescrizione = st.date_input("Data prescrizione", format="DD/MM/YYYY")
        submitted = st.form_submit_button("Salva prescrizione")
        if submitted:
            data_str = data_prescrizione.strftime("%d/%m/%Y")
            salva_prescrizione(paziente, farmaco, dose, frequenza, data_str)
            st.success(f"💊 Prescrizione per {paziente} registrata con successo.")

    df = carica_prescrizioni()
    if not df.empty:
        df["data_prescrizione"] = pd.to_datetime(df["data_prescrizione"], errors="coerce")
        df["data_prescrizione"] = df["data_prescrizione"].dt.strftime("%d/%m/%Y")
        st.dataframe(df)
    else:
        st.info("Nessuna prescrizione registrata.")

def elenco_farmaci():
    st.subheader("📦 Elenco Farmaci in Magazzino")
    df = carica_farmaci()
    if df.empty:
        st.warning("Nessun farmaco presente nel magazzino.")
        return
    # Converte in data e calcola giorni alla scadenza
    df["Scadenza"] = pd.to_datetime(df["scadenza"], errors="coerce", dayfirst=True)
    oggi = pd.Timestamp.now()
    df["Giorni alla scadenza"] = (df["Scadenza"] - oggi).dt.days
    df["Scadenza"] = df["Scadenza"].dt.strftime("%d/%m/%Y")
    df = df.rename(columns={"nome": "Nome", "quantita": "Quantità", "posologia": "Posologia"})
    st.dataframe(df[["Nome", "Quantità", "Scadenza", "Giorni alla scadenza", "Posologia"]])

def avvisi():
    st.subheader("⏰ Avvisi e Scadenze")
    df = carica_farmaci()
    if df.empty:
        st.info("Nessun farmaco registrato.")
        return
    df["Scadenza"] = pd.to_datetime(df["scadenza"], errors="coerce", dayfirst=True)
    oggi = pd.Timestamp.now()
    df["Giorni alla scadenza"] = (df["Scadenza"] - oggi).dt.days
    scadenza_vicina = df[df["Giorni alla scadenza"] <= 30]
    if scadenza_vicina.empty:
        st.success("✅ Nessun farmaco in scadenza nei prossimi 30 giorni.")
    else:
        st.warning("⚠️ Attenzione! Farmaci in scadenza:")
        scadenza_vicina["Scadenza"] = scadenza_vicina["Scadenza"].dt.strftime("%d/%m/%Y")
        st.dataframe(scadenza_vicina[["nome", "quantita", "Scadenza", "Giorni alla scadenza"]])

# ============================================================
# MENU PRINCIPALE
# ============================================================
def main():
    menu = ["🏠 Home", "➕ Aggiungi farmaco", "📋 Prescrizioni", "📦 Elenco farmaci", "⏰ Avvisi"]
    scelta = st.sidebar.radio("Naviga", menu)
    if scelta == "🏠 Home":
        home()
    elif scelta == "➕ Aggiungi farmaco":
        aggiungi_farmaco()
    elif scelta == "📋 Prescrizioni":
        prescrizioni()
    elif scelta == "📦 Elenco farmaci":
        elenco_farmaci()
    elif scelta == "⏰ Avvisi":
        avvisi()

if __name__ == "__main__":
    main()

