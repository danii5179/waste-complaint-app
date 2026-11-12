
import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import date, datetime, timedelta
from contextlib import contextmanager

# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="천산환경 생활폐기물 민원 분석 시스템",
    page_icon="♻️",
    layout="wide"
)

DB_PATH = "complaints.db"

CATEGORIES = [
    "재활용품 미수거",
    "음식물류 미수거",
    "일반쓰레기 미수거",
    "중간집하지 악취",
    "수거 지연",
    "기타"
]

DONGS = ["용현동", "숭의동"]
CHANNELS = ["지자체 경유", "전화", "기타"]
PRIORITIES = ["HIGH", "MEDIUM", "LOW"]
STATUSES = ["접수", "처리중", "처리완료"]


# =========================================================
# 2. 데이터베이스 연결 및 초기화
# =========================================================

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_date TEXT NOT NULL,
                dong TEXT NOT NULL,
                location TEXT,
                category TEXT NOT NULL,
                content TEXT,
                channel TEXT,
                priority TEXT,
                status TEXT DEFAULT '접수',
                summary TEXT,
                driver_message TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS dispatch_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id INTEGER,
                message TEXT,
                created_at TEXT,
                FOREIGN KEY (complaint_id)
                REFERENCES complaints(id)
            )
        """)


def get_complaints():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM complaints
            ORDER BY complaint_date DESC, id DESC
        """).fetchall()

    return pd.DataFrame([dict(row) for row in rows])


def get_complaint(complaint_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM complaints WHERE id = ?",
            (int(complaint_id),)
        ).fetchone()

    return dict(row) if row else None


# =========================================================
# 3. AI 규칙 기반 민원 분석
# =========================================================

def analyze_complaint(content, category, dong, location):
    """
    외부 AI API를 사용하지 않는 규칙 기반 시연 분석 엔진
    """

    text = str(content).lower()

    high_keywords = [
        "악취", "심각", "긴급", "위험",
        "쌓여", "넘쳐", "반복", "장기간"
    ]

    medium_keywords = [
        "미수거", "수거하지", "방치",
        "늦게", "지연", "냄새"
    ]

    if any(keyword in text for keyword in high_keywords):
        priority = "HIGH"
    elif any(keyword in text for keyword in medium_keywords):
        priority = "MEDIUM"
    else:
        priority = "LOW"

    if category == "중간집하지 악취":
        priority = "HIGH"

    summary = (
        f"{dong} {location}에서 발생한 "
        f"{category} 관련 민원입니다. "
        f"주요 내용: {content[:100]}"
    )

    driver_message = (
        f"[수거 민원 전달]\n"
        f"행정동: {dong}\n"
        f"위치: {location}\n"
        f"민원 유형: {category}\n"
        f"우선순위: {priority}\n"
        f"내용: {content}\n"
        f"현장 확인 및 조치 부탁드립니다."
    )

    return priority, summary, driver_message


# =========================================================
# 4. 민원 등록 / 수정 / 삭제 / 상태 변경
# =========================================================

def add_complaint(data):
    priority, summary, message = analyze_complaint(
        data["content"],
        data["category"],
        data["dong"],
        data["location"]
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO complaints (
                complaint_date, dong, location,
                category, content, channel,
                priority, status, summary,
                driver_message, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["complaint_date"],
            data["dong"],
            data["location"],
            data["category"],
            data["content"],
            data["channel"],
            priority,
            "접수",
            summary,
            message,
            now,
            now
        ))


def update_complaint(complaint_id, data):
    """
    기존 민원 정보를 수정하고 분석 결과도 다시 계산
    """

    priority, summary, message = analyze_complaint(
        data["content"],
        data["category"],
        data["dong"],
        data["location"]
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        conn.execute("""
            UPDATE complaints
            SET
                complaint_date = ?,
                dong = ?,
                location = ?,
                category = ?,
                content = ?,
                channel = ?,
                priority = ?,
                status = ?,
                summary = ?,
                driver_message = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            data["complaint_date"],
            data["dong"],
            data["location"],
            data["category"],
            data["content"],
            data["channel"],
            priority,
            data["status"],
            summary,
            message,
            now,
            int(complaint_id)
        ))


def delete_complaint(complaint_id):
    """
    선택한 민원 삭제
    관련 기사 전달 이력도 함께 삭제
    """

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM dispatch_logs WHERE complaint_id = ?",
            (int(complaint_id),)
        )

        conn.execute(
            "DELETE FROM complaints WHERE id = ?",
            (int(complaint_id),)
        )


def update_status(complaint_id, status):
    with get_connection() as conn:
        conn.execute("""
            UPDATE complaints
            SET status = ?, updated_at = ?
            WHERE id = ?
        """, (
            status,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            int(complaint_id)
        ))


# =========================================================
# 5. 기사 전달 이력
# =========================================================

def save_dispatch_log(complaint_id, message):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO dispatch_logs (
                complaint_id, message, created_at
            )
            VALUES (?, ?, ?)
        """, (
            int(complaint_id),
            message,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))


def get_dispatch_logs():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM dispatch_logs
            ORDER BY id DESC
        """).fetchall()

    return pd.DataFrame([dict(row) for row in rows])


# =========================================================
# 6. 시연용 가상 데이터 27건 생성
# =========================================================

def create_demo_data():
    """
    보고서의 주요 집계 수치를 재현하는 가상 데이터

    총 27건
    용현동 20건 / 숭의동 7건
    지자체 경유 17건
    재활용품 미수거 9건
    음식물류 미수거 6건
    중간집하지 악취 3건

    실제 민원 원본 데이터가 아닌 시연용 데이터입니다.
    """

    existing = get_complaints()

    if not existing.empty:
        return False

    category_data = (
        ["재활용품 미수거"] * 9
        + ["음식물류 미수거"] * 6
        + ["중간집하지 악취"] * 3
        + ["일반쓰레기 미수거"] * 3
        + ["수거 지연"] * 3
        + ["기타"] * 3
    )

    dong_data = ["용현동"] * 20 + ["숭의동"] * 7

    channel_data = (
        ["지자체 경유"] * 17
        + ["전화"] * 6
        + ["기타"] * 4
    )

    locations = [
        "주택가 인근",
        "아파트 정문",
        "골목길 입구",
        "상가 주변",
        "도로변 수거 장소",
        "중간집하지 주변"
    ]

    contents = {
        "재활용품 미수거": "재활용품이 수거되지 않고 현장에 남아 있습니다.",
        "음식물류 미수거": "음식물 쓰레기가 수거되지 않아 불편이 발생하고 있습니다.",
        "중간집하지 악취": "중간집하지 주변에서 심한 악취가 발생하고 있습니다.",
        "일반쓰레기 미수거": "일반 생활폐기물이 수거되지 않았습니다.",
        "수거 지연": "예정된 수거 시간보다 수거가 지연되고 있습니다.",
        "기타": "생활폐기물 수거 관련 확인이 필요합니다."
    }

    base_date = date(2026, 10, 1)

    for i in range(27):
        category = category_data[i]
        dong = dong_data[i]
        channel = channel_data[i]
        location = locations[i % len(locations)]

        complaint_date = (
            base_date + timedelta(days=i)
        ).isoformat()

        add_complaint({
            "complaint_date": complaint_date,
            "dong": dong,
            "location": location,
            "category": category,
            "content": contents[category],
            "channel": channel
        })

    return True


# =========================================================
# 7. 공통 화면 스타일
# =========================================================

st.markdown("""
<style>
    .main-title {
        font-size: 28px;
        font-weight: 800;
        color: #173B2D;
    }

    .sub-title {
        font-size: 15px;
        color: #64748b;
        margin-bottom: 20px;
    }

    div[data-testid="stMetric"] {
        background: #F4F8F5;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #E2EBE4;
    }

    .stButton button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# 8. 공통 헤더
# =========================================================

def page_header(title, description):
    st.markdown(
        f'<div class="main-title">{title}</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="sub-title">{description}</div>',
        unsafe_allow_html=True
    )


# =========================================================
# 9. 대시보드
# =========================================================

def show_dashboard():
    page_header(
        "📊 민원 분석 대시보드",
        "동별·유형별 생활폐기물 민원 현황을 한눈에 확인합니다."
    )

    df = get_complaints()

    if df.empty:
        st.info("등록된 민원이 없습니다. 시연 데이터를 생성해주세요.")

        if st.button("시연 데이터 27건 생성", type="primary"):
            create_demo_data()
            st.success("시연 데이터가 생성되었습니다.")
            st.rerun()

        return

    total = len(df)
    high = len(df[df["priority"] == "HIGH"])
    processing = len(df[df["status"] == "처리중"])
    completed = len(df[df["status"] == "처리완료"])

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("전체 민원", f"{total}건")
    c2.metric("긴급 민원", f"{high}건")
    c3.metric("처리중", f"{processing}건")
    c4.metric("처리완료", f"{completed}건")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("행정동별 민원 현황")
        dong_counts = df["dong"].value_counts()
        st.bar_chart(dong_counts)

    with right:
        st.subheader("민원 유형별 현황")
        category_counts = df["category"].value_counts()
        st.bar_chart(category_counts)

    st.divider()

    st.subheader("최근 접수 민원")

    recent = df.head(7)

    st.dataframe(
        recent[[
            "id", "complaint_date", "dong",
            "category", "priority", "status"
        ]],
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "※ 본 화면의 통계는 현재 데이터베이스에 저장된 민원을 기준으로 계산됩니다."
    )


# =========================================================
# 10. 민원 접수 및 분석
# =========================================================

def show_register():
    page_header(
        "📝 민원 접수 및 AI 분석",
        "민원 내용을 입력하면 규칙 기반 분석을 통해 우선순위와 기사 전달 문구를 생성합니다."
    )

    with st.form("complaint_register_form"):
        col1, col2 = st.columns(2)

        with col1:
            complaint_date = st.date_input(
                "접수 일자",
                value=date.today()
            )

            dong = st.selectbox(
                "행정동",
                DONGS
            )

            location = st.text_input(
                "세부 위치",
                placeholder="예: 용현동 OO아파트 정문"
            )

        with col2:
            category = st.selectbox(
                "민원 유형",
                CATEGORIES
            )

            channel = st.selectbox(
                "접수 경로",
                CHANNELS
            )

        content = st.text_area(
            "민원 내용",
            placeholder="민원 내용을 자세히 입력해주세요.",
            height=130
        )

        submitted = st.form_submit_button(
            "민원 등록 및 AI 분석",
            type="primary",
            use_container_width=True
        )

        if submitted:
            if not location.strip() or not content.strip():
                st.error("세부 위치와 민원 내용을 입력해주세요.")
            else:
                add_complaint({
                    "complaint_date": str(complaint_date),
                    "dong": dong,
                    "location": location.strip(),
                    "category": category,
                    "content": content.strip(),
                    "channel": channel
                })

                st.success("민원이 등록되고 분석되었습니다.")
                st.rerun()

    st.divider()

    st.subheader("🎙️ 음성 입력 안내")
    st.info(
        "현재 버전은 텍스트 입력 방식으로 동작합니다. "
        "음성인식(STT)은 별도 API 연동이 필요한 향후 개발 기능입니다."
    )


# =========================================================
# 11. 민원 관리 / 검색 / 수정 / 삭제
# =========================================================

def show_management():
    page_header(
        "📋 민원 관리",
        "접수된 민원을 검색하고 내용을 수정하거나 삭제할 수 있습니다."
    )

    df = get_complaints()

    if df.empty:
        st.info("관리할 민원이 없습니다.")
        return

    # 검색 및 필터
    col1, col2, col3 = st.columns(3)

    with col1:
        search_text = st.text_input(
            "민원 검색",
            placeholder="위치 또는 민원 내용 검색"
        )

    with col2:
        dong_filter = st.selectbox(
            "행정동 필터",
            ["전체"] + DONGS
        )

    with col3:
        status_filter = st.selectbox(
            "처리 상태 필터",
            ["전체"] + STATUSES
        )

    filtered = df.copy()

    if search_text:
        filtered = filtered[
            filtered["location"].astype(str).str.contains(
                search_text, case=False, na=False
            )
            |
            filtered["content"].astype(str).str.contains(
                search_text, case=False, na=False
            )
        ]

    if dong_filter != "전체":
        filtered = filtered[
            filtered["dong"] == dong_filter
        ]

    if status_filter != "전체":
        filtered = filtered[
            filtered["status"] == status_filter
        ]

    st.dataframe(
        filtered[[
            "id", "complaint_date", "dong",
            "location", "category", "priority", "status"
        ]],
        use_container_width=True,
        hide_index=True
    )

    st.caption(f"검색 결과: {len(filtered)}건")

    if filtered.empty:
        st.warning("검색 조건에 해당하는 민원이 없습니다.")
        return

    st.divider()

    st.subheader("민원 상세 및 수정")

    selected_id = st.selectbox(
        "수정할 민원 선택",
        filtered["id"].astype(int).tolist(),
        format_func=lambda x: (
            f"민원 #{x} | "
            f"{df.loc[df['id'] == x, 'dong'].iloc[0]} | "
            f"{df.loc[df['id'] == x, 'category'].iloc[0]}"
        )
    )

    selected = get_complaint(selected_id)

    if not selected:
        st.error("선택한 민원을 찾을 수 없습니다.")
        return

    st.markdown(
        f"**민원 번호:** #{selected['id']}  \n"
        f"**최초 등록일:** {selected['created_at']}"
    )

    st.markdown("#### ✏️ 민원 정보 수정")

    with st.form("edit_complaint_form"):
        col1, col2 = st.columns(2)

        with col1:
            edit_date = st.date_input(
                "접수 일자",
                value=pd.to_datetime(
                    selected["complaint_date"]
                ).date(),
                key=f"edit_date_{selected_id}"
            )

            edit_dong = st.selectbox(
                "행정동",
                DONGS,
                index=(
                    DONGS.index(selected["dong"])
                    if selected["dong"] in DONGS else 0
                ),
                key=f"edit_dong_{selected_id}"
            )

            edit_location = st.text_input(
                "세부 위치",
                value=selected["location"] or "",
                key=f"edit_location_{selected_id}"
            )

            edit_channel = st.selectbox(
                "접수 경로",
                CHANNELS,
                index=(
                    CHANNELS.index(selected["channel"])
                    if selected["channel"] in CHANNELS else 0
                ),
                key=f"edit_channel_{selected_id}"
            )

        with col2:
            edit_category = st.selectbox(
                "민원 유형",
                CATEGORIES,
                index=(
                    CATEGORIES.index(selected["category"])
                    if selected["category"] in CATEGORIES else 0
                ),
                key=f"edit_category_{selected_id}"
            )

            edit_priority_display = st.info(
                f"저장 시 민원 내용을 기준으로 우선순위가 다시 분석됩니다. "
                f"현재 우선순위: {selected['priority']}"
            )

            edit_status = st.selectbox(
                "처리 상태",
                STATUSES,
                index=(
                    STATUSES.index(selected["status"])
                    if selected["status"] in STATUSES else 0
                ),
                key=f"edit_status_{selected_id}"
            )

        edit_content = st.text_area(
            "민원 내용",
            value=selected["content"] or "",
            height=120,
            key=f"edit_content_{selected_id}"
        )

        save_edit = st.form_submit_button(
            "수정 내용 저장",
            type="primary",
            use_container_width=True
        )

        if save_edit:
            if not edit_location.strip() or not edit_content.strip():
                st.error("세부 위치와 민원 내용을 입력해주세요.")
            else:
                update_complaint(
                    selected_id,
                    {
                        "complaint_date": str(edit_date),
                        "dong": edit_dong,
                        "location": edit_location.strip(),
                        "category": edit_category,
                        "content": edit_content.strip(),
                        "channel": edit_channel,
                        "status": edit_status
                    }
                )

                st.success("민원 정보가 수정되었습니다.")
                st.rerun()

    # 삭제 기능
    st.divider()
    st.subheader("🗑️ 민원 삭제")

    st.warning(
        "삭제한 민원은 복구할 수 없습니다. "
        "정말 잘못 등록된 민원인지 확인해주세요."
    )

    confirm_delete = st.checkbox(
        f"민원 #{selected_id} 삭제에 동의합니다.",
        key=f"delete_checkbox_{selected_id}"
    )

    if st.button(
        "선택한 민원 삭제",
        type="primary",
        disabled=not confirm_delete,
        key=f"delete_button_{selected_id}"
    ):
        st.session_state["delete_target"] = int(selected_id)
        st.rerun()

    # 최종 삭제 확인
    if "delete_target" in st.session_state:
        target_id = st.session_state["delete_target"]
        target = get_complaint(target_id)

        if target is None:
            del st.session_state["delete_target"]
            st.warning("삭제 대상 민원이 이미 존재하지 않습니다.")
            st.rerun()

        st.error(
            f"정말 민원 #{target_id} 데이터를 삭제하시겠습니까? "
            "이 작업은 되돌릴 수 없습니다."
        )

        confirm_col, cancel_col = st.columns(2)

        with confirm_col:
            if st.button(
                "네, 삭제합니다",
                type="primary",
                key="confirm_final_delete"
            ):
                delete_complaint(target_id)
                del st.session_state["delete_target"]

                st.success("민원이 삭제되었습니다.")
                st.rerun()

        with cancel_col:
            if st.button(
                "취소",
                key="cancel_final_delete"
            ):
                del st.session_state["delete_target"]
                st.rerun()


# =========================================================
# 12. 기사 전달
# =========================================================

def show_dispatch():
    page_header(
        "🚛 수거 기사 전달",
        "민원 내용을 기사 전달용 메시지로 정리하고 전달 이력을 기록합니다."
    )

    df = get_complaints()

    if df.empty:
        st.info("등록된 민원이 없습니다.")
        return

    selected_id = st.selectbox(
        "전달할 민원 선택",
        df["id"].astype(int).tolist(),
        format_func=lambda x: (
            f"민원 #{x} | "
            f"{df.loc[df['id'] == x, 'dong'].iloc[0]} | "
            f"{df.loc[df['id'] == x, 'category'].iloc[0]}"
        )
    )

    selected = get_complaint(selected_id)

    if not selected:
        st.error("민원 정보를 불러올 수 없습니다.")
        return

    st.subheader("기사 전달 메시지")

    message = selected["driver_message"] or (
        f"[수거 민원 전달]\n"
        f"행정동: {selected['dong']}\n"
        f"위치: {selected['location']}\n"
        f"유형: {selected['category']}\n"
        f"내용: {selected['content']}"
    )

    st.text_area(
        "전달 메시지",
        value=message,
        height=220,
        key=f"dispatch_message_{selected_id}"
    )

    if st.button(
        "전달 이력 저장",
        type="primary",
        use_container_width=True
    ):
        save_dispatch_log(selected_id, message)
        st.success("기사 전달 메시지 이력이 저장되었습니다.")

    st.caption(
        "※ 현재 기능은 메시지 생성 및 전달 이력 저장용 시연 기능입니다. "
        "실제 기사 휴대전화 문자 발송은 구현되어 있지 않습니다."
    )

    st.divider()

    st.subheader("전달 이력")

    logs = get_dispatch_logs()

    if logs.empty:
        st.info("저장된 전달 이력이 없습니다.")
    else:
        st.dataframe(
            logs,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 13. 통계 및 CSV 다운로드
# =========================================================

def show_statistics():
    page_header(
        "📈 민원 통계 분석",
        "행정동, 민원 유형, 접수 경로 및 우선순위별 통계를 확인합니다."
    )

    df = get_complaints()

    if df.empty:
        st.info("통계 데이터가 없습니다.")
        return

    total = len(df)

    st.metric("전체 민원 건수", f"{total}건")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("행정동별 민원")

        dong_stats = (
            df["dong"]
            .value_counts()
            .rename_axis("행정동")
            .reset_index(name="민원 건수")
        )

        st.dataframe(
            dong_stats,
            use_container_width=True,
            hide_index=True
        )

        st.bar_chart(
            dong_stats.set_index("행정동")
        )

    with col2:
        st.subheader("민원 유형별 민원")

        category_stats = (
            df["category"]
            .value_counts()
            .rename_axis("민원 유형")
            .reset_index(name="민원 건수")
        )

        st.dataframe(
            category_stats,
            use_container_width=True,
            hide_index=True
        )

        st.bar_chart(
            category_stats.set_index("민원 유형")
        )

    st.divider()

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("접수 경로별 현황")
        st.bar_chart(df["channel"].value_counts())

    with col4:
        st.subheader("우선순위별 현황")
        st.bar_chart(df["priority"].value_counts())

    st.divider()

    st.subheader("처리 상태별 현황")
    st.bar_chart(df["status"].value_counts())

    st.divider()

    st.subheader("📥 민원 데이터 다운로드")

    csv = df.to_csv(
        index=False,
        encoding="utf-8-sig"
    )

    st.download_button(
        label="민원 데이터 CSV 다운로드",
        data=csv,
        file_name="cheon_san_complaints.csv",
        mime="text/csv",
        use_container_width=True
    )


# =========================================================
# 14. 앱 실행
# =========================================================

init_db()

# 최초 실행 시 데이터가 없으면 시연용 데이터 자동 생성
if get_complaints().empty:
    create_demo_data()


st.sidebar.title("♻️ 천산환경")
st.sidebar.caption("생활폐기물 민원 분석 시스템")

menu = st.sidebar.radio(
    "메뉴",
    [
        "대시보드",
        "민원 접수 및 AI 분석",
        "민원 관리",
        "수거 기사 전달",
        "통계 분석"
    ]
)

st.sidebar.divider()

st.sidebar.caption(
    "AI 기반 동별·유형별 생활폐기물 민원 분석 및 해결 지원"
)

if st.sidebar.button("시연 데이터 초기화"):
    with get_connection() as conn:
        conn.execute("DELETE FROM dispatch_logs")
        conn.execute("DELETE FROM complaints")
        conn.execute(
            "DELETE FROM sqlite_sequence WHERE name = 'complaints'"
        )

    create_demo_data()
    st.sidebar.success("시연 데이터가 초기화되었습니다.")
    st.rerun()


if menu == "대시보드":
    show_dashboard()

elif menu == "민원 접수 및 AI 분석":
    show_register()

elif menu == "민원 관리":
    show_management()

elif menu == "수거 기사 전달":
    show_dispatch()

elif menu == "통계 분석":
    show_statistics()


st.divider()

st.caption(
    "㈜천산환경 | 생활폐기물 민원 분석 시연 시스템 | "
    "Python · Streamlit · SQLite"
)
