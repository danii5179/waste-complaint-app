
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

from pathlib import Path
from datetime import datetime, date, time


# =====================================================
# 1. 기본 설정
# =====================================================

st.set_page_config(
    page_title="천산환경 생활폐기물 민원 분석",
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

CATEGORY_COLORS = {
    "재활용품 미수거": "#347DB5",
    "음식물류 미수거": "#E5A044",
    "일반폐기물 미수거": "#9274BD",
    "중간집하지 악취": "#42A17A",
    "기타 민원": "#D47778"
}

STATUS_COLORS = {
    "접수": "#E5A044",
    "확인 중": "#568DB8",
    "처리 중": "#9274BD",
    "완료": "#42A17A"
}

PRIORITY_COLORS = {
    "긴급": "#D9534F",
    "높음": "#E58A45",
    "보통": "#4C8DB8",
    "낮음": "#76A98A"
}

BASE_FONT = "Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif"


# =====================================================
# 2. 화면 디자인 및 모바일 최적화
# =====================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}

.stApp {
    background: #F3F6F5;
    color: #203633;
}

.main .block-container {
    max-width: 1500px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* 제목 */
h1 {
    color: #173C3A !important;
    font-size: 29px !important;
    font-weight: 800 !important;
    letter-spacing: -0.7px;
}

h2 {
    color: #173C3A !important;
    font-size: 23px !important;
    font-weight: 800 !important;
}

h3 {
    color: #24574D !important;
    font-size: 18px !important;
    font-weight: 700 !important;
}

p, label, li {
    color: #263D39;
    font-size: 15px;
    line-height: 1.7;
}

/* 사이드바 */
[data-testid="stSidebar"] {
    background: #173C3A;
}

[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}

/* KPI 카드 */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #DCE7E2;
    border-radius: 13px;
    padding: 17px;
    box-shadow: 0 2px 8px rgba(23, 60, 58, 0.04);
}

[data-testid="stMetricLabel"] {
    color: #4B625B !important;
    font-size: 14px !important;
    font-weight: 700 !important;
}

[data-testid="stMetricValue"] {
    color: #173C3A !important;
    font-size: 28px !important;
    font-weight: 800 !important;
}

/* 입력창 */
.stTextInput input,
.stTextArea textarea,
.stDateInput input,
.stTimeInput input {
    background: #FFFFFF !important;
    color: #203633 !important;
    font-size: 16px !important;
    border: 1px solid #B9CBC4 !important;
    border-radius: 9px !important;
}

/* 버튼 */
.stButton > button,
.stFormSubmitButton > button {
    min-height: 46px;
    border-radius: 9px;
    font-size: 15px !important;
    font-weight: 700 !important;
}

.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background: #18765E !important;
    color: #FFFFFF !important;
    border-color: #18765E !important;
}

/* 폼 */
div[data-testid="stForm"] {
    background: #FFFFFF;
    border: 1px solid #DCE7E2;
    border-radius: 12px;
    padding: 18px;
}

/* 안내 박스 */
.notice {
    background: #E8F2EE;
    border-left: 5px solid #25866B;
    padding: 15px;
    border-radius: 8px;
    color: #173C3A;
    font-size: 15px;
    line-height: 1.8;
    margin-bottom: 18px;
}

/* 모바일 */
@media screen and (max-width: 768px) {
    .main .block-container {
        padding: 1rem 0.7rem 2rem 0.7rem;
    }

    h1 {
        font-size: 23px !important;
        line-height: 1.45 !important;
    }

    h2 {
        font-size: 20px !important;
    }

    h3 {
        font-size: 17px !important;
    }

    p, label, li {
        font-size: 15px !important;
        line-height: 1.7 !important;
    }

    [data-testid="stMetric"] {
        padding: 11px 9px;
    }

    [data-testid="stMetricLabel"] {
        font-size: 12px !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 21px !important;
    }

    .stButton > button,
    .stFormSubmitButton > button {
        min-height: 48px;
        font-size: 15px !important;
    }

    .stTextInput input,
    .stTextArea textarea {
        font-size: 16px !important;
    }

    div[data-testid="stForm"] {
        padding: 12px;
    }
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# 3. Plotly 공통 디자인
# =====================================================

def chart_layout(fig, height=360, margin_left=150):
    fig.update_layout(
        height=height,
        autosize=True,
        font=dict(
            family=BASE_FONT,
            size=13,
            color="#263D39"
        ),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(
            l=margin_left,
            r=35,
            t=35,
            b=45
        ),
        showlegend=False,
        hoverlabel=dict(
            bgcolor="#173C3A",
            font=dict(
                family=BASE_FONT,
                color="#FFFFFF",
                size=13
            )
        )
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="#E8EEEB",
        zeroline=False,
        tickfont=dict(size=12, color="#425A53"),
        title=None,
        automargin=True
    )

    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        tickfont=dict(size=13, color="#263D39"),
        title=None,
        automargin=True
    )

    return fig


def make_horizontal_bar(
    df,
    name_col,
    value_col,
    color_map=None,
    height=350
):
    data = df.copy()

    if data.empty:
        return None

    data[value_col] = pd.to_numeric(
        data[value_col], errors="coerce"
    ).fillna(0)

    data = data.sort_values(value_col, ascending=True)

    if color_map:
        colors = [
            color_map.get(name, "#4C8DB8")
            for name in data[name_col]
        ]
    else:
        colors = ["#347DB5"] * len(data)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=data[value_col],
        y=data[name_col],
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(width=0),
            cornerradius=5
        ),
        text=[f"{int(v)}건" for v in data[value_col]],
        textposition="outside",
        textfont=dict(
            family=BASE_FONT,
            size=13,
            color="#263D39"
        ),
        cliponaxis=False,
        hovertemplate="%{y}<br>%{x}건<extra></extra>"
    ))

    fig = chart_layout(
        fig,
        height=max(height, len(data) * 55 + 90),
        margin_left=165
    )

    fig.update_xaxes(
        rangemode="tozero",
        showticklabels=False,
        showgrid=False
    )

    fig.update_yaxes(
        categoryorder="array",
        categoryarray=data[name_col].tolist(),
        tickangle=0
    )

    return fig


def make_donut(df, name_col, value_col, color_map=None):
    data = df.copy()

    if data.empty:
        return None

    data = data[data[value_col] > 0]

    if data.empty:
        return None

    colors = None

    if color_map:
        colors = [
            color_map.get(name, "#8CA8A0")
            for name in data[name_col]
        ]

    fig = go.Figure(data=[go.Pie(
        labels=data[name_col],
        values=data[value_col],
        hole=0.62,
        sort=False,
        marker=dict(
            colors=colors,
            line=dict(color="#FFFFFF", width=3)
        ),
        textinfo="percent",
        textposition="inside",
        insidetextfont=dict(
            family=BASE_FONT,
            size=12,
            color="#FFFFFF"
        ),
        hovertemplate="%{label}<br>%{value}건 (%{percent})<extra></extra>"
    )])

    fig.update_layout(
        height=350,
        autosize=True,
        paper_bgcolor="#FFFFFF",
        font=dict(family=BASE_FONT, size=13, color="#263D39"),
        margin=dict(l=15, r=15, t=25, b=25),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.08,
            xanchor="center",
            x=0.5,
            font=dict(size=12)
        ),
        showlegend=True
    )

    return fig


def make_daily_line(df):
    if df.empty:
        return None

    data = df.copy()

    data["날짜"] = pd.to_datetime(
        data["received_at"],
        errors="coerce"
    ).dt.date

    data = data.dropna(subset=["날짜"])

    if data.empty:
        return None

    daily = (
        data.groupby("날짜")
        .size()
        .reset_index(name="민원 건수")
        .sort_values("날짜")
    )

    fig = px.line(
        daily,
        x="날짜",
        y="민원 건수",
        markers=True
    )

    fig.update_traces(
        line=dict(color="#347DB5", width=3),
        marker=dict(
            size=8,
            color="#347DB5",
            line=dict(color="#FFFFFF", width=2)
        ),
        hovertemplate="%{x|%Y-%m-%d}<br>%{y}건<extra></extra>"
    )

    fig = chart_layout(fig, height=330, margin_left=55)

    fig.update_xaxes(
        tickformat="%m/%d",
        tickangle=0
    )

    fig.update_yaxes(
        rangemode="tozero",
        dtick=1
    )

    return fig


# =====================================================
# 4. 데이터베이스
# =====================================================

def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )
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

    existing = {
        row["name"]
        for row in cur.execute(
            "PRAGMA table_info(complaints)"
        ).fetchall()
    }

    required = {
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

    for column, column_type in required.items():
        if column not in existing:
            cur.execute(
                f"ALTER TABLE complaints ADD COLUMN {column} {column_type}"
            )

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


def add_complaint(values):
    conn = get_connection()

    conn.execute("""
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


def update_complaint(complaint_id, values):
    conn = get_connection()

    conn.execute("""
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


def save_delivery_log(complaint_id, message):
    conn = get_connection()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        INSERT INTO delivery_logs (
            complaint_id, created_at, message
        )
        VALUES (?, ?, ?)
    """, (complaint_id, now, message))

    conn.execute("""
        UPDATE complaints
        SET action_message = ?, updated_at = ?
        WHERE id = ?
    """, (message, now, complaint_id))

    conn.commit()
    conn.close()


def get_delivery_logs():
    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            delivery_logs.id,
            delivery_logs.complaint_id,
            delivery_logs.created_at,
            delivery_logs.message,
            complaints.dong,
            complaints.category
        FROM delivery_logs
        LEFT JOIN complaints
        ON delivery_logs.complaint_id = complaints.id
        ORDER BY delivery_logs.created_at DESC
    """, conn)

    conn.close()
    return df


# =====================================================
# 5. 시연 데이터 27건
# =====================================================

def create_demo_data():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM delivery_logs")
    cur.execute("DELETE FROM complaints")

    dong_list = ["용현동"] * 20 + ["숭의동"] * 7

    category_list = (
        ["재활용품 미수거"] * 9
        + ["음식물류 미수거"] * 6
        + ["중간집하지 악취"] * 3
        + ["일반폐기물 미수거"] * 3
        + ["기타 민원"] * 6
    )

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
        "긴급", "보통", "보통", "긴급", "보통",
        "높음", "보통", "낮음", "보통"
    ]

    statuses = [
        "완료", "접수", "처리 중", "완료", "확인 중",
        "접수", "완료", "처리 중", "접수"
    ]

    for i in range(27):
        dong = dong_list[i]
        category = category_list[i]
        channel = channel_list[i]

        summary = summaries[category][i % len(summaries[category])]

        original_text = (
            f"{dong} 지역 {summary}. "
            "현장 확인 및 수거 조치를 요청합니다."
        )

        cur.execute("""
            INSERT INTO complaints (
                received_at, dong, location, category, priority,
                summary, original_text, channel, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dates[i],
            dong,
            f"{dong} 시연용 위치 {i + 1:02d}",
            category,
            priorities[i % len(priorities)],
            summary,
            original_text,
            channel,
            statuses[i % len(statuses)],
            dates[i]
        ))

    conn.commit()
    conn.close()


# =====================================================
# 6. 민원 분석 및 문자 생성
# =====================================================

def analyze_complaint(text):
    text = text.strip()

    if any(x in text for x in ["악취", "냄새"]):
        return "중간집하지 악취", "높음", "중간집하지 현장 상태와 청결 상태를 우선 확인합니다."

    if any(x in text for x in ["음식물", "음식물류"]):
        return "음식물류 미수거", "높음", "음식물류 수거 여부와 수거 일정을 확인합니다."

    if any(x in text for x in ["재활용", "플라스틱", "캔", "종이"]):
        return "재활용품 미수거", "보통", "재활용품 배출 상태와 수거 누락 여부를 확인합니다."

    if any(x in text for x in ["일반폐기물", "종량제", "일반 쓰레기", "쓰레기"]):
        return "일반폐기물 미수거", "보통", "일반폐기물 배출 상태와 수거 여부를 확인합니다."

    return "기타 민원", "보통", "민원 내용을 확인한 후 담당자에게 전달합니다."


def make_sms_message(row):
    return f"""[생활폐기물 수거 요청]

민원번호: {row['id']}
행정동: {row['dong']}
위치: {row['location']}

민원유형: {row['category']}
우선순위: {row['priority']}
접수일시: {row['received_at']}

민원내용:
{row['summary']}

현장 확인 후 수거 및 필요한 조치를 부탁드립니다.

처리 결과를 담당자에게 회신해 주시기 바랍니다.

※ 천산환경 민원 관리 시스템 시연용 문안"""


# =====================================================
# 7. 최초 실행 및 데이터 로딩
# =====================================================

init_db()

if get_complaints().empty:
    create_demo_data()


# =====================================================
# 8. 사이드바
# =====================================================

with st.sidebar:
    st.markdown("## ♻️ 천산환경")
    st.markdown("### 생활폐기물 민원 분석")
    st.caption("AI·통계 기반 민원 관리 시스템")
    st.divider()

    menu = st.radio(
        "메뉴 선택",
        [
            "대시보드",
            "민원 접수 및 분석",
            "민원 관리",
            "통계 분석",
            "기사 전달 문자",
            "기사 전달 이력"
        ]
    )

    st.divider()
    st.markdown("### 데이터 관리")
    st.caption("2026년 10월 시연 데이터 27건")

    if st.button("시연 데이터 초기화", use_container_width=True):
        st.session_state["reset_confirm"] = True

    if st.session_state.get("reset_confirm", False):
        st.warning(
            "기존 민원과 전달 이력이 삭제되고 시연 데이터 27건으로 교체됩니다."
        )

        agree = st.checkbox("초기화에 동의합니다.")

        if st.button("초기화 실행"):
            if agree:
                create_demo_data()
                st.session_state["reset_confirm"] = False
                st.success("초기화되었습니다.")
                st.rerun()
            else:
                st.error("동의 항목을 체크해 주세요.")

        if st.button("초기화 취소"):
            st.session_state["reset_confirm"] = False
            st.rerun()

    st.divider()
    st.caption("㈜천산환경 | 시연용 프로그램")


# =====================================================
# 9. 공통 데이터
# =====================================================

df = get_complaints()

total = len(df)

completed = int((df["status"] == "완료").sum()) if total else 0
pending = total - completed
urgent = int((df["priority"] == "긴급").sum()) if total else 0


def show_kpis():
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("전체 민원", f"{total}건")
    c2.metric("처리 완료", f"{completed}건")
    c3.metric("미완료", f"{pending}건")
    c4.metric("긴급 민원", f"{urgent}건")


def category_statistics(data):
    counts = (
        data["category"]
        .value_counts()
        .reindex(CATEGORIES, fill_value=0)
        .reset_index()
    )

    counts.columns = ["민원 유형", "건수"]
    return counts


def dong_statistics(data):
    counts = (
        data["dong"]
        .value_counts()
        .reindex(DONGS, fill_value=0)
        .reset_index()
    )

    counts.columns = ["행정동", "건수"]
    return counts


def channel_statistics(data):
    counts = (
        data["channel"]
        .value_counts()
        .reindex(CHANNELS, fill_value=0)
        .reset_index()
    )

    counts.columns = ["접수 경로", "건수"]
    return counts


# =====================================================
# 10. 대시보드
# =====================================================

if menu == "대시보드":

    st.title("생활폐기물 민원 분석 대시보드")

    st.markdown("""
    <div class="notice">
    <b>민원 현황 통합 관리</b><br>
    용현동·숭의동의 생활폐기물 민원을 유형별로 분석하고
    접수 현황과 처리 상태를 확인할 수 있습니다.
    </div>
    """, unsafe_allow_html=True)

    show_kpis()

    st.divider()

    st.subheader("행정동별 민원 현황")

    dong_stats = dong_statistics(df)

    fig = make_horizontal_bar(
        dong_stats,
        "행정동",
        "건수",
        {"용현동": "#287B91", "숭의동": "#69A995"},
        height=220
    )

    if fig:
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("민원 유형별 현황")

    st.caption("민원 유형별 발생 건수를 색상으로 구분했습니다.")

    category_stats = category_statistics(df)

    fig = make_horizontal_bar(
        category_stats,
        "민원 유형",
        "건수",
        CATEGORY_COLORS,
        height=380
    )

    if fig:
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("접수 경로별 비율")

        channel_stats = channel_statistics(df)

        fig = make_donut(
            channel_stats,
            "접수 경로",
            "건수",
            {
                "지자체 경유": "#347DB5",
                "전화": "#E5A044",
                "기타": "#8D9D97"
            }
        )

        if fig:
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("처리 상태별 현황")

        status_stats = (
            df["status"]
            .value_counts()
            .reindex(STATUSES, fill_value=0)
            .reset_index()
        )

        status_stats.columns = ["처리 상태", "건수"]

        fig = make_donut(
            status_stats,
            "처리 상태",
            "건수",
            STATUS_COLORS
        )

        if fig:
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("날짜별 민원 접수 추이")

    fig = make_daily_line(df)

    if fig:
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("최근 접수 민원")

    if total:
        recent = df.head(8).copy()

        recent = recent[[
            "id", "received_at", "dong",
            "category", "priority", "summary", "status"
        ]]

        recent.columns = [
            "번호", "접수일시", "행정동",
            "민원 유형", "우선순위", "민원 내용", "처리 상태"
        ]

        st.dataframe(
            recent,
            use_container_width=True,
            hide_index=True
        )


# =====================================================
# 11. 민원 접수 및 분석
# =====================================================

elif menu == "민원 접수 및 분석":

    st.title("민원 접수 및 자동 분석")

    st.markdown(
        "민원 내용을 입력하면 유형과 우선순위를 규칙 기반으로 자동 분류합니다."
    )

    with st.form("new_complaint"):

        dong = st.selectbox("행정동", DONGS)

        location = st.text_input(
            "위치 메모",
            placeholder="예: 용현동 ○○ 주변"
        )

        channel = st.selectbox("접수 경로", CHANNELS)

        received_date = st.date_input(
            "접수 날짜",
            value=date.today()
        )

        received_time = st.time_input(
            "접수 시간",
            value=time(9, 0)
        )

        original_text = st.text_area(
            "민원 내용",
            placeholder="민원 내용을 입력해 주세요.",
            height=150
        )

        submit = st.form_submit_button(
            "민원 분석 및 등록",
            type="primary",
            use_container_width=True
        )

    if submit:
        if not original_text.strip():
            st.error("민원 내용을 입력해 주세요.")
        else:
            category, priority, action = analyze_complaint(original_text)

            received_at = datetime.combine(
                received_date,
                received_time
            ).strftime("%Y-%m-%d %H:%M:%S")

            add_complaint({
                "received_at": received_at,
                "dong": dong,
                "location": location.strip() or f"{dong} 위치 미입력",
                "category": category,
                "priority": priority,
                "summary": original_text.strip()[:100],
                "original_text": original_text.strip(),
                "channel": channel,
                "status": "접수"
            })

            st.success("민원이 등록되었습니다.")

            a, b, c = st.columns(3)
            a.metric("분류 유형", category)
            b.metric("우선순위", priority)
            c.metric("처리 상태", "접수")

            st.info(f"권장 조치: {action}")
            st.caption(
                "키워드 기반 시연 분석이며 실제 AI 모델의 분석 결과는 아닙니다."
            )

            st.rerun()


# =====================================================
# 12. 민원 관리
# =====================================================

elif menu == "민원 관리":

    st.title("민원 관리")

    df = get_complaints()

    if df.empty:
        st.info("등록된 민원이 없습니다.")

    else:
        search = st.text_input(
            "민원 검색",
            placeholder="행정동, 민원 유형, 민원 내용 검색"
        )

        dong_filter = st.selectbox("행정동 필터", ["전체"] + DONGS)
        status_filter = st.selectbox("처리 상태 필터", ["전체"] + STATUSES)

        filtered = df.copy()

        if search.strip():
            mask = (
                filtered["summary"].fillna("").str.contains(search, case=False, na=False)
                | filtered["dong"].fillna("").str.contains(search, case=False, na=False)
                | filtered["category"].fillna("").str.contains(search, case=False, na=False)
            )
            filtered = filtered[mask]

        if dong_filter != "전체":
            filtered = filtered[filtered["dong"] == dong_filter]

        if status_filter != "전체":
            filtered = filtered[filtered["status"] == status_filter]

        st.caption(f"검색 결과 {len(filtered)}건")

        display = filtered[[
            "id", "received_at", "dong",
            "category", "priority", "summary", "status"
        ]].copy()

        display.columns = [
            "번호", "접수일시", "행정동",
            "민원 유형", "우선순위", "민원 내용", "상태"
        ]

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True
        )

        st.divider()
        st.subheader("민원 수정 및 상태 변경")

        ids = filtered["id"].tolist()

        if ids:
            selected_id = st.selectbox("민원 번호 선택", ids)
            selected = df[df["id"] == selected_id].iloc[0]

            with st.form("edit_complaint"):

                edit_dong = st.selectbox(
                    "행정동",
                    DONGS,
                    index=DONGS.index(selected["dong"])
                    if selected["dong"] in DONGS else 0
                )

                edit_location = st.text_input(
                    "위치 메모",
                    value=selected["location"] or ""
                )

                edit_category = st.selectbox(
                    "민원 유형",
                    CATEGORIES,
                    index=CATEGORIES.index(selected["category"])
                    if selected["category"] in CATEGORIES else 0
                )

                edit_priority = st.selectbox(
                    "우선순위",
                    PRIORITIES,
                    index=PRIORITIES.index(selected["priority"])
                    if selected["priority"] in PRIORITIES else 2
                )

                edit_channel = st.selectbox(
                    "접수 경로",
                    CHANNELS,
                    index=CHANNELS.index(selected["channel"])
                    if selected["channel"] in CHANNELS else 0
                )

                edit_status = st.selectbox(
                    "처리 상태",
                    STATUSES,
                    index=STATUSES.index(selected["status"])
                    if selected["status"] in STATUSES else 0
                )

                edit_summary = st.text_input(
                    "민원 요약",
                    value=selected["summary"] or ""
                )

                edit_original = st.text_area(
                    "민원 원문",
                    value=selected["original_text"] or "",
                    height=100
                )

                save = st.form_submit_button(
                    "수정 내용 저장",
                    type="primary",
                    use_container_width=True
                )

            if save:
                update_complaint(selected_id, {
                    "received_at": selected["received_at"],
                    "dong": edit_dong,
                    "location": edit_location,
                    "category": edit_category,
                    "priority": edit_priority,
                    "summary": edit_summary,
                    "original_text": edit_original,
                    "channel": edit_channel,
                    "status": edit_status
                })

                st.success("수정되었습니다.")
                st.rerun()

            st.divider()
            st.subheader("민원 삭제")

            st.warning(
                "삭제하면 해당 민원에 연결된 전달 이력도 삭제됩니다."
            )

            agree = st.checkbox(
                f"민원 #{selected_id} 삭제에 동의합니다."
            )

            if st.button("선택 민원 삭제"):
                if agree:
                    delete_complaint(selected_id)
                    st.success("삭제되었습니다.")
                    st.rerun()
                else:
                    st.error("삭제 동의 항목을 체크해 주세요.")


# =====================================================
# 13. 통계 분석
# =====================================================

elif menu == "통계 분석":

    st.title("민원 통계 분석")

    df = get_complaints()

    if df.empty:
        st.info("통계 데이터가 없습니다.")

    else:
        st.subheader("민원 유형별 통계")

        category_stats = category_statistics(df)

        category_stats["비율(%)"] = (
            category_stats["건수"] / len(df) * 100
        ).round(1)

        st.dataframe(
            category_stats,
            use_container_width=True,
            hide_index=True
        )

        fig = make_horizontal_bar(
            category_stats,
            "민원 유형",
            "건수",
            CATEGORY_COLORS
        )

        if fig:
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("행정동별 통계")

        dong_stats = dong_statistics(df)

        dong_stats["비율(%)"] = (
            dong_stats["건수"] / len(df) * 100
        ).round(1)

        st.dataframe(
            dong_stats,
            use_container_width=True,
            hide_index=True
        )

        fig = make_horizontal_bar(
            dong_stats,
            "행정동",
            "건수",
            {"용현동": "#287B91", "숭의동": "#69A995"}
        )

        if fig:
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("접수 경로별 통계")

        channel_stats = channel_statistics(df)

        channel_stats["비율(%)"] = (
            channel_stats["건수"] / len(df) * 100
        ).round(1)

        st.dataframe(
            channel_stats,
            use_container_width=True,
            hide_index=True
        )

        fig = make_donut(
            channel_stats,
            "접수 경로",
            "건수",
            {
                "지자체 경유": "#347DB5",
                "전화": "#E5A044",
                "기타": "#8D9D97"
            }
        )

        if fig:
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("처리 상태별 통계")

        status_stats = (
            df["status"]
            .value_counts()
            .reindex(STATUSES, fill_value=0)
            .reset_index()
        )

        status_stats.columns = ["처리 상태", "건수"]

        fig = make_horizontal_bar(
            status_stats,
            "처리 상태",
            "건수",
            STATUS_COLORS
        )

        if fig:
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("우선순위별 통계")

        priority_stats = (
            df["priority"]
            .value_counts()
            .reindex(PRIORITIES, fill_value=0)
            .reset_index()
        )

        priority_stats.columns = ["우선순위", "건수"]

        fig = make_horizontal_bar(
            priority_stats,
            "우선순위",
            "건수",
            PRIORITY_COLORS
        )

        if fig:
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("날짜별 민원 접수 추이")

        fig = make_daily_line(df)

        if fig:
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("민원 데이터 다운로드")

        csv_data = df.to_csv(
            index=False,
            encoding="utf-8-sig"
        )

        st.download_button(
            "CSV 파일 다운로드",
            data=csv_data,
            file_name="생활폐기물_민원_데이터.csv",
            mime="text/csv",
            use_container_width=True
        )


# =====================================================
# 14. 기사 전달 문자
# =====================================================

elif menu == "기사 전달 문자":

    st.title("현장 기사 전달 문자")

    st.markdown("""
    <div class="notice">
    <b>기사 전달 문안 자동 생성</b><br>
    민원 정보를 선택하면 현장 기사에게 전달할 문자 예시를 자동으로 작성합니다.
    실제 문자 발송은 이루어지지 않습니다.
    </div>
    """, unsafe_allow_html=True)

    df = get_complaints()

    if df.empty:
        st.info("등록된 민원이 없습니다.")

    else:
        selected_id = st.selectbox(
            "전달할 민원 선택",
            df["id"].tolist()
        )

        selected = df[df["id"] == selected_id].iloc[0]

        st.divider()
        st.subheader("선택한 민원 정보")

        a, b, c = st.columns(3)

        a.metric("행정동", selected["dong"])
        b.metric("민원 유형", selected["category"])
        c.metric("우선순위", selected["priority"])

        st.write(f"**민원 내용:** {selected['summary']}")
        st.write(f"**접수 일시:** {selected['received_at']}")
        st.write(f"**처리 상태:** {selected['status']}")

        st.divider()
        st.subheader("기사 전달 문자 예시")

        message = make_sms_message(selected)

        st.text_area(
            "전달 문자 내용",
            value=message,
            height=330
        )

        st.caption(
            "문자 내용을 복사하려면 입력창을 클릭한 뒤 전체 선택하여 복사하세요."
        )

        st.code(message, language="text")

        if st.button(
            "전달 문안 이력 저장",
            type="primary",
            use_container_width=True
        ):
            save_delivery_log(selected_id, message)

            st.success(
                "전달 문안이 저장되었습니다. 실제 문자 발송은 되지 않았습니다."
            )

            st.rerun()


# =====================================================
# 15. 기사 전달 이력
# =====================================================

elif menu == "기사 전달 이력":

    st.title("기사 전달 이력")

    st.markdown("""
    <div class="notice">
    생성하여 저장한 기사 전달 문안을 확인할 수 있습니다.
    이력 저장은 실제 문자 발송을 의미하지 않습니다.
    </div>
    """, unsafe_allow_html=True)

    logs = get_delivery_logs()

    if logs.empty:
        st.info("저장된 전달 이력이 없습니다.")

    else:
        display = logs[[
            "id", "created_at", "complaint_id",
            "dong", "category"
        ]].copy()

        display.columns = [
            "이력 번호", "저장 일시", "민원 번호",
            "행정동", "민원 유형"
        ]

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        log_id = st.selectbox(
            "상세 내용을 확인할 이력 선택",
            logs["id"].tolist()
        )

        selected_log = logs[logs["id"] == log_id].iloc[0]

        st.subheader("저장된 문자 내용")

        st.text_area(
            "문자 내용",
            value=selected_log["message"],
            height=350,
            disabled=True
        )


# =====================================================
# 16. 하단 안내
# =====================================================

st.divider()

st.caption(
    "㈜천산환경 생활폐기물 민원 분석 시스템 | "
    "시연용 데이터 사용"
)


