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
    ref_excel     = st.file_uploader("Excel Riferimenti Originali", type=["xlsx","xls"])
    apps_excel    = st.file_uploader("Excel Applicazioni Macchine", type=["xlsx","xls"])
    b2b_file      = st.file_uploader("Excel Prodotti B2B", type=["xlsx", "xls"])
    sap_file      = st.file_uploader("Excel Dati SAP", type=["xlsx","xls"])

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
## Riferimenti Originali da Excel
brand_cols, reference_cols = [], []
if ref_excel:
    # 1) Leggi Excel
    df_ref = load_excel(ref_excel)

    # 2) Raggruppa per 'code' e crea brandN/referenceN dinamiche
    records = []
    for sku, grp in df_ref.groupby('code'):
        entry = {'sku': sku}
        for i, row in enumerate(grp.itertuples(index=False), start=1):
            entry[f'brand{i}']     = row.company_name
            entry[f'reference{i}'] = row.relation_code
        records.append(entry)

    # 3) DataFrame e normalizzazione SKU
    df_codes = pd.DataFrame(records, dtype=str)
    df_codes['sku_stripped'] = df_codes['sku'].str.lstrip('0')
else:
    st.sidebar.warning("Carica l'Excel dei Riferimenti Originali per procedere.")
    st.stop()

# 4) Merge con df_products
df_products = df_products.merge(
    df_codes,
    left_on='prod_stripped',
    right_on='sku_stripped',
    how='left'
)

# 5) Identifica colonne dinamiche e converti in category
brand_cols     = [c for c in df_codes.columns if c.startswith('brand')]
reference_cols = [c for c in df_codes.columns if c.startswith('reference')]
for c in brand_cols + reference_cols:
    df_products[c] = df_products[c].astype('category')


# ——— Applicazioni Macchine da Excel ———
if apps_excel:
    df_apps = load_excel(apps_excel)

    records = []
    for _, row in df_apps.iterrows():
        # 1) tieni il codice così com'è (con zeri)
        code = str(row['code'])
        # 2) crei anche la versione stripped per il merge
        sku_stripped = code.lstrip('0')

        brand = str(row['company_name']).strip()
        raw_refs = row.get('relation_code', '')
        for ref in str(raw_refs).split(','):
            if ref.strip():
                records.append({
                    'sku':           code,          # con zeri
                    'sku_stripped':  sku_stripped,  # senza zeri
                    'brand':         brand,
                    'reference':     ref.strip()
                })

    df_apps_long = pd.DataFrame(records)
else:
    st.sidebar.warning("Carica l'Excel Applicazioni Macchine per procedere.")
    st.stop()


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

# Load Dati SAP
if sap_file:
    df_sap = load_excel(sap_file)
else:
    df_sap = None

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Dati",
    "🔍 Rif. Originale",
    "🚜 Applicazioni macchine",
    "📊 B2B (tutti)",
    "📊 B2B (esclusivi)",
    "📈 Dati SAP",
    "📋 SAP esclusivi"
])

# Tab1: Visualizzazione Prodotti
with tab1:
    st.subheader("Visualizzazione Prodotti")

    # 1) Selezione categoria (solo se value_it esiste)
    if 'value_it' in df_products.columns:
        sel_cat = st.selectbox(
            "Categoria (value_it)",
            options=list(df_products['value_it'].cat.categories)
        )
        df_cat = df_products[df_products['value_it'] == sel_cat].copy()
    else:
        # se manca, lavoro sull'intero df
        df_cat = df_products.copy()

    # 2) Toggle sellout (non stock)
    mostra_sellout = st.checkbox("Mostra sellout ivato")

    # 3) Attributi extra pre-mappati
    available_attrs = []
    if 'value_it' in df_products.columns:
        available_attrs = [
            attr for attr in mapping.get(sel_cat, [])
            if attr in df_cat.columns and df_cat[attr].notna().any()
        ]
    extras = st.multiselect(
        "Attributi Extra (mappati)",
        options=available_attrs,
        default=available_attrs
    )

    # 4) Un solo attributo extra non mappato
    remaining = [
        col for col in df_products.columns
        if col not in ['product_code','titolo_prodotto','value_it'] + available_attrs
    ]
    extra_manual = st.selectbox(
        "Aggiungi un attributo in più",
        options=[""] + remaining
    )
    if extra_manual:
        extras.append(extra_manual)

    # 5) Filtri (multi-selezione) su product_code, titolo_prodotto e extras
    st.markdown("**Filtri (multi-selezione)**")
    df_filtered = df_cat.copy()
    filter_cols = ['product_code', 'titolo_prodotto'] + extras
    for col in filter_cols:
        if col in df_filtered.columns:
            opts = sorted(df_filtered[col].dropna().astype(str).unique())
            vals = st.multiselect(f"Filtra {col}", options=opts, key=f"flt_{col}")
            if vals:
                df_filtered = df_filtered[df_filtered[col].astype(str).isin(vals)]

    # 6) Colonne da mostrare
    display_cols = ['product_code', 'titolo_prodotto']
    if 'value_it' in df_products.columns:
        display_cols.append('value_it')
    display_cols += extras
    if mostra_sellout and 'sellout_ivato' in df_filtered.columns:
        display_cols.append('sellout_ivato')

    # 7) Mostra tabella
    st.dataframe(
        df_filtered[display_cols].reset_index(drop=True),
        use_container_width=True
    )

# Tab2: Ricerca Brand/Modello
with tab2:
    st.subheader("Ricerca Brand/Modello")

    # 1) Selezione del Brand
    if brand_cols:
        all_brands = sorted({
            b.strip().lower()
            for col in brand_cols
            for cell in df_products[col].dropna().astype(str)
            for b in cell.split(',')
        })
        sel_brand = st.selectbox("Brand", [""] + all_brands)
    else:
        sel_brand = ""

    # Se non hai scelto il Brand, esci qui
    if not sel_brand:
        st.info("Seleziona prima un Brand per vedere i Modelli disponibili.")
    else:
        # 2) Selezione del Modello/Riferimento a cascata
        df_brand = df_products[
            df_products[brand_cols]
                .apply(lambda row: sel_brand in [str(v).strip().lower() for v in row if isinstance(v, str)], axis=1)
        ]
        all_refs = sorted({
            ref.strip()
            for col in reference_cols
            for cell in df_brand[col].dropna().astype(str)
            for ref in cell.split(',')
        })
        sel_mod = st.selectbox("Modello / Riferimento", [""] + all_refs)

        # Se non hai scelto il Modello, esci qui
        if not sel_mod:
            st.info("Seleziona un Modello / Riferimento per procedere.")
        else:
            # 3) Prepara df_search filtrando su Brand e su tutte le colonne referenceN
            df_search = df_products.copy()
            # filtro Brand
            df_search = df_search[
                df_search[brand_cols]
                    .apply(lambda row: sel_brand in [str(v).strip().lower() for v in row if isinstance(v, str)], axis=1)
            ]
            # filtro Modello/Riferimento
            mask_ref = df_search[reference_cols].eq(sel_mod).any(axis=1)
            df_search = df_search[mask_ref].copy()

            # aggiungo colonne fisse per visualizzazione
            df_search['Brand'] = sel_brand
            df_search['Riferimento'] = sel_mod

            # 4) Mostra risultati
            if df_search.empty:
                st.info("Nessun risultato trovato.")
            else:
                display_cols = ['product_code', 'titolo_prodotto', 'value_it', 'Brand', 'Riferimento']
                st.dataframe(
                    df_search[display_cols].reset_index(drop=True),
                    use_container_width=True
                )

# Tab3: Applicazioni Macchine
with tab3:
    st.subheader("Applicazioni Macchine")

    if df_apps_long.empty:
        st.info("Carica l'Excel Applicazioni Macchine per procedere.")
    else:
        # 1) Selezione SKU (mostra con zeri)
        skus = sorted(df_apps_long['sku'].unique())
        sel_sku = st.selectbox("SKU", [""] + skus)
        dff = df_apps_long.copy()
        if sel_sku:
            dff = dff[dff['sku'] == sel_sku]

        # 2) Selezione Brand a cascata
        brands = sorted(dff['brand'].unique())
        sel_brand_app = st.selectbox("Brand", [""] + brands)
        if sel_brand_app:
            dff = dff[dff['brand'] == sel_brand_app]

        # 3) Selezione Reference a cascata
        refs = sorted(dff['reference'].unique())
        sel_ref = st.selectbox("Riferimento", [""] + refs)
        if sel_ref:
            dff = dff[dff['reference'] == sel_ref]

        # 4) Aggiungi titolo_prodotto se mancante, mergeando su sku_stripped
        if 'titolo_prodotto' not in dff.columns:
            dff = dff.merge(
                df_products[['prod_stripped', 'titolo_prodotto']],
                left_on='sku_stripped',
                right_on='prod_stripped',
                how='left'
            )

        # 5) Visualizzazione
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

# Tab6: Dati SAP
with tab6:
    st.subheader("Dati SAP")
    if df_sap is None:
        st.info("Carica l'Excel Dati SAP nella sidebar per procedere.")
    else:
        # Partiamo da df_sap intero
        df_sap_f = df_sap.copy()
        st.markdown("**Filtri Dati SAP**")
        # Per ogni colonna, offriamo un multiselect se ha pochi valori unici
        for col in df_sap_f.columns:
            vals = df_sap_f[col].dropna().unique().tolist()
            # mostriamo il filtro solo se non è una colonna troppo variegata
            if 1 < len(vals) <= 100:
                sel = st.multiselect(f"Filtra {col}", options=sorted(vals), key=f"sap_{col}")
                if sel:
                    df_sap_f = df_sap_f[df_sap_f[col].isin(sel)]
        # Visualizza
        st.dataframe(df_sap_f.reset_index(drop=True), use_container_width=True)

# Tab7: SKU in Dati SAP esclusivi (non in B2B)
with tab7:
    st.subheader("SKU SAP non presenti in B2B (tutti)")

    # Controllo file caricati
    if df_sap is None or b2b_file is None:
        st.info("Carica sia l'Excel Dati SAP che l'Excel Prodotti B2B nella sidebar.")
    else:
        # 1) Prepara i codici per il confronto
        df_sap_proc = df_sap.copy()
        # rimuove eventuali caratteri non alfanumerici e gli zeri iniziali
        df_sap_proc['sku_stripped'] = (
            df_sap_proc['materialcode']
              .str.replace(r'[^A-Za-z0-9]', '', regex=True)
              .str.lstrip('0')
        )

        # 2) Prendi l'insieme di SKU B2B già caricati e normalizzati
        b2b_skus = set(df_b2b['prod_stripped'])

        # 3) Filtra quelli di SAP che NON sono in B2B
        df_exclusive = df_sap_proc[
            ~df_sap_proc['sku_stripped'].isin(b2b_skus)
        ].copy()

        # 4) Mostra la tabella
        st.dataframe(
            df_exclusive.reset_index(drop=True),
            use_container_width=True
        )

# -------------------------------------------
# Footer
# -------------------------------------------
st.markdown(
    """
   <footer style="
  text-align: center;
  padding: 1rem;
  background-color: #111827;       /* sfondo scuro */
">
  <p style="
    margin: 0;
    color: #F3F4F6;                /* testo chiaro */
    font-family: sans-serif;
    font-size: 0.9rem;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  ">
    <!-- foglia verde come grafica semplice -->
    <svg width="16" height="16" viewBox="0 0 24 24" fill="#10B981" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2C8.13 2 5 5.13 5 9c0 4.97 7 13 7 13s7-8.03 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5S10.62 6.5 12 6.5s2.5 1.12 2.5 2.5S13.38 11.5 12 11.5z"/>
    </svg>
    © 2025 Agristore. Tutti i diritti riservati.
  </p>
</footer>

    """,
    unsafe_allow_html=True
)
