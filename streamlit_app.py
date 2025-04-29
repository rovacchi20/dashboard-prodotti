import streamlit as st
import pandas as pd

# -------------------------------------------
# Styled Streamlit App: Dashboard Prodotti Agristore
# -------------------------------------------
st.set_page_config(page_title="Dashboard Prodotti Agristore", layout="wide")

# Custom CSS
st.markdown(
    """
    <style>
      .main > .block-container { padding:1rem 2rem; }
      h1 { font-size:2.5rem; color:#4B5563; margin-bottom:0.5rem; }
      .sidebar .sidebar-content { background-color:#F9FAFB; padding:1rem; border-radius:8px; }
      .stButton>button { background-color:#3B82F6; color:white; border-radius:6px; }
      .stDownloadButton>button { background-color:#10B981; color:white; border-radius:6px; }
    </style>
    """, unsafe_allow_html=True
)

st.markdown("# 📦 Dashboard Prodotti Agristore")

# Caching data loads for performance
@st.cache_data
def load_products(file):
    return pd.read_excel(file)

@st.cache_data
def load_split(file):
    split_dfs = pd.read_excel(file, sheet_name=None)
    return pd.concat(split_dfs.values(), ignore_index=True)

@st.cache_data
def load_codes(file):
    return pd.read_json(file)

# Sidebar: file uploads
with st.sidebar:
    st.markdown("## 📤 Carica File")
    products_file = st.file_uploader("Excel Prodotti", type=["xlsx","xls"])
    split_file    = st.file_uploader("Excel Split by Category", type=["xlsx","xls"])
    code_file     = st.file_uploader("JSON Codici Originali", type=["json"])

# Verify uploads
if not products_file or not split_file:
    st.sidebar.warning("Carica i file Excel Prodotti e Split by Category per procedere.")
    st.stop()

# Load data
df_products = load_products(products_file)
split_df     = load_split(split_file)

# Precompute mapping
mapping = {cat: grp['attributo'].tolist() for cat, grp in split_df.groupby('categoria')}

# Merge JSON codes
if code_file:
    df_codes        = load_codes(code_file)
    df_products     = df_products.merge(df_codes, left_on='product_code', right_on='sku', how='left')
    brand_cols      = [c for c in df_codes.columns if c.startswith('brand')]
    reference_cols  = [c.replace('brand','reference') for c in brand_cols]
else:
    brand_cols     = []
    reference_cols = []

# Optimize dtypes
df_products['value_it'] = df_products['value_it'].astype('category')
for col in brand_cols + reference_cols:
    df_products[col] = df_products[col].astype('category')

# Tabs
tab1, tab2 = st.tabs(["📊 Dati", "🔍 Ricerca"])

# Tab 1: Dati
with tab1:
    st.subheader("Visualizzazione Prodotti")
    sel_cat = st.selectbox(
        "Categoria (value_it)",
        options=list(df_products['value_it'].cat.categories)
    )
    df_cat = df_products[df_products['value_it'] == sel_cat]

    # Stock & sellout toggle
    mostra_stock = st.checkbox("Mostra stock & sellout ivato")

    # Determine available attributes: only those in mapping and non-null
    available_attrs = [
        attr for attr in mapping.get(sel_cat, [])
        if attr in df_cat.columns and df_cat[attr].notna().any()
    ]

    # Multiselect with defaults
    extras = st.multiselect(
        "Attributi Extra",
        options=available_attrs,
        default=available_attrs
    )

    # Filtri per colonna
    st.markdown("**Filtri**")
    filter_values = {}
    filter_cols = ['product_code', 'titolo_prodotto'] + extras
    for col in filter_cols:
        filter_values[col] = st.text_input(f"Filtra {col}", key=f"flt_{col}")

    # Applica filtri
    for col, val in filter_values.items():
        if val:
            df_cat = df_cat[df_cat[col].astype(str).str.contains(val, case=False, na=False)]

    # Build display columns
    cols = ['product_code', 'titolo_prodotto', 'value_it'] + extras
    if mostra_stock:
        for c in ['agrmkp_stock_qty','sellout_ivato']:
            if c in df_cat.columns:
                cols.append(c)

    # Display
    st.dataframe(
        df_cat[cols].reset_index(drop=True),
        use_container_width=True
    )

# Tab 2: Ricerca con filtro a cascata
with tab2:
    st.subheader("Ricerca Brand/Modello")

    # 1) Selectbox Brand
    if brand_cols:
        all_brands = sorted({
            b.strip()
            for col in brand_cols
            for cell in df_products[col].dropna().astype(str)
            for b in cell.split(',')
        })
        sel_brand = st.selectbox("Brand", [""] + all_brands)
    else:
        sel_brand = ""

    # 2) Selectbox Modello / Riferimento (dipendente da Brand)
    sel_mod = ""
    if sel_brand:
        # Data subset per brand
        df_brand = df_products[
            df_products[brand_cols]
                .apply(lambda row: any(sel_brand.lower() in str(v).lower() for v in row), axis=1)
        ]
        all_refs = sorted({
            ref.strip()
            for col in reference_cols
            for cell in df_brand[col].dropna().astype(str)
            for ref in cell.split(',')
        })
        sel_mod = st.selectbox("Modello / Riferimento", [""] + all_refs)
    else:
        st.info("Seleziona prima un Brand per vedere i Modelli disponibili.")

    # 3) Applica filtri
    df_search = df_products.copy()
    if sel_brand:
        df_search = df_search[
            df_search[brand_cols]
                .apply(lambda row: any(sel_brand.lower() in str(v).lower() for v in row), axis=1)
        ]
    if sel_mod:
        df_search = df_search[
            df_search[reference_cols]
                .apply(lambda row: any(sel_mod.lower() in str(v).lower() for v in row), axis=1)
        ]

    # 4) Visualizza risultati
    if df_search.empty:
        st.info("Nessun risultato trovato.")
    else:
        def get_ref(row):
            for i, bc in enumerate(brand_cols):
                if sel_brand.lower() in str(row[bc]).lower():
                    return row[reference_cols[i]]
            return ""
        df_search = df_search.assign(
            Brand=sel_brand,
            Riferimento=df_search.apply(get_ref, axis=1)
        )
        display_cols = ['product_code','titolo_prodotto','value_it','Brand','Riferimento']
        st.dataframe(df_search[display_cols].reset_index(drop=True), use_container_width=True)

st.markdown("---")
st.markdown("<em>Powered by Streamlit</em>", unsafe_allow_html=True)
