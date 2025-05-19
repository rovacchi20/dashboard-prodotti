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
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------
# Sidebar: Upload dei file
# -------------------------------------------
with st.sidebar:
    st.markdown("## 📤 Carica File")
    products_file = st.file_uploader("Excel Prodotti", type=["xlsx", "xls"])
    split_file    = st.file_uploader("Excel Split by Category", type=["xlsx", "xls"])
    code_file     = st.file_uploader("JSON Codici Originali", type=["json"])
    apps_file     = st.file_uploader("JSON Applicazioni Macchine", type=["json"])
    b2b_file      = st.file_uploader("Excel Prodotti B2B", type=["xlsx", "xls"])

# Stop if essential files missing
if not products_file or not split_file:
    st.sidebar.warning("Carica i file Excel Prodotti e Split by Category per procedere.")
    st.stop()

# -------------------------------------------
# Data Loading Functions
# -------------------------------------------
@st.cache_data
def load_excel(file):
    return pd.read_excel(file, dtype=str)

@st.cache_data
def load_json(file):
    return pd.read_json(file, dtype=str)

# -------------------------------------------
# Load Base DataFrames
# -------------------------------------------
df_products = load_excel(products_file)
# Load split file with all sheets
split_sheets = pd.read_excel(split_file, sheet_name=None, dtype=str)
split_df = pd.concat(split_sheets.values(), ignore_index=True)

# dopo aver concatenato split_df
# split_df ha almeno due colonne: 'categoria' e 'attributo'
mapping = split_df.groupby('categoria')['attributo'].apply(list).to_dict()


# Prepare df_products
if 'product_code' in df_products.columns:
    df_products['prod_stripped'] = df_products['product_code'].str.lstrip('0')
if 'value_it' in df_products.columns:
    df_products['value_it'] = df_products['value_it'].astype('category')

# Merge optional JSON codici
brand_cols, reference_cols = [], []
if code_file:
    df_codes = load_json(code_file)
    df_codes['sku_stripped'] = df_codes['sku'].str.lstrip('0')
    df_products = df_products.merge(
        df_codes, left_on='prod_stripped', right_on='sku_stripped', how='left'
    )
    brand_cols     = [c for c in df_codes if c.startswith('brand')]
    reference_cols = [c for c in df_codes if c.startswith('reference')]
    # Convert to category
    for c in brand_cols+reference_cols:
        df_products[c] = df_products[c].astype('category')

# Load optional JSON applicazioni corretto per tua struttura JSON
if apps_file:
    df_apps = load_json(apps_file)

    records = []
    for _, row in df_apps.iterrows():
        sku = row.get('sku', '').lstrip('0')
        for i in range(1, 10):  # gestisce brand1-reference1, brand2-reference2, ecc.
            brand = row.get(f'brand{i}')
            references = row.get(f'reference{i}')

            if brand and references:
                references_list = [ref.strip() for ref in references.split(',')]
                for ref in references_list:
                    records.append({'sku': sku, 'brand': brand.strip(), 'reference': ref.strip()})

    df_apps_long = pd.DataFrame(records)
else:
    df_apps_long = pd.DataFrame(columns=['sku', 'brand', 'reference'])



# -------------------------------------------
# Load B2B DataFrames
# -------------------------------------------
if b2b_file:
    df_b2b = load_excel(b2b_file)
else:
    df_b2b = pd.DataFrame(columns=df_products.columns.tolist())
# Normalize and categorize
if 'product_code' in df_b2b.columns:
    df_b2b['prod_stripped'] = df_b2b['product_code'].str.lstrip('0')
if 'value_it' in df_b2b.columns:
    df_b2b['value_it'] = df_b2b['value_it'].astype('category')

# Unique B2B (exclude existing)
existing = set(df_products['prod_stripped'])
df_b2b_unique = df_b2b[~df_b2b['prod_stripped'].isin(existing)].copy()
if 'value_it' in df_b2b_unique.columns:
    df_b2b_unique['value_it'] = df_b2b_unique['value_it'].astype('category')

# -------------------------------------------
# Utility to apply filters identical to Tab1
# -------------------------------------------
def apply_tab_filters(df, key_prefix):
    # Category
    if 'value_it' in df.columns:
        sel_cat = st.selectbox(
            "Categoria (value_it)",
            options=list(df['value_it'].cat.categories),
            key=f"{key_prefix}_cat"
        )
        df = df[df['value_it'] == sel_cat]
    # Brand
    if brand_cols:
        all_brands = sorted({
            b.strip() for c in brand_cols for cell in df[c].dropna().astype(str) for b in cell.split(',')
        })
        sel_brand = st.selectbox(
            "Brand",
            options=[""] + all_brands,
            key=f"{key_prefix}_brand"
        )
        if sel_brand:
            df = df[df[brand_cols].apply(
                lambda row: sel_brand in [x.strip() for x in ','.join(map(str,row)).split(',')],
                axis=1
            )]
    # Stock
    if 'stock_qty' in df.columns:
        if st.checkbox(
            "Mostra solo in stock",
            key=f"{key_prefix}_stock"
        ):
            df = df[df['stock_qty'].astype(int) > 0]
    return df

# -------------------------------------------
# Tabs
# -------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dati",
    "🔍 Rif. Originale",
    "🚜 Applicazioni",
    "📊 B2B (tutti)",
    "📊 B2B (esclusivi)"
])

with tab1:
    st.subheader("Visualizzazione Prodotti")

    # 1) Seleziona categoria
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

    # 5) Filtri MULTIPLI AD ETICHETTA (multiselect)
    st.markdown("**Filtri (multi-selezione)**")
    df_filtered = df_cat.copy()
    filter_cols = ['product_code', 'titolo_prodotto'] + extras

    for col in filter_cols:
        opts = sorted(df_filtered[col].dropna().astype(str).unique())
        vals = st.multiselect(f"Filtra {col}", options=opts, key=f"flt_{col}")
        if vals:
            df_filtered = df_filtered[df_filtered[col].astype(str).isin(vals)]

    # 6) Costruisci colonne da mostrare
    cols = ['product_code', 'titolo_prodotto', 'value_it'] + extras
    if mostra_stock:
        for c in ['agrmkp_stock_qty','sellout_ivato']:
            if c in df_filtered.columns:
                cols.append(c)

    # 7) Display
    st.dataframe(
        df_filtered[cols].reset_index(drop=True),
        use_container_width=True
    )


# Tab2 & Tab3: existing logic
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


# Tab3: Applicazioni Macchine
with tab3:
    st.subheader("Applicazioni Macchine")
    if df_apps_long.empty:
        st.info("Carica il file JSON Applicazioni Macchine per procedere.")
    else:
        # Aggiungo titolo_prodotto da df_products tramite merge
        df_apps_long = df_apps_long.merge(
            df_products[['prod_stripped', 'titolo_prodotto']],
            left_on='sku', 
            right_on='prod_stripped',
            how='left'
        ).drop(columns=['prod_stripped'])

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

# Tab4: B2B (tutti) with Tab1-style filters
with tab4:
    st.subheader("Tutti i Prodotti B2B")
    if df_b2b.empty:
        st.info("Carica il file Excel Prodotti B2B nella sidebar.")
    else:
        # Categoria filter
        df_tmp = df_b2b.copy()
        if 'value_it' in df_tmp.columns:
            sel_cat_b2b = st.selectbox(
                "Categoria (value_it)",
                options=list(df_tmp['value_it'].cat.categories),
                key="cat_b2b_all"
            )
            df_tmp = df_tmp[df_tmp['value_it'] == sel_cat_b2b]

        # Brand filter (aggiunta verifica esistenza colonne)
        existing_brand_cols = [col for col in brand_cols if col in df_tmp.columns]

        if existing_brand_cols:
            all_brands_b2b = sorted({
                b.strip() 
                for c in existing_brand_cols 
                for cell in df_tmp[c].dropna().astype(str) 
                for b in cell.split(',')
            })
            sel_brand_b2b = st.selectbox(
                "Brand",
                options=[""] + all_brands_b2b,
                key="brand_b2b_all"
            )
            if sel_brand_b2b:
                df_tmp = df_tmp[df_tmp[existing_brand_cols].apply(
                    lambda row: sel_brand_b2b in [x.strip() for x in ','.join(map(str,row)).split(',')],
                    axis=1
                )]
        else:
            st.info("Le colonne Brand non sono presenti nel file B2B.")

        # Stock filter
        if 'stock_qty' in df_tmp.columns:
            show_stock_b2b = st.checkbox(
                "Mostra solo in stock", key="stock_b2b_all"
            )
            if show_stock_b2b:
                df_tmp = df_tmp[df_tmp['stock_qty'].astype(int) > 0]

        st.dataframe(
            df_tmp.drop(columns=['prod_stripped'], errors='ignore').reset_index(drop=True),
            use_container_width=True
        )


# Tab5: Prodotti B2B Esclusivi con filtro “Attributi Extra” e valori delle colonne
with tab5:
    st.subheader("Prodotti B2B Esclusivi")
    if df_b2b_unique.empty:
        st.info("Nessun prodotto esclusivo o file B2B non caricato.")
    else:
        df_exc = df_b2b_unique.copy()

        # filtro su category_text
        if 'category_text' in df_exc.columns:
            opts = [''] + sorted(df_exc['category_text'].dropna().unique())
            sel_cat = st.selectbox("category_text", opts, key="tab5_cat")
            if sel_cat:
                df_exc = df_exc[df_exc['category_text'] == sel_cat]

        # rimuovo colonne totalmente vuote
        df_exc = df_exc.loc[:, df_exc.notna().any()]

        # selezione attributi extra
        excluded = {'product_code','titolo_prodotto','value_it','stock_qty',
                    'category_text','prod_stripped'}
        attrs = [c for c in df_exc.columns if c not in excluded]
        sel_attrs = st.multiselect("Attributi Extra (mappati)", options=attrs, key="tab5_attrs")

        # per ogni attributo scelto, mostro un secondo filtro sui suoi valori
        for a in sel_attrs:
            vals = sorted(df_exc[a].dropna().unique())
            sel_vals = st.multiselect(f"Valori {a}", options=vals, key=f"tab5_vals_{a}")
            if sel_vals:
                df_exc = df_exc[df_exc[a].isin(sel_vals)]

        # visualizzo risultato
        st.dataframe(df_exc.reset_index(drop=True), use_container_width=True)

# -------------------------------------------
# Footer
# -------------------------------------------
st.markdown(
    """
    <footer style="text-align: center; padding: 1rem; background-color: #F9FAFB;">
        <p style="color: #6B7280;">© 2025 Agristore. Tutti i diritti riservati.</p>
    </footer>
    """,
    unsafe_allow_html=True
)
