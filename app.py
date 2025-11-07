import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# =========================
# Configurazione pagina
# =========================
st.set_page_config(page_title="Magazzino Farmaceutico AFIR", page_icon="💊", layout="wide")
st.title("💊 Magazzino Farmaceutico AFIR")
st.markdown(
    "Benvenuto nel gestionale **AFIR Magazzino Farmaceutico**. "
    "- Registra farmaci con scadenze e giacenze, "
    "gestisci prescrizioni e consegne, e controlla gli avvisi."
)

DB_FILE = "db_magazzino.db"

# =========================
# Funzioni di inizializzazione / migrazione DB
# =========================
def get_db_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    """
    Crea le tabelle se non esistono e applica migrazioni minime
    per colonne mancanti (safe).
    """
    conn = get_db_conn()
    c = conn.cursor()

    # Tabella pazienti
    c.execute("""
        CREATE TABLE IF NOT EXISTS pazienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            cognome TEXT,
            codice_fiscale TEXT
        )
    """)

    # Tabella farmaci (schema canonico: scadenza come ISO YYYY-MM-DD)
    c.execute("""
        CREATE TABLE IF NOT EXISTS farmaci (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            principio_attivo TEXT,
            quantita INTEGER DEFAULT 0,
            scadenza TEXT,             -- ISO date YYYY-MM-DD
            posologia TEXT,
            note TEXT
        )
    """)

    # Tabella prescrizioni (collega paziente e farmaco)
    c.execute("""
        CREATE TABLE IF NOT EXISTS prescrizioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_paziente INTEGER,
            id_farmaco INTEGER,
            posologia TEXT,
            durata_giorni INTEGER,
            data_inizio TEXT,         -- ISO date YYYY-MM-DD
            piano_terapeutico TEXT,
            FOREIGN KEY(id_paziente) REFERENCES pazienti(id),
            FOREIGN KEY(id_farmaco) REFERENCES farmaci(id)
        )
    """)

    # Tabella consegne (storico consegne/dispense)
    c.execute("""
        CREATE TABLE IF NOT EXISTS consegne (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_prescrizione INTEGER,
            data_consegna TEXT,       -- ISO date YYYY-MM-DD
            quantita INTEGER,
            operatore TEXT,
            verifica_piano INTEGER DEFAULT 0,
            FOREIGN KEY(id_prescrizione) REFERENCES prescrizioni(id)
        )
    """)

    conn.commit()

    # Migrazione semplice: assicurati che colonne esistano (in caso DB vecchio)
    # Ottieni lista colonne per farmaci
    c.execute("PRAGMA table_info(farmaci)")
    cols_farmaci = [r[1] for r in c.fetchall()]
    if "note" not in cols_farmaci:
        try:
            c.execute("ALTER TABLE farmaci ADD COLUMN note TEXT")
            conn.commit()
        except Exception:
            pass  # se non possibile, ignoriamo (DB può essere ricreato manualmente)

    conn.close()

# Chiama init all'avvio
init_db()

# =========================
# Helper DB (esecuzioni sicure)
# =========================
def run_sql(query, params=()):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()

def fetch_df(query, params=()):
    conn = get_db_conn()
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

# =========================
# Utility date formatting
# =========================
def iso_to_display(iso_date):
    """Da 'YYYY-MM-DD' a 'dd/mm/YYYY' (gestisce None/NaT)."""
    if not iso_date or pd.isna(iso_date):
        return ""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        # prova a interpretare altri formati
        try:
            dt = pd.to_datetime(iso_date, dayfirst=False)
            return pd.to_datetime(dt).strftime("%d/%m/%Y")
        except Exception:
            return iso_date

def date_to_iso(dt_obj):
    """Da oggetto datetime.date -> 'YYYY-MM-DD'"""
    if not dt_obj:
        return ""
    try:
        return dt_obj.strftime("%Y-%m-%d")
    except Exception:
        return str(dt_obj)

# =========================
# Funzionalità: Pazienti
# =========================
def pagina_pazienti():
    st.header("👥 Pazienti")
    with st.form("form_paziente"):
        nome = st.text_input("Nome")
        cognome = st.text_input("Cognome")
        cf = st.text_input("Codice fiscale")
        submit = st.form_submit_button("Aggiungi paziente")
        if submit:
            if nome.strip() == "" and cognome.strip() == "":
                st.error("Inserisci almeno nome o cognome del paziente.")
            else:
                run_sql(
                    "INSERT INTO pazienti (nome, cognome, codice_fiscale) VALUES (?, ?, ?)",
                    (nome.strip(), cognome.strip(), cf.strip())
                )
                st.success("Paziente aggiunto.")

    df = fetch_df("SELECT id, nome, cognome, codice_fiscale FROM pazienti ORDER BY cognome, nome")
    if df.empty:
        st.info("Nessun paziente registrato.")
    else:
        st.dataframe(df)

# =========================
# Funzionalità: Farmaci
# =========================
def pagina_aggiungi_farmaco():
    st.header("➕ Aggiungi / Aggiorna Farmaco")
    with st.form("form_farmaco"):
        nome = st.text_input("Nome commerciale", key="f_nome")
        principio = st.text_input("Principio attivo", key="f_principio")
        quantita = st.number_input("Quantità in magazzino", min_value=0, step=1, key="f_qta")
        scadenza_dt = st.date_input("Data scadenza", key="f_scad")
        posologia = st.text_area("Posologia (es. 1 compressa ogni 8 ore)", key="f_poso")
        note = st.text_area("Note", key="f_note")
        submit = st.form_submit_button("Salva farmaco")
        if submit:
            if not nome.strip():
                st.error("Il nome del farmaco è obbligatorio.")
            else:
                scadenza_iso = date_to_iso(scadenza_dt)
                run_sql(
                    "INSERT INTO farmaci (nome, principio_attivo, quantita, scadenza, posologia, note) VALUES (?, ?, ?, ?, ?, ?)",
                    (nome.strip(), principio.strip(), quantita, scadenza_iso, posologia.strip(), note.strip())
                )
                st.success(f"Farmaco '{nome.strip()}' salvato.")

def pagina_elenco_farmaci():
    st.header("📦 Elenco farmaci in magazzino")
    df = fetch_df("SELECT * FROM farmaci ORDER BY nome")
    if df.empty:
        st.warning("Nessun farmaco registrato.")
        return

    # Assicuriamoci che la colonna scadenza esista
    if "scadenza" not in df.columns:
        df["scadenza"] = ""

    # Converti e calcola giorni alla scadenza
    df["Scadenza_iso"] = pd.to_datetime(df["scadenza"], errors="coerce", dayfirst=False)
    oggi = pd.Timestamp.now().normalize()
    df["Giorni_alla_scadenza"] = (df["Scadenza_iso"] - oggi).dt.days
    # Stato
    def stato_from_days(days):
        if pd.isna(days):
            return "Sconosciuta"
        if days < 0:
            return "Scaduto"
        if days <= 30:
            return "In scadenza"
        return "OK"
    df["Stato"] = df["Giorni_alla_scadenza"].apply(stato_from_days)

    # Formatta data per visualizzazione dd/mm/YYYY
    df["Scadenza_visual"] = df["Scadenza_iso"].dt.strftime("%d/%m/%Y")
    # Per eventuali valori NaT, sostituisci con stringa vuota
    df["Scadenza_visual"] = df["Scadenza_visual"].fillna("")

    # Rinomina colonne per UI
    df_ui = df.rename(columns={
        "nome": "Nome",
        "principio_attivo": "Principio attivo",
        "quantita": "Quantità",
        "posologia": "Posologia",
        "note": "Note",
        "Giorni_alla_scadenza": "Giorni alla scadenza",
        "Scadenza_visual": "Scadenza"
    })

    display_cols = ["Nome", "Principio attivo", "Quantità", "Scadenza", "Giorni alla scadenza", "Stato", "Posologia", "Note"]
    st.dataframe(df_ui[display_cols])

    # Azioni rapide: seleziona farmaco per decremento/aggiornamento
    st.markdown("---")
    st.subheader("Azioni rapide")
    farmaci = df_ui["Nome"].tolist()
    if farmaci:
        sel = st.selectbox("Seleziona farmaco", farmaci)
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            if st.button("Decrementa quantità (-1)"):
                # decrementa la prima occorrenza con quel nome
                row = df[df["nome"] == sel].iloc[0]
                new_q = max(0, int(row["quantita"]) - 1)
                run_sql("UPDATE farmaci SET quantita = ? WHERE id = ?", (new_q, int(row["id"])))
                st.success(f"Quantità aggiornata a {new_q} per {sel}")
        with col2:
            if st.button("Elimina farmaco"):
                row = df[df["nome"] == sel].iloc[0]
                run_sql("DELETE FROM farmaci WHERE id = ?", (int(row["id"]),))
                st.success(f"Farmaco '{sel}' eliminato.")
        with col3:
            if st.button("Ricarica pagina"):
                st.experimental_rerun()

# =========================
# Funzionalità: Prescrizioni & Consegne
# =========================
def pagina_prescrizioni():
    st.header("📋 Prescrizioni")
    # Carica pazienti e farmaci per selezione
    pazienti_df = fetch_df("SELECT id, nome || ' ' || cognome as paziente FROM pazienti ORDER BY cognome, nome")
    farmaci_df = fetch_df("SELECT id, nome FROM farmaci ORDER BY nome")
    if pazienti_df.empty:
        st.info("Aggiungi prima almeno un paziente (scheda Pazienti).")
    if farmaci_df.empty:
        st.info("Aggiungi prima almeno un farmaco (scheda Farmaci).")

    with st.form("form_prescrizione"):
        paz_sel = st.selectbox("Seleziona paziente", pazienti_df["paziente"] if not pazienti_df.empty else [])
        farm_sel = st.selectbox("Seleziona farmaco", farmaci_df["nome"] if not farmaci_df.empty else [])
        posologia = st.text_input("Posologia (es. 1 compressa ogni 12h)")
        durata = st.number_input("Durata terapia (giorni)", min_value=1, step=1)
        data_inizio_dt = st.date_input("Data inizio terapia")
        piano = st.text_area("Piano terapeutico / note")
        submit = st.form_submit_button("Registra prescrizione & consegna")
        if submit:
            if paz_sel == "" or farm_sel == "":
                st.error("Seleziona paziente e farmaco.")
            else:
                id_paz = pazienti_df.loc[pazienti_df["paziente"] == paz_sel, "id"].values[0]
                id_farm = farmaci_df.loc[farmaci_df["nome"] == farm_sel, "id"].values[0]
                data_iso = date_to_iso(data_inizio_dt)
                run_sql(
                    "INSERT INTO prescrizioni (id_paziente, id_farmaco, posologia, durata_giorni, data_inizio, piano_terapeutico) VALUES (?, ?, ?, ?, ?, ?)",
                    (int(id_paz), int(id_farm), posologia, int(durata), data_iso, piano.strip())
                )
                # registra anche una consegna (quantità decrementata di 1 per semplicità)
                run_sql("INSERT INTO consegne (id_prescrizione, data_consegna, quantita) VALUES ((SELECT last_insert_rowid()), ?, ?)",
                        (date_to_iso(datetime.now().date()), 1))
                # decrementa giacenza del farmaco di 1 (senza andare sotto 0)
                run_sql("UPDATE farmaci SET quantita = MAX(0, quantita - 1) WHERE id = ?", (int(id_farm),))
                st.success("Prescrizione registrata e consegna annotata.")

    # Mostra elenco prescrizioni
    df_pres = fetch_df("""
        SELECT pr.id, pa.nome || ' ' || pa.cognome as paziente, f.nome as farmaco,
               pr.posologia, pr.durata_giorni, pr.data_inizio
        FROM prescrizioni pr
        LEFT JOIN pazienti pa ON pr.id_paziente = pa.id
        LEFT JOIN farmaci f ON pr.id_farmaco = f.id
        ORDER BY pr.data_inizio DESC
    """)
    if not df_pres.empty:
        df_pres["data_inizio"] = pd.to_datetime(df_pres["data_inizio"], errors="coerce")
        df_pres["Data inizio"] = df_pres["data_inizio"].dt.strftime("%d/%m/%Y")
        st.dataframe(df_pres[["paziente", "farmaco", "posologia", "durata_giorni", "Data inizio"]])
    else:
        st.info("Nessuna prescrizione registrata.")

def pagina_consegne():
    st.header("📦 Consegne storiche")
    df_cons = fetch_df("""
        SELECT c.id, pr.id as id_prescrizione, pa.nome || ' ' || pa.cognome as paziente,
               f.nome as farmaco, c.data_consegna, c.quantita, c.operatore
        FROM consegne c
        LEFT JOIN prescrizioni pr ON c.id_prescrizione = pr.id
        LEFT JOIN pazienti pa ON pr.id_paziente = pa.id
        LEFT JOIN farmaci f ON pr.id_farmaco = f.id
        ORDER BY c.data_consegna DESC
    """)
    if df_cons.empty:
        st.info("Nessuna consegna registrata.")
    else:
        df_cons["data_consegna"] = pd.to_datetime(df_cons["data_consegna"], errors="coerce")
        df_cons["Data consegna"] = df_cons["data_consegna"].dt.strftime("%d/%m/%Y")
        st.dataframe(df_cons[["paziente", "farmaco", "quantita", "Data consegna", "operatore"]])

# =========================
# Avvisi
# =========================
def pagina_avvisi():
    st.header("⏰ Avvisi: scadenze e scorte")
    df = fetch_df("SELECT id, nome, quantita, scadenza FROM farmaci")
    if df.empty:
        st.info("Nessun farmaco registrato.")
        return

    # Prepara colonne
    df["Scadenza_iso"] = pd.to_datetime(df["scadenza"], errors="coerce", dayfirst=False)
    oggi = pd.Timestamp.now().normalize()
    df["Giorni_alla_scadenza"] = (df["Scadenza_iso"] - oggi).dt.days

    # Farmaci scaduti
    scaduti = df[df["Giorni_alla_scadenza"] < 0]
    in_scadenza = df[(df["Giorni_alla_scadenza"] >= 0) & (df["Giorni_alla_scadenza"] <= 30)]
    scorte_basse = df[df["quantita"] <= 2]

    if not scaduti.empty:
        st.error("❌ Farmaci scaduti:")
        scaduti["Scadenza"] = scaduti["Scadenza_iso"].dt.strftime("%d/%m/%Y")
        st.table(scaduti[["nome", "quantita", "Scadenza"]])

    if not in_scadenza.empty:
        st.warning("⚠️ Farmaci in scadenza entro 30 giorni:")
        in_scadenza["Scadenza"] = in_scadenza["Scadenza_iso"].dt.strftime("%d/%m/%Y")
        st.table(in_scadenza[["nome", "quantita", "Scadenza", "Giorni_alla_scadenza"]])

    if not scorte_basse.empty:
        st.info("ℹ️ Farmaci con scorte basse (≤2):")
        st.table(scorte_basse[["nome", "quantita"]])

    if scaduti.empty and in_scadenza.empty and scorte_basse.empty:
        st.success("✅ Nessun problema rilevato.")

# =========================
# MENU PRINCIPALE
# =========================
def main():
    menu = st.sidebar.radio(
        "Naviga",
        ["🏠 Home", "👥 Pazienti", "➕ Aggiungi farmaco", "📦 Elenco farmaci", "📋 Prescrizioni", "📦 Consegne", "⏰ Avvisi"]
    )

    if menu == "🏠 Home":
        st.subheader("Home")
        st.write("Usa il menu a sinistra per navigare.")
    elif menu == "👥 Pazienti":
        pagina_pazienti()
    elif menu == "➕ Aggiungi farmaco":
        pagina_aggiungi_farmaco()
    elif menu == "📦 Elenco farmaci":
        pagina_elenco_farmaci()
    elif menu == "📋 Prescrizioni":
        pagina_prescrizioni()
    elif menu == "📦 Consegne":
        pagina_consegne()
    elif menu == "⏰ Avvisi":
        pagina_avvisi()

if __name__ == "__main__":
    main()
