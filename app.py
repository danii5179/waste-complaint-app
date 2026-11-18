
import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import folium
import html
import random

from streamlit_folium import st_folium
from datetime import datetime
from pathlib import Path


# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="생활폐기물 민원 분석 시스템",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = Path(__file__).with_name("complaints.db")

DONGS = ["용현동", "숭의동"]

CATEGORIES = [
    "재활용품 미수거",
    "음식물류 미수거",
    "일반폐기물 미수거",
    "중간집하지 악취",
    "기타 민원"
]

CHANNELS = ["지자체 경유", "전화", "기타"]

PRIORITIES = ["긴급", "높음", "보통", "낮음"]

STATUSES = ["접수", "확인 중", "처리 중", "완료"]


# =========================================================
# 2. 화면 디자인
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}

.stApp {
    background-color: #f4f7f6;
    color: #172b2b;
}

[data-testid="stSidebar"] {
    background: #173c3a;
}

[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

[data-testid="stSidebar"] .stRadio label {
    font-size: 15px;
    font-weight: 600;
}

h1, h2, h3, h4 {
    color: #173c3a;
    font-weight: 800;
}

p, label, li, span {
    color: #243b3a;
}

[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #dce8e4;
    padding: 18px;
    border-radius: 14px;
    box-shadow: 0 2px 8px rgba(20, 60, 55, 0.04);
}

[data-testid="stMetricLabel"] {
    color: #405b57 !important;
    font-weight: 600;
}

[data-testid="stMetricValue"] {
    color: #173c3a !important;
    font-weight: 800;
}

.stButton > button {
    min-height: 43px;
    border-radius: 9px;
    font-weight: 700;
    border: 1px solid #b8d1c9;
}

.stButton > button[kind="primary"] {
    background: #18765e;
    border-color: #18765e;
    color: white;
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"],
.stDateInput input,
.stTimeInput input {
    background: #ffffff !important;
    color: #172b2b !important;
    border-radius: 8px;
}

[data-testid="stDataFrame"] {
    background: #ffffff;
    border-radius: 10px;
}

div[data-testid="stForm"] {
    background: #ffffff;
    border: 1px solid #dce8e4;
    border-radius: 12px;
    padding: 18px;
}

.section-note {
    color: #526a65;
    font-size: 14px;
    margin-top: -8px;
}

.demo-notice {
    background: #e8f3ef;
    border-left: 5px solid #25866b;
    padding: 13px 16px;
    border-radius: 7px;
    color: #173c3a;
    font-size: 14px;
    margin-bottom: 16px;
}

@media (max-width: 768px) {
    .block-container {
        padding: 1rem 0.8rem 2rem 0.8rem;
    }

    h1 {
        font-size: 1.55rem !important;
    }

    h2 {
        font-size: 1.3rem !important;
    }

    h3 {
        font-size: 1.1rem !important;
    }

    p, label, li, span {
        font-size: 14px;
    }

    [data-testid="stMetric"] {
        padding: 12px;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }

    .stButton > button {
        width: 100%;
        min-height: 46px;
    }
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 3. 데이터베이스
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT,
            dong TEXT,
            location TEXT,
            category TEXT,
            priority TEXT,
            summary TEXT,
            original_text TEXT,
            channel TEXT,
            status TEXT DEFAULT '접수',
            action_message TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS delivery_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER,
            created_at TEXT,
            message TEXT
        )
    """)

    # 기존 DB에 새 컬럼이 없는 경우 자동 추가
    existing_columns = {
        row["name"]
        for row in cur.execute("PRAGMA table_info(complaints)").fetchall()
    }

    required_columns = {
        "received_at": "TEXT",
        "dong": "TEXT",
        "location": "TEXT",
        "category": "TEXT",
        "priority": "TEXT",
        "summary": "TEXT",
        "original_text": "TEXT",
        "channel": "TEXT",
        "status": "TEXT DEFAULT '접수'",
        "action_message": "TEXT",
        "updated_at": "TEXT"
    }

    for column, column_type in required_columns.items():
        if column not in existing_columns:
            cur.execute(
                f"ALTER TABLE complaints ADD COLUMN {column} {column_type}"
            )

    # 사용하지 않는 기존 분류값은 삭제하지 않고 현재 분류로 정리
    cur.execute("""
        UPDATE complaints
        SET category = '기타 민원'
        WHERE category = '대형폐기물 수거 지연'
    """)

    cur.execute("""
        UPDATE complaints
        SET channel = '기타'
        WHERE channel = '문자'
    """)

    conn.commit()
    conn.close()


def get_complaints():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM complaints ORDER BY received_at DESC, id DESC",
        conn
    )
    conn.close()
    return df


def get_delivery_logs():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT
            delivery_logs.id,
            delivery_logs.complaint_id,
            delivery_logs.created_at,
            delivery_logs.message,
            complaints.dong,
            complaints.category,
            complaints.status
        FROM delivery_logs
        LEFT JOIN complaints
        ON delivery_logs.complaint_id = complaints.id
        ORDER BY delivery_logs.created_at DESC
    """, conn)
    conn.close()
    return df


def update_complaint(complaint_id, values):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE complaints
        SET received_at = ?,
            dong = ?,
            location = ?,
            category = ?,
            priority = ?,
            summary = ?,
            original_text = ?,
            channel = ?,
            status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        values["received_at"],
        values["dong"],
        values["location"],
        values["category"],
        values["priority"],
        values["summary"],
        values["original_text"],
        values["channel"],
        values["status"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        complaint_id
    ))

    conn.commit()
    conn.close()


def add_complaint(values):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO complaints (
            received_at, dong, location, category, priority,
            summary, original_text, channel, status, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        values["received_at"],
        values["dong"],
        values["location"],
        values["category"],
        values["priority"],
        values["summary"],
        values["original_text"],
        values["channel"],
        values["status"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def delete_complaint(complaint_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM delivery_logs WHERE complaint_id = ?",
        (complaint_id,)
    )

    cur.execute(
        "DELETE FROM complaints WHERE id = ?",
        (complaint_id,)
    )

    conn.commit()
    conn.close()


def save_delivery_log(complaint_id, message):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO delivery_logs (complaint_id, created_at, message)
        VALUES (?, ?, ?)
    """, (
        complaint_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        message
    ))

    cur.execute("""
        UPDATE complaints
        SET action_message = ?, updated_at = ?
        WHERE id = ?
    """, (
        message,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        complaint_id
    ))

    conn.commit()
    conn.close()


# =========================================================
# 4. 시연 데이터 27건
# =========================================================

def create_demo_data():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM delivery_logs")
    cur.execute("DELETE FROM complaints")

    # 용현동 20건, 숭의동 7건
    dong_list = ["용현동"] * 20 + ["숭의동"] * 7

    # 재활용품 9건, 음식물 6건, 악취 3건,
    # 일반폐기물 3건, 기타 6건
    category_list = (
        ["재활용품 미수거"] * 9
        + ["음식물류 미수거"] * 6
        + ["중간집하지 악취"] * 3
        + ["일반폐기물 미수거"] * 3
        + ["기타 민원"] * 6
    )

    # 지자체 경유 17건, 전화 10건
    channel_list = ["지자체 경유"] * 17 + ["전화"] * 10

    summaries = {
        "재활용품 미수거": [
            "재활용품 수거 누락 신고",
            "분리배출 재활용품이 수거되지 않음",
            "재활용품 수거 일정 확인 요청"
        ],
        "음식물류 미수거": [
            "음식물류 폐기물 미수거 신고",
            "음식물 수거통 주변 수거 요청",
            "음식물류 배출물 수거 지연"
        ],
        "중간집하지 악취": [
            "중간집하지 악취 발생 신고",
            "집하지 주변 악취 개선 요청",
            "중간집하지 청결 상태 확인 요청"
        ],
        "일반폐기물 미수거": [
            "일반폐기물 수거 누락 신고",
            "종량제 봉투 미수거 확인 요청",
            "일반폐기물 수거 지연 신고"
        ],
        "기타 민원": [
            "폐기물 수거 관련 문의",
            "수거 일정 확인 요청",
            "배출 장소 관련 문의"
        ]
    }

    # 2026년 10월의 날짜와 시간을 다양하게 지정
    dates = [
        "2026-10-01 08:15:00",
        "2026-10-02 09:20:00",
        "2026-10-03 10:35:00",
        "2026-10-05 08:50:00",
        "2026-10-06 11:10:00",
        "2026-10-07 14:25:00",
        "2026-10-08 09:40:00",
        "2026-10-09 10:05:00",
        "2026-10-10 13:15:00",
        "2026-10-12 08:30:00",
        "2026-10-13 09:55:00",
        "2026-10-14 11:45:00",
        "2026-10-15 14:10:00",
        "2026-10-16 08:25:00",
        "2026-10-17 10:50:00",
        "2026-10-19 09:15:00",
        "2026-10-20 13:40:00",
        "2026-10-21 08:45:00",
        "2026-10-22 10:20:00",
        "2026-10-23 14:35:00",
        "2026-10-24 09:05:00",
        "2026-10-26 11:25:00",
        "2026-10-27 08:55:00",
        "2026-10-28 10:40:00",
        "2026-10-29 13:05:00",
        "2026-10-30 09:30:00",
        "2026-10-31 14:20:00"
    ]

    priorities = [
        "높음", "보통", "보통", "긴급", "보통",
        "높음", "보통", "낮음", "보통"
    ]

    statuses = [
        "완료", "접수", "처리 중", "완료", "확인 중",
        "접수", "완료", "처리 중", "접수"
    ]

    random.seed(42)

    for i in range(27):
        dong = dong_list[i]
        category = category_list[i]
        channel = channel_list[i]

        summary = summaries[category][i % len(summaries[category])]
        priority = priorities[i % len(priorities)]
        status = statuses[i % len(statuses)]

        original_text = (
            f"{dong} 지역 {summary}. "
            "현장 확인 및 수거 조치를 요청합니다."
        )

        location = f"{dong} 시연용 위치 {i + 1:02d}"

        cur.execute("""
            INSERT INTO complaints (
                received_at, dong, location, category, priority,
                summary, original_text, channel, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dates[i],
            dong,
            location,
            category,
            priority,
            summary,
            original_text,
            channel,
            status,
            dates[i]
        ))

    conn.commit()
    conn.close()


# =========================================================
# 5. 민원 분석 규칙
# =========================================================

def analyze_complaint(text):
    text = text.strip()

    if any(word in text for word in ["악취", "냄새", "악취 발생"]):
        category = "중간집하지 악취"
        priority = "높음"
        action = "중간집하지 현장 상태 및 청결 상태를 우선 확인합니다."

    elif any(word in text for word in ["음식물", "음식물류"]):
        category = "음식물류 미수거"
        priority = "높음"
        action = "음식물류 수거 여부와 수거 일정을 확인합니다."

    elif any(word in text for word in ["재활용", "플라스틱", "캔", "종이"]):
        category = "재활용품 미수거"
        priority = "보통"
        action = "재활용품 배출 상태와 수거 누락 여부를 확인합니다."

    elif any(word in text for word in ["일반폐기물", "종량제", "일반 쓰레기", "쓰레기"]):
        category = "일반폐기물 미수거"
        priority = "보통"
        action = "일반폐기물 배출 상태와 수거 여부를 확인합니다."

    else:
        category = "기타 민원"
        priority = "보통"
        action = "민원 내용을 확인한 후 담당자에게 전달합니다."

    return category, priority, action


def make_action_message(row):
    return f"""
[생활폐기물 수거 민원 현장 확인 요청]

■ 민원 번호: {row['id']}
■ 행정동: {row['dong']}
■ 위치: {row['location']}
■ 민원 유형: {row['category']}
■ 우선순위: {row['priority']}
■ 접수 일시: {row['received_at']}

■ 민원 내용
{row['summary']}

■ 현장 조치 요청
{row['action_message'] if row['action_message'] else '현장 확인 후 조치 바랍니다.'}

■ 전달 안내
현장 확인 후 처리 결과를 담당자에게 회신해 주시기 바랍니다.

※ 본 메시지는 시연용 전달 문안이며 실제 발송되지 않습니다.
""".strip()


# =========================================================
# 6. 지도용 시연 좌표
# =========================================================

# 실제 민원 주소가 아닌 지도 기능 확인용 임의 좌표
# 용현동·숭의동 인근의 대략적인 지도 표시 범위 안에서 생성
def get_demo_coordinates(df):
    locations = []

    yonghyeon_center = (37.4515, 126.6385)
    sungui_center = (37.4630, 126.6500)

    random.seed(101)

    for _, row in df.iterrows():
        if row["dong"] == "용현동":
            base_lat, base_lon = yonghyeon_center
        else:
            base_lat, base_lon = sungui_center

        lat = base_lat + random.uniform(-0.0040, 0.0040)
        lon = base_lon + random.uniform(-0.0040, 0.0040)

        locations.append((lat, lon))

    return locations


def render_complaint_map(df):
    st.markdown("""
    <div class="demo-notice">
    <b>시연용 가상 위치 안내</b><br>
    지도에 표시된 위치는 기능 시연을 위한 임의 좌표입니다.
    실제 민원 발생 주소나 현장 위치를 의미하지 않습니다.
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("지도에 표시할 민원이 없습니다.")
        return

    center = [37.4565, 126.6440]

    m = folium.Map(
        location=center,
        zoom_start=14,
        tiles="CartoDB positron",
        control_scale=True
    )

    coordinates = get_demo_coordinates(df)

    for index, (_, row) in enumerate(df.iterrows()):
        lat, lon = coordinates[index]

        if row["status"] == "완료":
            color = "green"
        elif row["priority"] == "긴급":
            color = "red"
        elif row["priority"] == "높음":
            color = "orange"
        else:
            color = "blue"

        popup_html = f"""
        <div style="width:230px; font-family:sans-serif;">
            <h4 style="margin-bottom:8px;">민원 #{int(row['id'])}</h4>
            <b>행정동:</b> {html.escape(str(row['dong']))}<br>
            <b>유형:</b> {html.escape(str(row['category']))}<br>
            <b>접수일시:</b> {html.escape(str(row['received_at']))}<br>
            <b>우선순위:</b> {html.escape(str(row['priority']))}<br>
            <b>상태:</b> {html.escape(str(row['status']))}<br>
            <b>내용:</b> {html.escape(str(row['summary']))}<br>
            <hr>
            <span style="color:#b45309;">
                ※ 시연용 임의 위치
            </span>
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row['dong']} / {row['category']}",
            icon=folium.Icon(
                color=color,
                icon="info-sign"
            )
        ).add_to(m)

    st_folium(
        m,
        width=None,
        height=570,
        returned_objects=[]
    )

    st.caption(
        "지도 색상: 빨강(긴급) · 주황(높음) · 파랑(일반) · 초록(완료)"
    )


# =========================================================
# 7. 초기 실행
# =========================================================

init_db()

# 최초 실행 시 DB가 비어 있을 때만 시연 데이터 생성
if get_complaints().empty:
    create_demo_data()


# =========================================================
# 8. 사이드바
# =========================================================

with st.sidebar:
    st.markdown("## ♻️ 천산환경")
    st.markdown("### 생활폐기물 민원 분석")
    st.caption("AI·통계 기반 민원 관리 시연 시스템")

    st.divider()

    menu = st.radio(
        "메뉴",
        [
            "대시보드",
            "민원 접수 및 분석",
            "민원 관리",
            "민원 지도",
            "통계 분석",
            "기사 전달 이력"
        ]
    )

    st.divider()

    st.markdown("### 데이터 관리")
    st.caption("시연 데이터는 2026년 10월 기준 27건입니다.")

    if st.button("시연 데이터 초기화", use_container_width=True):
        st.session_state["confirm_reset"] = True

    if st.session_state.get("confirm_reset", False):
        st.warning(
            "기존 민원과 기사 전달 이력이 모두 삭제되고 "
            "시연 데이터 27건으로 교체됩니다."
        )

        confirm_reset = st.checkbox(
            "기존 데이터를 삭제하고 시연 데이터를 다시 생성하는 것에 동의합니다."
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("초기화 실행", type="primary"):
                if confirm_reset:
                    create_demo_data()
                    st.session_state["confirm_reset"] = False
                    st.success("시연 데이터 27건을 생성했습니다.")
                    st.rerun()
                else:
                    st.error("초기화 동의 항목을 체크해 주세요.")

        with col2:
            if st.button("취소"):
                st.session_state["confirm_reset"] = False
                st.rerun()

    st.divider()
    st.caption("㈜천산환경 | 시연용 프로그램")


# =========================================================
# 9. 공통 데이터
# =========================================================

df = get_complaints()

if not df.empty:
    df["received_at"] = pd.to_datetime(
        df["received_at"],
        errors="coerce"
    )

    df["접수일"] = df["received_at"].dt.strftime("%Y-%m-%d")
    df["접수일시"] = df["received_at"].dt.strftime("%Y-%m-%d %H:%M")

total_count = len(df)

completed_count = (
    int((df["status"] == "완료").sum())
    if total_count else 0
)

pending_count = total_count - completed_count

urgent_count = (
    int((df["priority"] == "긴급").sum())
    if total_count else 0
)


# =========================================================
# 10. 대시보드
# =========================================================

if menu == "대시보드":

    st.title("생활폐기물 민원 분석 대시보드")
    st.markdown(
        "행정동·민원 유형·접수 경로별 민원 현황을 확인합니다."
    )

    st.markdown("""
    <div class="demo-notice">
    <b>시연 데이터 안내</b><br>
    보고서의 2026년 10월 민원 통계 수치를 반영한 시연용 데이터입니다.
    일부 민원 내용과 위치는 프로그램 시연을 위해 구성했습니다.
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("전체 민원", f"{total_count}건")
    c2.metric("처리 완료", f"{completed_count}건")
    c3.metric("미완료", f"{pending_count}건")
    c4.metric("긴급 민원", f"{urgent_count}건")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("행정동별 민원 현황")

        if total_count:
            dong_counts = (
                df["dong"]
                .value_counts()
                .reindex(DONGS, fill_value=0)
                .reset_index()
            )
            dong_counts.columns = ["행정동", "민원 건수"]

            fig = px.bar(
                dong_counts,
                x="민원 건수",
                y="행정동",
                orientation="h",
                text="민원 건수",
                color="행정동",
                color_discrete_sequence=["#25866b", "#75aa91"]
            )

            fig.update_layout(
                showlegend=False,
                yaxis_title="",
                xaxis_title="민원 건수",
                font=dict(family="Arial", size=13),
                height=300
            )

            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("민원 유형별 현황")

        if total_count:
            category_counts = (
                df["category"]
                .value_counts()
                .reset_index()
            )
            category_counts.columns = ["민원 유형", "민원 건수"]

            fig = px.bar(
                category_counts,
                x="민원 건수",
                y="민원 유형",
                orientation="h",
                text="민원 건수",
                color_discrete_sequence=["#397c8c"]
            )

            fig.update_layout(
                yaxis_title="",
                xaxis_title="민원 건수",
                font=dict(family="Arial", size=12),
                height=350
            )

            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("최근 접수 민원")

    if total_count:
        recent = df.sort_values(
            "received_at",
            ascending=False
        ).head(8)

        display_df = recent[[
            "id", "접수일시", "dong", "category",
            "priority", "summary", "status"
        ]].copy()

        display_df.columns = [
            "번호", "접수일시", "행정동", "민원 유형",
            "우선순위", "민원 내용", "처리 상태"
        ]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("등록된 민원이 없습니다.")


# =========================================================
# 11. 민원 접수 및 분석
# =========================================================

elif menu == "민원 접수 및 분석":

    st.title("민원 접수 및 AI 분석")
    st.markdown(
        "민원 내용을 입력하면 규칙 기반으로 민원 유형과 우선순위를 분석합니다."
    )

    with st.form("complaint_form"):

        dong = st.selectbox("행정동", DONGS)

        location = st.text_input(
            "위치 메모",
            placeholder="예: 용현동 ○○ 주변 (시연용 메모)"
        )

        channel = st.selectbox("접수 경로", CHANNELS)

        received_date = st.date_input(
            "접수 날짜",
            value=datetime.now().date()
        )

        received_time = st.time_input(
            "접수 시간",
            value=datetime.now().time().replace(second=0, microsecond=0)
        )

        original_text = st.text_area(
            "민원 내용",
            placeholder="민원 내용을 입력해 주세요.",
            height=140
        )

        submitted = st.form_submit_button(
            "민원 분석 및 등록",
            type="primary",
            use_container_width=True
        )

    if submitted:

        if not original_text.strip():
            st.error("민원 내용을 입력해 주세요.")

        else:
            category, priority, action = analyze_complaint(
                original_text
            )

            received_at = datetime.combine(
                received_date,
                received_time
            ).strftime("%Y-%m-%d %H:%M:%S")

            summary = original_text.strip()[:100]

            if not location.strip():
                location = f"{dong} 시연용 위치"

            values = {
                "received_at": received_at,
                "dong": dong,
                "location": location.strip(),
                "category": category,
                "priority": priority,
                "summary": summary,
                "original_text": original_text.strip(),
                "channel": channel,
                "status": "접수"
            }

            add_complaint(values)

            st.success("민원이 등록되었습니다.")

            st.subheader("분석 결과")

            r1, r2, r3 = st.columns(3)
            r1.metric("분류 유형", category)
            r2.metric("우선순위", priority)
            r3.metric("처리 상태", "접수")

            st.info(f"**권장 조치:** {action}")

            st.caption(
                "본 분석은 키워드 기반 시연 로직이며, "
                "실제 AI 모델의 판단 결과가 아닙니다."
            )

            st.rerun()


# =========================================================
# 12. 민원 관리
# =========================================================

elif menu == "민원 관리":

    st.title("민원 관리")
    st.markdown("등록된 민원을 검색하고 수정하거나 삭제할 수 있습니다.")

    df = get_complaints()

    if df.empty:
        st.info("등록된 민원이 없습니다.")

    else:
        search = st.text_input(
            "민원 검색",
            placeholder="민원 내용, 행정동, 유형으로 검색"
        )

        filter_dong = st.selectbox(
            "행정동 필터",
            ["전체"] + DONGS
        )

        filter_status = st.selectbox(
            "처리 상태 필터",
            ["전체"] + STATUSES
        )

        filtered = df.copy()

        if search.strip():
            mask = (
                filtered["summary"].fillna("").str.contains(
                    search, case=False, na=False
                )
                | filtered["dong"].fillna("").str.contains(
                    search, case=False, na=False
                )
                | filtered["category"].fillna("").str.contains(
                    search, case=False, na=False
                )
            )
            filtered = filtered[mask]

        if filter_dong != "전체":
            filtered = filtered[
                filtered["dong"] == filter_dong
            ]

        if filter_status != "전체":
            filtered = filtered[
                filtered["status"] == filter_status
            ]

        st.caption(f"검색 결과: {len(filtered)}건")

        view_df = filtered[[
            "id", "received_at", "dong", "category",
            "priority", "summary", "status"
        ]].copy()

        view_df.columns = [
            "번호", "접수일시", "행정동", "민원 유형",
            "우선순위", "민원 내용", "처리 상태"
        ]

        st.dataframe(
            view_df,
            use_container_width=True,
            hide_index=True
        )

        st.divider()
        st.subheader("민원 수정")

        complaint_ids = filtered["id"].tolist()

        if complaint_ids:
            selected_id = st.selectbox(
                "수정할 민원 번호",
                complaint_ids
            )

            selected = df[df["id"] == selected_id].iloc[0]

            with st.form("edit_form"):

                edit_dong = st.selectbox(
                    "행정동",
                    DONGS,
                    index=(
                        DONGS.index(selected["dong"])
                        if selected["dong"] in DONGS else 0
                    )
                )

                edit_location = st.text_input(
                    "위치 메모",
                    value=selected["location"] or ""
                )

                edit_category = st.selectbox(
                    "민원 유형",
                    CATEGORIES,
                    index=(
                        CATEGORIES.index(selected["category"])
                        if selected["category"] in CATEGORIES else 0
                    )
                )

                edit_priority = st.selectbox(
                    "우선순위",
                    PRIORITIES,
                    index=(
                        PRIORITIES.index(selected["priority"])
                        if selected["priority"] in PRIORITIES else 2
                    )
                )

                edit_channel = st.selectbox(
                    "접수 경로",
                    CHANNELS,
                    index=(
                        CHANNELS.index(selected["channel"])
                        if selected["channel"] in CHANNELS else 0
                    )
                )

                edit_status = st.selectbox(
                    "처리 상태",
                    STATUSES,
                    index=(
                        STATUSES.index(selected["status"])
                        if selected["status"] in STATUSES else 0
                    )
                )

                edit_summary = st.text_input(
                    "민원 요약",
                    value=selected["summary"] or ""
                )

                edit_original = st.text_area(
                    "원본 민원 내용",
                    value=selected["original_text"] or "",
                    height=100
                )

                edit_submitted = st.form_submit_button(
                    "수정 내용 저장",
                    type="primary",
                    use_container_width=True
                )

            if edit_submitted:
                values = {
                    "received_at": selected["received_at"],
                    "dong": edit_dong,
                    "location": edit_location,
                    "category": edit_category,
                    "priority": edit_priority,
                    "summary": edit_summary,
                    "original_text": edit_original,
                    "channel": edit_channel,
                    "status": edit_status
                }

                update_complaint(selected_id, values)
                st.success("민원 정보가 수정되었습니다.")
                st.rerun()

            st.divider()
            st.subheader("민원 삭제")

            st.warning(
                "삭제하면 해당 민원과 연결된 기사 전달 이력도 함께 삭제됩니다."
            )

            delete_confirm = st.checkbox(
                f"민원 #{selected_id}번을 삭제하는 것에 동의합니다."
            )

            if st.button("선택 민원 삭제", type="secondary"):
                if delete_confirm:
                    delete_complaint(selected_id)
                    st.success("민원이 삭제되었습니다.")
                    st.rerun()
                else:
                    st.error("삭제 동의 항목을 체크해 주세요.")


# =========================================================
# 13. 민원 지도
# =========================================================

elif menu == "민원 지도":

    st.title("민원 위치 현황 지도")
    st.markdown(
        "용현동·숭의동의 민원 분포를 지도에서 확인합니다."
    )

    df = get_complaints()

    if not df.empty:

        col1, col2 = st.columns(2)

        with col1:
            map_dong = st.selectbox(
                "행정동 선택",
                ["전체"] + DONGS
            )

        with col2:
            map_status = st.selectbox(
                "처리 상태 선택",
                ["전체"] + STATUSES
            )

        map_df = df.copy()

        if map_dong != "전체":
            map_df = map_df[
                map_df["dong"] == map_dong
            ]

        if map_status != "전체":
            map_df = map_df[
                map_df["status"] == map_status
            ]

        st.caption(f"지도 표시 민원: {len(map_df)}건")

        render_complaint_map(map_df)

        st.divider()
        st.subheader("지도 표시 민원 목록")

        map_list = map_df[[
            "id", "received_at", "dong",
            "category", "priority", "status"
        ]].copy()

        map_list.columns = [
            "번호", "접수일시", "행정동",
            "민원 유형", "우선순위", "처리 상태"
        ]

        st.dataframe(
            map_list,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("지도에 표시할 민원이 없습니다.")


# =========================================================
# 14. 통계 분석
# =========================================================

elif menu == "통계 분석":

    st.title("민원 통계 분석")

    df = get_complaints()

    if df.empty:
        st.info("통계 데이터가 없습니다.")

    else:
        df["received_at"] = pd.to_datetime(
            df["received_at"],
            errors="coerce"
        )

        st.subheader("민원 유형별 통계")

        category_stats = (
            df["category"]
            .value_counts()
            .reindex(CATEGORIES, fill_value=0)
            .reset_index()
        )

        category_stats.columns = ["민원 유형", "건수"]
        category_stats["비율(%)"] = (
            category_stats["건수"] / len(df) * 100
        ).round(1)

        st.dataframe(
            category_stats,
            use_container_width=True,
            hide_index=True
        )

        fig = px.bar(
            category_stats,
            x="민원 유형",
            y="건수",
            text="건수",
            color_discrete_sequence=["#25866b"]
        )

        fig.update_layout(
            xaxis_title="",
            yaxis_title="민원 건수",
            font=dict(size=12),
            height=350
        )

        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("행정동별 통계")

        dong_stats = (
            df["dong"]
            .value_counts()
            .reindex(DONGS, fill_value=0)
            .reset_index()
        )

        dong_stats.columns = ["행정동", "건수"]
        dong_stats["비율(%)"] = (
            dong_stats["건수"] / len(df) * 100
        ).round(1)

        st.dataframe(
            dong_stats,
            use_container_width=True,
            hide_index=True
        )

        st.divider()
        st.subheader("접수 경로별 통계")

        channel_stats = (
            df["channel"]
            .value_counts()
            .reindex(CHANNELS, fill_value=0)
            .reset_index()
        )

        channel_stats.columns = ["접수 경로", "건수"]
        channel_stats["비율(%)"] = (
            channel_stats["건수"] / len(df) * 100
        ).round(1)

        st.dataframe(
            channel_stats,
            use_container_width=True,
            hide_index=True
        )

        fig = px.pie(
            channel_stats,
            names="접수 경로",
            values="건수",
            hole=0.4,
            color_discrete_sequence=[
                "#25866b", "#75aa91", "#b6cfc3"
            ]
        )

        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("월별 접수 추이")

        monthly = (
            df.dropna(subset=["received_at"])
            .assign(
                월=lambda x: x["received_at"].dt.strftime("%Y-%m")
            )
            .groupby("월")
            .size()
            .reset_index(name="민원 건수")
            .sort_values("월")
        )

        fig = px.line(
            monthly,
            x="월",
            y="민원 건수",
            markers=True,
            text="민원 건수"
        )

        fig.update_layout(
            xaxis_title="접수 월",
            yaxis_title="민원 건수",
            height=320
        )

        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("민원 데이터 다운로드")

        export_df = df.copy()

        csv_data = export_df.to_csv(
            index=False,
            encoding="utf-8-sig"
        )

        st.download_button(
            "민원 데이터 CSV 다운로드",
            data=csv_data,
            file_name="생활폐기물_민원_데이터.csv",
            mime="text/csv",
            use_container_width=True
        )


# =========================================================
# 15. 기사 전달 이력
# =========================================================

elif menu == "기사 전달 이력":

    st.title("현장 기사 전달 관리")

    st.markdown("""
    <div class="demo-notice">
    <b>시연 모드 안내</b><br>
    아래 기능은 현장 기사에게 전달할 메시지 초안을 생성하고
    전달 이력을 저장하는 시연 기능입니다.
    실제 문자 발송이나 외부 메신저 전송은 수행하지 않습니다.
    </div>
    """, unsafe_allow_html=True)

    df = get_complaints()

    if df.empty:
        st.info("등록된 민원이 없습니다.")

    else:
        st.subheader("기사 전달 메시지 생성")

        complaint_ids = df["id"].tolist()

        selected_id = st.selectbox(
            "전달할 민원 선택",
            complaint_ids
        )

        selected = df[df["id"] == selected_id].iloc[0]

        st.write(
            f"**민원 #{selected_id} | "
            f"{selected['dong']} | {selected['category']}**"
        )

        st.write(f"우선순위: {selected['priority']}")
        st.write(f"처리 상태: {selected['status']}")

        message = make_action_message(selected)

        st.text_area(
            "기사 전달 메시지 초안",
            value=message,
            height=300,
            key=f"message_preview_{selected_id}"
        )

        st.caption(
            "메시지를 복사한 뒤 필요한 경우 외부 전달 수단에 붙여넣을 수 있습니다."
        )

        st.code(message, language="text")

        st.button(
            "메시지 복사 안내",
            on_click=lambda: st.toast(
                "위 메시지 영역을 선택해 복사해 주세요."
            )
        )

        if st.button(
            "전달 이력 저장",
            type="primary",
            use_container_width=True
        ):
            save_delivery_log(selected_id, message)
            st.success(
                "전달 문안이 이력에 저장되었습니다. 실제 발송은 되지 않았습니다."
            )
            st.rerun()

    st.divider()
    st.subheader("전달 이력 목록")

    logs = get_delivery_logs()

    if logs.empty:
        st.info("저장된 전달 이력이 없습니다.")

    else:
        log_view = logs[[
            "id", "created_at", "complaint_id",
            "dong", "category", "status"
        ]].copy()

        log_view.columns = [
            "이력 번호", "저장 일시", "민원 번호",
            "행정동", "민원 유형", "현재 상태"
        ]

        st.dataframe(
            log_view,
            use_container_width=True,
            hide_index=True
        )

        selected_log_id = st.selectbox(
            "상세 내용을 확인할 전달 이력",
            logs["id"].tolist()
        )

        log_row = logs[
            logs["id"] == selected_log_id
        ].iloc[0]

        st.text_area(
            "저장된 전달 메시지",
            value=log_row["message"],
            height=250,
            disabled=True
        )


# =========================================================
# 16. 하단 안내
# =========================================================

st.divider()

st.caption(
    "㈜천산환경 생활폐기물 민원 분석 시스템 | "
    "시연용 데이터 및 가상 위치 사용"
)

