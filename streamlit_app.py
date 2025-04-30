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
    df = pd.read_excel(file, dtype=str)
    df['prod_stripped'] = df['product_code'].str.lstrip('0')
    return df

@st.cache_data
def load_split(file):
    split_dfs = pd.read_excel(file, sheet_name=None)
    return pd.concat(split_dfs.values(), ignore_index=True)

@st.cache_data
def load_codes(file):
    df = pd.read_json(file, dtype=str)
    df['sku_stripped'] = df['sku'].str.lstrip('0')
    return df

# In the Sidebar, add file uploader for JSON Applicazioni Macchine
with st.sidebar:
    st.markdown("## 📤 Carica File")
    products_file = st.file_uploader("Excel Prodotti", type=["xlsx","xls"])
    split_file    = st.file_uploader("Excel Split by Category", type=["xlsx","xls"])
    code_file     = st.file_uploader("JSON Codici Originali", type=["json"])
    apps_file     = st.file_uploader("JSON Applicazioni Macchine", type=["json"])

# Verify uploads
if not products_file or not split_file:
    st.sidebar.warning("Carica i file Excel Prodotti e Split by Category per procedere.")
    st.stop()

# Load data
df_products = load_products(products_file)
split_df    = load_split(split_file)

# Precompute mapping
mapping = {cat: grp['attributo'].tolist() for cat, grp in split_df.groupby('categoria')}

# -------------------------------------------------------------------
# Define a new function to load the Applicazioni Macchine JSON
@st.cache_data
def load_apps(file):
    return pd.read_json(file, dtype=str)

# -------------------------------------------------------------------
# Merge JSON codes (existing code)
if code_file:
    df_codes = load_codes(code_file)
    df_products = df_products.merge(
        df_codes,
        left_on='prod_stripped',
        right_on='sku_stripped',
        how='left',
        suffixes=("", "_json")
    )
    brand_cols     = [c for c in df_codes.columns if c.startswith('brand')]
    reference_cols = [c for c in df_codes.columns if c.startswith('reference')]
    for col in brand_cols + reference_cols:
        df_products[col] = df_products[col].fillna("").astype(str)
else:
    brand_cols     = []
    reference_cols = []

# -------------------------------------------------------------------
# Load and prepare the Applicazioni Macchine data right after the merge
if apps_file:
    df_apps = load_apps(apps_file)
    # trasforma brand/reference in righe separate
    apps = []
    for _, r in df_apps.iterrows():
        sku = r['sku']
        for i in range(1, 10):
            bcol, rcol = f"brand{i}", f"reference{i}"
            if bcol in r and pd.notna(r[bcol]) and r[bcol].strip():
                for ref in str(r.get(rcol, "")).split(','):
                    ref = ref.strip()
                    if ref:
                        apps.append({"sku": sku, "brand": r[bcol].strip(), "reference": ref})
    df_apps_long = pd.DataFrame(apps)
    # qui mergiamo per aggiungere il titolo
    df_apps_long = df_apps_long.merge(
        df_products[['sku', 'titolo_prodotto']].drop_duplicates(),
        on='sku',
        how='left'
    )
else:
    df_apps_long = pd.DataFrame(columns=["sku", "brand", "reference", "titolo_prodotto"])

# -------------------------------------------------------------------
# Optimize dtypes
df_products['value_it'] = df_products['value_it'].astype('category')
for col in brand_cols + reference_cols:
    df_products[col] = df_products[col].astype('category')

# Extend tabs to three
tab1, tab2, tab3 = st.tabs(["📊 Dati", "🔍 Rif. Originale", "🚜 Applicazioni"])

# --- Tab 1: Dati ---
with tab1:
    st.subheader("Visualizzazione Prodotti")

    # 1) Seleziona categoria e filtra sottoinsieme
    sel_cat = st.selectbox(
        "Categoria (value_it)",
        options=list(df_products['value_it'].cat.categories)
    )
    df_cat = df_products[df_products['value_it'] == sel_cat]

    # 2) Stock & sellout toggle
    mostra_stock = st.checkbox("Mostra stock & sellout ivato")

    # 3) Attributi extra pre-mappati
    available_attrs = [
        attr for attr in mapping.get(sel_cat, [])
        if attr in df_cat.columns and df_cat[attr].notna().any()
    ]
    extras = st.multiselect(
        "Attributi Extra (mappati)",
        options=available_attrs,
        default=available_attrs
    )

    # 4) Permetti di aggiungere UN SOLO attributo extra non mappato
    remaining = [
        col for col in df_products.columns
        if col not in ['product_code','titolo_prodotto','value_it'] + available_attrs
    ]
    extra_manual = st.selectbox(
        "Aggiungi un attributo in più",
        options=[""] + remaining
    )
    if extra_manual:
        extras = extras + [extra_manual]

    # 5) Filtri a cascata
    st.markdown("**Filtri**")
    df_filtered = df_cat.copy()
    filter_cols = ['product_code', 'titolo_prodotto'] + extras
    for col in filter_cols:
        opts = sorted(df_filtered[col].dropna().astype(str).unique())
        val = st.selectbox(f"Filtra {col}", options=[""] + opts, key=f"flt_{col}")
        if val:
            df_filtered = df_filtered[df_filtered[col].astype(str) == val]

    # 6) Costruisci colonne da mostrare
    cols = ['product_code', 'titolo_prodotto', 'value_it'] + extras
    if mostra_stock:
        for c in ['ama_stock_b2c','sellout_ivato']:
            if c in df_filtered.columns:
                cols.append(c)

    # 7) Display
    st.dataframe(
        df_filtered[cols].reset_index(drop=True),
        use_container_width=True
    )

# --- Tab 2: Ricerca ---
with tab2:
    st.subheader("Ricerca Brand/Modello")

    # 1) Brand
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

    # 2) Modello/Riferimento a cascata
    sel_mod = ""
    if sel_brand:
        df_brand = df_products[
            df_products[brand_cols]
                .apply(lambda row: any(sel_brand.lower() == str(v).strip().lower() for v in row), axis=1)
        ]
        all_refs = sorted({
            ref.strip()
            for col in reference_cols
            for cell in df_brand[col].dropna().astype(str)
            for ref in cell.split(',')
        })
        sel_mod = st.selectbox("Modello / Riferimento", [""] + all_refs, key=f"sel_mod_{sel_brand}")
    else:
        st.info("Seleziona prima un Brand per vedere i Modelli disponibili.")

    # 3) Prepara df_search
    df_search = df_products.copy()
    if sel_brand:
        df_search = df_search[
            df_search[brand_cols]
                .apply(lambda row: any(sel_brand.lower() == str(v).strip().lower() for v in row), axis=1)
        ]
    if sel_mod:
        df_search = df_search[
            df_search[reference_cols]
                .apply(
                    lambda row: any(
                        sel_mod == ref.strip()
                        for cell in row
                        for ref in str(cell).split(',')
                        if ref.strip()
                    ),
                    axis=1
                )
        ]

    # 4) Mostra risultati
    if df_search.empty:
        st.info("Nessun risultato trovato.")
    else:
        def get_ref(row):
            for bcol, rcol in zip(brand_cols, reference_cols):
                brands = [b.strip() for b in str(row[bcol]).split(',') if b.strip()]
                if sel_brand in brands:
                    for ref in [r.strip() for r in str(row[rcol]).split(',') if r.strip()]:
                        if ref == sel_mod:
                            return ref
            return ""

        df_search = df_search.assign(
            Brand=sel_brand,
            Riferimento=df_search.apply(get_ref, axis=1)
        )

        display_cols = ['product_code','titolo_prodotto','value_it','Brand','Riferimento']
        st.dataframe(df_search[display_cols].reset_index(drop=True), use_container_width=True)

# -------------------------------------------------------------------
# New Tab 3 – Applicazioni Macchine
with tab3:
    st.subheader("Applicazioni Macchine")
    if df_apps_long.empty:
        st.info("Carica il file JSON Applicazioni Macchine per procedere.")
    else:
        # 1) Select SKU
        skus = sorted(df_apps_long['sku'].unique())
        sel_sku = st.selectbox("SKU", [""] + skus)
        dff = df_apps_long.copy()
        if sel_sku:
            dff = dff[dff['sku'] == sel_sku]
        # 2) Select Brand a cascata
        brands = sorted(dff['brand'].unique())
        sel_brand = st.selectbox("Brand", [""] + brands)
        if sel_brand:
            dff = dff[dff['brand'] == sel_brand]
        # 3) Select Reference a cascata
        refs = sorted(dff['reference'].unique())
        sel_ref = st.selectbox("Riferimento", [""] + refs)
        if sel_ref:
            dff = dff[dff['reference'] == sel_ref]
        # 4) Visualizza includendo titolo_prodotto
        display_cols = ['sku', 'titolo_prodotto', 'brand', 'reference']
        st.dataframe(
            dff[display_cols].reset_index(drop=True),
            use_container_width=True
        )

st.markdown("---")
st.markdown("<em>Powered by Streamlit</em>", unsafe_allow_html=True)
