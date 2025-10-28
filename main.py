# app.py
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from typing import List

st.set_page_config(page_title="MBTI by Country — TOP 10 (Fixed)", layout="wide")

STANDARD_MBTI = [
    "INTJ","INTP","ENTJ","ENTP","INFJ","INFP","ENFJ","ENFP",
    "ISTJ","ISFJ","ESTJ","ESFJ","ISTP","ISFP","ESTP","ESFP"
]

@st.cache_data
def load_csv(uploaded_file):
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    else:
        return pd.read_csv("/mnt/data/countriesMBTI_16types.csv", encoding="utf-8", low_memory=False)

def find_mbti_columns(df: pd.DataFrame) -> List[str]:
    cols = list(df.columns)
    exact = [c for c in cols if c.strip().upper() in STANDARD_MBTI]
    if exact:
        return exact

    contains = []
    for c in cols:
        cu = c.upper()
        for m in STANDARD_MBTI:
            if m in cu:
                contains.append(c)
                break
    if contains:
        # dedupe preserve order
        seen = []
        for c in contains:
            if c not in seen:
                seen.append(c)
        return seen

    candidates = [c for c in cols if df[c].dtype == object and ('mbti' in c.lower() or 'type' in c.lower())]
    for c in candidates:
        s = df[c].dropna().astype(str).str.strip().str.upper()
        match_ratio = s.isin(STANDARD_MBTI).mean() if len(s) > 0 else 0
        if match_ratio > 0.3:
            return [c]

    for c in cols:
        if df[c].dtype == object:
            s = df[c].dropna().astype(str).str.strip().str.upper()
            if len(s) > 0 and (s.isin(STANDARD_MBTI).mean() > 0.4):
                return [c]
    return []

def prepare_mbti_matrix(df: pd.DataFrame, country_col='Country'):
    cols = find_mbti_columns(df)
    if not cols:
        st.warning("MBTI 관련 열을 자동으로 찾지 못했습니다.")
        return None, None

    # Case: single column that is a MBTI string column (e.g., each row has a type)
    if len(cols) == 1 and cols[0].strip().upper() not in STANDARD_MBTI:
        mbti_col = cols[0]
        if country_col not in df.columns:
            st.error(f"Country 열을 못 찾음. 데이터 컬럼: {list(df.columns)}")
            return None, None
        grouped = df[[country_col, mbti_col]].dropna()
        grouped[mbti_col] = grouped[mbti_col].astype(str).str.strip().str.upper()
        grouped = grouped[grouped[mbti_col].isin(STANDARD_MBTI)]
        if grouped.empty:
            st.warning("MBTI 문자열 열을 찾았지만 유효한 MBTI값이 없습니다.")
            return None, None
        ct = pd.crosstab(grouped[country_col].str.strip(), grouped[mbti_col])
        pct = ct.div(ct.sum(axis=1).replace(0, np.nan), axis=0) * 100
        # ensure all 16 types present
        for m in STANDARD_MBTI:
            if m not in ct.columns:
                ct[m] = 0
                pct[m] = 0.0
        ct = ct[STANDARD_MBTI]
        pct = pct[STANDARD_MBTI]
        return ct, pct

    # Case: multiple columns representing MBTI types (maybe with suffixes)
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

    if country_col not in df.columns:
        st.error(f"Country 열을 못 찾음. 데이터 컬럼: {list(df.columns)}")
        return None, None

    # Coerce mapped columns to numeric where possible
    for mbti, colname in mbti_map.items():
        if not np.issubdtype(df[colname].dtype, np.number):
            coerced = pd.to_numeric(df[colname], errors='coerce')
            # if conversion meaningful, replace; otherwise set zeros
            if coerced.notna().sum() > 0:
                df[colname] = coerced.fillna(0)
            else:
                df[colname] = 0

    agg = df[[country_col] + list(mbti_map.values())].groupby(df[country_col].astype(str).str.strip()).sum(min_count=1)
    agg = agg.rename(columns={v: k for k, v in mbti_map.items()})
    for m in STANDARD_MBTI:
        if m not in agg.columns:
            agg[m] = 0.0
    agg = agg[STANDARD_MBTI]
    row_sums = agg.sum(axis=1).replace(0, np.nan)
    pct = agg.div(row_sums, axis=0) * 100
    return agg, pct

# UI
st.title("특정 MBTI 유형이 높은 국가 TOP 10 — 안정화 버전")
st.markdown("CSV 업로드 권장. 없으면 `/mnt/data/countriesMBTI_16types.csv`를 시도합니다.")

uploaded = st.sidebar.file_uploader("CSV 파일 업로드 (선택)", type=["csv"])
try:
    df = load_csv(uploaded)
except Exception as e:
    st.error(f"파일 불러오기 실패: {e}")
    st.stop()

st.sidebar.markdown("### 데이터 미리보기")
if st.sidebar.checkbox("상위 10행 보기", value=False):
    st.sidebar.dataframe(df.head(10))

# detect country column heuristically
possible_country_cols = [c for c in df.columns if c.lower() in ("country","nation","country_name","countryname","country/region","country_region")]
country_col = possible_country_cols[0] if possible_country_cols else None
if not country_col:
    string_cols = [c for c in df.columns if df[c].dtype == object]
    if string_cols:
        string_uniques = sorted(string_cols, key=lambda c: df[c].nunique(), reverse=True)
        country_col = string_uniques[0]
if not country_col:
    st.error("국가 컬럼을 자동으로 찾지 못했습니다. CSV에 국가명 컬럼(예: 'Country')이 필요합니다.")
    st.stop()

st.write(f"감지된 국가 컬럼: **{country_col}**")

counts_matrix, pct_matrix = prepare_mbti_matrix(df, country_col=country_col)
if pct_matrix is None:
    st.stop()

available_mbti = [m for m in pct_matrix.columns if m in STANDARD_MBTI]
available_mbti_sorted = sorted(available_mbti)
if not available_mbti_sorted:
    st.error("데이터에서 사용할 수 있는 MBTI 유형을 찾을 수 없습니다.")
    st.stop()

with st.sidebar:
    mbti_choice = st.selectbox("관심 있는 MBTI 유형을 선택하세요", options=available_mbti_sorted, index=0)
    top_n = st.slider("Top N 국가 개수", min_value=3, max_value=20, value=10)
    show_counts = st.checkbox("절대값(건수)으로 보기 (체크하지 않으면 비율 %로 표시)", value=False)

if show_counts and counts_matrix is None:
    st.warning("건수(absolute counts) 열을 존재하지 않습니다. 비율(%)로 대체합니다.")
    show_counts = False

if show_counts:
    series = counts_matrix[mbti_choice].sort_values(ascending=False).head(top_n)
    value_label = "Count"
else:
    series = pct_matrix[mbti_choice].sort_values(ascending=False).head(top_n)
    value_label = "Percent"

top_df = series.reset_index().rename(columns={0: "value"})
# ensure column names uniform
top_df.columns = [country_col if i == 0 else "value" for i, _ in enumerate(top_df.columns)]

# display formatting
if value_label == "Percent":
    top_df["display"] = top_df["value"].round(2)
else:
    top_df["display"] = top_df["value"].apply(lambda x: int(x) if pd.notna(x) and float(x).is_integer() else round(float(x), 2))

st.subheader(f"{mbti_choice} 유형이 높은 국가 Top {top_n}")
st.write(f"측정값: **{value_label}** — 데이터에 포함된 국가 수: {len(pct_matrix)}")

chart = alt.Chart(top_df).mark_bar().encode(
    x=alt.X("value:Q", title=f"{mbti_choice} ({value_label})"),
    y=alt.Y(f"{country_col}:N", sort=alt.EncodingSortField(field="value", order="descending")),
    tooltip=[alt.Tooltip(country_col + ":N"), alt.Tooltip("value:Q", format=".2f")]
).properties(height=50 * len(top_df), width=800)

text = alt.Chart(top_df).mark_text(align='left', dx=3).encode(
    x=alt.X("value:Q"),
    y=alt.Y(f"{country_col}:N"),
    text=alt.Text("display:N")
)

st.altair_chart((chart + text).configure_axis(labelFontSize=12, titleFontSize=14), use_container_width=True)

st.markdown("### Top 표")
st.dataframe(top_df[[country_col, "display"]].rename(columns={"display": value_label}))

# --- 안전한 선택 국가 분포 표시 (KeyError 방지) ---
st.markdown("---")
st.subheader("선택 국가의 MBTI 분포 확인")

country_list = sorted(pct_matrix.index.tolist())
if not country_list:
    st.warning("분석 가능한 국가가 없습니다.")
    st.stop()

country_select = st.selectbox("국가 선택", options=country_list, index=0)

# 안전하게 series로 취득하고 컬럼 이름을 확정
try:
    s = pct_matrix.loc[country_select]
except Exception as e:
    st.error(f"{country_select}에 대한 데이터를 찾을 수 없습니다: {e}")
    st.stop()

# s는 Series인 것이 정상 — 이를 안전하게 DataFrame으로 변환
if isinstance(s, pd.Series):
    dist = s.reset_index()
    dist.columns = ["MBTI", "Percent"]
else:
    # 혹시 DataFrame 구조면 첫 열을 percent로 취급
    dist = pd.DataFrame(s).reset_index()
    if dist.shape[1] >= 2:
        dist.columns = ["MBTI", "Percent"] + list(dist.columns[2:])
    else:
        dist.columns = ["MBTI", "Percent"]

# 정렬 및 소수점 포맷
dist["Percent"] = pd.to_numeric(dist["Percent"], errors='coerce').fillna(0)
dist = dist.sort_values("Percent", ascending=False)

bar = alt.Chart(dist).mark_bar().encode(
    x=alt.X("Percent:Q"),
    y=alt.Y("MBTI:N", sort=alt.EncodingSortField(field="Percent", order="descending")),
    tooltip=[alt.Tooltip("MBTI:N"), alt.Tooltip("Percent:Q", format=".2f")]
).properties(width=700, height=400)

st.altair_chart(bar, use_container_width=True)
# show pretty table with percent formatting
dist_to_show = dist.copy()
dist_to_show["Percent"] = dist_to_show["Percent"].map(lambda x: f"{x:.2f}%")
st.dataframe(dist_to_show)

st.markdown("""
앱 개선 포인트:
- 이제 `KeyError` 발생 지점을 방어적으로 고쳤습니다. `reset_index()` 결과의 컬럼 이름을 직접 설정하여 어떤 케이스에서도 `"MBTI"`와 `"Percent"` 컬럼이 확보됩니다.
- 데이터 구조가 다양하면 자동감지에 실패할 수 있으니 실패 시 CSV 헤더(열 이름)를 알려주시면 맞춤 수정해 드립니다.
""")
