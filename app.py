
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
import re

# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="생활폐기물 민원 분석 시스템",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "complaints.db"

CATEGORIES = [
    "재활용품 미수거",
    "음식물류 미수거",
    "일반폐기물 미수거",
    "중간집하지 악취",
    "기타 민원"
]

CHANNELS = ["지자체 경유", "전화", "기타"]
STATUSES = ["접수", "확인 중", "기사 전달", "처리 완료"]
PRIORITIES = ["HIGH", "MEDIUM", "LOW"]

CATEGORY_COLORS = {
    "재활용품 미수거": "#269C83",
    "음식물류 미수거": "#55B9A6",
    "일반폐기물 미수거": "#4D83C6",
    "중간집하지 악취": "#E7A64B",
    "기타 민원": "#8B91A5"
}

# =========================================================
# 디자인 CSS
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}

.stApp {
    background: #F5F8FA;
    color: #26364A;
}

[data-testid="stHeader"] {
    background: rgba(245,248,250,0.92);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #172D43 0%, #203D52 100%);
    border-right: 1px solid #29465A;
}

[data-testid="stSidebar"] * {
    color: #F1F7F8 !important;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #D4E3E8 !important;
}

[data-testid="stSidebar"] .stRadio label {
    padding: 10px 12px;
    border-radius: 9px;
    margin-bottom: 5px;
}

[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.09);
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

h1, h2, h3 {
    color: #1E3449 !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px;
}

.page-eyebrow {
    color: #29977F;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1.5px;
    margin-bottom: 5px;
}

.page-description {
    color: #718096;
    font-size: 14px;
    margin-top: -8px;
    margin-bottom: 24px;
}

.metric-card {
    background: #FFFFFF;
    border: 1px solid #E7EDF1;
    border-radius: 16px;
    padding: 21px 22px;
    min-height: 130px;
    box-shadow: 0 4px 16px rgba(32,61,82,0.035);
}

.metric-label {
    color: #718096;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 12px;
}

.metric-value {
    color: #20384D;
    font-size: 30px;
    font-weight: 800;
    line-height: 1.2;
}

.metric-caption {
    color: #91A0AD;
    font-size: 12px;
    margin-top: 8px;
}

.section-card {
    background: #FFFFFF;
    border: 1px solid #E7EDF1;
    border-radius: 16px;
    padding: 22px;
    box-shadow: 0 4px 16px rgba(32,61,82,0.035);
    margin-bottom: 18px;
}

.section-title {
    color: #263D52;
    font-size: 17px;
    font-weight: 750;
    margin-bottom: 5px;
}

.section-subtitle {
    color: #8997A5;
    font-size: 12px;
    margin-bottom: 16px;
}

.info-banner {
    background: #EAF6F2;
    border: 1px solid #D5ECE4;
    color: #287B68;
    border-radius: 12px;
    padding: 13px 16px;
    font-size: 13px;
    margin-bottom: 18px;
}

.stButton > button {
    border-radius: 10px;
    min-height: 42px;
    font-weight: 650;
    border: 1px solid #DCE6EA;
    transition: all 0.2s ease;
}

.stButton > button[kind="primary"] {
    background: #218D79;
    border-color: #218D79;
    color: white;
}

.stButton > button[kind="primary"]:hover {
    background: #187762;
    border-color: #187762;
}

.stTextInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"],
.stDateInput input {
    border-radius: 9px;
}

div[data-testid="stDataFrame"] {
    border: 1px solid #E8EEF1;
    border-radius: 12px;
    overflow: hidden;
}

hr {
    border-color: #E8EEF1;
}

.small-muted {
    color: #8493A0;
    font-size: 12px;
}

.status-pill {
    display: inline-block;
    border-radius: 20px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 700;
    background: #EAF6F2;
    color: #218D79;
}

[data-testid="stForm"] {
    background: #FFFFFF;
    border: 1px solid #E7EDF1;
    border-radius: 14px;
    padding: 20px;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 10px 16px;
}

@media (max-width: 768px) {
    .block-container {
        padding: 1rem 1rem 2rem 1rem;
    }
    .metric-value {
        font-size: 24px;
    }
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 데이터베이스
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_columns(conn, table_name):
    return [
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    ]


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

    # 기존 DB에 컬럼이 부족한 경우 누락 컬럼 추가
    existing = get_columns(conn, "complaints")
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

    for column, definition in required_columns.items():
        if column not in existing:
            cur.execute(
                f"ALTER TABLE complaints ADD COLUMN {column} {definition}"
            )

    log_columns = get_columns(conn, "delivery_logs")
    if "complaint_id" not in log_columns:
        cur.execute("ALTER TABLE delivery_logs ADD COLUMN complaint_id INTEGER")
    if "created_at" not in log_columns:
        cur.execute("ALTER TABLE delivery_logs ADD COLUMN created_at TEXT")
    if "message" not in log_columns:
        cur.execute("ALTER TABLE delivery_logs ADD COLUMN message TEXT")

    # 기존 데이터의 구분값을 새 화면의 선택 항목에 맞게 정리
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
    cur.execute("""
        UPDATE complaints
        SET status = '접수'
        WHERE status IS NULL OR TRIM(status) = ''
    """)
    cur.execute("""
        UPDATE complaints
        SET updated_at = received_at
        WHERE updated_at IS NULL OR TRIM(updated_at) = ''
    """)

    conn.commit()
    conn.close()


def fetch_complaints():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM complaints ORDER BY id DESC",
        conn
    )
    conn.close()
    return df


def fetch_delivery_logs():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM delivery_logs ORDER BY id DESC",
        conn
    )
    conn.close()
    return df


# =========================================================
# 규칙 기반 민원 분석
# =========================================================

def analyze_complaint(text):
    text = (text or "").strip()
    lower = text.lower()

    if any(word in lower for word in [
        "재활용", "분리수거", "플라스틱", "캔", "종이", "폐지", "페트병"
    ]):
        category = "재활용품 미수거"
    elif any(word in lower for word in [
        "음식물", "음식물쓰레기", "음식물류"
    ]):
        category = "음식물류 미수거"
    elif any(word in lower for word in [
        "악취", "냄새", "악취가", "집하지"
    ]):
        category = "중간집하지 악취"
    elif any(word in lower for word in [
        "일반쓰레기", "일반폐기물", "종량제", "생활쓰레기", "쓰레기봉투"
    ]):
        category = "일반폐기물 미수거"
    else:
        category = "기타 민원"

    high_words = [
        "긴급", "위험", "사고", "넘쳐", "넘쳐서", "심각",
        "악취가 심", "며칠째", "계속 방치", "통행 불편"
    ]
    medium_words = [
        "미수거", "수거하지", "수거 안", "방치", "불편",
        "냄새", "누락", "지연"
    ]

    if any(word in lower for word in high_words):
        priority = "HIGH"
    elif any(word in lower for word in medium_words):
        priority = "MEDIUM"
    else:
        priority = "LOW"

    dong = "미확인"
    for name in ["용현동", "숭의동"]:
        if name in text:
            dong = name
            break

    location = "세부 위치 확인 필요"
    location_match = re.search(
        r"([가-힣0-9]+(?:로|길|번길|아파트|시장|공원|초등학교|중학교|고등학교)"
        r"[가-힣0-9\- ]{0,15})",
        text
    )
    if location_match:
        location = location_match.group(1).strip()

    summary = text[:100]
    if len(text) > 100:
        summary += "..."

    return {
        "dong": dong,
        "location": location,
        "category": category,
        "priority": priority,
        "summary": summary
    }


# =========================================================
# 데이터 저장 / 수정 / 삭제
# =========================================================

def insert_complaint(data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO complaints (
            received_at, dong, location, category, priority,
            summary, original_text, channel, status,
            action_message, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now,
        data["dong"],
        data["location"],
        data["category"],
        data["priority"],
        data["summary"],
        data["original_text"],
        data["channel"],
        "접수",
        "",
        now
    ))

    complaint_id = cur.lastrowid
    conn.commit()
    conn.close()
    return complaint_id


def update_complaint(complaint_id, data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    conn.execute("""
        UPDATE complaints
        SET dong = ?, location = ?, category = ?, priority = ?,
            summary = ?, original_text = ?, channel = ?,
            status = ?, updated_at = ?
        WHERE id = ?
    """, (
        data["dong"],
        data["location"],
        data["category"],
        data["priority"],
        data["summary"],
        data["original_text"],
        data["channel"],
        data["status"],
        now,
        complaint_id
    ))
    conn.commit()
    conn.close()


def update_status(complaint_id, status):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    conn.execute("""
        UPDATE complaints
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (status, now, complaint_id))
    conn.commit()
    conn.close()


def delete_complaint(complaint_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM delivery_logs WHERE complaint_id = ?",
        (complaint_id,)
    )
    conn.execute(
        "DELETE FROM complaints WHERE id = ?",
        (complaint_id,)
    )
    conn.commit()
    conn.close()


# =========================================================
# 기사 전달 메시지
# =========================================================

def make_driver_message(row):
    return f"""[생활폐기물 수거 민원 전달]

민원 번호: #{row['id']}
행정동: {row['dong']}
세부 위치: {row['location']}
민원 유형: {row['category']}
우선순위: {row['priority']}

민원 내용:
{row['original_text']}

요청 사항:
현장 확인 후 수거 여부 및 조치 결과를 확인해 주시기 바랍니다.
"""


def save_delivery_log(complaint_id, message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    conn.execute("""
        INSERT INTO delivery_logs (complaint_id, created_at, message)
        VALUES (?, ?, ?)
    """, (complaint_id, now, message))
    conn.execute("""
        UPDATE complaints
        SET status = '기사 전달',
            action_message = ?,
            updated_at = ?
        WHERE id = ?
    """, (message, now, complaint_id))
    conn.commit()
    conn.close()


# =========================================================
# 시연 데이터
# =========================================================

def create_demo_data(force_reset=False):
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM complaints"
    ).fetchone()[0]

    if count > 0 and not force_reset:
        conn.close()
        return False

    if force_reset:
        conn.execute("DELETE FROM delivery_logs")
        conn.execute("DELETE FROM complaints")
        conn.commit()

    demo_rows = []

    examples = [
        ("용현동", "용현로 인근", "재활용품 미수거", "MEDIUM",
         "재활용품 수거일이 지났으나 플라스틱과 종이류가 수거되지 않았습니다.", "지자체 경유"),
        ("용현동", "용현시장 주변", "재활용품 미수거", "HIGH",
         "재활용품이 계속 쌓여 보행에 불편이 발생하고 있습니다.", "지자체 경유"),
        ("용현동", "용현동 주택가", "재활용품 미수거", "MEDIUM",
         "분리배출한 캔과 페트병이 수거되지 않았습니다.", "전화"),
        ("용현동", "용현초등학교 인근", "재활용품 미수거", "MEDIUM",
         "재활용품 수거 누락으로 현장 확인을 요청합니다.", "지자체 경유"),
        ("용현동", "용현동 아파트 앞", "재활용품 미수거", "LOW",
         "재활용품 일부가 남아 있어 수거를 요청합니다.", "전화"),
        ("용현동", "용현로 주택가", "재활용품 미수거", "MEDIUM",
         "종이류와 플라스틱이 수거되지 않았습니다.", "지자체 경유"),
        ("숭의동", "숭의시장 인근", "재활용품 미수거", "HIGH",
         "재활용품이 도로에 쌓여 있어 빠른 수거가 필요합니다.", "지자체 경유"),
        ("용현동", "용현동 골목", "재활용품 미수거", "LOW",
         "배출한 재활용품이 남아 있습니다.", "전화"),
        ("숭의동", "숭의동 주택가", "재활용품 미수거", "MEDIUM",
         "재활용품 미수거 관련 현장 확인을 요청합니다.", "지자체 경유"),

        ("용현동", "용현동 공동주택", "음식물류 미수거", "HIGH",
         "음식물류 폐기물이 수거되지 않아 악취가 발생합니다.", "지자체 경유"),
        ("용현동", "용현시장 주변", "음식물류 미수거", "HIGH",
         "음식물 쓰레기가 장기간 남아 있어 신속한 수거가 필요합니다.", "지자체 경유"),
        ("용현동", "용현동 주택가", "음식물류 미수거", "MEDIUM",
         "음식물류 수거가 누락되어 확인을 요청합니다.", "전화"),
        ("숭의동", "숭의동 골목", "음식물류 미수거", "MEDIUM",
         "음식물 쓰레기 수거가 되지 않았습니다.", "지자체 경유"),
        ("용현동", "용현로 인근", "음식물류 미수거", "LOW",
         "음식물류 폐기물이 일부 남아 있습니다.", "전화"),
        ("숭의동", "숭의시장 인근", "음식물류 미수거", "HIGH",
         "음식물류 미수거로 주변 악취와 불편이 발생합니다.", "지자체 경유"),

        ("용현동", "용현동 중간집하지", "중간집하지 악취", "HIGH",
         "중간집하지 주변에서 심한 악취가 발생하고 있습니다.", "지자체 경유"),
        ("용현동", "용현동 집하지 주변", "중간집하지 악취", "MEDIUM",
         "집하지 주변 냄새가 심해 현장 점검을 요청합니다.", "지자체 경유"),
        ("숭의동", "숭의동 중간집하지", "중간집하지 악취", "HIGH",
         "중간집하지 악취로 인근 주민 불편이 발생하고 있습니다.", "지자체 경유"),

        ("용현동", "용현동 주택가", "일반폐기물 미수거", "MEDIUM",
         "종량제 봉투가 수거되지 않고 남아 있습니다.", "전화"),
        ("숭의동", "숭의동 골목", "일반폐기물 미수거", "LOW",
         "일반 생활쓰레기 수거를 요청합니다.", "전화"),
        ("용현동", "용현로 인근", "일반폐기물 미수거", "MEDIUM",
         "일반폐기물이 수거되지 않아 확인이 필요합니다.", "지자체 경유"),

        ("용현동", "용현동 주택가", "기타 민원", "LOW",
         "폐기물 배출 위치에 대한 문의가 접수되었습니다.", "전화"),
        ("용현동", "용현시장 주변", "기타 민원", "MEDIUM",
         "폐기물 배출 장소 주변 정리가 필요합니다.", "지자체 경유"),
        ("숭의동", "숭의동 주택가", "기타 민원", "LOW",
         "수거 일정 관련 문의가 접수되었습니다.", "전화"),
        ("용현동", "용현동 골목", "기타 민원", "MEDIUM",
         "폐기물 배출 장소 확인을 요청합니다.", "지자체 경유"),
        ("용현동", "용현동 주택가", "기타 민원", "LOW",
         "생활폐기물 수거 관련 문의입니다.", "전화"),
        ("숭의동", "숭의동 골목", "기타 민원", "MEDIUM",
         "폐기물 수거 현황 확인을 요청합니다.", "지자체 경유"),
    ]

    now = datetime.now()
    for index, item in enumerate(examples):
        dong, location, category, priority, content, channel = item
        received = now.strftime("%Y-%m-%d %H:%M:%S")
        demo_rows.append((
            received, dong, location, category, priority,
            content[:100], content, channel, "접수", "", received
        ))

    conn.executemany("""
        INSERT INTO complaints (
            received_at, dong, location, category, priority,
            summary, original_text, channel, status,
            action_message, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, demo_rows)

    conn.commit()
    conn.close()
    return True


# =========================================================
# 공통 화면 함수
# =========================================================

def page_header(eyebrow, title, description):
    st.markdown(
        f'<div class="page-eyebrow">{eyebrow}</div>',
        unsafe_allow_html=True
    )
    st.title(title)
    st.markdown(
        f'<div class="page-description">{description}</div>',
        unsafe_allow_html=True
    )


def metric_card(label, value, caption, color="#218D79"):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="color:{color}">{value}</div>
        <div class="metric-caption">{caption}</div>
    </div>
    """, unsafe_allow_html=True)


def section_heading(title, subtitle=""):
    st.markdown(f"""
    <div class="section-title">{title}</div>
    <div class="section-subtitle">{subtitle}</div>
    """, unsafe_allow_html=True)


def style_chart(fig, height=420):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Noto Sans KR, sans-serif",
            color="#526477",
            size=13
        ),
        margin=dict(l=175, r=45, t=35, b=45),
        showlegend=False,
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family="Noto Sans KR"
        )
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#EDF1F4",
        zeroline=False,
        title=""
    )
    fig.update_yaxes(
        showgrid=False,
        tickfont=dict(size=14, color="#526477"),
        title=""
    )
    return fig


def horizontal_bar(df, category_col, value_col, title, color="#29977F"):
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return

    chart_df = df.sort_values(value_col, ascending=True)

    fig = px.bar(
        chart_df,
        x=value_col,
        y=category_col,
        orientation="h",
        text=value_col,
        color_discrete_sequence=[color]
    )
    fig.update_traces(
        texttemplate="%{text}건",
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0
    )
    fig.update_layout(title=dict(text=title, x=0.02, font=dict(size=17)))
    fig = style_chart(fig, max(340, len(chart_df) * 58 + 100))
    fig.update_layout(margin=dict(l=195, r=75, t=55, b=35))
    st.plotly_chart(fig, use_container_width=True)


def dataframe_for_display(df):
    if df.empty:
        return df

    display = df.copy()
    rename_map = {
        "id": "민원번호",
        "received_at": "접수일시",
        "dong": "행정동",
        "location": "세부 위치",
        "category": "민원 유형",
        "priority": "우선순위",
        "summary": "민원 요약",
        "channel": "접수 경로",
        "status": "처리 상태",
        "updated_at": "최근 수정"
    }
    display = display.rename(columns=rename_map)

    columns = [
        "민원번호", "접수일시", "행정동", "세부 위치",
        "민원 유형", "우선순위", "민원 요약",
        "접수 경로", "처리 상태"
    ]
    return display[[c for c in columns if c in display.columns]]


# =========================================================
# 앱 시작
# =========================================================

init_db()
create_demo_data()

df = fetch_complaints()

if not df.empty:
    df["received_at"] = pd.to_datetime(df["received_at"], errors="coerce")
    df["updated_at"] = pd.to_datetime(df["updated_at"], errors="coerce")

# =========================================================
# 사이드바
# =========================================================

with st.sidebar:
    st.markdown("""
    <div style="padding:12px 5px 22px 5px;">
        <div style="font-size:34px;">♻️</div>
        <div style="font-size:18px;font-weight:800;margin-top:8px;">
            생활폐기물 민원
        </div>
        <div style="font-size:12px;color:#BBD0D8;margin-top:4px;">
            AI 기반 민원 분석 시스템
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**WORKSPACE**")

    page = st.radio(
        "메뉴 선택",
        [
            "대시보드",
            "민원 접수 및 분석",
            "민원 관리",
            "통계 분석",
            "기사 전달 이력"
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown("**시스템 정보**")
    st.caption("㈜천산환경")
    st.caption("생활폐기물 민원 분석 시연 시스템")
    st.caption("Python · Streamlit · SQLite")

    st.markdown("---")
    st.markdown("**시연 데이터 관리**")
    st.caption("초기 시연 데이터는 27건입니다.")

    if st.button("시연 데이터 초기화", use_container_width=True):
        create_demo_data(force_reset=True)
        st.success("시연 데이터 27건을 다시 생성했습니다.")
        st.rerun()

    st.markdown("""
    <div style="font-size:10px;color:#AFC2CD;margin-top:25px;">
        DEMO VERSION · 2026
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# 1. 대시보드
# =========================================================

if page == "대시보드":
    page_header(
        "OVERVIEW",
        "민원 현황 대시보드",
        "생활폐기물 수거 민원 현황과 주요 발생 유형을 한눈에 확인합니다."
    )

    total = len(df)
    pending = len(df[df["status"] != "처리 완료"]) if total else 0
    high = len(df[df["priority"] == "HIGH"]) if total else 0
    completed = len(df[df["status"] == "처리 완료"]) if total else 0

    st.markdown('<div class="info-banner">● 민원 데이터를 기반으로 행정동별·유형별 현황을 분석하고 있습니다.</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("전체 민원", f"{total:,}건", "누적 접수 민원", "#20384D")
    with c2:
        metric_card("미완료 민원", f"{pending:,}건", "처리 완료 제외", "#D89A39")
    with c3:
        metric_card("긴급 민원", f"{high:,}건", "우선 확인 필요", "#D66D62")
    with c4:
        metric_card("처리 완료", f"{completed:,}건", "완료 상태 민원", "#218D79")

    st.markdown("")
    left, right = st.columns([1.1, 0.9], gap="large")

    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_heading("민원 유형별 현황", "접수된 민원의 유형별 건수")
        if total:
            category_counts = (
                df["category"].fillna("기타 민원")
                .value_counts()
                .rename_axis("민원 유형")
                .reset_index(name="건수")
            )
            horizontal_bar(
                category_counts,
                "민원 유형",
                "건수",
                "유형별 민원 건수",
                "#29977F"
            )
        else:
            st.info("등록된 민원이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_heading("행정동별 민원 현황", "지역별 민원 발생 건수")
        if total:
            dong_counts = (
                df["dong"].fillna("미확인")
                .value_counts()
                .rename_axis("행정동")
                .reset_index(name="건수")
            )
            horizontal_bar(
                dong_counts,
                "행정동",
                "건수",
                "행정동별 민원 건수",
                "#4D83C6"
            )
        else:
            st.info("등록된 민원이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)

    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_heading("처리 상태", "민원 처리 진행 현황")
        if total:
            status_counts = (
                df["status"].fillna("접수")
                .value_counts()
                .reindex(STATUSES, fill_value=0)
                .rename_axis("처리 상태")
                .reset_index(name="건수")
            )
            fig = px.bar(
                status_counts,
                x="처리 상태",
                y="건수",
                text="건수",
                color="처리 상태",
                color_discrete_sequence=[
                    "#4D83C6", "#E7A64B", "#29977F", "#80B8A8"
                ]
            )
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(
                height=300,
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=25, b=20),
                font=dict(family="Noto Sans KR")
            )
            fig.update_yaxes(showgrid=True, gridcolor="#EDF1F4", title="")
            fig.update_xaxes(title="", tickangle=0)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_heading("최근 접수 민원", "가장 최근 등록된 민원")
        if total:
            recent = df.head(5)
            st.dataframe(
                dataframe_for_display(recent),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("최근 접수 민원이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 2. 민원 접수 및 분석
# =========================================================

elif page == "민원 접수 및 분석":
    page_header(
        "COMPLAINT INTAKE",
        "민원 접수 및 분석",
        "민원 내용을 입력하면 규칙 기반 분석을 통해 유형과 우선순위를 자동으로 분류합니다."
    )

    st.markdown("""
    <div class="info-banner">
        입력한 민원 내용은 시스템 내부의 규칙 기반 분석 로직으로 분류됩니다.
        분석 결과를 확인한 뒤 민원을 등록할 수 있습니다.
    </div>
    """, unsafe_allow_html=True)

    with st.form("complaint_form", clear_on_submit=False):
        st.markdown("### 01. 민원 기본 정보")

        col1, col2 = st.columns(2)
        with col1:
            channel = st.selectbox("접수 경로", CHANNELS)
        with col2:
            manual_dong = st.selectbox(
                "행정동",
                ["자동 분석"] + ["용현동", "숭의동", "미확인"]
            )

        complaint_text = st.text_area(
            "민원 내용",
            placeholder="예: 용현동 용현시장 인근 재활용품이 수거되지 않아 도로에 쌓여 있습니다.",
            height=150
        )

        submitted = st.form_submit_button(
            "민원 분석하기",
            type="primary",
            use_container_width=True
        )

    if submitted:
        if not complaint_text.strip():
            st.warning("민원 내용을 입력해 주세요.")
        else:
            result = analyze_complaint(complaint_text)
            if manual_dong != "자동 분석":
                result["dong"] = manual_dong

            st.session_state["analysis_result"] = result
            st.session_state["analysis_text"] = complaint_text
            st.session_state["analysis_channel"] = channel

    if "analysis_result" in st.session_state:
        result = st.session_state["analysis_result"]

        st.markdown("")
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### 02. 분석 결과")

        a, b, c = st.columns(3)
        with a:
            metric_card("분류된 민원 유형", result["category"], "규칙 기반 자동 분류", "#218D79")
        with b:
            metric_card("우선순위", result["priority"], "민원 내용의 키워드 기준", "#D89A39" if result["priority"] == "HIGH" else "#4D83C6")
        with c:
            metric_card("행정동", result["dong"], "위치 정보 분석", "#20384D")

        st.markdown("")
        st.markdown("**세부 위치 추정**")
        st.info(result["location"])

        st.markdown("**민원 요약**")
        st.write(result["summary"])

        if st.button("분석 결과로 민원 등록하기", type="primary", use_container_width=True):
            data = {
                **result,
                "original_text": st.session_state["analysis_text"],
                "channel": st.session_state["analysis_channel"]
            }
            new_id = insert_complaint(data)
            st.success(f"민원 #{new_id}번이 등록되었습니다.")
            del st.session_state["analysis_result"]
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 3. 민원 관리
# =========================================================

elif page == "민원 관리":
    page_header(
        "COMPLAINT MANAGEMENT",
        "민원 관리",
        "접수된 민원을 검색하고 내용을 수정하거나 처리 상태를 관리합니다."
    )

    if df.empty:
        st.info("등록된 민원이 없습니다.")
    else:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_heading("민원 검색 및 필터", "조건을 선택해 원하는 민원을 찾을 수 있습니다.")

        f1, f2, f3 = st.columns(3)
        with f1:
            keyword = st.text_input("검색어", placeholder="민원 내용, 위치, 민원번호")
        with f2:
            category_filter = st.selectbox("민원 유형", ["전체"] + CATEGORIES)
        with f3:
            status_filter = st.selectbox("처리 상태", ["전체"] + STATUSES)

        filtered = df.copy()

        if keyword.strip():
            search_text = keyword.strip()
            mask = (
                filtered["original_text"].fillna("").astype(str).str.contains(search_text, case=False)
                | filtered["location"].fillna("").astype(str).str.contains(search_text, case=False)
                | filtered["dong"].fillna("").astype(str).str.contains(search_text, case=False)
                | filtered["id"].astype(str).str.contains(search_text, case=False)
            )
            filtered = filtered[mask]

        if category_filter != "전체":
            filtered = filtered[filtered["category"] == category_filter]

        if status_filter != "전체":
            filtered = filtered[filtered["status"] == status_filter]

        st.caption(f"검색 결과: {len(filtered)}건")
        st.dataframe(
            dataframe_for_display(filtered),
            use_container_width=True,
            hide_index=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("")
        st.markdown("### 민원 상세 관리")

        ids = filtered["id"].astype(int).tolist()
        if ids:
            selected_id = st.selectbox(
                "관리할 민원 선택",
                ids,
                format_func=lambda x: f"민원 #{x}"
            )
            selected = df[df["id"] == selected_id].iloc[0]

            tab_edit, tab_status, tab_delete, tab_message = st.tabs([
                "민원 수정",
                "처리 상태 변경",
                "민원 삭제",
                "기사 전달 메시지"
            ])

            with tab_edit:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown("**민원 정보 수정**")

                with st.form("edit_complaint_form"):
                    e1, e2 = st.columns(2)
                    with e1:
                        edit_dong = st.selectbox(
                            "행정동",
                            ["용현동", "숭의동", "미확인"],
                            index=["용현동", "숭의동", "미확인"].index(
                                selected["dong"] if selected["dong"] in ["용현동", "숭의동", "미확인"] else "미확인"
                            )
                        )
                        edit_category = st.selectbox(
                            "민원 유형",
                            CATEGORIES,
                            index=CATEGORIES.index(
                                selected["category"] if selected["category"] in CATEGORIES else "기타 민원"
                            )
                        )
                        edit_priority = st.selectbox(
                            "우선순위",
                            PRIORITIES,
                            index=PRIORITIES.index(
                                selected["priority"] if selected["priority"] in PRIORITIES else "LOW"
                            )
                        )
                    with e2:
                        edit_location = st.text_input(
                            "세부 위치",
                            value=str(selected["location"] or "")
                        )
                        edit_channel = st.selectbox(
                            "접수 경로",
                            CHANNELS,
                            index=CHANNELS.index(
                                selected["channel"] if selected["channel"] in CHANNELS else "기타"
                            )
                        )
                        edit_status = st.selectbox(
                            "처리 상태",
                            STATUSES,
                            index=STATUSES.index(
                                selected["status"] if selected["status"] in STATUSES else "접수"
                            )
                        )

                    edit_text = st.text_area(
                        "민원 원문",
                        value=str(selected["original_text"] or ""),
                        height=120
                    )
                    edit_summary = st.text_area(
                        "민원 요약",
                        value=str(selected["summary"] or ""),
                        height=80
                    )

                    edit_submit = st.form_submit_button(
                        "수정 내용 저장",
                        type="primary",
                        use_container_width=True
                    )

                if edit_submit:
                    update_complaint(selected_id, {
                        "dong": edit_dong,
                        "location": edit_location,
                        "category": edit_category,
                        "priority": edit_priority,
                        "summary": edit_summary,
                        "original_text": edit_text,
                        "channel": edit_channel,
                        "status": edit_status
                    })
                    st.success("민원 정보가 수정되었습니다.")
                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

            with tab_status:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown("**현재 처리 상태**")
                st.info(selected["status"])

                new_status = st.selectbox(
                    "변경할 처리 상태",
                    STATUSES,
                    index=STATUSES.index(
                        selected["status"] if selected["status"] in STATUSES else "접수"
                    ),
                    key="new_status_select"
                )

                if st.button("처리 상태 저장", type="primary"):
                    update_status(selected_id, new_status)
                    st.success("처리 상태가 변경되었습니다.")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_delete:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.warning("민원을 삭제하면 해당 민원에 연결된 기사 전달 이력도 함께 삭제됩니다.")
                confirm_delete = st.checkbox(
                    f"민원 #{selected_id}번을 삭제하는 것에 동의합니다."
                )

                if st.button(
                    "선택 민원 삭제",
                    type="primary",
                    disabled=not confirm_delete
                ):
                    delete_complaint(selected_id)
                    st.success("민원이 삭제되었습니다.")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_message:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown("**현장 기사 전달 메시지**")
                message = make_driver_message(selected)

                st.text_area(
                    "전달 메시지 미리보기",
                    value=message,
                    height=240,
                    key=f"message_preview_{selected_id}"
                )

                st.caption("※ 이 버튼은 실제 문자를 발송하지 않고 전달 메시지와 이력만 저장합니다.")

                if st.button(
                    "기사 전달 이력 저장",
                    type="primary",
                    use_container_width=True
                ):
                    save_delivery_log(selected_id, message)
                    st.success("기사 전달 메시지가 이력에 저장되었습니다.")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 4. 통계 분석
# =========================================================

elif page == "통계 분석":
    page_header(
        "DATA ANALYTICS",
        "민원 통계 분석",
        "행정동, 민원 유형, 접수 경로 및 우선순위별 민원 데이터를 분석합니다."
    )

    if df.empty:
        st.info("분석할 민원 데이터가 없습니다.")
    else:
        total = len(df)
        dong_counts = df["dong"].fillna("미확인").value_counts()
        category_counts = df["category"].fillna("기타 민원").value_counts()
        channel_counts = df["channel"].fillna("기타").value_counts()
        priority_counts = df["priority"].fillna("LOW").value_counts()

        m1, m2, m3 = st.columns(3)
        with m1:
            metric_card("분석 대상 민원", f"{total:,}건", "전체 등록 데이터", "#20384D")
        with m2:
            top_dong = dong_counts.index[0] if len(dong_counts) else "-"
            metric_card("민원 최다 발생 지역", top_dong, f"{dong_counts.iloc[0] if len(dong_counts) else 0}건", "#4D83C6")
        with m3:
            top_category = category_counts.index[0] if len(category_counts) else "-"
            metric_card("최다 민원 유형", top_category, f"{category_counts.iloc[0] if len(category_counts) else 0}건", "#218D79")

        st.markdown("")
        left, right = st.columns(2, gap="large")

        with left:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            section_heading("행정동별 민원 발생 현황", "행정동별 접수 건수 비교")
            dong_data = dong_counts.rename_axis("행정동").reset_index(name="건수")
            horizontal_bar(
                dong_data, "행정동", "건수",
                "행정동별 민원 건수", "#4D83C6"
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with right:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            section_heading("민원 유형별 발생 현황", "유형별 민원 접수 건수")
            category_data = category_counts.rename_axis("민원 유형").reset_index(name="건수")
            horizontal_bar(
                category_data, "민원 유형", "건수",
                "민원 유형별 건수", "#29977F"
            )
            st.markdown("</div>", unsafe_allow_html=True)

        left, right = st.columns(2, gap="large")

        with left:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            section_heading("접수 경로별 현황", "민원이 접수된 경로")
            channel_data = channel_counts.rename_axis("접수 경로").reset_index(name="건수")
            fig = px.bar(
                channel_data,
                x="접수 경로",
                y="건수",
                text="건수",
                color="접수 경로",
                color_discrete_sequence=["#29977F", "#4D83C6", "#9BA8B5"]
            )
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(
                height=350,
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=25, b=25),
                font=dict(family="Noto Sans KR")
            )
            fig.update_xaxes(title="", tickangle=0)
            fig.update_yaxes(title="", showgrid=True, gridcolor="#EDF1F4")
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with right:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            section_heading("우선순위별 민원 현황", "민원 대응 우선순위 분포")
            priority_data = (
                priority_counts.reindex(PRIORITIES, fill_value=0)
                .rename_axis("우선순위")
                .reset_index(name="건수")
            )
            fig = px.bar(
                priority_data,
                x="우선순위",
                y="건수",
                text="건수",
                color="우선순위",
                color_discrete_map={
                    "HIGH": "#D66D62",
                    "MEDIUM": "#E7A64B",
                    "LOW": "#29977F"
                }
            )
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(
                height=350,
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=25, b=25),
                font=dict(family="Noto Sans KR")
            )
            fig.update_xaxes(title="", tickangle=0)
            fig.update_yaxes(title="", showgrid=True, gridcolor="#EDF1F4")
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_heading("통계 데이터 다운로드", "현재 민원 데이터를 CSV 파일로 저장합니다.")

        csv_df = df.copy()
        csv = csv_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

        st.download_button(
            "민원 통계 데이터 CSV 다운로드",
            data=csv,
            file_name=f"생활폐기물_민원데이터_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            type="primary"
        )
        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 5. 기사 전달 이력
# =========================================================

elif page == "기사 전달 이력":
    page_header(
        "DELIVERY HISTORY",
        "기사 전달 이력",
        "민원별 현장 기사 전달 메시지 생성 및 저장 이력을 확인합니다."
    )

    logs = fetch_delivery_logs()

    if logs.empty:
        st.info("저장된 기사 전달 이력이 없습니다.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            metric_card("전체 전달 이력", f"{len(logs):,}건", "저장된 메시지 수", "#20384D")
        with c2:
            unique_complaints = logs["complaint_id"].nunique()
            metric_card("전달 민원 수", f"{unique_complaints:,}건", "전달 이력이 있는 민원", "#218D79")

        st.markdown("")
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_heading("전달 이력 목록", "최근 저장된 메시지부터 표시합니다.")

        display_logs = logs.rename(columns={
            "id": "이력 번호",
            "complaint_id": "민원 번호",
            "created_at": "저장 일시",
            "message": "전달 메시지"
        })

        st.dataframe(
            display_logs[["이력 번호", "민원 번호", "저장 일시"]],
            use_container_width=True,
            hide_index=True
        )

        log_ids = logs["id"].astype(int).tolist()
        selected_log_id = st.selectbox("상세 확인할 이력 선택", log_ids)

        selected_log = logs[logs["id"] == selected_log_id].iloc[0]
        st.text_area(
            "저장된 전달 메시지",
            value=str(selected_log["message"]),
            height=240
        )
        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 하단 안내
# =========================================================

st.markdown("---")
st.markdown("""
<div style="text-align:center;color:#9AA8B3;font-size:11px;padding:8px;">
    생활폐기물 민원 분석 시스템 · DEMO VERSION<br>
    본 시스템은 시연용 규칙 기반 분석 프로그램이며 실제 문자 발송 및 현장 기사 자동 배정 기능은 포함하지 않습니다.
</div>
""", unsafe_allow_html=True)
