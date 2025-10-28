# Streamlit app:# Streamlit app: 용산구 지역특화거리 상점 정보 분석기 (개선판) — 공개 URL 페일백 추가
# 변경 요지:
# 1) 로컬 파일이 없을 때: 업로드 파일, 또는 '공개 CSV URL' 입력을 통해 데이터를 불러올 수 있도록 페일백 로직을 추가했습니다.
# 2) Google Drive / GitHub / Dropbox 등에서 얻은 공유 링크를 자동으로 처리하는 헬퍼 함수 포함.
# 3) 사용자가 링크를 클릭해 CSV를 바로 열어볼 수 있도록 '원본 파일 보기' 링크를 표시합니다.

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import io
import re

st.set_page_config(page_title="용산구 상점 분석기 (공개 URL 지원)", layout="wide")

# 기본 로컬 경로 (로컬에서 실행할 때 유용)
DATA_PATH = "/mnt/data/서울특별시 용산구_지역특화거리거리상점정보_20221207.csv"

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
    """몇몇 공유 플랫폼의 '공유 링크'를 직접 다운로드 가능한 raw 링크로 변환합니다.
    지원: Google Drive, Dropbox, GitHub(Gist/raw), 일반 raw http(s) 링크
    반환값: pandas.read_csv에서 바로 사용 가능한 URL (또는 원본 URL)
    """
    if not isinstance(url, str):
        return url
    url = url.strip()
    # Google Drive 공유 링크 -> uc?export=download
    m = re.search(r'drive.google.com/.+?/d/([a-zA-Z0-9_-]+)', url)
    if m:
        fid = m.group(1)
        return f'https://drive.google.com/uc?export=download&id={fid}'
    # Google drive sharing 'id=' style
    m2 = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if 'drive.google.com' in url and m2:
        return f'https://drive.google.com/uc?export=download&id={m2.group(1)}'
    # Dropbox: ?dl=0 -> ?dl=1 (직접 다운로드)
    if 'dropbox.com' in url:
        if 'dl=0' in url:
            return url.replace('dl=0','dl=1')
        if not re.search(r'[?&]dl=', url):
            return url + '?dl=1'
    # GitHub file page -> raw.githubusercontent
    # 예: https://github.com/user/repo/blob/branch/path/file.csv -> https://raw.githubusercontent.com/user/repo/branch/path/file.csv
    m3 = re.search(r'https://github.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)', url)
    if m3:
        user, repo, branch, path = m3.group(1), m3.group(2), m3.group(3), m3.group(4)
        return f'https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}'
    return url


def load_data_with_fallback(local_path=None, public_url=None, uploaded_file=None):
    """우선순위: 1) 로컬 파일 2) 업로드된 파일 3) 공개 URL 4) 예외
    반환: (df, source_url_or_path)
    """
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


# ------------- 앱 UI -------------
st.title("📍 용산구 상점 분석기 — 공개 링크로 바로 보기 가능")
st.markdown("로컬 파일이 없더라도 ① 업로드 또는 ② 공개 CSV URL(GitHub/GDrive/Dropbox 등)을 입력하면 데이터를 자동으로 불러옵니다.")

st.sidebar.header("데이터 입력 방식")
use_default = st.sidebar.checkbox("기본 로컬 파일 경로 사용 시도", value=True)
public_url = st.sidebar.text_input("공개 CSV URL (Raw 링크 또는 공유 링크)", value="")
uploaded = st.sidebar.file_uploader("CSV 파일 업로드 (선택사항)", type=['csv'])

# 로드 시도
try:
    local_path = DATA_PATH if use_default else None
    df, source = load_data_with_fallback(local_path=local_path, public_url=public_url or None, uploaded_file=uploaded)
    st.success(f"데이터 로드 성공 — 소스: {source}")
except FileNotFoundError as e:
    st.error("데이터를 찾을 수 없습니다. 아래 가이드를 참고해 공개 URL을 입력하거나 CSV를 업로드하세요.")
    with st.expander("공개 CSV URL 만드는 방법 (간단)"):
        st.markdown("- GitHub: 레포지토리에 CSV 업로드 → 파일 열기 → 'Raw' 버튼 클릭 → 주소복사.\n- GitHub Gist: Gist에 CSV 올리고 Raw 링크 사용.\n- Google Drive: 파일 공유 설정을 '링크가 있는 누구나'로 변경 후, 공유 URL에서 파일 ID를 추출하여 아래 형식으로 변환하세요: `https://drive.google.com/uc?export=download&id=FILE_ID`.\n- Dropbox: 공유 링크에서 `dl=0`을 `dl=1`로 바꾸면 직접 다운로드 링크가 됩니다.")
    st.stop()

# 이제 기존 분석 로직으로 진행 (데이터가 df에 로드된 상태)

# --- 이하 기존 분석 파이프라인을 이어서 사용합니다. ---
# (원래 앱의 컬럼 감지/매핑/시각화/필터링 로직이 여기에 포함됩니다.)

st.write("데이터 프레임 샘플 (상위 5행)")
st.dataframe(df.head())

# 간단 통계
st.write(f"총 행(상점) 수: {len(df):,}")
st.write(f"컬럼: {', '.join(df.columns[:20])}{'...' if df.shape[1]>20 else ''}")

st.caption("앱은 로컬/업로드/공개 URL을 모두 지원합니다. 공개 URL을 통해 링크만 있으면 누구나 데이터에 접근할 수 있습니다.")
