import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os


# --- Názov súboru s dátami ---
SUBOR_HISTORIA = "historia_nepodarkov.csv"

# --- Konfigurácia stránky ---
st.set_page_config(
    page_title="Dashboard Nepodarkov",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard Nepodarkov")
st.markdown("---")

# --- Funkcia na načítanie a spracovanie dát ---
@st.cache_data(ttl=60)  # Obnoví dáta každých 60 sekúnd
def load_data():
    if not os.path.exists(SUBOR_HISTORIA):
        st.error(f"Súbor '{SUBOR_HISTORIA}' nebol nájdený. Spustite najprv hlavnú aplikáciu, aby sa vygeneroval.")
        return None
    
    try:
        # Načítanie dát, explicitne definujeme hlavičku a oddeľovač
        df = pd.read_csv(
            SUBOR_HISTORIA, 
            delimiter=';',
            names=["Dátum", "Čas", "PIN", "Meno", "Typ", "Chyba", "Hodnota"],
            header=0, # Prvý riadok je hlavička
            encoding='utf-8'
        )
        # Konverzia stĺpca 'Dátum' na dátumový typ
        df['Dátum'] = pd.to_datetime(df['Dátum'], format='%Y-%m-%d')

        # Rozdelenie stĺpca 'Chyba' na dva nové stĺpce
        # expand=True vytvorí nové stĺpce, fillna('') zaistí, že nevznikne chyba pri záznamoch bez pomlčky (napr. 'SYS')
        split_chyba = df['Chyba'].str.split(' - ', n=1, expand=True)
        df['Hlavná Chyba'] = split_chyba[0].fillna('').str.strip()
        df['Pod-chyba'] = split_chyba[1].fillna('').str.strip()

        return df
    except Exception as e:
        st.error(f"Chyba pri načítavaní CSV súboru: {e}")
        return None

data = load_data()

if data is not None:
    st.sidebar.header("Filtre")

    # Filter podľa mena operátora
    operator = st.sidebar.multiselect(
        "Vyberte operátora:",
        options=data["Meno"].unique(),
        default=data["Meno"].unique()
    )

    # Filter podľa typu chyby
    hlavna_chyba = st.sidebar.multiselect(
        "Vyberte hlavný typ chyby:",
        options=sorted(data[data['Hlavná Chyba'] != '']['Hlavná Chyba'].unique()),
        default=sorted(data[data['Hlavná Chyba'] != '']['Hlavná Chyba'].unique())
    )

    # Aplikovanie filtrov
    filtered_data = data.query(
        "Meno == @operator & `Hlavná Chyba` == @hlavna_chyba"
    )

    # --- Vizuálizácie ---
    col1, col2 = st.columns(2)

    with col1:
        st.header("Celkový počet nepodarkov")
        st.markdown("Graf zobrazuje celkový počet zaznamenaných nepodarkov (`Typ` = 'PRIDANÉ') pre každú hlavnú kategóriu chyby.")
        
        # SPRÁVNA AGREGÁCIA: Sčítame počet riadkov s typom 'PRIDANÉ' pre každú chybu.
        pridane_kusy = filtered_data[filtered_data["Typ"] == "PRIDANÉ"]
        chyby_sumar = pridane_kusy.groupby('Hlavná Chyba').size().sort_values(ascending=False)

        if not chyby_sumar.empty:
            st.bar_chart(chyby_sumar)
        else:
            st.warning("Pre zadané filtre neboli nájdené žiadne záznamy o pridaných nepodarkoch.")

    with col2:
        st.header("Pomer pod-chýb")
        st.markdown("Graf zobrazuje percentuálny podiel jednotlivých pod-chýb na celkovom počte.")

        # Agregácia pre koláčový graf
        podchyby_sumar = pridane_kusy[pridane_kusy['Pod-chyba'] != ''].groupby('Pod-chyba').size()

        if not podchyby_sumar.empty:
            st.pyplot(podchyby_sumar.plot.pie(autopct='%1.1f%%', legend=False, figsize=(6, 6)).figure)
        else:
            st.warning("Neboli nájdené žiadne dáta pre pod-chyby.")

    st.markdown("---") # Oddelovač
    # Zobrazenie surových dát v tabuľke
    st.header("Detailná história")
    st.dataframe(filtered_data)

    # Tlačidlo na obnovenie dát
    if st.button('Obnoviť dáta'):
        st.cache_data.clear()
        st.rerun()