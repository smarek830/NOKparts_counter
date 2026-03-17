import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

# --- NASTAVENIE STRÁNKY ---
st.set_page_config(page_title="Analýza Nepodarkov", layout="wide")

# Názov súboru s dátami (musí byť v tej istej zložke)
SUBOR_DATA = "historia_nepodarkov.csv"

# --- FUNKCIE ---
def nacitat_data():
    try:
        # Načítame CSV, separátor je bodkočiarka
        df = pd.read_csv(SUBOR_DATA, sep=';', encoding='utf-8')
        
        # Spojíme Dátum a Čas do jedného stĺpca pre ľahšie filtrovanie
        df['Datetime'] = pd.to_datetime(df['Dátum'] + ' ' + df['Čas'], format='%Y-%m-%d %H:%M:%S')
        
        # Vypočítame zmenu (+1 alebo -1) podľa typu udalosti
        # Ignorujeme "RESET" a iné systémové veci, zaujíma nás len PRIDANÉ a ODSTRÁNENÉ
        df['Kusy'] = 0
        df.loc[df['Typ'].str.contains('PRIDANÉ', na=False), 'Kusy'] = 1
        df.loc[df['Typ'].str.contains('ODSTRÁNENÉ', na=False), 'Kusy'] = -1
        
        # Určenie zmeny (Smeny)
        def urci_smenu(dt):
            h = dt.hour
            if 6 <= h < 14: return "1. Ranná (06-14)"
            elif 14 <= h < 22: return "2. Poobedná (14-22)"
            else: return "3. Nočná (22-06)"
            
        df['Smena'] = df['Datetime'].apply(urci_smenu)
        
        return df
    except FileNotFoundError:
        return None

# --- HLAVNÁ APLIKÁCIA ---
st.title("📊 Prehľad a Analýza Nepodarkov")

df = nacitat_data()

if df is not None:
    # --- FILTRE V ĽAVOM PANELI ---
    st.sidebar.header("Filtrovanie")
    
    # 1. Výber Dátumu
    min_date = df['Datetime'].min().date()
    max_date = df['Datetime'].max().date()
    
    start_date = st.sidebar.date_input("Dátum od:", min_date)
    end_date = st.sidebar.date_input("Dátum do:", max_date)
    
    # 2. Výber Smeny
    vsetky_smeny = sorted(df['Smena'].unique())
    vybrane_smeny = st.sidebar.multiselect("Vyber smeny:", vsetky_smeny, default=vsetky_smeny)
    
    # --- FILTROVANIE DÁT ---
    maska = (df['Datetime'].dt.date >= start_date) & \
            (df['Datetime'].dt.date <= end_date) & \
            (df['Smena'].isin(vybrane_smeny))
            
    filtered_df = df.loc[maska]
    
    # Filtrujeme len riadky, kde sa reálne menil počet (nie Resety)
    filtered_df = filtered_df[filtered_df['Kusy'] != 0]

    # --- KPI KARTY (Hore) ---
    col1, col2, col3 = st.columns(3)
    celkovo_ks = filtered_df['Kusy'].sum()
    najcastejsia_chyba = filtered_df.groupby('Chyba')['Kusy'].sum().idxmax() if not filtered_df.empty else "Žiadna"
    
    col1.metric("Celkový počet nepodarkov", f"{celkovo_ks} ks")
    col2.metric("Najčastejšia chyba", najcastejsia_chyba)
    col3.metric("Počet záznamov", len(filtered_df))
    
    st.markdown("---")

    # --- GRAF 1: POČET PODĽA TYPU CHYBY ---
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("Typy chýb (Pareto)")
        chyby_sum = filtered_df.groupby('Chyba')['Kusy'].sum().reset_index().sort_values('Kusy', ascending=True)
        fig_bar = px.bar(chyby_sum, x='Kusy', y='Chyba', orientation='h', text='Kusy', color='Kusy', color_continuous_scale='Reds')
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- GRAF 2: VÝVOJ V ČASE (ALEBO POROVNANIE SMIEN) ---
    with col_g2:
        st.subheader("Porovnanie Smien")
        smeny_sum = filtered_df.groupby('Smena')['Kusy'].sum().reset_index()
        fig_pie = px.pie(smeny_sum, values='Kusy', names='Smena', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- GRAF 3: DETAILY V ČASE ---
    st.subheader("Vývoj v čase (Timeline)")
    # Zoskupíme po hodinách
    timeline = filtered_df.copy()
    timeline['Hodina'] = timeline['Datetime'].dt.floor('H')
    timeline_grp = timeline.groupby(['Hodina', 'Chyba'])['Kusy'].sum().reset_index()
    
    fig_line = px.bar(timeline_grp, x='Hodina', y='Kusy', color='Chyba', title="Výskyt chýb v čase")
    st.plotly_chart(fig_line, use_container_width=True)

    # --- TABUĽKA OPERÁTOROV ---
    st.subheader("Výkonnosť Obsluhy")
    operatori = filtered_df.groupby(['Meno', 'Chyba'])['Kusy'].sum().unstack().fillna(0)
    operatori['SPOLU'] = operatori.sum(axis=1)
    operatori = operatori.sort_values('SPOLU', ascending=False)
    st.dataframe(operatori.style.background_gradient(cmap="Reds"))

    # --- RAW DATA ---
    with st.expander("Zobraziť surové dáta (Tabuľka)"):
        st.dataframe(filtered_df[['Datetime', 'Smena', 'Meno', 'Chyba', 'Kusy']].sort_values('Datetime', ascending=False))

else:
    st.error(f"Súbor {SUBOR_DATA} sa nenašiel. Spustite najprv hlavnú aplikáciu a zadajte nejaké dáta.")