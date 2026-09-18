import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)


# KOBIS 일일 박스오피스 API 주소
API_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)

# 한국 시간대
KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------
# 2. KOBIS API 호출 함수
# ---------------------------------------------------------
# @st.cache_data를 사용하면 같은 날짜를 다시 조회할 때
# 일정 시간 동안 API를 다시 호출하지 않습니다.
#
# ttl=3600 -> 캐시를 1시간(3600초) 동안 유지합니다.
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_date, api_key):
    """지정한 날짜의 일일 박스오피스를 KOBIS에서 가져옵니다."""

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    # API 요청
    response = requests.get(
        API_URL,
        params=params,
        timeout=10,
    )

    # HTTP 상태 코드가 200이 아니면 오류로 처리
    response.raise_for_status()

    # JSON 응답으로 변환
    data = response.json()

    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있습니다.
    # 따라서 faultInfo가 있는지도 반드시 확인합니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        message = (
            fault_info.get("message")
            or fault_info.get("errorMessage")
            or "KOBIS API에서 오류를 반환했습니다."
        )

        raise RuntimeError(message)

    # 정상적인 경우 boxOfficeResult 안에 목록이 있습니다.
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        raise RuntimeError(
            "KOBIS 응답에 boxOfficeResult가 없습니다."
        )

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    if not movie_list:
        raise RuntimeError(
            "해당 날짜의 영화 목록이 비어 있습니다."
        )

    return movie_list


# ---------------------------------------------------------
# 3. 문자열 숫자를 실제 숫자로 변환
# ---------------------------------------------------------
# KOBIS API는 rank, audiCnt, audiAcc, scrnCnt 등을
# 문자열로 보내므로 그래프와 정렬에 사용할 수 있도록
# 정수로 바꿉니다.
# ---------------------------------------------------------

def convert_numbers(movie_list):
    """KOBIS 응답의 숫자 문자열을 정수로 변환합니다."""

    converted = []

    for movie in movie_list:
        item = movie.copy()

        # 숫자로 사용할 항목들
        numeric_fields = [
            "rank",
            "rankInten",
            "audiCnt",
            "audiAcc",
            "scrnCnt",
            "showCnt",
        ]

        for field in numeric_fields:
            try:
                item[field] = int(item.get(field, 0))
            except (ValueError, TypeError):
                # 숫자로 변환할 수 없으면 0으로 처리
                item[field] = 0

        converted.append(item)

    return converted


# ---------------------------------------------------------
# 4. 어제 날짜 계산
# ---------------------------------------------------------
# 서버가 어느 나라 시간으로 동작하는지는 상관없이
# Asia/Seoul 기준으로 현재 시각을 구합니다.
# ---------------------------------------------------------

now_kst = datetime.now(KST)
yesterday_kst = now_kst - timedelta(days=1)

# KOBIS가 요구하는 YYYYMMDD 형식
target_date = yesterday_kst.strftime("%Y%m%d")

# 화면에 보여 줄 날짜
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 5. Secrets에서 인증키 가져오기
# ---------------------------------------------------------
# Streamlit Cloud의 Secrets에 다음과 같이 저장해야 합니다.
#
# KOBIS_KEY = "발급받은_인증키"
#
# 실제 인증키는 코드에 넣지 않습니다.
# ---------------------------------------------------------

try:
    api_key = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
        "KOBIS_KEY라는 이름으로 KOBIS 인증키를 등록했는지 확인하세요."
    )
    st.stop()


# ---------------------------------------------------------
# 6. 화면 제목
# ---------------------------------------------------------

st.title("🎬 어제의 박스오피스")
st.caption(f"한국 시간 기준 {display_date} 일일 박스오피스")


# ---------------------------------------------------------
# 7. API 호출
# ---------------------------------------------------------

try:
    movies = get_boxoffice(target_date, api_key)
    movies = convert_numbers(movies)

except requests.exceptions.Timeout:
    st.error(
        "KOBIS API 요청 시간이 초과되었습니다.\n\n"
        "잠시 후 다시 시도하거나 KOBIS API 서버 상태를 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(
        "KOBIS API에 접속하지 못했습니다.\n\n"
        "인터넷 연결, KOBIS API 주소, KOBIS 서버 상태를 확인해 주세요.\n\n"
        f"상세 내용: {e}"
    )
    st.stop()

except RuntimeError as e:
    st.error(
        "KOBIS에서 정상적인 영화 목록을 받지 못했습니다.\n\n"
        f"확인할 내용: {e}\n\n"
        "KOBIS 인증키가 정확한지, 조회 날짜에 박스오피스 데이터가 "
        "존재하는지 확인해 주세요."
    )
    st.stop()

except Exception as e:
    st.error(
        "박스오피스 데이터를 불러오는 중 예상하지 못한 오류가 발생했습니다.\n\n"
        "KOBIS 인증키와 Streamlit Secrets 설정을 확인하고 "
        "잠시 후 다시 시도해 주세요.\n\n"
        f"상세 내용: {e}"
    )
    st.stop()


# ---------------------------------------------------------
# 8. 영화 목록이 정말 있는지 한 번 더 확인
# ---------------------------------------------------------

if not movies:
    st.warning(
        "표시할 영화 목록이 없습니다.\n\n"
        "KOBIS에 해당 날짜의 일일 박스오피스 데이터가 있는지, "
        "조회 날짜와 API 인증키가 올바른지 확인해 주세요."
    )
    st.stop()


# 순위 순서대로 정렬
movies = sorted(movies, key=lambda x: x["rank"])


# ---------------------------------------------------------
# 9. 1위 영화 지표 카드
# ---------------------------------------------------------

first_movie = movies[0]

st.subheader("🥇 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "오늘 관객수",
        f"{first_movie['audiCnt']:,}명",
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{first_movie['audiAcc']:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['scrnCnt']:,}개",
    )

st.markdown(
    f"### {first_movie['movieNm']}"
)

st.caption(
    f"개봉일: {first_movie['openDt'] or '정보 없음'}"
)


# ---------------------------------------------------------
# 10. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda x: x["audiCnt"],
    reverse=True,
)[:5]

# Streamlit 차트는 DataFrame 형태의 데이터를 사용합니다.
# pandas를 이용해 영화명을 인덱스로 설정합니다.
import pandas as pd

chart_data = pd.DataFrame(
    {
        "관객수": [movie["audiCnt"] for movie in top5]
    },
    index=[
        movie["movieNm"]
        for movie in top5
    ],
)

st.bar_chart(chart_data)


# ---------------------------------------------------------
# 11. 전체 영화 표
# ---------------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

table_data = []

for movie in movies:
    table_data.append(
        {
            "순위": movie["rank"],
            "영화명": movie["movieNm"],
            "개봉일": movie["openDt"],
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
        }
    )

df = pd.DataFrame(table_data)

# 관객수 등을 보기 좋게 천 단위 쉼표로 표시합니다.
# 데이터 자체는 이미 숫자이므로 정렬에도 숫자로 동작합니다.
display_df = df.copy()

display_df["관객수"] = display_df["관객수"].map(
    lambda x: f"{x:,}"
)
display_df["누적관객"] = display_df["누적관객"].map(
    lambda x: f"{x:,}"
)
display_df["스크린수"] = display_df["스크린수"].map(
    lambda x: f"{x:,}"
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# 12. 데이터 출처 안내
# ---------------------------------------------------------

st.caption(
    "데이터 출처: 영화진흥위원회(KOBIS) 일일 박스오피스 API"
)
