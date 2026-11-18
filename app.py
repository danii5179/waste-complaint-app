
import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import glob
import random
import re
from datetime import datetime, date, timedelta
from collections import Counter

# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="생활폐기물 민원 분석 시스템",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_TITLE = "생활폐기물 민원 분석 시스템"

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
STATUSES = ["접수", "처리 중", "완료", "보류"]

# 기존 데이터베이스 자동 탐색
def find_database():
    preferred = [
        "waste_complaints.db",
        "complaints.db",
        "waste_management.db",
        "app.db"
    ]

    for filename in preferred:
        if os.path.exists(filename):
            try:
                conn = sqlite3.connect(filename)
                result = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='complaints'"
                ).fetchone()
                conn.close()
                if result:
                    return filename
            except Exception:
                pass

    for filename in glob.glob("*.db"):
        try:
            conn = sqlite3.connect(filename)
            result = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='complaints'"
            ).fetchone()
            conn.close()
            if result:
                return filename
        except Exception:
            pass

    return "waste_complaints.db"


DB_PATH = find_database()


# =========================================================
# 2. 디자인 CSS
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}

.stApp {
    background-color: #F4F7FB;
    color: #172B4D;
}

header[data-testid="stHeader"] {
    background: rgba(244,247,251,0.95);
}

.block-container {
    padding-top: 1.6rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

h1, h2, h3, h4 {
    color: #17365D !important;
    font-weight: 800 !important;
}

p, label, span, div {
    color: inherit;
}

[data-testid="stSidebar"] {
    background: #17365D;
}

[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}

[data-testid="stSidebar"] .stRadio label {
    padding: 8px 5px;
    font-weight: 600;
}

[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E1E8F0;
    border-radius: 13px;
    padding: 17px 18px;
    box-shadow: 0 2px 8px rgba(20,45,80,0.04);
}

[data-testid="stMetricLabel"] {
    color: #52647A !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
}

[data-testid="stMetricValue"] {
    color: #17365D !important;
    font-weight: 800 !important;
}

.stButton > button {
    background: #1E6B57;
    color: #FFFFFF !important;
    border: 0;
    border-radius: 9px;
    min-height: 42px;
    font-weight: 700;
}

.stButton > button:hover {
    background: #155442;
    color: #FFFFFF !important;
}

.stDownloadButton > button {
    background: #17365D;
    color: white !important;
    border-radius: 9px;
    font-weight: 700;
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"],
.stDateInput input,
.stNumberInput input {
    background: #FFFFFF !important;
    color: #172B4D !important;
    border-radius: 8px !important;
}

.stTextInput label,
.stTextArea label,
.stSelectbox label,
.stDateInput label,
.stNumberInput label {
    color: #263D59 !important;
    font-weight: 700 !important;
}

div[data-testid="stDataFrame"] {
    background: #FFFFFF;
    border-radius: 10px;
}

div[data-testid="stAlert"] {
    border-radius: 10px;
}

.section-card {
    background: #FFFFFF;
    padding: 20px;
    border-radius: 13px;
    border: 1px solid #E1E8F0;
    margin-bottom: 15px;
}

.info-note {
    background: #EAF2F8;
    border-left: 4px solid #1E6B57;
    padding: 12px 15px;
    border-radius: 6px;
    color: #17365D;
    margin: 10px 0 18px 0;
}

.small-muted {
    color: #64748B;
    font-size: 0.88rem;
}

@media (max-width: 768px) {
    .block-container {
        padding: 1rem 0.75rem 2rem 0.75rem;
    }

    h1 {
        font-size: 1.55rem !important;
    }

    h2 {
        font-size: 1.3rem !important;
    }

    h3 {
        font-size: 1.12rem !important;
    }

    [data-testid="stMetric"] {
        padding: 12px;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
    }

    .stButton > button,
    .stDownloadButton > button {
        width: 100%;
    }
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 3. 데이터베이스 초기화 및 마이그레이션
# =========================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn, table, column, definition):
    existing = [
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    ]

    if column not in existing:
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_db():
    conn = get_conn()

    conn.execute("""
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

    # 기존 DB에 필요한 컬럼만 추가
    migrations = {
        "received_at": "TEXT",
        "dong": "TEXT",
        "location": "TEXT",
        "place_name": "TEXT",
        "detail_address": "TEXT",
        "category": "TEXT",
        "priority": "TEXT",
        "summary": "TEXT",
        "original_text": "TEXT",
        "channel": "TEXT",
        "status": "TEXT DEFAULT '접수'",
        "action_message": "TEXT",
        "action_direction": "TEXT",
        "keywords": "TEXT",
        "updated_at": "TEXT",
        "completed_at": "TEXT"
    }

    for column, definition in migrations.items():
        ensure_column(conn, "complaints", column, definition)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS delivery_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER,
            created_at TEXT,
            message TEXT
        )
    """)

    # 이전 버전의 사용하지 않는 분류값 정리
    conn.execute("""
        UPDATE complaints
        SET category='기타 민원'
        WHERE category='대형폐기물 수거 지연'
    """)

    conn.execute("""
        UPDATE complaints
        SET channel='기타'
        WHERE channel='문자'
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# 4. 자동 분석 로직
# =========================================================

CATEGORY_KEYWORDS = {
    "재활용품 미수거": [
        "재활용", "플라스틱", "페트병", "캔", "종이",
        "박스", "비닐", "분리수거"
    ],
    "음식물류 미수거": [
        "음식물", "음식물쓰레기", "음식물류", "잔반"
    ],
    "일반폐기물 미수거": [
        "일반쓰레기", "일반폐기물", "종량제", "쓰레기봉투"
    ],
    "중간집하지 악취": [
        "악취", "냄새", "중간집하", "집하지", "악취 발생"
    ]
}

URGENT_KEYWORDS = [
    "긴급", "심각", "위험", "넘침", "화재",
    "통행 불편", "보행 위험", "심한 악취"
]

HIGH_KEYWORDS = [
    "반복", "며칠째", "계속", "다량", "방치",
    "악취", "민원 재접수", "장기간"
]

ACTION_GUIDES = {
    "재활용품 미수거": "재활용품 배출 상태와 수거 여부를 현장에서 확인하고 미수거 물량을 수거합니다.",
    "음식물류 미수거": "음식물류 배출 상태와 수거 여부를 확인하고 주변 오염 여부를 점검합니다.",
    "일반폐기물 미수거": "일반폐기물 배출 위치와 수거 일정을 확인하고 미수거 폐기물을 처리합니다.",
    "중간집하지 악취": "중간집하지 주변 악취 발생 여부와 오염 상태를 확인하고 청소 및 위생 조치를 검토합니다.",
    "기타 민원": "민원 내용을 현장에서 확인한 후 담당자 판단에 따라 적절한 조치를 진행합니다."
}


def extract_keywords(text):
    text_lower = text.lower()

    words = [
        "재활용", "플라스틱", "페트병", "캔", "종이",
        "박스", "비닐", "음식물", "일반쓰레기", "종량제",
        "악취", "냄새", "중간집하", "넘침", "방치",
        "미수거", "수거 지연", "반복", "위험", "긴급"
    ]

    found = [word for word in words if word in text_lower]
    return list(dict.fromkeys(found))[:8]


def classify_category(text):
    text_lower = text.lower()

    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(
            1 for keyword in keywords if keyword in text_lower
        )

    best_category = max(scores, key=scores.get)

    if scores[best_category] == 0:
        return "기타 민원"

    return best_category


def classify_priority(text):
    text_lower = text.lower()

    if any(word in text_lower for word in URGENT_KEYWORDS):
        return "긴급"

    if any(word in text_lower for word in HIGH_KEYWORDS):
        return "높음"

    if len(text.strip()) < 15:
        return "보통"

    return "보통"


def summarize_text(text, max_length=120):
    """
    단순 앞부분 자르기가 아니라 핵심 키워드가 포함된
    문장을 우선 추출하는 규칙 기반 요약
    """
    clean = re.sub(r"\s+", " ", text).strip()

    if not clean:
        return "입력된 민원 내용이 없습니다."

    sentences = re.split(r"(?<=[.!?。])\s+|(?<=다)\s+", clean)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        sentences = [clean]

    important_words = [
        "미수거", "수거", "악취", "냄새", "넘침",
        "방치", "위험", "반복", "불편", "쓰레기",
        "재활용", "음식물", "일반폐기물"
    ]

    scored = []

    for index, sentence in enumerate(sentences):
        score = sum(
            2 for word in important_words if word in sentence
        )
        score += min(len(sentence) / 100, 1)
        scored.append((score, index, sentence))

    scored.sort(key=lambda x: (-x[0], x[1]))

    selected = []
    current_length = 0

    for _, _, sentence in scored:
        if sentence in selected:
            continue

        if current_length + len(sentence) > max_length:
            continue

        selected.append(sentence)
        current_length += len(sentence)

        if current_length >= max_length * 0.7:
            break

    if not selected:
        result = clean[:max_length]
    else:
        # 원문 순서로 복원
        selected_set = set(selected)
        result = " ".join(
            sentence for sentence in sentences
            if sentence in selected_set
        )

    if len(result) > max_length:
        result = result[:max_length].rstrip() + "..."

    return result


def analyze_complaint(text):
    category = classify_category(text)
    priority = classify_priority(text)
    summary = summarize_text(text)
    keywords = extract_keywords(text)
    action_direction = ACTION_GUIDES[category]

    return {
        "category": category,
        "priority": priority,
        "summary": summary,
        "keywords": keywords,
        "action_direction": action_direction
    }


def make_action_message(
    complaint_id,
    dong,
    location,
    category,
    priority,
    summary,
    action_direction
):
    return f"""[생활폐기물 민원 현장 확인 요청]

민원 번호: {complaint_id if complaint_id else '등록 전'}
행정동: {dong}
배출장소: {location}
민원 유형: {category}
우선순위: {priority}

민원 요약:
{summary}

현장 조치 방향:
{action_direction}

현장 확인 후 처리 결과를 담당자에게 공유해 주시기 바랍니다.

※ 본 문안은 내부 전달용 초안이며 자동 발송되지 않습니다.
"""


# =========================================================
# 5. 민원 데이터 처리
# =========================================================

def add_complaint(
    received_at,
    dong,
    place_name,
    detail_address,
    category,
    priority,
    summary,
    original_text,
    channel,
    action_direction,
    keywords,
    action_message
):
    location = " ".join(
        x for x in [place_name, detail_address] if x
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    conn.execute("""
        INSERT INTO complaints (
            received_at, dong, location, place_name, detail_address,
            category, priority, summary, original_text, channel,
            status, action_message, action_direction, keywords,
            updated_at, completed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '접수', ?, ?, ?, ?, NULL)
    """, (
        received_at, dong, location, place_name, detail_address,
        category, priority, summary, original_text, channel,
        action_message, action_direction, ", ".join(keywords), now
    ))

    complaint_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    # 등록 후 민원 번호를 포함한 전달 문안 저장
    final_message = make_action_message(
        complaint_id, dong, location, category,
        priority, summary, action_direction
    )

    conn.execute("""
        UPDATE complaints
        SET action_message=?
        WHERE id=?
    """, (final_message, complaint_id))

    conn.commit()
    conn.close()

    return complaint_id


def update_complaint(
    complaint_id,
    dong,
    place_name,
    detail_address,
    category,
    priority,
    summary,
    original_text,
    channel,
    status,
    action_direction,
    keywords,
    completed_at_input
):
    conn = get_conn()

    old = conn.execute(
        "SELECT status, completed_at FROM complaints WHERE id=?",
        (complaint_id,)
    ).fetchone()

    if not old:
        conn.close()
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    location = " ".join(
        x for x in [place_name, detail_address] if x
    )

    completed_at = None

    if status == "완료":
        if completed_at_input.strip():
            try:
                parsed = datetime.strptime(
                    completed_at_input.strip(),
                    "%Y-%m-%d %H:%M"
                )
                completed_at = parsed.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                conn.close()
                raise ValueError(
                    "완료 일시는 YYYY-MM-DD HH:MM 형식으로 입력해 주세요."
                )
        elif old["completed_at"]:
            completed_at = old["completed_at"]
        else:
            completed_at = now

    action_message = make_action_message(
        complaint_id, dong, location, category,
        priority, summary, action_direction
    )

    conn.execute("""
        UPDATE complaints
        SET dong=?, location=?, place_name=?, detail_address=?,
            category=?, priority=?, summary=?, original_text=?,
            channel=?, status=?, action_message=?, action_direction=?,
            keywords=?, updated_at=?, completed_at=?
        WHERE id=?
    """, (
        dong, location, place_name, detail_address,
        category, priority, summary, original_text,
        channel, status, action_message, action_direction,
        ", ".join(keywords), now, completed_at, complaint_id
    ))

    conn.commit()
    conn.close()
    return True


def get_complaints():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM complaints ORDER BY received_at DESC, id DESC",
        conn
    )
    conn.close()

    if not df.empty:
        df["received_at"] = pd.to_datetime(
            df["received_at"], errors="coerce"
        )
        df["completed_at"] = pd.to_datetime(
            df["completed_at"], errors="coerce"
        )

    return df


def get_complaint(complaint_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM complaints WHERE id=?",
        (complaint_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def add_delivery_log(complaint_id, message):
    conn = get_conn()
    conn.execute("""
        INSERT INTO delivery_logs (complaint_id, created_at, message)
        VALUES (?, ?, ?)
    """, (
        complaint_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        message
    ))
    conn.commit()
    conn.close()


def get_delivery_logs():
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT
            d.id,
            d.complaint_id,
            d.created_at,
            d.message,
            c.dong,
            c.category,
            c.location
        FROM delivery_logs d
        LEFT JOIN complaints c
            ON d.complaint_id = c.id
        ORDER BY d.created_at DESC
    """, conn)
    conn.close()
    return df


# =========================================================
# 6. 시연 데이터 생성
# =========================================================

def create_demo_data():
    conn = get_conn()

    # 명시적인 초기화 요청이 있을 때만 기존 데이터를 교체
    conn.execute("DELETE FROM delivery_logs")
    conn.execute("DELETE FROM complaints")
    conn.commit()
    conn.close()

    categories = (
        ["재활용품 미수거"] * 9
        + ["음식물류 미수거"] * 6
        + ["중간집하지 악취"] * 3
        + ["일반폐기물 미수거"] * 3
        + ["기타 민원"] * 6
    )

    dongs = ["용현동"] * 20 + ["숭의동"] * 7
    channels = ["지자체 경유"] * 17 + ["전화"] * 10

    statuses = (
        ["접수"] * 6
        + ["처리 중"] * 6
        + ["완료"] * 9
        + ["보류"] * 6
    )

    priorities = (
        ["긴급"] * 3
        + ["높음"] * 8
        + ["보통"] * 10
        + ["낮음"] * 6
    )

    random.seed(42)

    random.shuffle(categories)
    random.shuffle(dongs)
    random.shuffle(channels)
    random.shuffle(statuses)
    random.shuffle(priorities)

    sample_texts = {
        "재활용품 미수거": [
            "배출장소에 재활용품이 수거되지 않고 남아 있습니다.",
            "플라스틱과 종이류가 며칠째 수거되지 않아 확인이 필요합니다.",
            "재활용품 수거 누락으로 주변 정리가 필요합니다."
        ],
        "음식물류 미수거": [
            "음식물류 폐기물이 수거되지 않아 냄새가 발생하고 있습니다.",
            "음식물 쓰레기가 배출장소에 남아 있어 수거 요청합니다.",
            "음식물류 미수거가 반복되어 현장 확인이 필요합니다."
        ],
        "중간집하지 악취": [
            "중간집하지 주변에서 악취가 발생하고 있습니다.",
            "집하지 주변 냄새가 심해 청소 상태 확인이 필요합니다.",
            "중간집하지 악취 관련 현장 점검을 요청합니다."
        ],
        "일반폐기물 미수거": [
            "일반폐기물이 수거되지 않고 남아 있습니다.",
            "종량제 봉투가 배출장소에 계속 방치되어 있습니다.",
            "일반쓰레기 수거 여부를 확인해 주시기 바랍니다."
        ],
        "기타 민원": [
            "배출장소 주변 정리 상태를 확인해 주시기 바랍니다.",
            "폐기물 배출 관련 현장 확인을 요청합니다.",
            "수거 작업 관련 불편 사항이 접수되었습니다."
        ]
    }

    for i in range(27):
        category = categories[i]
        dong = dongs[i]
        channel = channels[i]
        status = statuses[i]
        priority = priorities[i]

        day = (i * 7 + 2) % 31 + 1
        hour = 7 + (i * 3) % 13
        minute = (i * 11) % 60

        received_dt = datetime(
            2026, 10, day, hour, minute
        )

        original_text = random.choice(sample_texts[category])
        analysis = analyze_complaint(original_text)

        location = f"{dong} 시연용 배출장소 {i+1:02d}"

        completed_at = None

        if status == "완료":
            completed_dt = received_dt + timedelta(
                hours=random.randint(2, 30)
            )
            completed_at = completed_dt.strftime("%Y-%m-%d %H:%M:%S")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_conn()
        conn.execute("""
            INSERT INTO complaints (
                received_at, dong, location, place_name,
                detail_address, category, priority, summary,
                original_text, channel, status, action_message,
                action_direction, keywords, updated_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            received_dt.strftime("%Y-%m-%d %H:%M:%S"),
            dong,
            location,
            f"시연용 배출장소 {i+1:02d}",
            "",
            category,
            priority,
            analysis["summary"],
            original_text,
            channel,
            status,
            "",
            analysis["action_direction"],
            ", ".join(analysis["keywords"]),
            now,
            completed_at
        ))

        complaint_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        message = make_action_message(
            complaint_id,
            dong,
            location,
            category,
            priority,
            analysis["summary"],
            analysis["action_direction"]
        )

        conn.execute(
            "UPDATE complaints SET action_message=? WHERE id=?",
            (message, complaint_id)
        )

        conn.commit()
        conn.close()

    return True


# =========================================================
# 7. 그래프 함수
# =========================================================

CHART_COLORS = [
    "#1E6B57", "#2D8A73", "#17365D",
    "#4F81BD", "#E3A43B", "#7895B2",
    "#8AAE9B", "#A7B8C9"
]


def make_horizontal_bar(
    df,
    x,
    y,
    title,
    color="#1E6B57"
):
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return

    chart_df = df.copy()
    chart_df[y] = chart_df[y].astype(str)
    chart_df[x] = pd.to_numeric(
        chart_df[x], errors="coerce"
    ).fillna(0)

    chart_df = chart_df.sort_values(x, ascending=True)

    height = max(320, len(chart_df) * 55 + 100)

    fig = px.bar(
        chart_df,
        x=x,
        y=y,
        orientation="h",
        text=x,
        color_discrete_sequence=[color]
    )

    fig.update_traces(
        textposition="outside",
        texttemplate="%{x:,.0f}",
        cliponaxis=False,
        marker_line_width=0
    )

    fig.update_layout(
        title={
            "text": title,
            "font": {"size": 18, "color": "#17365D"}
        },
        height=height,
        autosize=True,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={
            "family": "Noto Sans KR",
            "size": 13,
            "color": "#263D59"
        },
        margin=dict(l=20, r=45, t=65, b=35),
        showlegend=False,
        xaxis=dict(
            title="민원 건수",
            showgrid=True,
            gridcolor="#E8EDF3",
            zeroline=False,
            rangemode="tozero",
            automargin=True
        ),
        yaxis=dict(
            title="",
            automargin=True,
            tickfont=dict(size=13, color="#263D59"),
            categoryorder="array",
            categoryarray=chart_df[y].tolist()
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "responsive": True
        }
    )


def make_trend_chart(df):
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return

    fig = px.line(
        df,
        x="날짜",
        y="민원 건수",
        markers=True,
        color_discrete_sequence=["#1E6B57"]
    )

    fig.update_traces(
        line_width=3,
        marker_size=8
    )

    fig.update_layout(
        title={
            "text": "날짜별 민원 접수 추이",
            "font": {"size": 18, "color": "#17365D"}
        },
        height=370,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={
            "family": "Noto Sans KR",
            "size": 13,
            "color": "#263D59"
        },
        margin=dict(l=25, r=25, t=65, b=55),
        xaxis=dict(
            title="접수 날짜",
            tickangle=0,
            automargin=True,
            tickformat="%m-%d",
            showgrid=False
        ),
        yaxis=dict(
            title="민원 건수",
            rangemode="tozero",
            gridcolor="#E8EDF3"
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "responsive": True
        }
    )


def count_frame(df, column, order=None):
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=["항목", "건수"])

    result = (
        df[column]
        .fillna("미분류")
        .astype(str)
        .value_counts()
        .rename_axis("항목")
        .reset_index(name="건수")
    )

    if order:
        order_map = {v: i for i, v in enumerate(order)}
        result["_order"] = result["항목"].map(
            lambda x: order_map.get(x, len(order))
        )
        result = result.sort_values("_order").drop(
            columns="_order"
        )

    return result


def render_distribution(df, column, title, order=None):
    result = count_frame(df, column, order)

    if result.empty:
        st.info("표시할 데이터가 없습니다.")
        return

    make_horizontal_bar(
        result,
        x="건수",
        y="항목",
        title=title
    )


# =========================================================
# 8. 공통 통계 함수
# =========================================================

def calculate_duration(df):
    if df.empty:
        return None, 0

    completed = df[
        (df["status"] == "완료")
        & df["received_at"].notna()
        & df["completed_at"].notna()
    ].copy()

    if completed.empty:
        return None, 0

    completed["소요시간"] = (
        completed["completed_at"] - completed["received_at"]
    ).dt.total_seconds() / 3600

    completed = completed[
        completed["소요시간"] >= 0
    ]

    if completed.empty:
        return None, 0

    return completed["소요시간"].mean(), len(completed)


def apply_date_filter(df, start_date, end_date):
    if df.empty:
        return df

    result = df.copy()

    result = result[
        result["received_at"].notna()
    ]

    result = result[
        (result["received_at"].dt.date >= start_date)
        & (result["received_at"].dt.date <= end_date)
    ]

    return result


def show_header(title, description=None):
    st.title(title)

    if description:
        st.markdown(
            f'<div class="info-note">{description}</div>',
            unsafe_allow_html=True
        )


# =========================================================
# 9. 사이드바
# =========================================================

with st.sidebar:
    st.markdown("## ♻️ 생활폐기물")
    st.markdown("### 민원 분석 시스템")
    st.caption("㈜천산환경 업무 시연 프로그램")
    st.divider()

    menu = st.radio(
        "메뉴",
        [
            "대시보드",
            "민원 접수 및 분석",
            "민원 관리",
            "통계 분석"
        ]
    )

    st.divider()
    st.markdown("**관할 행정동**")
    st.write("• 용현동")
    st.write("• 숭의동")

    st.divider()
    st.caption(f"데이터베이스: {DB_PATH}")

    current_count = len(get_complaints())

    if current_count == 0:
        st.info("등록된 민원이 없습니다.")
        if st.button("시연 데이터 27건 생성", use_container_width=True):
            create_demo_data()
            st.success("시연 데이터 27건을 생성했습니다.")
            st.rerun()

    else:
        st.caption(f"현재 등록 민원: {current_count}건")
        with st.expander("시연 데이터 초기화"):
            st.warning(
                "주의: 기존 민원과 기사 전달 이력이 모두 삭제되고 "
                "시연용 데이터 27건으로 교체됩니다."
            )

            confirm_reset = st.checkbox(
                "기존 데이터를 삭제하고 시연 데이터를 생성하는 데 동의합니다."
            )

            if st.button(
                "기존 데이터 초기화 및 재생성",
                disabled=not confirm_reset,
                use_container_width=True
            ):
                create_demo_data()
                st.success("시연 데이터를 재생성했습니다.")
                st.rerun()

    if st.button("화면 새로고침", use_container_width=True):
        st.rerun()


# =========================================================
# 10. 데이터 불러오기
# =========================================================

df = get_complaints()

if not df.empty:
    df["status"] = df["status"].fillna("접수")
    df["category"] = df["category"].fillna("기타 민원")
    df["dong"] = df["dong"].fillna("미분류")
    df["channel"] = df["channel"].fillna("기타")
    df["priority"] = df["priority"].fillna("보통")


# =========================================================
# 11. 대시보드
# =========================================================

if menu == "대시보드":

    show_header(
        "생활폐기물 민원 대시보드",
        "관할 지역의 민원 접수 현황과 처리 상태를 한눈에 확인합니다."
    )

    if df.empty:
        st.info("등록된 민원이 없습니다. 사이드바에서 시연 데이터를 생성하거나 민원을 접수해 주세요.")

    else:
        total = len(df)
        completed = int((df["status"] == "완료").sum())
        uncompleted = total - completed
        urgent = int((df["priority"] == "긴급").sum())
        processing = int((df["status"] == "처리 중").sum())

        completion_rate = (
            completed / total * 100 if total else 0
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("전체 민원", f"{total:,}건")
        c2.metric("완료 민원", f"{completed:,}건")
        c3.metric("미완료 민원", f"{uncompleted:,}건")
        c4.metric("긴급 민원", f"{urgent:,}건")

        st.progress(completion_rate / 100)
        st.caption(
            f"전체 민원 처리 완료율: {completion_rate:.1f}% "
            f"· 처리 중 {processing}건"
        )

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            render_distribution(
                df, "dong", "행정동별 민원 현황", DONGS
            )

        with col2:
            render_distribution(
                df, "category", "민원 유형별 현황", CATEGORIES
            )

        col3, col4 = st.columns(2)

        with col3:
            render_distribution(
                df, "status", "처리 상태별 현황", STATUSES
            )

        with col4:
            render_distribution(
                df, "priority", "우선순위별 현황", PRIORITIES
            )

        st.divider()

        avg_hours, duration_count = calculate_duration(df)

        if avg_hours is not None:
            st.metric(
                "평균 처리 소요 시간",
                f"{avg_hours:.1f}시간",
                help=f"완료 시각이 기록된 {duration_count}건 기준"
            )
        else:
            st.info(
                "완료 시각이 기록된 데이터가 아직 없습니다. "
                "민원을 완료 처리하면 소요 시간이 집계됩니다."
            )

        st.subheader("최근 접수 민원")

        recent = df.head(8).copy()

        display_columns = [
            "id", "received_at", "dong", "category",
            "priority", "status", "location"
        ]

        recent_display = recent[
            [c for c in display_columns if c in recent.columns]
        ].copy()

        if "received_at" in recent_display.columns:
            recent_display["received_at"] = (
                recent_display["received_at"].dt.strftime(
                    "%Y-%m-%d %H:%M"
                )
            )

        st.dataframe(
            recent_display,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 12. 민원 접수 및 분석
# =========================================================

elif menu == "민원 접수 및 분석":

    show_header(
        "민원 접수 및 분석",
        "민원 내용을 입력하면 규칙 기반 분석을 통해 유형, 우선순위, 핵심 요약 및 현장 조치 방향을 추천합니다."
    )

    st.caption(
        "※ 본 화면은 규칙 기반 자동 분석 시연 기능입니다. "
        "외부 생성형 AI API를 호출하지 않습니다."
    )

    with st.form("complaint_form", clear_on_submit=False):

        col1, col2 = st.columns(2)

        with col1:
            dong = st.selectbox(
                "행정동",
                DONGS
            )

            place_name = st.text_input(
                "배출장소",
                placeholder="예: 용현시장 인근 배출장소"
            )

            channel = st.selectbox(
                "접수 경로",
                CHANNELS
            )

        with col2:
            received_date = st.date_input(
                "접수 날짜",
                value=date.today()
            )

            received_time = st.time_input(
                "접수 시간",
                value=datetime.now().time().replace(
                    second=0, microsecond=0
                )
            )

            detail_address = st.text_input(
                "상세 주소 또는 위치 설명",
                placeholder="예: 건물 옆, 도로변 수거함 앞 등"
            )

        original_text = st.text_area(
            "민원 상세 내용",
            placeholder=(
                "민원 내용을 구체적으로 입력해 주세요.\n"
                "예: 용현동 배출장소에 재활용품이 며칠째 수거되지 않고 "
                "쌓여 있어 현장 확인 및 수거를 요청합니다."
            ),
            height=150
        )

        submitted = st.form_submit_button(
            "민원 분석 및 등록",
            use_container_width=True
        )

    if submitted:
        if not original_text.strip():
            st.error("민원 상세 내용을 입력해 주세요.")

        elif not place_name.strip() and not detail_address.strip():
            st.error("배출장소 또는 상세 위치를 입력해 주세요.")

        else:
            analysis = analyze_complaint(original_text)

            received_at = datetime.combine(
                received_date, received_time
            ).strftime("%Y-%m-%d %H:%M:%S")

            location = " ".join(
                x for x in [place_name, detail_address] if x
            )

            message = make_action_message(
                None,
                dong,
                location,
                analysis["category"],
                analysis["priority"],
                analysis["summary"],
                analysis["action_direction"]
            )

            new_id = add_complaint(
                received_at,
                dong,
                place_name,
                detail_address,
                analysis["category"],
                analysis["priority"],
                analysis["summary"],
                original_text,
                channel,
                analysis["action_direction"],
                analysis["keywords"],
                message
            )

            st.success(f"민원 {new_id}번이 등록되었습니다.")
            st.rerun()

    st.divider()

    st.subheader("자동 분석 기능 안내")

    st.markdown("""
    - **유형 분류:** 민원 내용의 키워드를 기준으로 유형을 추천합니다.
    - **우선순위 판단:** 긴급·위험·반복 등의 표현을 기준으로 우선순위를 추천합니다.
    - **핵심 요약:** 주요 키워드가 포함된 문장을 우선 추출합니다.
    - **조치 방향:** 민원 유형별 현장 확인 및 조치 방향을 제시합니다.
    - **기사 전달 문안:** 분석 결과를 바탕으로 내부 전달용 초안을 생성합니다.
    """)

    st.info(
        "자동 분석 결과는 담당자가 확인하고 수정할 수 있는 추천 결과입니다. "
        "실제 현장 상황에 따라 최종 판단이 필요합니다."
    )


# =========================================================
# 13. 민원 관리
# =========================================================

elif menu == "민원 관리":

    show_header(
        "민원 관리",
        "등록된 민원의 상세 내용, 처리 상태, 완료 시각 및 기사 전달용 문안을 관리합니다."
    )

    if df.empty:
        st.info("등록된 민원이 없습니다.")

    else:
        filter_col1, filter_col2, filter_col3 = st.columns(3)

        with filter_col1:
            filter_dong = st.selectbox(
                "행정동 필터",
                ["전체"] + DONGS,
                key="manage_dong"
            )

        with filter_col2:
            filter_status = st.selectbox(
                "처리 상태 필터",
                ["전체"] + STATUSES,
                key="manage_status"
            )

        with filter_col3:
            filter_priority = st.selectbox(
                "우선순위 필터",
                ["전체"] + PRIORITIES,
                key="manage_priority"
            )

        filtered = df.copy()

        if filter_dong != "전체":
            filtered = filtered[
                filtered["dong"] == filter_dong
            ]

        if filter_status != "전체":
            filtered = filtered[
                filtered["status"] == filter_status
            ]

        if filter_priority != "전체":
            filtered = filtered[
                filtered["priority"] == filter_priority
            ]

        st.caption(f"조회 결과: {len(filtered)}건")

        list_columns = [
            "id", "received_at", "dong", "category",
            "priority", "status", "location"
        ]

        display = filtered[
            [c for c in list_columns if c in filtered.columns]
        ].copy()

        if "received_at" in display.columns:
            display["received_at"] = (
                display["received_at"].dt.strftime(
                    "%Y-%m-%d %H:%M"
                )
            )

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True
        )

        st.divider()
        st.subheader("민원 상세 조회 및 수정")

        if not filtered.empty:
            complaint_options = {
                f"#{int(row['id'])} | {row['dong']} | {row['category']} | {row['status']}": int(row["id"])
                for _, row in filtered.iterrows()
            }

            selected_label = st.selectbox(
                "관리할 민원 선택",
                list(complaint_options.keys())
            )

            selected_id = complaint_options[selected_label]
            item = get_complaint(selected_id)

            if item:
                st.markdown(f"### 민원 번호 #{selected_id}")

                with st.form(f"edit_form_{selected_id}"):

                    c1, c2 = st.columns(2)

                    with c1:
                        edit_dong = st.selectbox(
                            "행정동",
                            DONGS,
                            index=(
                                DONGS.index(item["dong"])
                                if item["dong"] in DONGS else 0
                            )
                        )

                        edit_place = st.text_input(
                            "배출장소",
                            value=item.get("place_name") or ""
                        )

                        edit_category = st.selectbox(
                            "민원 유형",
                            CATEGORIES,
                            index=(
                                CATEGORIES.index(item["category"])
                                if item["category"] in CATEGORIES else 0
                            )
                        )

                        edit_priority = st.selectbox(
                            "우선순위",
                            PRIORITIES,
                            index=(
                                PRIORITIES.index(item["priority"])
                                if item["priority"] in PRIORITIES else 2
                            )
                        )

                    with c2:
                        edit_detail = st.text_input(
                            "상세 주소 또는 위치 설명",
                            value=item.get("detail_address") or ""
                        )

                        edit_channel = st.selectbox(
                            "접수 경로",
                            CHANNELS,
                            index=(
                                CHANNELS.index(item["channel"])
                                if item["channel"] in CHANNELS else 2
                            )
                        )

                        edit_status = st.selectbox(
                            "처리 상태",
                            STATUSES,
                            index=(
                                STATUSES.index(item["status"])
                                if item["status"] in STATUSES else 0
                            )
                        )

                        existing_completed = item.get("completed_at") or ""
                        if existing_completed:
                            try:
                                existing_completed = datetime.strptime(
                                    existing_completed,
                                    "%Y-%m-%d %H:%M:%S"
                                ).strftime("%Y-%m-%d %H:%M")
                            except Exception:
                                existing_completed = str(existing_completed)[:16]

                        edit_completed_at = st.text_input(
                            "완료 일시 (선택)",
                            value=existing_completed,
                            placeholder="YYYY-MM-DD HH:MM",
                            help=(
                                "완료 상태로 변경할 때 비워두면 현재 시각이 자동 저장됩니다. "
                                "직접 입력하면 해당 시각으로 저장됩니다."
                            )
                        )

                    edit_original = st.text_area(
                        "민원 상세 내용",
                        value=item.get("original_text") or "",
                        height=130
                    )

                    edit_summary = st.text_area(
                        "핵심 요약",
                        value=item.get("summary") or "",
                        height=80
                    )

                    edit_direction = st.text_area(
                        "현장 조치 방향",
                        value=item.get("action_direction") or "",
                        height=80
                    )

                    save_edit = st.form_submit_button(
                        "수정 내용 저장",
                        use_container_width=True
                    )

                if save_edit:
                    if not edit_original.strip():
                        st.error("민원 상세 내용을 입력해 주세요.")
                    elif not edit_place.strip() and not edit_detail.strip():
                        st.error("배출장소 또는 상세 위치를 입력해 주세요.")
                    else:
                        if edit_summary.strip():
                            summary_to_save = edit_summary.strip()
                        else:
                            summary_to_save = summarize_text(edit_original)

                        keywords = extract_keywords(edit_original)

                        try:
                            update_complaint(
                                selected_id,
                                edit_dong,
                                edit_place,
                                edit_detail,
                                edit_category,
                                edit_priority,
                                summary_to_save,
                                edit_original,
                                edit_channel,
                                edit_status,
                                edit_direction,
                                keywords,
                                edit_completed_at
                            )
                            st.success("민원 정보가 수정되었습니다.")
                            st.rerun()

                        except ValueError as e:
                            st.error(str(e))

                st.divider()
                st.subheader("기사 전달용 메시지 초안")

                current_location = item.get("location") or ""
                current_message = make_action_message(
                    selected_id,
                    item.get("dong") or "",
                    current_location,
                    item.get("category") or "",
                    item.get("priority") or "",
                    item.get("summary") or "",
                    item.get("action_direction") or ""
                )

                st.code(current_message, language="text")

                if st.button(
                    "기사 전달 이력에 저장",
                    key=f"delivery_{selected_id}"
                ):
                    add_delivery_log(
                        selected_id,
                        current_message
                    )
                    st.success(
                        "전달 문안이 이력에 저장되었습니다. 실제 발송은 되지 않았습니다."
                    )
                    st.rerun()

                with st.expander("기사 전달 이력 조회"):
                    logs = get_delivery_logs()

                    if not logs.empty:
                        complaint_logs = logs[
                            logs["complaint_id"] == selected_id
                        ]

                        if complaint_logs.empty:
                            st.info("해당 민원의 전달 이력이 없습니다.")
                        else:
                            for _, log in complaint_logs.iterrows():
                                st.markdown(
                                    f"**저장 일시:** {log['created_at']}"
                                )
                                st.code(
                                    log["message"],
                                    language="text"
                                )
                    else:
                        st.info("저장된 전달 이력이 없습니다.")

        st.divider()

        st.subheader("민원 데이터 내보내기")

        export_df = filtered.copy()

        if not export_df.empty:
            export_df["received_at"] = (
                export_df["received_at"].astype(str)
            )
            export_df["completed_at"] = (
                export_df["completed_at"].astype(str)
            )

            csv = export_df.to_csv(
                index=False,
                encoding="utf-8-sig"
            )

            st.download_button(
                "조회 결과 CSV 다운로드",
                data=csv,
                file_name="생활폐기물_민원관리.csv",
                mime="text/csv",
                use_container_width=True
            )


# =========================================================
# 14. 통계 분석
# =========================================================

elif menu == "통계 분석":

    show_header(
        "통계 분석",
        "행정동, 민원 유형, 접수 경로, 우선순위 및 처리 현황을 분석합니다."
    )

    if df.empty:
        st.info("통계 분석을 위한 데이터가 없습니다.")

    else:
        valid_dates = df["received_at"].dropna()

        if not valid_dates.empty:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()
        else:
            min_date = date.today()
            max_date = date.today()

        col1, col2 = st.columns(2)

        with col1:
            start_date = st.date_input(
                "조회 시작일",
                value=min_date,
                key="stats_start"
            )

        with col2:
            end_date = st.date_input(
                "조회 종료일",
                value=max_date,
                key="stats_end"
            )

        if start_date > end_date:
            st.error("조회 시작일은 종료일보다 늦을 수 없습니다.")
            stats_df = pd.DataFrame()
        else:
            stats_df = apply_date_filter(
                df, start_date, end_date
            )

        if not stats_df.empty:
            st.caption(
                f"조회 기간: {start_date} ~ {end_date} "
                f"· 총 {len(stats_df)}건"
            )

            st.divider()

            # 보고서에 명시된 통계 항목
            st.subheader("행정동별 민원 현황")
            render_distribution(
                stats_df,
                "dong",
                "행정동별 민원 건수",
                DONGS
            )

            st.subheader("민원 유형별 현황")
            render_distribution(
                stats_df,
                "category",
                "민원 유형별 민원 건수",
                CATEGORIES
            )

            st.subheader("접수 경로별 현황")
            render_distribution(
                stats_df,
                "channel",
                "접수 경로별 민원 건수",
                CHANNELS
            )

            st.subheader("우선순위별 현황")
            render_distribution(
                stats_df,
                "priority",
                "우선순위별 민원 건수",
                PRIORITIES
            )

            st.subheader("처리 상태별 현황")
            render_distribution(
                stats_df,
                "status",
                "처리 상태별 민원 건수",
                STATUSES
            )

            st.divider()

            st.subheader("날짜별 민원 접수 추이")

            trend = (
                stats_df.dropna(subset=["received_at"])
                .assign(
                    날짜=lambda x: x["received_at"].dt.date
                )
                .groupby("날짜")
                .size()
                .reset_index(name="민원 건수")
            )

            if not trend.empty:
                trend["날짜"] = pd.to_datetime(trend["날짜"])
                make_trend_chart(trend)

            st.divider()

            st.subheader("처리 소요 시간 분석")

            completed_df = stats_df[
                (stats_df["status"] == "완료")
                & stats_df["received_at"].notna()
                & stats_df["completed_at"].notna()
            ].copy()

            if not completed_df.empty:
                completed_df["처리 소요 시간(시간)"] = (
                    completed_df["completed_at"]
                    - completed_df["received_at"]
                ).dt.total_seconds() / 3600

                completed_df = completed_df[
                    completed_df["처리 소요 시간(시간)"] >= 0
                ]

                if not completed_df.empty:
                    avg = completed_df[
                        "처리 소요 시간(시간)"
                    ].mean()

                    median = completed_df[
                        "처리 소요 시간(시간)"
                    ].median()

                    a, b, c = st.columns(3)

                    a.metric(
                        "완료 건수",
                        f"{len(completed_df)}건"
                    )

                    b.metric(
                        "평균 처리 시간",
                        f"{avg:.1f}시간"
                    )

                    c.metric(
                        "중앙 처리 시간",
                        f"{median:.1f}시간"
                    )

                    duration_by_category = (
                        completed_df.groupby("category")[
                            "처리 소요 시간(시간)"
                        ].mean()
                        .reset_index()
                    )

                    make_horizontal_bar(
                        duration_by_category,
                        x="처리 소요 시간(시간)",
                        y="category",
                        title="민원 유형별 평균 처리 시간",
                        color="#4F81BD"
                    )
                else:
                    st.info("유효한 처리 소요 시간 데이터가 없습니다.")
            else:
                st.info(
                    "선택한 기간에 완료 시각이 기록된 민원이 없습니다. "
                    "완료 시각이 저장되면 처리 소요 시간이 자동 집계됩니다."
                )

            st.divider()

            st.subheader("보고서 기준 데이터와 비교")

            baseline_total = 27
            baseline_yonghyeon = 20
            baseline_sungui = 7
            baseline_channel = 17
            baseline_recycle = 9
            baseline_food = 6

            current_total = len(stats_df)

            if current_total > 0:
                current_yong = int(
                    (stats_df["dong"] == "용현동").sum()
                )
                current_sung = int(
                    (stats_df["dong"] == "숭의동").sum()
                )

                current_local = int(
                    (stats_df["channel"] == "지자체 경유").sum()
                )

                current_recycle = int(
                    (stats_df["category"] == "재활용품 미수거").sum()
                )

                current_food = int(
                    (stats_df["category"] == "음식물류 미수거").sum()
                )

                current_yong_pct = current_yong / current_total * 100
                current_local_pct = current_local / current_total * 100
                current_major_pct = (
                    current_recycle + current_food
                ) / current_total * 100

                st.markdown("**보고서 기준 (2026년 10월, 27건)**")

                base1, base2, base3 = st.columns(3)
                base1.metric("용현동", "74.1%")
                base2.metric("지자체 경유", "63.0%")
                base3.metric("재활용·음식물", "55.5%")

                st.markdown("**현재 조회 기간 데이터**")

                now1, now2, now3 = st.columns(3)

                now1.metric(
                    "용현동 비중",
                    f"{current_yong_pct:.1f}%",
                    f"{current_yong - baseline_yonghyeon:+d}건 vs 기준 건수"
                )

                now2.metric(
                    "지자체 경유 비중",
                    f"{current_local_pct:.1f}%",
                    f"{current_local - baseline_channel:+d}건 vs 기준 건수"
                )

                now3.metric(
                    "재활용·음식물 비중",
                    f"{current_major_pct:.1f}%",
                    f"{current_recycle + current_food - (baseline_recycle + baseline_food):+d}건 vs 기준 건수"
                )

                st.caption(
                    "참고: 보고서의 55.5%는 원문 표기값입니다. "
                    "9건과 6건을 합산한 15건을 27건으로 나누면 "
                    "계산상 약 55.6%입니다. 현재 조회 기간과 기준 기간의 "
                    "민원 건수가 다를 수 있으므로 비중을 중심으로 비교해 주세요."
                )

            st.divider()

            st.subheader("통계 데이터 다운로드")

            stats_export = stats_df.copy()
            stats_export["received_at"] = (
                stats_export["received_at"].astype(str)
            )
            stats_export["completed_at"] = (
                stats_export["completed_at"].astype(str)
            )

            st.download_button(
                "통계 분석 데이터 CSV 다운로드",
                data=stats_export.to_csv(
                    index=False,
                    encoding="utf-8-sig"
                ),
                file_name="생활폐기물_통계분석.csv",
                mime="text/csv",
                use_container_width=True
            )

        else:
            st.warning("선택한 기간에 해당하는 민원이 없습니다.")


# =========================================================
# 15. 하단 안내
# =========================================================

st.divider()

st.caption(
    "생활폐기물 민원 분석 시스템 | ㈜천산환경 | "
    "규칙 기반 자동 분석 및 통계 시각화 시연 프로그램"
)


