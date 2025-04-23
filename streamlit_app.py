import streamlit as st
import pandas as pd
from rapidfuzz import fuzz

# -------------------------------------------
# Styled Streamlit App: Dashboard Prodotti Agristore
# -------------------------------------------
# Page configuration MUST be first Streamlit command
st.set_page_config(page_title="Dashboard Prodotti Agristore", layout="wide")

# Custom CSS for improved look & feel
st.markdown(
    """
    <style>
      .main > .block-container { padding: 1rem 2rem; }
      h1 { font-size:2.5rem; color:#4B5563; margin-bottom: 0.5rem; }
      h3 { font-size:1.5rem; margin-top:1.5rem; }
      .sidebar .sidebar-content { background-color:#F9FAFB; padding:1rem; border-radius:8px; }
      .stButton>button { background-color:#3B82F6; color:white; border-radius:6px; }
      .stDownloadButton>button { background-color:#10B981; color:white; border-radius:6px; }
      .st-expander { border:1px solid #E5E7EB; border-radius:6px; }
    </style>
    """, unsafe_allow_html=True
)

# Header
st.markdown("# 📦 Dashboard Prodotti Agristore")

# Sidebar: File upload and configuration
with st.sidebar:
    st.markdown("## 📤 Carica File")
    products_file = st.file_uploader("Excel Prodotti (xlsx/xls)", type=["xlsx", "xls"])
    split_file    = st.file_uploader("Excel split_by_category (xlsx/xls)", type=["xlsx", "xls"])
    st.markdown("---")
    st.markdown("## 🔧 Configura Colonne")
    if products_file and split_file:
        # Load minimal for column selection
        df_tmp = pd.read_excel(products_file)
        cols = df_tmp.columns.tolist()
        code_column  = st.selectbox(
            "Codice Prodotto", options=cols,
            index=cols.index('product_code') if 'product_code' in cols else 0)
        title_column = st.selectbox(
            "Titolo Prodotto", options=cols,
            index=cols.index('titolo_prodotto') if 'titolo_prodotto' in cols else 1)
        cat_column   = st.selectbox(
            "Categoria (value_it)", options=cols,
            index=cols.index('value_it') if 'value_it' in cols else 2)
    else:
        st.info("Carica i file sopra per configurare le colonne.")
        st.stop()

    st.markdown("---")
    st.markdown("## 📋 Filtri")
    # Load full data for filters
    df_full = pd.read_excel(products_file)
    split_dfs = pd.read_excel(split_file, sheet_name=None)
    split_df = pd.concat(split_dfs.values(), ignore_index=True)
    mapping = {cat: grp['attributo'].tolist() for cat, grp in split_df.groupby('categoria')}

    # Category filter
    categories = sorted(df_full[cat_column].dropna().astype(str).unique())
    sel_cat = st.selectbox("Scegli Categoria", options=categories)
    df_cat = df_full[df_full[cat_column].astype(str) == sel_cat].copy()

    # Value_it filter (mandatory)
    st.subheader("Filtro Value_it")
    vi_vals = sorted(df_cat['value_it'].dropna().astype(str).unique())
    sel_vi = st.multiselect("Seleziona Value_it", options=vi_vals)
    if sel_vi:
        df_cat = df_cat[df_cat['value_it'].astype(str).isin(sel_vi)]

    # Stock & sellout toggle
    st.subheader("Opzioni Stock/Sellout")
    enable_stock = st.checkbox("Mostra agrmkp_stock_qty e sellout_ivato")

    # Extra attributes picker
    extras = [c for c in df_cat.columns if c not in [code_column, title_column, cat_column, 'value_it']]
    extra_attrs = st.multiselect("Aggiungi Attributi Extra", options=extras)

    # —— NUOVO: Filtro per valore sugli attributi extra ——
    if extra_attrs:
        st.subheader("Filtra Attributi Extra")
        for attr in extra_attrs:
            val = st.text_input(f"Inserisci valore per '{attr}'", key=f"filtro_{attr}")
            if val:
                # filtro semplice "contains"
                df_cat = df_cat[df_cat[attr].astype(str).str.contains(val, case=False, na=False)]
    # ——————————————————————————————————————————————

# Main content
# Build list of columns to display
attrs = mapping.get(sel_cat, [])
basic = [code_column, title_column, 'value_it']
fixed = ['descrizione_estesa', 'brand', 'sell_out']
if enable_stock:
    fixed += [col for col in ['agrmkp_stock_qty', 'sellout_ivato'] if col in df_cat.columns]

def has_values(col):
    return col in df_cat.columns and df_cat[col].notna().any()

display_cols = []
for col in basic + attrs + fixed + extra_attrs:
    if has_values(col) and col not in display_cols:
        display_cols.append(col)

# Display table
st.markdown(f"### {sel_cat} — {len(df_cat)} prodotti")
st.dataframe(df_cat[display_cols], use_container_width=True)

# Actions
col1, col2 = st.columns(2)
with col1:
    if st.button("📋 Copia Codici Prodotti"):
        st.write("\n".join(df_cat[code_column].astype(str)))
with col2:
    csv_data = df_cat[display_cols].to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Scarica CSV", data=csv_data, file_name=f"prodotti_{sel_cat}.csv")

# Footer
st.markdown("---")
st.markdown("<em>Powered by Streamlit e RapidFuzz</em>", unsafe_allow_html=True)
