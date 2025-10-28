# Streamlit app: 용산구 지역특화거리 상점 정보 분석기
# 파일 경로(앱에서 기본 사용): /mnt/data/서울특별시 용산구_지역특화거리거리상점정보_20221207.csv
# 설명: 업로드된 CSV를 자동으로 판별하고(인코딩 포함), 요약 통계, 결측치 분석,
# 업종 분포 시각화(Altair), 좌표가 존재하면 지도 시각화 등 인터랙티브한 대시보드를 제공합니다.
# 의존성: streamlit, pandas, altair, numpy (Streamlit Cloud 환경에 기본적으로 설치된 것으로 가정)

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import os
import io
import textwrap

st.set_page_config(page_title="용산구 지역특화거리 상점 분석", layout="wide")

DATA_PATH = "/mnt/data/서울특별시 용산구_지역특화거리거리상점정보_20221207.csv"

@st.cache_data(show_spinner=True)
def load_data(path=DATA_PATH):
    # 여러 인코딩을 시도해 안전하게 파일 로드
    encodings = ["utf-8", "cp949", "euc-kr", "latin1"]
    last_err = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df
        except Exception as e:
            last_err = e
    # 실패 시 에러 리레이즈
    raise last_err


def guess_columns(df):
    # 컬럼 이름을 소문자/공백 제거 형태로 매핑해 유사 컬럼을 찾음
    cols = {c: c for c in df.columns}
    lowered = {c: c.lower().replace(' ', ''): c for c in df.columns}

    def find(keys):
        for k in keys:
            if k in lowered:
                return lowered[k]
        return None

    candidates = {
        'name': find(['상호', '상호명', '업소명', 'name', 'shopname']),
        'category': find(['업종', '업태', '업종대분류', '업종명', 'category']),
        'address': find(['도로명주소', '지번주소', '주소', 'addr', 'address']),
        'lat': find(['위도', 'latitude', 'lat']),
        'lon': find(['경도', 'longitude', 'lon', 'lng']),
        'reg_date': find(['등록일', '등록날짜', 'date', '작성일'])
    }
    return candidates


def summarize(df):
    total = len(df)
    missing = (df.isna().mean() * 100).round(2).sort_values(ascending=False)
    dtypes = df.dtypes.astype(str)
    unique_counts = df.nunique(dropna=False).sort_values(ascending=False)
    return {
        'total': total,
        'missing': missing,
        'dtypes': dtypes,
        'unique_counts': unique_counts
    }


# ---------- 앱 레이아웃 ----------
st.title("📊 용산구 지역특화거리 상점 정보 — 분석 대시보드")
st.markdown(
    "이 앱은 업로드된 CSV 파일을 자동으로 읽고(인코딩을 시도함), 주요 통계와 시각화를 제공합니다.\n"
    "그래프는 Altair로 만들며, 추가 라이브러리 설치가 필요하지 않습니다."
)

# 사이드바: 파일 확인 및 로드
st.sidebar.header("데이터 로드 & 옵션")
st.sidebar.write(f"기본 데이터 경로: `{DATA_PATH}`")
use_default = st.sidebar.checkbox("기본 파일 사용", value=True)

if use_default:
    try:
        df = load_data()
    except Exception as e:
        st.sidebar.error(f"파일을 불러오지 못했습니다: {e}")
        st.stop()
else:
    uploaded = st.sidebar.file_uploader("CSV 파일 업로드 (인코딩 자동 시도)", type=["csv"])
    if uploaded is None:
        st.info("왼쪽 사이드바에서 업로드하거나 '기본 파일 사용'을 체크하세요.")
        st.stop()
    else:
        # 업로드된 파일을 메모리에서 읽음
        bytes_data = uploaded.read()
        # 먼저 utf-8, fallback cp949
        try:
            df = pd.read_csv(io.BytesIO(bytes_data), encoding='utf-8')
        except Exception:
            df = pd.read_csv(io.BytesIO(bytes_data), encoding='cp949')


# 기본 요약
candidates = guess_columns(df)
summary = summarize(df)

col1, col2, col3 = st.columns([1,1,2])
with col1:
    st.metric("총 행(상점) 수", f"{summary['total']:,}")
with col2:
    st.metric("컬럼 수", f"{df.shape[1]}")
with col3:
    st.metric("결측 컬럼(상위 1개)", f"{summary['missing'].index[0]}: {summary['missing'].iloc[0]}%")

st.markdown("---")

# 데이터 프리뷰 및 컬럼 정보
with st.expander("데이터 프리뷰 및 컬럼 정보 (클릭하여 확인)"):
    st.subheader("컬럼명 및 타입")
    st.dataframe(pd.DataFrame({'column': df.columns, 'dtype': df.dtypes.astype(str)}))
    st.subheader("데이터 샘플")
    st.dataframe(df.head(10))

# 결측치 시각화(Altair)
missing_df = summary['missing'].reset_index()
missing_df.columns = ['column', 'missing_percent']
missing_df = missing_df[missing_df['missing_percent'] > 0]

if not missing_df.empty:
    st.subheader("결측률 높은 컬럼")
    chart = alt.Chart(missing_df).mark_bar().encode(
        x=alt.X('missing_percent:Q', title='결측률 (%)'),
        y=alt.Y('column:N', sort='-x', title='컬럼'),
        tooltip=['column','missing_percent']
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("데이터에 결측치가 거의 없습니다.")

st.markdown("---")

# 업종/카테고리 분석
category_col = candidates.get('category')
name_col = candidates.get('name')
address_col = candidates.get('address')
lat_col = candidates.get('lat')
lon_col = candidates.get('lon')
reg_col = candidates.get('reg_date')

st.sidebar.header("필터")
filters = {}
if category_col:
    top_cats = df[category_col].fillna("(알수없음)").value_counts().head(50).index.tolist()
    sel_cats = st.sidebar.multiselect("업종(카테고리) 선택", options=top_cats, default=top_cats[:6])
    filters['category'] = sel_cats
else:
    st.sidebar.write("업종 컬럼을 자동으로 찾지 못했습니다.")

if name_col:
    name_search = st.sidebar.text_input("상호명 검색 (부분일치)")
    filters['name_search'] = name_search

coord_only = st.sidebar.checkbox("좌표(위도/경도) 있는 항목만 보기", value=False)
if coord_only and (lat_col is None or lon_col is None):
    st.sidebar.write("데이터에 위도/경도 컬럼을 찾지 못했습니다.")

# 필터 적용
df_filtered = df.copy()
if category_col and filters.get('category'):
    df_filtered = df_filtered[df_filtered[category_col].fillna('(알수없음)').isin(filters['category'])]
if name_col and filters.get('name_search'):
    sf = filters['name_search'].strip()
    if sf:
        df_filtered = df_filtered[df_filtered[name_col].astype(str).str.contains(sf, case=False, na=False)]
if coord_only and lat_col and lon_col:
    df_filtered = df_filtered[df_filtered[lat_col].notna() & df_filtered[lon_col].notna()]

st.subheader("필터 적용 결과")
st.write(f"필터 후 행 수: {len(df_filtered):,}")

# 상위 업종 시각화
if category_col:
    st.subheader("업종별 상점 수 (Top 20)")
    cat_counts = df_filtered[category_col].fillna('(알수없음)').value_counts().reset_index()
    cat_counts.columns = ['category','count']
    cat_top = cat_counts.head(20)
    chart = alt.Chart(cat_top).mark_bar().encode(
        x=alt.X('count:Q', title='상점 수'),
        y=alt.Y('category:N', sort='-x', title='업종'),
        tooltip=['category','count']
    ).properties(height=400)
    st.altair_chart(chart, use_container_width=True)

# 등록일/기간 분석 (있다면)
if reg_col:
    try:
        df[reg_col] = pd.to_datetime(df[reg_col], errors='coerce')
        df_filtered[reg_col] = pd.to_datetime(df_filtered[reg_col], errors='coerce')
        st.subheader("등록일 기반 트렌드")
        ts = df_filtered.dropna(subset=[reg_col]).set_index(reg_col).resample('M').size().reset_index(name='count')
        if not ts.empty:
            chart = alt.Chart(ts).mark_line(point=True).encode(
                x=alt.X(f"{reg_col}:T", title='기간(월)'),
                y=alt.Y('count:Q', title='등록 수'),
                tooltip=[reg_col,'count']
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
    except Exception:
        st.info("등록일 컬럼은 존재하지만 시계열로 변환할 수 없습니다.")

# 좌표가 있다면 지도 표시 (st.map 사용)
if lat_col and lon_col:
    st.subheader("지도에 점 표시 (위도/경도 기반)")
    try:
        coords = df_filtered[[lat_col, lon_col]].dropna()
        coords = coords.rename(columns={lat_col: 'lat', lon_col: 'lon'})
        # 숫자형으로 변환
        coords['lat'] = pd.to_numeric(coords['lat'], errors='coerce')
        coords['lon'] = pd.to_numeric(coords['lon'], errors='coerce')
        coords = coords.dropna()
        if not coords.empty:
            st.map(coords)
        else:
            st.info("필터된 데이터에서 유효한 좌표를 찾을 수 없습니다.")
    except Exception as e:
        st.info(f"지도 표시 중 오류가 발생했습니다: {e}")
else:
    st.info("데이터에서 위도/경도 컬럼을 자동으로 찾지 못했고, 외부 API 없이 지오코딩을 수행하지 않습니다.")

st.markdown("---")

# 데이터 테이블 및 다운로드
st.subheader("데이터 테이블 (필터 적용됨)")
st.dataframe(df_filtered.reset_index(drop=True))

# 다운로드 버튼
@st.cache_data
def to_csv_bytes(df_in):
    return df_in.to_csv(index=False).encode('utf-8')

csv_bytes = to_csv_bytes(df_filtered)
st.download_button(label="필터된 데이터 다운로드 (CSV)", data=csv_bytes, file_name="yongsan_filtered.csv", mime='text/csv')

st.markdown("---")

# 자동 인사이트 하이라이트 (간단한)
st.subheader("자동 인사이트 (요약)")
insights = []
# 1) 가장 많은 업종
if category_col:
    topcat = df[category_col].fillna('(알수없음)').value_counts().head(1)
    if not topcat.empty:
        insights.append(f"가장 많은 업종은 '{topcat.index[0]}'이며, 총 {int(topcat.iloc[0])}개입니다.")
# 2) 결측이 많은 컬럼
high_missing = summary['missing'][summary['missing'] > 50]
if not high_missing.empty:
    ins = ", ".join([f"{idx}({val}%)" for idx,val in high_missing.items()])
    insights.append(f"결측률 50% 이상인 컬럼: {ins}")
# 3) 좌표 존재 여부
if lat_col and lon_col:
    coords_count = df[lat_col].notna().sum()
    insights.append(f"위도/경도 정보가 있는 행: {coords_count}개")

if insights:
    for s in insights:
        st.write("- ", s)
else:
    st.write("명확한 자동 인사이트가 없습니다. 좌측 필터를 조정하거나 데이터를 살펴보세요.")

st.markdown("---")

st.caption("앱 내 분석은 업로드된 데이터의 컬럼명/포맷에 따라 자동으로 적응합니다. 추가 분석(예: 텍스트 마이닝, 정교한 지오코딩 등)을 원하시면 알려주세요.")
