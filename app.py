
import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime, timedelta
import plotly.express as px

# =====================================================
# 기본 설정
# =====================================================

st.set_page_config(
    page_title="생활폐기물 민원 분석 시스템",
    page_icon="♻️",
    layout="wide"
)

DB_PATH = "complaints.db"

CATEGORIES = [
    "재활용품 미수거",
    "음식물류 미수거",
    "일반폐기물 미수거",
    "중간집하지 악취",
    "기타 민원"
]

DONGS = ["용현동", "숭의동"]
CHANNELS = ["지자체 경유", "전화", "기타"]
STATUSES = ["접수", "확인 중", "처리 중", "처리 완료"]


# =====================================================
# 데이터베이스
# =====================================================

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_date TEXT,
            dong TEXT,
            location TEXT,
            category TEXT,
            channel TEXT,
            content TEXT,
            priority TEXT,
            summary TEXT,
            driver_message TEXT,
            status TEXT DEFAULT '접수'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dispatch_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER,
            message TEXT,
            dispatched_at TEXT
        )
    """)

    # 이전 버전 데이터 정리
    # 대형폐기물 민원은 기타 민원으로 변경
    cur.execute("""
        UPDATE complaints
        SET category = '기타 민원'
        WHERE category = '대형폐기물 수거 지연'
    """)

    # 문자 접수는 운영하지 않으므로 기타 경로로 변경
    cur.execute("""
        UPDATE complaints
        SET channel = '기타'
        WHERE channel = '문자'
    """)

    conn.commit()
    conn.close()


# =====================================================
# 규칙 기반 민원 분석 엔진
# =====================================================

def analyze_complaint(content, category, dong, location):
    text = str(content).strip()

    high_words = [
        "긴급", "위험", "악취 심각", "넘쳐",
        "방치", "도로", "통행 불편", "반복"
    ]

    medium_words = [
        "미수거", "수거 지연", "냄새",
        "쌓여", "불편", "청소"
    ]

    if any(word in text for word in high_words):
        priority = "HIGH"
    elif any(word in text for word in medium_words):
        priority = "MEDIUM"
    else:
        priority = "LOW"

    summary = (
        f"{dong} {location} 지역에서 "
        f"{category} 관련 민원 발생. "
        f"주요 내용: {text[:100]}"
    )

    driver_message = (
        f"[생활폐기물 수거 민원 전달]\n"
        f"행정동: {dong}\n"
        f"세부 위치: {location}\n"
        f"민원 유형: {category}\n"
        f"우선순위: {priority}\n"
        f"조치 요청: {text}"
    )

    return priority, summary, driver_message


# =====================================================
# 시연 데이터 생성
# =====================================================

def create_demo_data():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM complaints")
    count = cur.fetchone()[0]

    if count > 0:
        conn.close()
        return

    # 대형폐기물 항목을 제외한 27건의 시연 데이터
    demo_categories = (
        ["재활용품 미수거"] * 9
        + ["음식물류 미수거"] * 6
        + ["중간집하지 악취"] * 3
        + ["일반폐기물 미수거"] * 3
        + ["기타 민원"] * 6
    )

    demo_dongs = ["용현동"] * 20 + ["숭의동"] * 7

    demo_contents = {
        "재활용품 미수거":
            "재활용품이 수거되지 않고 쌓여 있어 수거 요청합니다.",
        "음식물류 미수거":
            "음식물 쓰레기가 수거되지 않아 악취가 발생합니다.",
        "중간집하지 악취":
            "중간집하지 주변에서 심한 악취가 발생합니다.",
        "일반폐기물 미수거":
            "일반 생활폐기물이 수거되지 않았습니다.",
        "기타 민원":
            "생활폐기물 수거와 관련하여 확인을 요청합니다."
    }

    for i in range(27):
        category = demo_categories[i]
        dong = demo_dongs[i]
        location = f"{dong} 주민센터 인근"
        content = demo_contents[category]

        # 지자체 경유 17건, 전화 10건
        channel = "지자체 경유" if i < 17 else "전화"

        received_date = (
            date(2026, 10, 1) + timedelta(days=i)
        ).isoformat()

        priority, summary, message = analyze_complaint(
            content, category, dong, location
        )

        status = "처리 완료" if i < 15 else "접수"

        cur.execute("""
            INSERT INTO complaints (
                received_date, dong, location, category,
                channel, content, priority, summary,
                driver_message, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            received_date, dong, location, category,
            channel, content, priority, summary,
            message, status
        ))

    conn.commit()
    conn.close()


# =====================================================
# 데이터 조회
# =====================================================

def load_complaints():
    conn = get_connection()

    df = pd.read_sql_query(
        "SELECT * FROM complaints ORDER BY id DESC",
        conn
    )

    conn.close()
    return df


def get_complaint(complaint_id):
    conn = get_connection()

    df = pd.read_sql_query(
        "SELECT * FROM complaints WHERE id = ?",
        conn,
        params=(complaint_id,)
    )

    conn.close()

    if df.empty:
        return None

    return df.iloc[0]


# =====================================================
# 공통 그래프 스타일
# =====================================================

def style_horizontal_chart(fig, height=430, left_margin=170):
    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=15)
    )

    fig.update_layout(
        height=height,
        margin=dict(
            l=left_margin,
            r=90,
            t=65,
            b=55
        ),
        xaxis_title="민원 건수",
        yaxis_title="",
        showlegend=False,
        bargap=0.35,
        yaxis=dict(
            automargin=True,
            ticklabelposition="outside",
            tickfont=dict(
                size=16,
                color="#222222"
            ),
            categoryorder="total ascending"
        ),
        xaxis=dict(
            automargin=True,
            tickangle=0,
            rangemode="tozero",
            tickfont=dict(size=13)
        )
    )

    return fig


def style_vertical_chart(fig, height=380):
    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=14)
    )

    fig.update_layout(
        height=height,
        margin=dict(l=45, r=45, t=60, b=65),
        bargap=0.35,
        xaxis=dict(
            tickangle=0,
            automargin=True,
            tickfont=dict(size=13)
        ),
        yaxis=dict(
            rangemode="tozero",
            automargin=True
        ),
        showlegend=False
    )

    return fig


# =====================================================
# 대시보드
# =====================================================

def show_dashboard():
    st.title("♻️ 생활폐기물 민원 분석 대시보드")
    st.caption("AI 규칙 기반 민원 분류 및 통계 분석 시연 시스템")

    df = load_complaints()

    if df.empty:
        st.info("등록된 민원이 없습니다.")
        return

    total = len(df)
    completed = len(df[df["status"] == "처리 완료"])
    pending = total - completed
    high = len(df[df["priority"] == "HIGH"])

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("전체 민원", f"{total}건")
    col2.metric("처리 완료", f"{completed}건")
    col3.metric("미완료 민원", f"{pending}건")
    col4.metric("긴급 우선순위", f"{high}건")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("행정동별 민원 현황")

        dong_data = (
            df.groupby("dong")
            .size()
            .reset_index(name="민원 건수")
        )

        fig = px.bar(
            dong_data,
            x="dong",
            y="민원 건수",
            text="민원 건수",
            color="dong",
            title="행정동별 민원 건수"
        )

        fig = style_vertical_chart(fig)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("우선순위별 민원 현황")

        priority_data = (
            df.groupby("priority")
            .size()
            .reset_index(name="민원 건수")
        )

        priority_order = ["HIGH", "MEDIUM", "LOW"]

        priority_data["priority"] = pd.Categorical(
            priority_data["priority"],
            categories=priority_order,
            ordered=True
        )

        priority_data = priority_data.sort_values("priority")

        fig = px.bar(
            priority_data,
            x="priority",
            y="민원 건수",
            text="민원 건수",
            color="priority",
            title="민원 우선순위"
        )

        fig = style_vertical_chart(fig)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("최근 접수 민원")

    display_columns = [
        "id", "received_date", "dong",
        "category", "priority", "status"
    ]

    st.dataframe(
        df[display_columns].head(10),
        use_container_width=True,
        hide_index=True
    )


# =====================================================
# 민원 접수
# =====================================================

def show_complaint_input():
    st.title("📝 민원 접수 및 AI 분석")

    with st.form("complaint_form"):
        received_date = st.date_input(
            "접수 일자",
            value=date.today()
        )

        dong = st.selectbox("행정동", DONGS)

        location = st.text_input(
            "세부 위치",
            placeholder="예: 용현동 주민센터 앞"
        )

        category = st.selectbox("민원 유형", CATEGORIES)
        channel = st.selectbox("접수 경로", CHANNELS)

        content = st.text_area(
            "민원 내용",
            placeholder="민원 내용을 입력하세요."
        )

        submitted = st.form_submit_button(
            "민원 분석 및 등록",
            use_container_width=True
        )

    if submitted:
        if not location.strip() or not content.strip():
            st.warning("세부 위치와 민원 내용을 입력해주세요.")
            return

        priority, summary, message = analyze_complaint(
            content, category, dong, location
        )

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO complaints (
                received_date, dong, location,
                category, channel, content,
                priority, summary, driver_message, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            received_date.isoformat(),
            dong,
            location,
            category,
            channel,
            content,
            priority,
            summary,
            message,
            "접수"
        ))

        complaint_id = cur.lastrowid

        conn.commit()
        conn.close()

        st.success(f"민원 #{complaint_id} 등록이 완료되었습니다.")

        st.subheader("AI 규칙 기반 분석 결과")

        col1, col2 = st.columns(2)
        col1.metric("우선순위", priority)
        col2.metric("민원 유형", category)

        st.info(summary)

        st.subheader("현장 기사 전달 메시지 초안")
        st.code(message, language="text")


# =====================================================
# 민원 관리
# =====================================================

def show_complaint_management():
    st.title("📋 민원 관리")

    df = load_complaints()

    if df.empty:
        st.info("등록된 민원이 없습니다.")
        return

    search = st.text_input(
        "민원 검색",
        placeholder="행정동, 위치, 민원 내용 검색"
    )

    if search:
        mask = (
            df["dong"].astype(str).str.contains(
                search, case=False, na=False
            )
            | df["location"].astype(str).str.contains(
                search, case=False, na=False
            )
            | df["content"].astype(str).str.contains(
                search, case=False, na=False
            )
            | df["category"].astype(str).str.contains(
                search, case=False, na=False
            )
        )

        df = df[mask]

    st.dataframe(
        df[[
            "id", "received_date", "dong",
            "location", "category", "priority", "status"
        ]],
        use_container_width=True,
        hide_index=True
    )

    if df.empty:
        st.warning("검색 결과가 없습니다.")
        return

    selected_id = st.selectbox(
        "관리할 민원 선택",
        df["id"].tolist()
    )

    complaint = get_complaint(selected_id)

    if complaint is None:
        st.error("민원 정보를 찾을 수 없습니다.")
        return

    st.divider()
    st.subheader(f"민원 #{selected_id} 상세 관리")

    with st.form("edit_complaint_form"):
        edit_date = st.date_input(
            "접수 일자",
            value=date.fromisoformat(complaint["received_date"])
        )

        dong_index = (
            DONGS.index(complaint["dong"])
            if complaint["dong"] in DONGS else 0
        )

        edit_dong = st.selectbox(
            "행정동",
            DONGS,
            index=dong_index
        )

        edit_location = st.text_input(
            "세부 위치",
            value=complaint["location"]
        )

        category_index = (
            CATEGORIES.index(complaint["category"])
            if complaint["category"] in CATEGORIES else 0
        )

        edit_category = st.selectbox(
            "민원 유형",
            CATEGORIES,
            index=category_index
        )

        channel_index = (
            CHANNELS.index(complaint["channel"])
            if complaint["channel"] in CHANNELS else 0
        )

        edit_channel = st.selectbox(
            "접수 경로",
            CHANNELS,
            index=channel_index
        )

        status_index = (
            STATUSES.index(complaint["status"])
            if complaint["status"] in STATUSES else 0
        )

        edit_status = st.selectbox(
            "처리 상태",
            STATUSES,
            index=status_index
        )

        edit_content = st.text_area(
            "민원 내용",
            value=complaint["content"]
        )

        save = st.form_submit_button(
            "수정 내용 저장",
            use_container_width=True
        )

    if save:
        if not edit_location.strip() or not edit_content.strip():
            st.warning("위치와 민원 내용을 입력해주세요.")
        else:
            priority, summary, message = analyze_complaint(
                edit_content,
                edit_category,
                edit_dong,
                edit_location
            )

            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                UPDATE complaints
                SET received_date = ?,
                    dong = ?,
                    location = ?,
                    category = ?,
                    channel = ?,
                    content = ?,
                    priority = ?,
                    summary = ?,
                    driver_message = ?,
                    status = ?
                WHERE id = ?
            """, (
                edit_date.isoformat(),
                edit_dong,
                edit_location,
                edit_category,
                edit_channel,
                edit_content,
                priority,
                summary,
                message,
                edit_status,
                selected_id
            ))

            conn.commit()
            conn.close()

            st.success("민원 정보가 수정되었습니다.")
            st.rerun()

    st.divider()
    st.subheader("기사 전달 메시지")

    st.code(complaint["driver_message"], language="text")

    if st.button("기사 전달 이력 저장", key="dispatch"):
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO dispatch_logs (
                complaint_id, message, dispatched_at
            )
            VALUES (?, ?, ?)
        """, (
            selected_id,
            complaint["driver_message"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

        st.success("기사 전달 메시지 이력이 저장되었습니다.")
        st.caption(
            "실제 문자 또는 모바일 자동 발송 기능은 구현되어 있지 않습니다."
        )

    st.divider()
    st.subheader("민원 삭제")

    confirm_delete = st.checkbox(
        f"민원 #{selected_id}을 삭제하는 것에 동의합니다."
    )

    if st.button(
        "선택 민원 삭제",
        disabled=not confirm_delete,
        type="secondary"
    ):
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "DELETE FROM dispatch_logs WHERE complaint_id = ?",
            (selected_id,)
        )

        cur.execute(
            "DELETE FROM complaints WHERE id = ?",
            (selected_id,)
        )

        conn.commit()
        conn.close()

        st.success("민원이 삭제되었습니다.")
        st.rerun()


# =====================================================
# 통계 분석
# =====================================================

def show_statistics():
    st.title("📊 민원 통계 분석")

    df = load_complaints()

    if df.empty:
        st.info("분석할 데이터가 없습니다.")
        return

    total = len(df)
    st.metric("전체 민원 건수", f"{total}건")

    st.divider()

    # 1. 행정동별 분석
    st.subheader("1. 행정동별 민원 현황")

    dong_data = (
        df.groupby("dong")
        .size()
        .reset_index(name="민원 건수")
        .sort_values("민원 건수", ascending=True)
    )

    fig = px.bar(
        dong_data,
        x="민원 건수",
        y="dong",
        orientation="h",
        text="민원 건수",
        color="dong",
        title="행정동별 민원 건수"
    )

    fig = style_horizontal_chart(
        fig,
        height=350,
        left_margin=170
    )

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        dong_data.sort_values(
            "민원 건수", ascending=False
        ),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # 2. 민원 유형별 분석
    st.subheader("2. 민원 유형별 현황")

    category_data = (
        df.groupby("category")
        .size()
        .reset_index(name="민원 건수")
        .sort_values("민원 건수", ascending=True)
    )

    fig = px.bar(
        category_data,
        x="민원 건수",
        y="category",
        orientation="h",
        text="민원 건수",
        color="category",
        title="민원 유형별 건수"
    )

    fig = style_horizontal_chart(
        fig,
        height=520,
        left_margin=200
    )

    # 유형별 그래프 제목과 글자 가독성 추가 개선
    fig.update_layout(
        title=dict(
            text="민원 유형별 건수",
            x=0.5,
            xanchor="center",
            font=dict(size=20)
        ),
        yaxis=dict(
            tickfont=dict(
                size=17,
                color="#111111"
            ),
            automargin=True,
            ticklabelposition="outside"
        ),
        xaxis=dict(
            title="민원 건수",
            tickfont=dict(size=14),
            rangemode="tozero"
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        category_data.sort_values(
            "민원 건수", ascending=False
        ),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # 3. 접수 경로별 분석
    st.subheader("3. 접수 경로별 현황")

    channel_data = (
        df.groupby("channel")
        .size()
        .reset_index(name="민원 건수")
        .sort_values("민원 건수", ascending=False)
    )

    fig = px.bar(
        channel_data,
        x="channel",
        y="민원 건수",
        text="민원 건수",
        color="channel",
        title="접수 경로별 민원 건수"
    )

    fig = style_vertical_chart(fig, height=350)

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        channel_data,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # 4. 우선순위별 분석
    st.subheader("4. 우선순위별 현황")

    priority_data = (
        df.groupby("priority")
        .size()
        .reset_index(name="민원 건수")
    )

    priority_order = ["HIGH", "MEDIUM", "LOW"]

    priority_data["priority"] = pd.Categorical(
        priority_data["priority"],
        categories=priority_order,
        ordered=True
    )

    priority_data = priority_data.sort_values("priority")

    fig = px.bar(
        priority_data,
        x="priority",
        y="민원 건수",
        text="민원 건수",
        color="priority",
        title="우선순위별 민원 건수"
    )

    fig = style_vertical_chart(fig, height=350)

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # 5. CSV 다운로드
    st.subheader("5. 민원 데이터 다운로드")

    csv = df.to_csv(
        index=False,
        encoding="utf-8-sig"
    )

    st.download_button(
        label="민원 데이터 CSV 다운로드",
        data=csv,
        file_name="생활폐기물_민원_분석.csv",
        mime="text/csv",
        use_container_width=True
    )


# =====================================================
# 시연 데이터 초기화
# =====================================================

def reset_demo_data():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM dispatch_logs")
    cur.execute("DELETE FROM complaints")

    conn.commit()
    conn.close()

    create_demo_data()


# =====================================================
# 프로그램 실행
# =====================================================

init_db()
create_demo_data()

st.sidebar.title("♻️ 메뉴")

menu = st.sidebar.radio(
    "기능 선택",
    [
        "대시보드",
        "민원 접수 및 AI 분석",
        "민원 관리",
        "통계 분석"
    ]
)

st.sidebar.divider()

st.sidebar.caption("생활폐기물 민원 분석 시연 시스템")

if st.sidebar.button(
    "시연 데이터 초기화",
    use_container_width=True
):
    reset_demo_data()
    st.sidebar.success("시연 데이터가 초기화되었습니다.")
    st.rerun()

st.sidebar.divider()

st.sidebar.caption(
    "※ 본 프로그램은 규칙 기반 분석 시연용입니다.\n\n"
    "※ 실제 STT 음성 인식 및 기사 자동 문자 발송은 구현되어 있지 않습니다.\n\n"
    "※ 시연 데이터는 보고서 집계 수치에 맞춘 가상 데이터입니다."
)

if menu == "대시보드":
    show_dashboard()

elif menu == "민원 접수 및 AI 분석":
    show_complaint_input()

elif menu == "민원 관리":
    show_complaint_management()

elif menu == "통계 분석":
    show_statistics()
