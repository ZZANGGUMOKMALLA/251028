# Streamlit app — 용산구 지역특화거리 상점 정보 분석기 (완성판)
# Single-file Streamlit app, Altair-only 시각화, Streamlit Cloud 배포 가능
# 주요 특징:
# - 로컬 파일, 업로드, 공개 CSV URL(GitHub/Drive/Dropbox 등) 모두 지원
# - 자동 컬럼 매핑 + 수동 매핑 옵션
# - Altair로 제작한 세련된 차트(막대, 도넛, 시계열, 결측 히트맵)
# - 지도는 st.map 사용(추가 라이브러리 불필요)
# - 기본 샘플 데이터 내장: 파일 없는 사용자를 위한 체험 모드
# - 다운로드, 요약 리포트(간단 텍스트), 인터랙티브 필터 제공

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import io
import re

# ----------------- 설정 -----------------
st.set_page_config(page_title="용산구 상점 분석기 (완성판)", layout="wide")
alt.data_transformers.disable_max_rows()

DATA_PATH = "/mnt/data/서울특별시 용산구_지역특화거리거리상점정보_20221207.csv"

# ----------------- 유틸리티 -----------------
@st.cache_data
def try_read_csv_from_path(path):
    encodings = ["utf-8", "utf-8-sig", "cp949", "euc-kr", "latin1"]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except Exception as e:
            last_err = e
    raise last_err


def normalize_public_url(url: str) -> str:
    if not isinstance(url, str):
        return url
    url = url.strip()
    # Google Drive
    m = re.search(r'drive.google.com/.+?/d/([a-zA-Z0-9_-]+)', url)
    if m:
        fid = m.group(1)
        return f'https://drive.google.com/uc?export=download&id={fid}'
    m2 = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if 'drive.google.com' in url and m2:
        return f'https://drive.google.com/uc?export=download&id={m2.group(1)}'
    # Dropbox
    if 'dropbox.com' in url:
        if 'dl=0' in url:
            return url.replace('dl=0','dl=1')
        if not re.search(r'[?&]dl=', url):
            return url + '?dl=1'
    # GitHub blob -> raw
    m3 = re.search(r'https://github.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)', url)
    if m3:
        user, repo, branch, path = m3.group(1), m3.group(2), m3.group(3), m3.group(4)
        return f'https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}'
    return url


@st.cache_data
def load_data_with_fallback(local_path=None, public_url=None, uploaded_file=None):
    # 1) 로컬
    if local_path:
        try:
            df_local = try_read_csv_from_path(local_path)
            return df_local, f'local:{local_path}'
        except Exception:
            pass
    # 2) 업로드
    if uploaded_file is not None:
        try:
            uploaded_file.seek(0)
            return pd.read_csv(io.BytesIO(uploaded_file.read()), encoding='utf-8', low_memory=False), 'uploaded:memory'
        except Exception:
            try:
                uploaded_file.seek(0)
                return pd.read_csv(io.BytesIO(uploaded_file.read()), encoding='cp949', low_memory=False), 'uploaded:memory'
            except Exception as e:
                raise e
    # 3) 공개 URL
    if public_url:
        try:
            norm = normalize_public_url(public_url)
            return pd.read_csv(norm, low_memory=False), f'url:{norm}'
        except Exception as e:
            raise e
    raise FileNotFoundError("No data source available. Provide a local file, upload, or public CSV URL.")


def guess_columns(df):
    lowered = {c.lower().replace(' ', '').replace('\t',''): c for c in df.columns}
    def find(keys):
        for k in keys:
            if k in lowered:
                return lowered[k]
        return None
    candidates = {
        'name': find(['상호','상호명','업소명','name','shopname']),
        'category': find(['업종','업태','업종대분류','업종명','category']),
        'address': find(['도로명주소','지번주소','주소','addr','address']),
        'lat': find(['위도','latitude','lat']),
        'lon': find(['경도','longitude','lon','lng']),
        'reg_date': find(['등록일','등록날짜','date','작성일','등록일자'])
    }
    return candidates


def summarize(df):
    total = len(df)
    missing = (df.isna().mean() * 100).round(2).sort_values(ascending=False)
    dtypes = df.dtypes.astype(str)
    unique_counts = df.nunique(dropna=False).sort_values(ascending=False)
    return total, missing, dtypes, unique_counts


# ----------------- 샘플 데이터 (앱 체험용) -----------------
SAMPLE_CSV = """상호,업종,도로명주소,위도,경도,등록일
카페A,카페,서울특별시 용산구 청파로 1,37.532,126.965,2022-01-05
베이커리B,제과제빵,서울특별시 용산구 한강대로 10,37.528,126.964,2021-11-20
식당C,한식,서울특별시 용산구 이태원로 5,37.534,126.994,2020-06-12
편의점D,편의점,서울특별시 용산구 원효로 50,37.529,126.967,2019-03-03
헤어샵E,미용,서울특별시 용산구 백범로 99,37.537,126.968,2023-02-14
"""

# ----------------- 앱 UI -----------------
st.title("📊 용산구 지역특화거리 상점 분석기 — 완성판")
st.markdown("로컬/업로드/공개 URL로 CSV를 불러오고, Altair 기반의 세련된 시각화를 제공합니다. 추가 패키지 설치 불필요합니다.")

# 사이드바: 데이터 입력
st.sidebar.header("데이터 입력 & 옵션")
use_default = st.sidebar.checkbox("기본 로컬 파일 사용 시도", value=True)
public_url = st.sidebar.text_input("공개 CSV URL (GitHub/GDrive/Dropbox 등)")
uploaded = st.sidebar.file_uploader("CSV 파일 업로드 (선택)", type=['csv'])
use_sample = st.sidebar.checkbox("샘플 데이터로 실행(데이터가 없을 때 추천)", value=False)

# 데이터 불러오기
try:
    if use_sample:
        df = pd.read_csv(io.StringIO(SAMPLE_CSV))
        source = 'sample'
    else:
        local_path = DATA_PATH if use_default else None
        df, source = load_data_with_fallback(local_path=local_path, public_url=public_url or None, uploaded_file=uploaded)
    st.success(f"데이터 로드 성공 — 소스: {source}")
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
    with st.expander("CSV 가져오기 가이드"):
        st.markdown("- GitHub: 파일 열기 → 'Raw' 버튼 클릭 → 주소 복사 붙여넣기.\n- Google Drive: 공유 설정 변경 후 `https://drive.google.com/uc?export=download&id=FILE_ID`.\n- Dropbox: 공유 링크의 `dl=0`을 `dl=1`로 변경.\n- 또는 CSV 파일을 업로드하세요.")
    st.stop()

# 자동 매핑 및 수동 매핑 UI
candidates = guess_columns(df)
st.sidebar.header("컬럼 매핑 (자동 추천 후 수동 조정 가능)")
col_options = ['(없음)'] + list(df.columns)

def idx_of(val):
    try:
        return col_options.index(val)
    except Exception:
        return 0

name_col = st.sidebar.selectbox("상호/업소명", options=col_options, index=idx_of(candidates.get('name') or '(없음)'))
category_col = st.sidebar.selectbox("업종/카테고리", options=col_options, index=idx_of(candidates.get('category') or '(없음)'))
address_col = st.sidebar.selectbox("주소", options=col_options, index=idx_of(candidates.get('address') or '(없음)'))
lat_col = st.sidebar.selectbox("위도", options=col_options, index=idx_of(candidates.get('lat') or '(없음)'))
lon_col = st.sidebar.selectbox("경도", options=col_options, index=idx_of(candidates.get('lon') or '(없음)'))
reg_col = st.sidebar.selectbox("등록일", options=col_options, index=idx_of(candidates.get('reg_date') or '(없음)'))

# normalize
def norm(col):
    return None if col == '(없음)' else col
name_col = norm(name_col)
category_col = norm(category_col)
address_col = norm(address_col)
lat_col = norm(lat_col)
lon_col = norm(lon_col)
reg_col = norm(reg_col)

# 필터 옵션
st.sidebar.header("필터")
filters = {}
if category_col:
    vals = df[category_col].fillna('(알수없음)')
    top_vals = vals.value_counts().index.tolist()
    default = top_vals[:6] if len(top_vals)>=6 else top_vals
    sel_cats = st.sidebar.multiselect("업종 선택", options=top_vals, default=default)
    filters['category'] = sel_cats
if name_col:
    filters['name_search'] = st.sidebar.text_input("상호명 검색(부분일치)")
coord_only = st.sidebar.checkbox("좌표 보유 항목만", value=False)
show_topn = st.sidebar.slider("Top N (업종 시각화)", min_value=5, max_value=50, value=20)

# 데이터 요약
total, missing, dtypes, unique_counts = summarize(df)

# KPI
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("총 상점 수", f"{total:,}")
with k2:
    st.metric("컬럼 수", f"{df.shape[1]}")
with k3:
    top_missing = missing.index[0] if len(missing)>0 else '-'
    top_missing_val = missing.iloc[0] if len(missing)>0 else 0
    st.metric("결측 최다 컬럼", f"{top_missing} ({top_missing_val}%)")
with k4:
    st.metric("최다 고유값 컬럼", f"{unique_counts.index[0]}: {unique_counts.iloc[0]}")

st.markdown("---")

# 데이터 미리보기 및 메타
left, right = st.columns([2,1])
with left:
    st.subheader("데이터 미리보기")
    st.dataframe(df.head(10))
with right:
    st.subheader("컬럼 메타")
    meta = pd.DataFrame({'column': df.columns, 'dtype': df.dtypes.astype(str), 'unique': df.nunique(dropna=False).values, 'missing_%': (df.isna().mean()*100).round(2).values})
    st.dataframe(meta.sort_values('missing_%', ascending=False).reset_index(drop=True))

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

# 결측치 차트 (Altair 히트맵)
missing_df = (df.isna().astype(int)).T
missing_df.index.name = 'column'
missing_df = missing_df.reset_index()
# reduce columns if too many rows
if df.shape[0] > 200:
    sample_idx = np.random.choice(df.index, 200, replace=False)
    missing_sample = df.loc[sample_idx].isna().astype(int).reset_index(drop=True)
else:
    missing_sample = df.isna().astype(int).reset_index(drop=True)

melt = missing_sample.reset_index().melt(var_name='column', value_name='is_na')
if not melt.empty:
    hm = alt.Chart(melt).mark_rect().encode(
        x=alt.X('index:O', title='row index (sample)'),
        y=alt.Y('column:N', sort='-x'),
        color=alt.Color('is_na:Q', scale=alt.Scale(domain=[0,1], scheme='greys'), legend=None),
        tooltip=['column','is_na']
    ).properties(height=300)
    st.subheader("결측 히트맵(샘플) - 검정=결측")
    st.altair_chart(hm, use_container_width=True)

# 업종 분포
if category_col:
    st.subheader("업종 분포 (Top N)")
    cat_counts = df_filtered[category_col].fillna('(알수없음)').value_counts().reset_index()
    cat_counts.columns = ['category','count']
    topn = cat_counts.head(show_topn)
    bchart = alt.Chart(topn).mark_bar().encode(
        x=alt.X('count:Q', title='상점 수'),
        y=alt.Y('category:N', sort='-x', title='업종'),
        tooltip=['category','count']
    ).properties(height=420)
    st.altair_chart(bchart, use_container_width=True)

    # 도넛 차트
    pie = topn.copy()
    pie['percent'] = (pie['count'] / pie['count'].sum() * 100).round(2)
    pie_chart = alt.Chart(pie).mark_arc(innerRadius=60).encode(
        theta=alt.Theta('count:Q'),
        color=alt.Color('category:N', legend=alt.Legend(orient='right')),
        tooltip=['category','count','percent']
    ).properties(width=380, height=380)
    st.markdown("### 업종 비중 (Top N)")
    st.altair_chart(pie_chart, use_container_width=False)

# 등록일 트렌드
if reg_col:
    st.subheader("등록일 기반 등록 추이")
    try:
        df[reg_col] = pd.to_datetime(df[reg_col], errors='coerce')
        df_filtered[reg_col] = pd.to_datetime(df_filtered[reg_col], errors='coerce')
        ts = df_filtered.dropna(subset=[reg_col]).set_index(reg_col).resample('M').size().reset_index(name='count')
        if not ts.empty:
            lchart = alt.Chart(ts).mark_line(point=True).encode(
                x=alt.X(f'{reg_col}:T', title='기간'),
                y=alt.Y('count:Q', title='등록 수'),
                tooltip=[reg_col,'count']
            ).properties(height=320)
            st.altair_chart(lchart, use_container_width=True)
    except Exception:
        st.info("등록일 컬럼을 시계열로 변환할 수 없습니다.")

# 지도
if lat_col and lon_col:
    st.subheader("지도 표시 (st.map)")
    try:
        coords = df_filtered[[lat_col, lon_col]].dropna()
        coords = coords.rename(columns={lat_col: 'lat', lon_col: 'lon'})
        coords['lat'] = pd.to_numeric(coords['lat'], errors='coerce')
        coords['lon'] = pd.to_numeric(coords['lon'], errors='coerce')
        coords = coords.dropna()
        if not coords.empty:
            st.map(coords)
        else:
            st.info("유효한 좌표가 없습니다.")
    except Exception as e:
        st.info(f"지도 표시 중 오류: {e}")
else:
    st.info("좌표(위도/경도) 컬럼을 지정하면 지도에 표시됩니다.")

st.markdown("---")

# 데이터 테이블 + 다운로드
st.subheader("필터된 데이터")
st.dataframe(df_filtered.reset_index(drop=True))

@st.cache_data
def to_csv_bytes(df_in):
    return df_in.to_csv(index=False).encode('utf-8-sig')

csv_bytes = to_csv_bytes(df_filtered)
st.download_button("CSV 다운로드 (필터 적용됨)", data=csv_bytes, file_name="yongsan_filtered.csv", mime='text/csv')

# 자동 인사이트
st.subheader("간단 자동 인사이트")
insights = []
if category_col:
    topcat = df[category_col].fillna('(알수없음)').value_counts().head(1)
    if not topcat.empty:
        insights.append(f"가장 많은 업종: '{topcat.index[0]}' — {int(topcat.iloc[0])}개")
high_missing = missing[missing > 50]
if not high_missing.empty:
    ins = ", ".join([f"{idx}({val}%)" for idx,val in high_missing.items()])
    insights.append(f"결측률 50% 이상 컬럼: {ins}")
if lat_col and lon_col:
    coords_count = df[lat_col].notna().sum()
    insights.append(f"좌표 보유 행: {coords_count}개")

if insights:
    for s in insights:
        st.write("- ", s)
else:
    st.write("명확한 인사이트가 없습니다. 필터를 바꿔보세요.")

st.markdown("---")

st.caption("이 앱은 배포/공유용으로 제작되었습니다. Streamlit Cloud에 업로드하면 누구나 공개 URL로 접속해 사용할 수 있습니다. 추가 분석(업종 표준화, 지오코딩, 텍스트 마이닝)도 확장 가능합니다.")
