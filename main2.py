# Streamlit app: 용산구 지역특화거리 상점 정보 분석기 (개선판)
# 파일 경로(앱에서 기본 사용): /mnt/data/서울특별시 용산구_지역특화거리거리상점정보_20221207.csv
# 주요 개선사항:
# - 기존 문법 에러(딕셔너리 컴프리헨션) 수정
# - 컬럼 자동 매핑을 더 견고하게 개선 및 수동 매핑 UI 추가
# - KPI 카드, Top-N 컨트롤, 도넛 차트(Altair), 결측치 히트맵(Altair) 추가
# - 필터링 상태를 명확히 보여주고 다운로드 및 요약 리포트 제공
# - 모든 시각화는 Altair 사용, 별도 패키지 설치 불필요

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import io

st.set_page_config(page_title="용산구 상점 분석기 (개선판)", layout="wide")

DATA_PATH = "/mnt/data/서울특별시 용산구_지역특화거리거리상점정보_20221207.csv"

@st.cache_data
def load_data(path=DATA_PATH):
    """여러 인코딩을 시도해서 CSV 를 안전하게 로드합니다."""
    encodings = ["utf-8", "utf-8-sig", "cp949", "euc-kr", "latin1"]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
    # 로컬 파일이 없거나 읽을 수 없으면 예외 발생
    raise last_err


def guess_columns(df):
    """데이터프레임 컬럼명으로부터 업소명/업종/주소/위도/경도/등록일 후보를 찾습니다."""
    lowered = {c.lower().replace(' ', '').replace('\t',''): c for c in df.columns}

    def find(keys):
        for k in keys:
            if k in lowered:
                return lowered[k]
        return None

    candidates = {
        'name': find(['상호', '상호명', '업소명', 'name', 'shopname', '상호명(한글)']),
        'category': find(['업종', '업태', '업종대분류', '업종명', 'category']),
        'address': find(['도로명주소', '지번주소', '주소', 'addr', 'address']),
        'lat': find(['위도', 'latitude', 'lat']),
        'lon': find(['경도', 'longitude', 'lon', 'lng']),
        'reg_date': find(['등록일', '등록날짜', 'date', '작성일', '등록일자'])
    }
    return candidates


def summarize(df):
    total = len(df)
    missing = (df.isna().mean() * 100).round(2).sort_values(ascending=False)
    dtypes = df.dtypes.astype(str)
    unique_counts = df.nunique(dropna=False).sort_values(ascending=False)
    return total, missing, dtypes, unique_counts


# ---------- UI ----------
st.title("📍 용산구 지역특화거리 상점 분석기 — 개선판")
st.markdown("간단하고 직관적인 대시보드입니다. (Altair 기반 시각화, 추가 설치 불필요)")

# 데이터 로드 옵션
st.sidebar.header("데이터 로드")
use_default = st.sidebar.checkbox("기본 데이터 사용", value=True)

if use_default:
    try:
        df = load_data()
    except Exception as e:
        st.sidebar.error(f"기본 파일을 읽을 수 없습니다: {e}")
        uploaded = st.sidebar.file_uploader("CSV 파일 업로드 (인코딩 자동 시도)", type=["csv"])
        if uploaded is None:
            st.stop()
        else:
            uploaded.seek(0)
            df = pd.read_csv(io.BytesIO(uploaded.read()), encoding='utf-8', low_memory=False)
else:
    uploaded = st.sidebar.file_uploader("CSV 파일 업로드 (인코딩 자동 시도)", type=["csv"])
    if uploaded is None:
        st.info("왼쪽 사이드바에서 CSV를 업로드하거나 '기본 데이터 사용'을 선택하세요.")
        st.stop()
    else:
        uploaded.seek(0)
        # 먼저 utf-8 시도, 실패하면 cp949
        try:
            df = pd.read_csv(io.BytesIO(uploaded.read()), encoding='utf-8', low_memory=False)
        except Exception:
            uploaded.seek(0)
            df = pd.read_csv(io.BytesIO(uploaded.read()), encoding='cp949', low_memory=False)

# 기본 정보
total, missing, dtypes, unique_counts = summarize(df)

# 자동 후보 추출
candidates = guess_columns(df)

st.sidebar.header("컬럼 매핑 (수동 선택 가능)")
# 각 logical column에 대해 selectbox로 수동 설정 허용
col_options = ['(없음)'] + list(df.columns)
name_col = st.sidebar.selectbox("상호/업소명 컬럼", options=col_options, index=col_options.index(candidates.get('name') or '(없음)'))
category_col = st.sidebar.selectbox("업종/카테고리 컬럼", options=col_options, index=col_options.index(candidates.get('category') or '(없음)'))
address_col = st.sidebar.selectbox("주소 컬럼", options=col_options, index=col_options.index(candidates.get('address') or '(없음)'))
lat_col = st.sidebar.selectbox("위도 컬럼", options=col_options, index=col_options.index(candidates.get('lat') or '(없음)'))
lon_col = st.sidebar.selectbox("경도 컬럼", options=col_options, index=col_options.index(candidates.get('lon') or '(없음)'))
reg_col = st.sidebar.selectbox("등록일 컬럼", options=col_options, index=col_options.index(candidates.get('reg_date') or '(없음)'))

# 바꿔서 None으로 표현
def norm(col):
    return None if col == '(없음)' else col

name_col = norm(name_col)
category_col = norm(category_col)
address_col = norm(address_col)
lat_col = norm(lat_col)
lon_col = norm(lon_col)
reg_col = norm(reg_col)

# 상단 KPI 카드
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("총 상점 수", f"{total:,}")
with k2:
    st.metric("컬럼 수", f"{df.shape[1]}")
with k3:
    top_missing = missing.index[0] if len(missing)>0 else "-"
    top_missing_val = missing.iloc[0] if len(missing)>0 else 0
    st.metric("결측이 가장 많은 컬럼", f"{top_missing} ({top_missing_val}%)")
with k4:
    st.metric("고유 컬럼(최다)", f"{unique_counts.index[0]}: {unique_counts.iloc[0]}")

st.markdown("---")

# 데이터 샘플과 타입
left, right = st.columns([2,1])
with left:
    st.subheader("데이터 샘플")
    st.dataframe(df.head(10))
with right:
    st.subheader("컬럼 타입 & 결측")
    meta = pd.DataFrame({'column': df.columns, 'dtype': df.dtypes.astype(str), 'unique': df.nunique(dropna=False).values, 'missing_%': (df.isna().mean()*100).round(2).values})
    st.dataframe(meta.sort_values('missing_%', ascending=False).reset_index(drop=True))

# 필터 영역
st.sidebar.header("데이터 필터링")
filters = {}
if category_col:
    cats = df[category_col].fillna('(알수없음)')
    unique_cats = cats.value_counts().index.tolist()
    default = unique_cats[:6] if len(unique_cats)>=6 else unique_cats
    sel_cats = st.sidebar.multiselect("업종 선택 (여러개 가능)", options=unique_cats, default=default)
    filters['category'] = sel_cats
if name_col:
    name_search = st.sidebar.text_input("상호명 검색 (부분일치)")
    filters['name_search'] = name_search
coord_only = st.sidebar.checkbox("좌표 보유 항목만", value=False)
show_topn = st.sidebar.slider("Top N 시각화 개수", min_value=5, max_value=50, value=20)

# 필터 적용
df_filtered = df.copy()
if category_col and filters.get('category'):
    df_filtered = df_filtered[df_filtered[category_col].fillna('(알수없음)').isin(filters['category'])]
if name_col and filters.get('name_search'):
    q = filters['name_search'].strip()
    if q:
        df_filtered = df_filtered[df_filtered[name_col].astype(str).str.contains(q, case=False, na=False)]
if coord_only and lat_col and lon_col:
    df_filtered = df_filtered[df_filtered[lat_col].notna() & df_filtered[lon_col].notna()]

st.subheader("필터 적용 결과")
st.write(f"필터 전: {len(df):,} 행 — 필터 후: {len(df_filtered):,} 행")

# 결측치 시각화 (상단 몇개)
missing_df = (df.isna().mean()*100).round(2).reset_index()
missing_df.columns = ['column','missing_percent']
missing_df = missing_df[missing_df['missing_percent']>0]
if not missing_df.empty:
    st.subheader("결측률 높은 컬럼")
    mchart = alt.Chart(missing_df).mark_bar().encode(
        x=alt.X('missing_percent:Q', title='결측률 (%)'),
        y=alt.Y('column:N', sort='-x', title='컬럼'),
        tooltip=['column','missing_percent']
    ).properties(height=300)
    st.altair_chart(mchart, use_container_width=True)
else:
    st.info("데이터에 결측치가 거의 없습니다.")

# 업종 분포 (Top N)
if category_col:
    st.subheader("업종별 분포 (Top N)")
    cat_counts = df_filtered[category_col].fillna('(알수없음)').value_counts().reset_index()
    cat_counts.columns = ['category','count']
    topn = cat_counts.head(show_topn)
    bchart = alt.Chart(topn).mark_bar().encode(
        x=alt.X('count:Q', title='상점 수'),
        y=alt.Y('category:N', sort='-x', title='업종'),
        tooltip=['category','count']
    ).properties(height=400)
    st.altair_chart(bchart, use_container_width=True)

    # 도넛(원형) 차트
    try:
        pie = topn.copy()
        pie['percent'] = (pie['count'] / pie['count'].sum() * 100).round(2)
        pie_chart = alt.Chart(pie).mark_arc(innerRadius=50).encode(
            theta=alt.Theta('count:Q'),
            color=alt.Color('category:N', legend=alt.Legend(orient='right')),
            tooltip=['category','count','percent']
        ).properties(width=350, height=350)
        st.markdown("### 업종 비중 (Top N) — 도넛 차트")
        st.altair_chart(pie_chart, use_container_width=False)
    except Exception:
        pass

# 등록일 트렌드
if reg_col:
    st.subheader("등록일 기반 트렌드")
    try:
        df[reg_col] = pd.to_datetime(df[reg_col], errors='coerce')
        df_filtered[reg_col] = pd.to_datetime(df_filtered[reg_col], errors='coerce')
        ts = df_filtered.dropna(subset=[reg_col]).set_index(reg_col).resample('M').size().reset_index(name='count')
        if not ts.empty:
            lchart = alt.Chart(ts).mark_line(point=True).encode(
                x=alt.X(f'{reg_col}:T', title='기간'),
                y=alt.Y('count:Q', title='등록 수'),
                tooltip=[reg_col,'count']
            ).properties(height=300)
            st.altair_chart(lchart, use_container_width=True)
    except Exception:
        st.info("등록일 컬럼을 시계열로 변환할 수 없습니다.")

# 지도 표시
if lat_col and lon_col:
    st.subheader("지도 (st.map) — 필터된 데이터의 좌표 표시")
    try:
        coords = df_filtered[[lat_col, lon_col]].dropna()
        coords = coords.rename(columns={lat_col: 'lat', lon_col: 'lon'})
        coords['lat'] = pd.to_numeric(coords['lat'], errors='coerce')
        coords['lon'] = pd.to_numeric(coords['lon'], errors='coerce')
        coords = coords.dropna()
        if not coords.empty:
            st.map(coords)
        else:
            st.info("유효한 좌표 데이터가 없습니다.")
    except Exception as e:
        st.info(f"지도 표시 중 오류: {e}")
else:
    st.info("위도/경도 컬럼을 지정하면 지도에 표시할 수 있습니다.")

st.markdown("---")

# 필터된 데이터 테이블 + 다운로드
st.subheader("필터된 데이터 (테이블)")
st.dataframe(df_filtered.reset_index(drop=True))

@st.cache_data
def to_csv_bytes(df_in):
    return df_in.to_csv(index=False).encode('utf-8-sig')

csv_bytes = to_csv_bytes(df_filtered)
st.download_button("필터된 데이터 다운로드 (CSV)", data=csv_bytes, file_name="yongsan_filtered.csv", mime='text/csv')

# 간단한 자동 인사이트 생성
st.subheader("자동 인사이트")
insights = []
if category_col:
    topcat = df[category_col].fillna('(알수없음)').value_counts().head(1)
    if not topcat.empty:
        insights.append(f"가장 많은 업종: '{topcat.index[0]}' ({int(topcat.iloc[0])}개)")
high_missing = missing[missing > 50]
if not high_missing.empty:
    ins = ", ".join([f"{idx}({val}%)" for idx,val in high_missing.items()])
    insights.append(f"결측률 50% 이상 컬럼: {ins}")
if lat_col and lon_col:
    coords_count = df[lat_col].notna().sum()
    insights.append(f"위도/경도 정보 보유 행: {coords_count}개")

if insights:
    for s in insights:
        st.write("- ", s)
else:
    st.write("명확한 자동 인사이트가 없습니다. 필터를 바꿔보세요.")

st.markdown("---")
st.caption("앱은 데이터를 탐색하기 위한 시작점입니다. 추가 분석(텍스트 정제, 업종 표준화, 지오코딩 등)을 원하시면 다음 단계로 확장해 드리겠습니다.")
