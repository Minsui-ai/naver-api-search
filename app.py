import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 환경 변수 로드 (로컬 개발용)
load_dotenv()

# Streamlit Secrets 우선 사용 (배포용), 없으면 환경 변수 사용 (로컬용)
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")

# --- API 호출 함수 ---
@st.cache_data(ttl=3600)
def call_naver_api(url, method="GET", body=None):
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("API Key가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return None
        
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    request.add_header("Content-Type", "application/json")
    
    try:
        if body:
            response = urllib.request.urlopen(request, data=json.dumps(body).encode("utf-8"))
        else:
            response = urllib.request.urlopen(request)
        
        if response.getcode() == 200:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        st.error(f"API 호출 중 오류 발생: {e}")
        return None

def fetch_search_trends(keywords, start_date, end_date):
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords]
    }
    return call_naver_api(url, method="POST", body=body)

def fetch_shopping_trends(keywords, start_date, end_date):
    # 실제로는 분야별 조회가 복잡하므로 키워드 기반 쇼핑 트렌드를 시뮬레이션하거나 
    # 데이터랩 쇼핑인사이트 API를 사용 (여기서는 키워드 검색 트렌드로 대체 가능성 높음)
    # 간단히 검색어 트렌드로 통합 관리
    return fetch_search_trends(keywords, start_date, end_date)

def fetch_search_results(query, domain, display=100):
    url = f"https://openapi.naver.com/v1/search/{domain}.json?query={urllib.parse.quote(query)}&display={display}&sort=sim"
    return call_naver_api(url)

# --- 데이터 가공 함수 ---
def process_trend_data(data):
    if not data or "results" not in data:
        return pd.DataFrame()
    rows = []
    for result in data["results"]:
        kw = result["title"]
        for entry in result["data"]:
            rows.append({"날짜": entry["period"], "키워드": kw, "검색량": entry["ratio"]})
    df = pd.DataFrame(rows)
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"])
    return df

def process_search_results(all_results):
    rows = []
    for kw, domains in all_results.items():
        for d_name, data in domains.items():
            if data and "items" in data:
                for item in data["items"]:
                    title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                    desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
                    rows.append({
                        "키워드": kw,
                        "구분": d_name,
                        "제목": title,
                        "설명": desc,
                        "링크": item.get("link", ""),
                        "날짜": item.get("postdate") or item.get("pubDate") or "",
                        "최저가": item.get("lprice", "0"),
                        "브랜드": item.get("brand", ""),
                        "몰이름": item.get("mallName", ""),
                        "카테고리1": item.get("category1", ""),
                        "카테고리2": item.get("category2", ""),
                        "카테고리3": item.get("category3", ""),
                        "카테고리4": item.get("category4", "")
                    })
    df = pd.DataFrame(rows)
    if not df.empty:
        # 가격 숫자 변환
        df["최저가"] = pd.to_numeric(df["최저가"], errors="coerce").fillna(0)
    return df

def get_word_freq(df, text_col):
    if df.empty or text_col not in df.columns:
        return pd.DataFrame()
    
    # 간단한 불용어 처리 및 띄어쓰기 기준 토큰화
    text = " ".join(df[text_col].astype(str))
    # 특수문자 제거
    import re
    text = re.sub(r'[^\w\s]', '', text)
    words = [w for w in text.split() if len(w) > 1] # 1글자 제외
    freq = pd.Series(words).value_counts().head(30).reset_index()
    freq.columns = ["단어", "빈도"]
    return freq

# --- Streamlit UI ---
st.set_page_config(page_title="Naver Market Intel Dashboard", layout="wide", initial_sidebar_state="expanded")

# CSS를 활용한 디자인 강화
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stAlert {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚀 Naver Market Intelligence Dashboard")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.markdown("""
        <div style="background-color:#03C75A; padding:10px; border-radius:5px; text-align:center; margin-bottom:20px;">
            <h1 style="color:white; margin:0; font-size:24px;">NAVER</h1>
            <p style="color:white; margin:0; font-size:12px;">Market Intelligence</p>
        </div>
    """, unsafe_allow_html=True)
    st.header("🔍 분석 컨트롤 타워")
    
    input_keywords = st.text_input("분석 키워드 (쉼표 구분)", "선풍기, 핫팩")
    keywords = [k.strip() for k in input_keywords.split(",") if k.strip()]
    
    date_range = st.date_input("분석 기간 설정", [datetime.now() - timedelta(days=90), datetime.now()])
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range[0]
    
    st.divider()
    st.write("**데이터 필터링**")
    selected_domain = st.multiselect("수집 채널 필터", ["shop", "blog", "cafe", "news"], default=["shop", "blog", "cafe", "news"])
    
    if st.button("실시간 데이터 분석 시작 🔄", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 데이터 수집 (캐싱 적용)
@st.cache_data
def get_all_data(kws, s_date, e_date):
    with st.spinner('네이버 API로부터 데이터를 수집 중입니다...'):
        # 트렌드 데이터
        trend_raw = fetch_search_trends(kws, s_date, e_date)
        trend_df = process_trend_data(trend_raw)
        
        # 검색 결과 데이터
        search_data = {}
        domains = {"blog": "blog", "cafe": "cafearticle", "news": "news", "shop": "shop"}
        for kw in kws:
            search_data[kw] = {}
            for d_label, d_api in domains.items():
                # API 호출 한도 고려하여 일부 제한
                search_data[kw][d_label] = fetch_search_results(kw, d_api)
        
        search_df = process_search_results(search_data)
        return trend_df, search_df

trend_df, search_df = get_all_data(keywords, start_date, end_date)

if trend_df.empty and search_df.empty:
    st.warning("수집된 데이터가 없습니다. API 설정을 확인해주세요.")
else:
    # 탭 구성
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📉 데이터 프로파일링", "📊 트렌드 분석", "🛍️ 쇼핑 상세", "💬 소셜 인사이트", "📂 데이터 탐색"
    ])

    with tab1:
        st.subheader("📋 데이터 수집 현황 및 프로파일링")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("트렌드 데이터 수", f"{len(trend_df)}건")
        m2.metric("검색/쇼핑 데이터 수", f"{len(search_df)}건")
        m3.metric("최종 업데이트", datetime.now().strftime("%H:%M:%S"))
        
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 📉 트렌드 데이터 요약")
            # 컬럼 객체 타입을 문자열로 변환하여 Arrow 에러 방지
            st.dataframe(trend_df.head(10).astype(str))
            with st.expander("기술 통계 정보"):
                st.write(trend_df.describe(include='all').astype(str))
            
        with col2:
            st.write("### 🛍️ 검색/쇼핑 데이터 요약")
            st.dataframe(search_df.head(10).astype(str))
            with st.expander("결측치 및 데이터 정보"):
                info_df = pd.DataFrame({
                    "컬럼명": search_df.columns,
                    "데이터타입": search_df.dtypes.astype(str),
                    "결측치수": search_df.isnull().sum().values
                })
                st.table(info_df)

    with tab2:
        st.subheader("📈 네이버 검색어 및 쇼핑 트렌드 통합 분석")
        if not trend_df.empty:
            fig_trend = px.line(trend_df, x="날짜", y="검색량", color="키워드", 
                                title="일별 검색 클릭 트렌드 (상대 수치)",
                                markers=True, template="plotly_white")
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.write("#### [통계 요약표]")
            pivot_trend = trend_df.pivot_table(index="키워드", values="검색량", aggfunc=["mean", "max", "min"])
            st.write(pivot_trend)
            st.info("검색어 트렌드는 설정된 기간 내 최대 검색량을 100으로 설정한 상대적 수치입니다.")
        else:
            st.warning("분석할 트렌드 데이터가 없습니다.")

    with tab3:
        st.subheader("🛍️ 쇼핑 채널 심층 분석")
        # 사이드바 필터 적용
        shop_df = search_df[search_df["구분"] == "shop"]
        if not shop_df.empty:
            # 카테고리 시각화 선택 (TreeMap or Sunburst)
            st.write("#### 카테고리 구조 분석 (전문가용 시각화)")
            chart_type = st.radio("시각화 유형 선택", ["TreeMap", "Sunburst"], horizontal=True)
            
            if chart_type == "TreeMap":
                fig_cat = px.treemap(shop_df, path=["카테고리1", "카테고리2", "카테고리3"], 
                                      title="데이터 기반 쇼핑 카테고리 분포 (TreeMap)",
                                      color_discrete_sequence=px.colors.qualitative.Pastel)
            else:
                fig_cat = px.sunburst(shop_df, path=["카테고리1", "카테고리2", "카테고리3"], 
                                       title="데이터 기반 쇼핑 카테고리 분포 (Sunburst)",
                                       color_discrete_sequence=px.colors.qualitative.Antique)
            st.plotly_chart(fig_cat, use_container_width=True)
            
            # 가격 분석
            c1, c2 = st.columns(2)
            with c1:
                fig_box = px.box(shop_df, x="키워드", y="최저가", points="all",
                                 color="키워드", title="상품 최저가 분포 (Box Plot)")
                st.plotly_chart(fig_box, use_container_width=True)
            with c2:
                brand_avg = shop_df.groupby("브랜드")["최저가"].agg(["mean", "count"]).sort_values("mean", ascending=False).head(20).reset_index()
                brand_avg.columns = ["브랜드", "평균가", "상품수"]
                fig_brand = px.bar(brand_avg, x="평균가", y="브랜드", orientation="h",
                                   color="상품수", title="상위 브랜드별 평균가 및 등록 상품 수")
                st.plotly_chart(fig_brand, use_container_width=True)
            
            st.write("#### [쇼핑 상세 데이터]")
            st.dataframe(shop_df[["키워드", "제목", "최저가", "브랜드", "몰이름", "카테고리3"]].head(20))
        else:
            st.info("조회된 쇼핑 상품 데이터가 없습니다.")

    with tab4:
        st.subheader("💬 소셜 여론 및 채널 영향력 분석")
        social_df = search_df[search_df["구분"].isin(["blog", "cafe", "news"])]
        if not social_df.empty:
            # 텍스트 빈도 분석 및 시각화
            st.write("#### 제목 기반 핵심 키워드 빈도 (Top 30)")
            freq_df = get_word_freq(social_df, "제목")
            if not freq_df.empty:
                fig_freq = px.bar(freq_df, x="빈도", y="단어", orientation="h",
                                  color="빈도", color_continuous_scale="Viridis")
                st.plotly_chart(fig_freq, use_container_width=True)
                
                with st.expander("워드 빈도 상세 표 확인"):
                    st.table(freq_df)
            
            # 채널 비중 시각화
            col_s1, col_s2 = st.columns([1, 2])
            with col_s1:
                fig_pie = px.pie(social_df, names="구분", hole=0.4, title="채널별 게시물 점유율")
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_s2:
                st.write("#### 최신 소셜 콘텐츠 리스트")
                st.dataframe(social_df[["구분", "키워드", "제목", "날짜", "링크"]].head(15))
        else:
            st.info("소셜 미디어 및 뉴스 데이터가 수집되지 않았습니다.")

    with tab5:
        st.subheader("📂 raw 데이터 익스플로러")
        st.info("분석에 활용된 원본 데이터를 조회하고 다운로드할 수 있습니다.")
        
        selected_target = st.radio("원본 데이터 종류 선택", ["통합 검색/쇼핑 데이터", "트렌드 원시 데이터"], horizontal=True)
        raw_display = search_df if selected_target == "통합 검색/쇼핑 데이터" else trend_df
        
        # 필터링 기능 강화
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            f_kws = st.multiselect("검색 키워드 필터", options=raw_display["키워드"].unique(), default=raw_display["키워드"].unique())
        
        final_df = raw_display[raw_display["키워드"].isin(f_kws)]
        
        st.dataframe(final_df)
        
        # 다운로드
        csv_data = final_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📁 분석 데이터 CSV 다운로드",
            data=csv_data,
            file_name=f"naver_market_intel_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
