# app.py
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from typing import List

st.set_page_config(page_title="MBTI by Country — TOP 10", layout="wide")

STANDARD_MBTI = [
    "INTJ","INTP","ENTJ","ENTP","INFJ","INFP","ENFJ","ENFP",
    "ISTJ","ISFJ","ESTJ","ESFJ","ISTP","ISFP","ESTP","ESFP"
]

@st.cache_data
def load_csv(uploaded_file):
    # If user uploaded, use it; else try default path
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
    else:
        # default path used in this session (from your provided file)
        df = pd.read_csv("/mnt/data/countriesMBTI_16types.csv", encoding="utf-8", low_memory=False)
    return df

def find_mbti_columns(df: pd.DataFrame) -> List[str]:
    cols = list(df.columns)
    # 1) exact matches (case-insensitive)
    exact = [c for c in cols if c.strip().upper() in STANDARD_MBTI]
    if exact:
        return exact

    # 2) columns whose name contains an MBTI type (e.g., "INTJ_pct" or "MBTI_INTJ")
    contains = []
    for c in cols:
        cu = c.upper()
        for m in STANDARD_MBTI:
            if m in cu:
                contains.append(c)
                break
    if contains:
        # deduplicate preserving order
        seen = []
        for c in contains:
            if c not in seen:
                seen.append(c)
        return seen

    # 3) try find a single column that contains MBTI strings per row
    candidates = [c for c in cols if df[c].dtype == object and ('mbti' in c.lower() or 'type' in c.lower())]
    for c in candidates:
        s = df[c].dropna().astype(str).str.strip().str.upper()
        match_ratio = s.isin(STANDARD_MBTI).mean() if len(s)>0 else 0
        if match_ratio > 0.3:  # heuristic
            return [c]

    # 4) fallback: detect any column whose values look like MBTI strings
    for c in cols:
        if df[c].dtype == object:
            s = df[c].dropna().astype(str).str.strip().str.upper()
            if len(s) > 0 and (s.isin(STANDARD_MBTI).mean() > 0.4):
                return [c]

    return []

def prepare_mbti_matrix(df: pd.DataFrame, country_col='Country'):
    """
    Return a DataFrame with index = country, columns = MBTI types (16), values = counts or percentages.
    Handles:
    - Case A: dataset has 16 separate columns named by MBTI types or containing MBTI substrings -> use as-is (numeric).
    - Case B: dataset has a single column with MBTI strings -> count per country.
    - Case C: dataset has MBTI columns but multiple rows per country -> aggregate by mean or sum (if counts).
    """
    cols = find_mbti_columns(df)
    if not cols:
        st.warning("데이터 내에서 MBTI 관련 열을 자동으로 찾지 못했습니다. 업로드한 파일의 구조가 특이할 수 있습니다.")
        return None, None

    # Case: single column that contains MBTI string values
    if len(cols) == 1 and cols[0].strip().upper() not in STANDARD_MBTI:
        mbti_col = cols[0]
        if country_col not in df.columns:
            st.error(f"Country(국가) 열을 찾을 수 없습니다. 데이터에 국가명 컬럼이 필요합니다 (예: 'Country'). 현재 컬럼: {list(df.columns)}")
            return None, None
        grouped = df[[country_col, mbti_col]].dropna()
        grouped[mbti_col] = grouped[mbti_col].astype(str).str.strip().str.upper()
        # keep only valid MBTI rows
        grouped = grouped[grouped[mbti_col].isin(STANDARD_MBTI)]
        # counts per country x mbti
        ct = pd.crosstab(grouped[country_col], grouped[mbti_col])
        # also compute percentages per country
        pct = ct.div(ct.sum(axis=1).replace(0, np.nan), axis=0) * 100
        return ct, pct

    # Otherwise multiple columns which are MBTI columns
    # Map column names to MBTI types via substring matching
    mbti_map = {}
    for c in cols:
        cu = c.upper()
        found = None
        for m in STANDARD_MBTI:
            if m in cu:
                found = m
                break
        if found:
            mbti_map[found] = c
    # If some MBTIs missing, add zeros
    if country_col not in df.columns:
        st.error(f"Country(국가) 열을 찾을 수 없습니다. 데이터에 국가명 컬럼이 필요합니다 (예: 'Country'). 현재 컬럼: {list(df.columns)}")
        return None, None

    # Build matrix: rows per country; values aggregated (sum or mean)
    numeric_cols = []
    for mbti, colname in mbti_map.items():
        # if col is numeric use it; else try to coerce
        if np.issubdtype(df[colname].dtype, np.number):
            numeric_cols.append(colname)
        else:
            # try convert
            coerced = pd.to_numeric(df[colname], errors='coerce')
            if coerced.notna().sum() > 0:
                df[colname] = coerced
                numeric_cols.append(colname)
            else:
                df[colname] = 0
                numeric_cols.append(colname)

    # Aggregate (sum if multiple rows per country)
    agg = df[[country_col] + list(mbti_map.values())].groupby(country_col).sum(min_count=1)
    # rename columns to MBTI standardized
    agg = agg.rename(columns={v: k for k, v in mbti_map.items()})
    # ensure all 16 columns present
    for m in STANDARD_MBTI:
        if m not in agg.columns:
            agg[m] = 0.0
    agg = agg[STANDARD_MBTI]  # order
    # Compute percentages per country
    row_sums = agg.sum(axis=1).replace(0, np.nan)
    pct = agg.div(row_sums, axis=0) * 100
    return agg, pct

# --- Streamlit UI ---
st.title("특정 MBTI 유형이 높은 국가 TOP 10")
st.markdown("Altair 시각화로 특정 MBTI 유형이 높은 국가 Top 10을 보여줍니다. CSV 업로드를 권장합니다. 업로드가 없으면 기본 경로(`/mnt/data/countriesMBTI_16types.csv`)를 시도합니다.")

uploaded = st.sidebar.file_uploader("CSV 파일 업로드 (선택)", type=["csv"])
df = None
try:
    df = load_csv(uploaded)
except Exception as e:
    st.error(f"파일 불러오기 실패: {e}")

if df is None:
    st.stop()

st.sidebar.markdown("**데이터 미리보기**")
if st.sidebar.checkbox("상위 10행 보기", value=False):
    st.sidebar.dataframe(df.head(10))

# try to find country column
possible_country_cols = [c for c in df.columns if c.lower() in ("country","nation","country_name","countryname","country/region")]
country_col = possible_country_cols[0] if possible_country_cols else None
if not country_col:
    # fallback: guess the column with many unique string values
    string_cols = [c for c in df.columns if df[c].dtype == object]
    if string_cols:
        # choose the string column that has many unique values (heuristic)
        string_uniques = sorted(string_cols, key=lambda c: df[c].nunique(), reverse=True)
        if string_uniques:
            country_col = string_uniques[0]

st.write(f"감지된 국가 컬럼: **{country_col}**")

counts_matrix, pct_matrix = prepare_mbti_matrix(df, country_col=country_col)
if counts_matrix is None and pct_matrix is None:
    st.stop()

# determine available MBTI types
available_mbti = list(pct_matrix.columns) if pct_matrix is not None else list(counts_matrix.columns)
available_mbti = [m for m in available_mbti if m in STANDARD_MBTI]
available_mbti_sorted = sorted(available_mbti)

with st.sidebar:
    mbti_choice = st.selectbox("관심 있는 MBTI 유형을 선택하세요", options=available_mbti_sorted, index=0)
    top_n = st.slider("Top N 국가 개수", min_value=3, max_value=20, value=10)
    show_counts = st.checkbox("절대값(건수)으로 보기 (체크하지 않으면 비율 %로 표시)", value=False)
    normalize_hint = st.caption("주의: 입력 데이터에 따라 '건수' 또는 '비율'이 적절할 수 있습니다.")

# Build the top-N table
if show_counts:
    if counts_matrix is None:
        st.warning("원본 데이터에서 건수(absolute counts)를 바로 만들 수 없습니다. 비율을 대신 사용합니다.")
        series = pct_matrix[mbti_choice].sort_values(ascending=False).head(top_n)
        value_label = "Percent"
    else:
        series = counts_matrix[mbti_choice].sort_values(ascending=False).head(top_n)
        value_label = "Count"
else:
    series = pct_matrix[mbti_choice].sort_values(ascending=False).head(top_n)
    value_label = "Percent"

top_df = series.reset_index().rename(columns={mbti_choice: "value", "index": country_col})
# if percent, format value
if value_label == "Percent":
    top_df["display"] = top_df["value"].round(2)
else:
    # if counts, show integer where possible
    top_df["display"] = top_df["value"].apply(lambda x: int(x) if pd.notna(x) and float(x).is_integer() else round(float(x),2))

st.subheader(f"{mbti_choice} 유형이 높은 국가 Top {top_n}")
st.write(f"측정값: **{value_label}** (내림차순) — 총 국가 수: {len(pct_matrix)}")

# Altair horizontal bar chart
chart = alt.Chart(top_df).mark_bar().encode(
    x=alt.X("value:Q", title=(f"{mbti_choice} ({value_label})")),
    y=alt.Y(f"{country_col}:N", sort=alt.EncodingSortField(field="value", order="descending")),
    tooltip=[country_col + ":N", alt.Tooltip("value:Q", format=".2f")]
).properties(height=50 * len(top_df), width=800)

text = alt.Chart(top_df).mark_text(
    align='left',
    dx=3
).encode(
    x=alt.X("value:Q"),
    y=alt.Y(f"{country_col}:N"),
    text=alt.Text("display:N")
)

st.altair_chart((chart + text).configure_axis(labelFontSize=12, titleFontSize=14), use_container_width=True)

st.markdown("### Top 표")
st.dataframe(top_df[[country_col, "display"]].rename(columns={"display": value_label}))

# also show for a selected country the distribution across MBTI (small multiple)
st.markdown("---")
st.subheader("선택 국가의 MBTI 분포 확인")
country_select = st.selectbox("국가 선택", options=sorted(pct_matrix.index.tolist()), index=0)
dist = pct_matrix.loc[country_select].reset_index().rename(columns={"index":"MBTI", country_select:"Percent"})
dist = dist[["MBTI", country_select]].rename(columns={country_select:"Percent"})
dist = dist.sort_values("Percent", ascending=False)

bar = alt.Chart(dist).mark_bar().encode(
    x=alt.X("Percent:Q"),
    y=alt.Y("MBTI:N", sort=alt.EncodingSortField(field="Percent", order="descending")),
    tooltip=["MBTI:N", alt.Tooltip("Percent:Q", format=".2f")]
).properties(width=700, height=400)

st.altair_chart(bar, use_container_width=True)
st.dataframe(dist.style.format({"Percent":"{:.2f}%"}))

st.markdown("""
앱 설명:
- 이 앱은 입력 CSV를 자동으로 분석하여 MBTI 관련 컬럼(16유형) 또는 MBTI 문자열 컬럼을 찾아냅니다.
- 각 국가별로 MBTI 비율(%)을 계산하고, 사용자가 선택한 유형에 대해 상위 국가들을 보여줍니다.
- 데이터 구조가 다양할 수 있으므로 자동 탐지에 실패하면 CSV 구조(열 이름)를 알려주시면 맞춤 조정을 해드리겠습니다.
""")
