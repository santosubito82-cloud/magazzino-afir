import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

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
# Inizializzazione / Migrazione DB
# =========================
def get_db_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_db_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS pazienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            cognome TEXT,
            codice_fiscale TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS farmaci (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            principio_attivo TEXT,
            quantita INTEGER DEFAULT 0,
            scadenza TEXT,
            posologia TEXT,
            note TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS prescrizioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_paziente INTEGER,
            id_farmaco INTEGER,
            posologia TEXT,
            durata_giorni INTEGER,
            data_inizio TEXT,
            piano_terapeutico TEXT,
            FOREIGN KEY(id_paziente) REFERENCES pazienti(id),
            FOREIGN KEY(id_farmaco) REFERENCES farmaci(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS consegne (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_prescrizione INTEGER,
            data_consegna TEXT,
            quantita INTEGER,
            operatore TEXT,
            verifica_piano INTEGER DEFAULT 0,
            FOREIGN KEY(id_prescrizione) REFERENCES prescrizioni(id)
        )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# Funzioni DB
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
# Utility date
# =========================
def date_to_iso(dt_obj):
    if not dt_obj:
        return ""
    return dt_obj.strftime("%Y-%m-%d")

# =========================
# Funzionalità Pazienti
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
                st.rerun()

    df = fetch_df("SELECT id, nome, cognome, codice_fiscale FROM pazienti ORDER BY cognome, nome")
    st.dataframe(df if not df.empty else pd.DataFrame())

# =========================
# Funzionalità Farmaci
# =========================
def pagina_aggiungi_farmaco():
    st.header("➕ Aggiungi / Aggiorna Farmaco")
    with st.form("form_farmaco"):
        nome = st.text_input("Nome commerciale", key="f_nome")
        principio = st.text_input("Principio attivo", key="f_principio")
        quantita = st.number_input("Quantità in magazzino", min_value=0, step=1, key="f_qta")
        scadenza_dt = st.date_input("Data scadenza", key="f_scad")
        posologia = st.text_area("Posologia", key="f_poso")
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
                st.rerun()

def pagina_elenco_farmaci():
    st.header("📦 Elenco farmaci")
    df = fetch_df("SELECT * FROM farmaci ORDER BY nome")
    if df.empty:
        st.warning("Nessun farmaco registrato.")
        return

    df["Scadenza_visual"] = pd.to_datetime(df["scadenza"], errors="coerce").dt.strftime("%d/%m/%Y")
    df["Giorni_alla_scadenza"] = (pd.to_datetime(df["scadenza"], errors="coerce") - pd.Timestamp.now()).dt.days

    def stato_from_days(days):
        if pd.isna(days):
            return "Sconosciuta"
        if days < 0:
            return "Scaduto"
        if days <= 30:
            return "In scadenza"
        return "OK"

    df["Stato"] = df["Giorni_alla_scadenza"].apply(stato_from_days)

    display_cols = ["nome", "principio_attivo", "quantita", "Scadenza_visual", "Giorni_alla_scadenza", "Stato", "posologia", "note"]
    df_ui = df.rename(columns={"nome": "Nome", "principio_attivo": "Principio attivo", "quantita": "Quantità",
                               "Scadenza_visual": "Scadenza", "Giorni_alla_scadenza": "Giorni alla scadenza",
                               "posologia": "Posologia", "note": "Note", "Stato": "Stato"})
    st.dataframe(df_ui[["Nome","Principio attivo","Quantità","Scadenza","Giorni alla scadenza","Stato","Posologia","Note"]])

# =========================
# Funzionalità Prescrizioni & Consegne
# =========================
def aggiungi_prescrizione(id_paz, id_farm, posologia, durata, data_iso, piano):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    # Inserisci prescrizione
    cur.execute(
        "INSERT INTO prescrizioni (id_paziente, id_farmaco, posologia, durata_giorni, data_inizio, piano_terapeutico) VALUES (?, ?, ?, ?, ?, ?)",
        (id_paz, id_farm, posologia, durata, data_iso, piano)
    )
    id_prescrizione = cur.lastrowid

    # Inserisci consegna
    cur.execute(
        "INSERT INTO consegne (id_prescrizione, data_consegna, quantita) VALUES (?, ?, ?)",
        (id_prescrizione, date_to_iso(datetime.now().date()), 1)
    )

    # Aggiorna quantità farmaco
    cur.execute("UPDATE farmaci SET quantita = MAX(0, quantita - 1) WHERE id = ?", (id_farm,))
    
    conn.commit()
    conn.close()

def pagina_prescrizioni():
    st.header("📋 Prescrizioni")
    pazienti_df = fetch_df("SELECT id, nome || ' ' || cognome AS paziente FROM pazienti ORDER BY cognome, nome")
    farmaci_df = fetch_df("SELECT id, nome FROM farmaci ORDER BY nome")
    
    with st.form("form_prescrizione"):
        paz_sel = st.selectbox("Seleziona paziente", pazienti_df["paziente"].tolist() if not pazienti_df.empty else [])
        farm_sel = st.selectbox("Seleziona farmaco", farmaci_df["nome"].tolist() if not farmaci_df.empty else [])
        posologia = st.text_input("Posologia")
        durata = st.number_input("Durata (giorni)", min_value=1, step=1, value=1)
        data_inizio_dt = st.date_input("Data inizio")
        piano = st.text_area("Piano terapeutico / note")
        submit = st.form_submit_button("Registra prescrizione & consegna")
        if submit:
            if not pazienti_df.empty and not farmaci_df.empty and paz_sel and farm_sel:
                id_paz = pazienti_df.loc[pazienti_df["paziente"] == paz_sel, "id"].values[0]
                id_farm = farmaci_df.loc[farmaci_df["nome"] == farm_sel, "id"].values[0]
                aggiungi_prescrizione(id_paz, id_farm, posologia.strip(), int(durata), date_to_iso(data_inizio_dt), piano.strip())
                st.success("Prescrizione registrata e consegna annotata.")
                st.rerun()
            else:
                st.error("Seleziona paziente e farmaco.")

    st.subheader("Prescrizioni registrate")
    df_pres = fetch_df("""
        SELECT pr.id, 
               COALESCE(pa.nome || ' ' || pa.cognome, 'N/A') AS paziente, 
               COALESCE(f.nome, 'N/A') AS farmaco,
               pr.posologia, 
               pr.durata_giorni, 
               pr.data_inizio
        FROM prescrizioni pr
        LEFT JOIN pazienti pa ON pr.id_paziente = pa.id
        LEFT JOIN farmaci f ON pr.id_farmaco = f.id
        ORDER BY pr.data_inizio DESC
    """)
    if not df_pres.empty:
        df_pres["data_inizio_formatted"] = pd.to_datetime(df_pres["data_inizio"], errors="coerce").dt.strftime("%d/%m/%Y")
        df_display = df_pres[["paziente","farmaco","posologia","durata_giorni","data_inizio_formatted"]].copy()
        df_display.columns = ["Paziente", "Farmaco", "Posologia", "Durata (gg)", "Data inizio"]
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("Nessuna prescrizione registrata.")

def pagina_consegne():
    st.header("📦 Consegne storiche")
    df_cons = fetch_df("""
        SELECT c.id, pr.id AS id_prescrizione, pa.nome || ' ' || pa.cognome AS paziente,
               f.nome AS farmaco, c.data_consegna, c.quantita, c.operatore
        FROM consegne c
        LEFT JOIN prescrizioni pr ON c.id_prescrizione = pr.id
        LEFT JOIN pazienti pa ON pr.id_paziente = pa.id
        LEFT JOIN farmaci f ON pr.id_farmaco = f.id
        ORDER BY c.data_consegna DESC
    """)
    if df_cons.empty:
        st.info("Nessuna consegna registrata.")
        return
    df_cons["Data consegna"] = pd.to_datetime(df_cons["data_consegna"], errors="coerce").dt.strftime("%d/%m/%Y")
    st.dataframe(df_cons[["paziente","farmaco","quantita","Data consegna","operatore"]])

# =========================
# Avvisi
# =========================
def pagina_avvisi():
    st.header("⏰ Avvisi: scadenze e scorte")
    df = fetch_df("SELECT id, nome, quantita, scadenza FROM farmaci")
    if df.empty:
        st.info("Nessun farmaco registrato.")
        return
    df["Scadenza_iso"] = pd.to_datetime(df["scadenza"], errors="coerce")
    oggi = pd.Timestamp.now().normalize()
    df["Giorni_alla_scadenza"] = (df["Scadenza_iso"] - oggi).dt.days
    scaduti = df[df["Giorni_alla_scadenza"] < 0]
    in_scadenza = df[(df["Giorni_alla_scadenza"] >= 0) & (df["Giorni_alla_scadenza"] <= 30)]
    scorte_basse = df[df["quantita"] <= 2]

    if not scaduti.empty:
        st.error("❌ Farmaci scaduti:")
        st.table(scaduti[["nome","quantita"]])
    if not in_scadenza.empty:
        st.warning("⚠️ Farmaci in scadenza entro 30 giorni:")
        st.table(in_scadenza[["nome","quantita","Giorni_alla_scadenza"]])
    if not scorte_basse.empty:
        st.info("ℹ️ Farmaci con scorte basse (≤2):")
        st.table(scorte_basse[["nome","quantita"]])
    if scaduti.empty and in_scadenza.empty and scorte_basse.empty:
        st.success("✅ Nessun problema rilevato.")

# =========================
# Menu principale
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
