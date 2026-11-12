import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import re
from pathlib import Path
from datetime import datetime, date

# ==========================================
# 1. 기본 설정
# ==========================================

st.set_page_config(
    page_title="천산환경 AI 민원 관리 시스템",
    page_icon="♻️",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "complaints.db"

CATEGORIES = [
    "재활용품 미수거",
    "음식물류 미수거",
    "중간집하지 악취",
    "일반생활폐기물 미수거",
    "수거 지연",
    "중간집하지 정리 미흡",
]

# 보고서에 명시된 3개 유형 외 나머지는 시연용 임시 분류
CATEGORY_KEYWORDS = {
    "재활용품 미수거": ["재활용", "캔", "페트병", "플라스틱", "종이", "병", "분리수거"],
    "음식물류 미수거": ["음식물", "음식물쓰레기", "잔반"],
    "중간집하지 악취": ["악취", "냄새", "악취가"],
    "일반생활폐기물 미수거": ["생활폐기물", "일반쓰레기", "종량제"],
    "수거 지연": ["수거 지연", "늦게", "아직 안", "며칠째"],
    "중간집하지 정리 미흡": ["뒷정리", "정리 미흡", "주변이 지저분", "청소"],
}

DISTRICTS = ["용현동", "숭의동"]

# ==========================================
# 2. 데이터베이스
# ==========================================

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                complaint_date TEXT NOT NULL,
                channel TEXT,
                original_text TEXT NOT NULL,
                district TEXT,
                location TEXT,
                category TEXT,
                priority TEXT,
                summary TEXT,
                driver_message TEXT,
                status TEXT DEFAULT '접수',
                delivered INTEGER DEFAULT 0
            )
        """)

init_db()

# ==========================================
# 3. 민원 자동 분석 엔진
# ==========================================

def analyze_complaint(text):
    text = text.strip()
    lower_text = text.lower()

    # 행정동 추출
    district = next(
        (d for d in DISTRICTS if d in text),
        "미확인"
    )

    # 세부 위치 추출: 동 이름 뒤의 문장을 참고용으로 저장
    location = "세부 위치 확인 필요"
    for district_name in DISTRICTS:
        match = re.search(
            district_name + r"\s*(.{2,30})",
            text
        )
        if match:
            location = match.group(1).strip()
            break

    # 민원 유형 분류
    category = "기타 / 담당자 확인"

    for name, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lower_text for keyword in keywords):
            category = name
            break

    # 긴급도 규칙
    high_words = [
        "긴급", "위험", "악취가 심", "도로를 막",
        "통행 불가", "며칠째", "심각", "넘쳐"
    ]
    medium_words = [
        "불편", "민원", "반복", "방치",
        "확인 요청", "주민들이"
    ]

    if any(word in text for word in high_words):
        priority = "HIGH"
    elif any(word in text for word in medium_words):
        priority = "MEDIUM"
    else:
        priority = "LOW"

    # 핵심 요약
    summary = (
        f"{district} {location} 관련 "
        f"{category} 민원"
    )

    # 기사 전달 메시지
    prefix = {
        "HIGH": "[긴급]",
        "MEDIUM": "[확인 요청]",
        "LOW": "[일반]"
    }[priority]

    driver_message = (
        f"{prefix} {district} {location} "
        f"{category} 민원입니다. "
        f"현장 확인 후 필요한 조치 부탁드립니다."
    )

    return {
        "district": district,
        "location": location,
        "category": category,
        "priority": priority,
        "summary": summary,
        "driver_message": driver_message
    }

# ==========================================
# 4. 데이터 조회 및 저장
# ==========================================

def save_complaint(data):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO complaints (
                received_at, complaint_date, channel,
                original_text, district, location,
                category, priority, summary,
                driver_message, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(data["complaint_date"]),
            data["channel"],
            data["original_text"],
            data["district"],
            data["location"],
            data["category"],
            data["priority"],
            data["summary"],
            data["driver_message"],
            "접수"
        ))

def get_complaints():
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM complaints ORDER BY id DESC",
            conn
        )

def update_status(complaint_id, status):
    with get_connection() as conn:
        conn.execute(
            "UPDATE complaints SET status=? WHERE id=?",
            (status, int(complaint_id))
        )

def update_delivery(complaint_id, delivered):
    with get_connection() as conn:
        conn.execute(
            "UPDATE complaints SET delivered=? WHERE id=?",
            (int(delivered), int(complaint_id))
        )

# ==========================================
# 5. 가상 시연 데이터
# ==========================================

def create_demo_data():
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM complaints"
        ).fetchone()[0]

        if count > 0:
            return False

    # 보고서 집계 수치를 재현하기 위한 가상 데이터
    types = (
        ["재활용품 미수거"] * 9
        + ["음식물류 미수거"] * 6
        + ["중간집하지 악취"] * 3
        + ["일반생활폐기물 미수거"] * 3
        + ["수거 지연"] * 3
        + ["중간집하지 정리 미흡"] * 3
    )

    districts = ["용현동"] * 20 + ["숭의동"] * 7
    channels = ["지자체 경유"] * 17 + ["직접 접수"] * 10

    templates = {
        "재활용품 미수거": "재활용품이 수거되지 않고 쌓여 있습니다.",
        "음식물류 미수거": "음식물 쓰레기가 수거되지 않았습니다.",
        "중간집하지 악취": "중간집하지 주변에서 악취가 심하게 발생합니다.",
        "일반생활폐기물 미수거": "일반 생활폐기물이 수거되지 않았습니다.",
        "수거 지연": "폐기물 수거가 예정 시간보다 늦어지고 있습니다.",
        "중간집하지 정리 미흡": "수거 후 주변 뒷정리가 미흡합니다."
    }

    import random
    random.seed(42)

    random.shuffle(types)
    random.shuffle(districts)
    random.shuffle(channels)

    for i in range(27):
        category = types[i]
        district = districts[i]
        channel = channels[i]

        original = (
            f"{district} ○○아파트 앞 "
            f"{templates[category]}"
        )

        analysis = analyze_complaint(original)

        # 가상 데이터의 분류값은 보고서 시연용 집계와 일치하도록 지정
        analysis["category"] = category

        received_date = date(2026, 10, 1).replace(
            day=(i % 27) + 1
        )

        with get_connection() as conn:
            conn.execute("""
                INSERT INTO complaints (
                    received_at, complaint_date, channel,
                    original_text, district, location,
                    category, priority, summary,
                    driver_message, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(received_date),
                channel,
                original,
                district,
                "○○아파트 앞",
                category,
                analysis["priority"],
                analysis["summary"],
                analysis["driver_message"],
                "완료" if i < 12 else "접수"
            ))

    return True

# ==========================================
# 6. 화면 디자인
# ==========================================

st.markdown("""
<style>
.stApp {
    background-color: #f7f9f8;
}
[data-testid="stSidebar"] {
    background-color: #123d32;
}
[data-testid="stSidebar"] * {
    color: white !important;
}
.main-title {
    font-size: 29px;
    font-weight: 800;
    color: #174b3b;
}
.sub-title {
    color: #687b72;
    font-size: 14px;
}
.metric-card {
    background: white;
    border-radius: 12px;
    padding: 18px;
    border: 1px solid #e6ece8;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="main-title">♻️ 천산환경 AI 민원 관리 시스템</div>',
    unsafe_allow_html=True
)
st.markdown(
    '<div class="sub-title">생활폐기물 수거 민원 자동 분석 및 이력 관리</div>',
    unsafe_allow_html=True
)
st.divider()

# ==========================================
# 7. 사이드바
# ==========================================

with st.sidebar:
    st.title("♻️ 천산환경")
    st.caption("AI 민원 관리 시스템")
    st.divider()

    menu = st.radio(
        "메뉴",
        [
            "대시보드",
            "민원 접수 및 AI 분석",
            "민원 관리",
            "현장 기사 전달",
            "통계 및 분석"
        ]
    )

    st.divider()
    st.caption("DEMO VERSION 1.0")

# ==========================================
# 8. 데이터 준비
# ==========================================

df = get_complaints()

if menu == "대시보드":

    st.subheader("📊 민원 현황 대시보드")

    total = len(df)
    pending = (
        len(df[df["status"] != "완료"])
        if total else 0
    )
    urgent = (
        len(df[df["priority"] == "HIGH"])
        if total else 0
    )
    completed = (
        len(df[df["status"] == "완료"])
        if total else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("전체 민원", f"{total}건")
    c2.metric("미처리 민원", f"{pending}건")
    c3.metric("긴급 민원", f"{urgent}건")
    c4.metric("완료 민원", f"{completed}건")

    st.divider()

    if total:
        left, right = st.columns(2)

        with left:
            st.markdown("#### 행정동별 민원")
            district_data = df["district"].value_counts()
            fig = px.bar(
                x=district_data.index,
                y=district_data.values,
                labels={"x": "행정동", "y": "민원 건수"},
                color_discrete_sequence=["#21966b"]
            )
            st.plotly_chart(fig, use_container_width=True)

        with right:
            st.markdown("#### 민원 유형별 현황")
            category_data = df["category"].value_counts()
            fig = px.pie(
                names=category_data.index,
                values=category_data.values,
                hole=0.45
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### 최근 접수 민원")
        st.dataframe(
            df[[
                "complaint_date", "district",
                "category", "priority", "status"
            ]].head(10),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("등록된 민원이 없습니다. 민원을 접수하거나 시연 데이터를 생성해주세요.")

    if st.button("시연용 가상 민원 27건 생성", type="primary"):
        if create_demo_data():
            st.success("가상 시연 데이터 27건을 생성했습니다.")
            st.rerun()
        else:
            st.warning("기존 데이터가 있어 생성하지 않았습니다. 중복 생성을 방지했습니다.")

# ==========================================
# 9. 민원 접수 및 AI 분석
# ==========================================

elif menu == "민원 접수 및 AI 분석":

    st.subheader("📝 민원 접수 및 자동 분석")

    with st.form("complaint_form"):
        complaint_date = st.date_input("접수 일자", value=date.today())

        channel = st.selectbox(
            "민원 유입 경로",
            ["직접 접수", "지자체 경유", "주민센터 경유", "기타"]
        )

        original_text = st.text_area(
            "민원 원문",
            placeholder="예: 용현동 ○○아파트 앞 재활용품이 수거되지 않았습니다.",
            height=150
        )

        submitted = st.form_submit_button(
            "AI 자동 분석 실행",
            type="primary"
        )

    if submitted:
        if not original_text.strip():
            st.error("민원 내용을 입력해주세요.")
        else:
            result = analyze_complaint(original_text)

            st.session_state["analysis_result"] = result
            st.session_state["analysis_original"] = original_text
            st.session_state["analysis_date"] = complaint_date
            st.session_state["analysis_channel"] = channel

    if "analysis_result" in st.session_state:
        result = st.session_state["analysis_result"]

        st.divider()
        st.markdown("### 🤖 자동 분석 결과")

        a, b, c = st.columns(3)
        a.metric("행정동", result["district"])
        b.metric("민원 유형", result["category"])
        c.metric("긴급도", result["priority"])

        st.info(f"📍 세부 위치: {result['location']}")

        st.markdown("#### 핵심 요약")
        st.success(result["summary"])

        st.markdown("#### 현장 기사 전달 메시지")
        st.code(result["driver_message"])

        if st.button("분석 결과 민원 DB에 저장", type="primary"):
            save_complaint({
                "complaint_date": st.session_state["analysis_date"],
                "channel": st.session_state["analysis_channel"],
                "original_text": st.session_state["analysis_original"],
                **result
            })
            st.success("민원이 SQLite 데이터베이스에 저장되었습니다.")
            st.session_state.pop("analysis_result", None)
            st.rerun()

# ==========================================
# 10. 민원 관리
# ==========================================

elif menu == "민원 관리":

    st.subheader("📋 민원 접수 및 처리 관리")

    if not df.empty:
        search = st.text_input("민원 검색", placeholder="행정동, 민원 내용, 유형 검색")

        filtered = df.copy()

        if search:
            mask = (
                filtered["original_text"].str.contains(search, case=False, na=False)
                | filtered["district"].str.contains(search, case=False, na=False)
                | filtered["category"].str.contains(search, case=False, na=False)
            )
            filtered = filtered[mask]

        district_filter = st.selectbox(
            "행정동 필터",
            ["전체"] + sorted(df["district"].dropna().unique().tolist())
        )

        if district_filter != "전체":
            filtered = filtered[
                filtered["district"] == district_filter
            ]

        st.dataframe(
            filtered[[
                "id", "complaint_date", "district",
                "category", "priority", "status"
            ]],
            use_container_width=True,
            hide_index=True
        )

        st.divider()
        st.markdown("#### 민원 처리 상태 변경")

        selected_id = st.selectbox(
            "민원 번호 선택",
            filtered["id"].tolist()
        )

        selected_status = st.selectbox(
            "변경할 상태",
            ["접수", "처리중", "완료"]
        )

        if st.button("처리 상태 저장"):
            update_status(selected_id, selected_status)
            st.success("처리 상태를 변경했습니다.")
            st.rerun()

        selected = df[df["id"] == selected_id].iloc[0]

        with st.expander("선택 민원 상세 내용"):
            st.write("민원 원문:", selected["original_text"])
            st.write("핵심 요약:", selected["summary"])
            st.write("기사 전달:", selected["driver_message"])

        csv = filtered.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "민원 목록 CSV 다운로드",
            csv,
            "complaints.csv",
            "text/csv"
        )

    else:
        st.info("등록된 민원이 없습니다.")

# ==========================================
# 11. 현장 기사 전달
# ==========================================

elif menu == "현장 기사 전달":

    st.subheader("🚚 현장 기사 전달 관리")

    if not df.empty:
        candidates = df[df["status"] != "완료"]

        if not candidates.empty:
            selected_id = st.selectbox(
                "전달할 민원 선택",
                candidates["id"].tolist()
            )

            selected = candidates[
                candidates["id"] == selected_id
            ].iloc[0]

            st.markdown("#### 전달 대상 민원")
            st.write(selected["original_text"])

            st.markdown("#### 기사 전달 메시지")

            message = st.text_area(
                "메시지",
                value=selected["driver_message"],
                height=120
            )

            st.caption("현재 버전은 실제 문자·알림톡 발송이 아닌 복사 및 전달 이력 관리용 시연 기능입니다.")

            st.code(message)

            st.text_input(
                "기사 전달 메시지 복사",
                value=message,
                key="copy_message"
            )

            delivered = st.checkbox(
                "현장 기사 전달 완료로 기록",
                value=bool(selected["delivered"])
            )

            if st.button("전달 상태 저장"):
                update_delivery(selected_id, delivered)
                st.success("전달 상태를 저장했습니다.")
                st.rerun()

        else:
            st.info("현재 전달 대기 중인 민원이 없습니다.")
    else:
        st.info("등록된 민원이 없습니다.")

# ==========================================
# 12. 통계 및 분석
# ==========================================

elif menu == "통계 및 분석":

    st.subheader("📈 민원 통계 및 원인 분석")

    if not df.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 행정동별 발생 비율")
            district_stats = (
                df["district"].value_counts(normalize=True) * 100
            ).round(1)

            st.dataframe(
                district_stats.rename("발생 비율(%)"),
                use_container_width=True
            )

        with col2:
            st.markdown("#### 민원 유형별 발생 건수")
            category_stats = df["category"].value_counts()
            st.dataframe(
                category_stats.rename("건수"),
                use_container_width=True
            )

        st.divider()
        st.markdown("#### 월별 민원 발생 추이")

        monthly = df.copy()
        monthly["month"] = pd.to_datetime(
            monthly["complaint_date"],
            errors="coerce"
        ).dt.to_period("M").astype(str)

        monthly_stats = (
            monthly.groupby("month")
            .size()
            .reset_index(name="건수")
        )

        fig = px.line(
            monthly_stats,
            x="month",
            y="건수",
            markers=True,
            labels={"month": "월", "건수": "민원 건수"}
        )

        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.markdown("#### 유입 채널별 현황")
        channel_stats = df["channel"].value_counts()
        fig = px.bar(
            x=channel_stats.index,
            y=channel_stats.values,
            labels={"x": "유입 경로", "y": "건수"},
            color_discrete_sequence=["#21966b"]
        )
        st.plotly_chart(fig, use_container_width=True)

        st.download_button(
            "전체 통계 데이터 CSV 다운로드",
            df.to_csv(index=False).encode("utf-8-sig"),
            "complaint_statistics.csv",
            "text/csv"
        )

    else:
        st.info("통계를 확인하려면 먼저 민원을 등록하거나 시연 데이터를 생성해주세요.")

# ==========================================
# 13. 하단 안내
# ==========================================

st.divider()
st.caption(
    "㈜천산환경 AI 민원 자동 분석·관리 시스템 | "
    "시연용 버전 1.0 | 규칙 기반 분석 엔진"
)
