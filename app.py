import os
import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "complaints.db"

CATEGORIES = [
    "재활용품 미수거",
    "음식물류 미수거",
    "수거시간 및 배출방법",
    "생활폐기물 미수거",
    "중간집하지 및 악취",
    "기타",
]
PRIORITIES = ["HIGH", "MEDIUM", "LOW"]


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source_type TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                dong TEXT,
                address_detail TEXT,
                category TEXT,
                ai_summary TEXT,
                priority TEXT,
                notification_text TEXT,
                status TEXT NOT NULL DEFAULT '접수'
            )
        """)


def heuristic_parse(raw_text: str) -> dict:
    """API 키 없이도 텍스트 흐름을 시연하기 위한 규칙 기반 임시 분류기."""
    text = raw_text.strip()
    lower = text.lower()

    if any(k in text for k in ["악취", "냄새", "중간집하", "집하장"]):
        category = "중간집하지 및 악취"
    elif any(k in text for k in ["음식물", "음쓰"]):
        category = "음식물류 미수거"
    elif any(k in text for k in ["재활용", "캔", "페트병", "플라스틱", "종이"]):
        category = "재활용품 미수거"
    elif any(k in text for k in ["배출방법", "수거시간", "몇 시", "몇시", "배출 시간"]):
        category = "수거시간 및 배출방법"
    elif any(k in text for k in ["생활폐기물", "쓰레기", "종량제", "일반폐기물"]):
        category = "생활폐기물 미수거"
    else:
        category = "기타"

    dong = ""
    for candidate in ["용현동", "숭의동", "학익동", "주안동", "도화동", "관교동", "문학동"]:
        if candidate in text:
            dong = candidate
            break

    priority = "MEDIUM"
    if any(k in text for k in ["사고", "불", "화재", "위험", "도로 막힘", "긴급"]):
        priority = "HIGH"
    elif any(k in text for k in ["악취", "넘쳐", "며칠째", "계속", "민원 반복"]):
        priority = "HIGH"
    elif any(k in text for k in ["문의", "궁금", "방법", "언제"]):
        priority = "LOW"

    summary = text if len(text) <= 100 else text[:97] + "..."
    return {
        "dong": dong or "확인 필요",
        "address_detail": "원문에서 위치를 확인하세요",
        "category": category,
        "ai_summary": summary,
        "priority": priority,
        "analysis_mode": "규칙 기반 데모(외부 AI 미사용)",
    }


def analyze_with_openai(raw_text: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. 텍스트는 데모 모드로 분석할 수 있고, 실제 AI 분석에는 API 키가 필요합니다.")
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": (
                    "당신은 생활폐기물 민원 접수 보조 시스템이다. 민원 원문에서 확인되는 사실만 추출한다. "
                    "주소나 동 이름이 없으면 추측하지 말고 '확인 필요'라고 쓴다. "
                    "긴급도는 실제 위험 단서가 명확할 때만 HIGH로 지정한다. "
                    "개인정보를 불필요하게 반복하지 말고, 현장 담당자가 이해할 수 있게 간결하게 작성한다. "
                    "반드시 JSON 객체만 출력한다."
                ),
            },
            {
                "role": "user",
                "content": f"""
민원 원문:
{raw_text}

다음 키를 가진 JSON으로 답해줘.
- dong: 행정동, 모르면 "확인 필요"
- address_detail: 세부 주소/위치, 모르면 "확인 필요"
- category: 아래 중 하나만 선택: {", ".join(CATEGORIES)}
- ai_summary: 한 문장 요약
- priority: HIGH, MEDIUM, LOW 중 하나
""",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    data = json.loads(response.choices[0].message.content)
    if data.get("category") not in CATEGORIES:
        data["category"] = "기타"
    if data.get("priority") not in PRIORITIES:
        data["priority"] = "MEDIUM"
    for key in ["dong", "address_detail", "ai_summary"]:
        if not data.get(key):
            data[key] = "확인 필요"
    data["analysis_mode"] = "OpenAI API"
    return data


def transcribe_audio(uploaded_file) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("음성 변환에는 OPENAI_API_KEY가 필요합니다. .env 파일 설정 안내를 확인하세요.")
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    suffix = Path(uploaded_file.name).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(uploaded_file.getvalue())
        temp_path = temp.name
    try:
        with open(temp_path, "rb") as audio:
            result = client.audio.transcriptions.create(
                model=os.getenv("OPENAI_STT_MODEL", "whisper-1"),
                file=audio,
                language="ko",
            )
        return result.text
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def make_notification(data: dict, complaint_id=None) -> str:
    number = f"민원번호: {complaint_id}\n" if complaint_id is not None else ""
    return (
        f"[현장 민원 전달]\n{number}"
        f"우선순위: {data.get('priority', 'MEDIUM')}\n"
        f"행정동: {data.get('dong', '확인 필요')}\n"
        f"위치: {data.get('address_detail', '확인 필요')}\n"
        f"유형: {data.get('category', '기타')}\n"
        f"내용: {data.get('ai_summary', '')}\n"
        "※ 출동 전 주소·내용을 담당자가 확인해 주세요."
    )


def save_complaint(source_type, raw_text, data):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_connect() as conn:
        cur = conn.execute(
            """INSERT INTO complaints
            (created_at, source_type, raw_text, dong, address_detail, category, ai_summary, priority, notification_text, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                created_at, source_type, raw_text, data.get("dong", "확인 필요"),
                data.get("address_detail", "확인 필요"), data.get("category", "기타"),
                data.get("ai_summary", ""), data.get("priority", "MEDIUM"),
                make_notification(data), "접수",
            ),
        )
        complaint_id = cur.lastrowid
        conn.execute(
            "UPDATE complaints SET notification_text=? WHERE id=?",
            (make_notification(data, complaint_id), complaint_id),
        )
    return complaint_id


def load_complaints():
    with db_connect() as conn:
        rows = conn.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def update_status(complaint_id, status):
    with db_connect() as conn:
        conn.execute("UPDATE complaints SET status=? WHERE id=?", (status, int(complaint_id)))


st.set_page_config(page_title="AI 민원 자동화 데모", page_icon="♻️", layout="wide")
init_db()

st.title("♻️ AI 기반 생활폐기물 민원 자동화")
st.caption("시연용 웹 프로그램 · 음성/텍스트 접수 → 민원 정보 정리 → 현장 전달 메시지 생성")
st.warning(
    "주의: 이 프로그램은 시범용입니다. AI 분류와 긴급도는 틀릴 수 있으므로 현장 전달 전 사람이 확인해야 합니다. "
    "현재 버전은 실제 전화 자동 수신이나 기사 휴대전화로의 자동 발송을 하지 않습니다."
)

with st.sidebar:
    st.header("설정 및 안내")
    api_key_exists = bool(os.getenv("OPENAI_API_KEY", "").strip())
    st.write("OpenAI API 키:", "설정됨" if api_key_exists else "미설정")
    st.write("텍스트 입력:", "규칙 기반 데모 가능")
    st.write("음성 변환:", "API 키 필요")
    st.write("AI 분석:", "API 키가 있으면 OpenAI 사용 가능")
    st.markdown("---")
    st.markdown("**처음 실행하는 경우**")
    st.markdown("1. `requirements.txt` 설치\n2. `.env.example`을 `.env`로 복사\n3. API 키를 넣으면 음성 변환과 AI 분석 활성화")

tab_new, tab_records, tab_guide = st.tabs(["➕ 민원 접수", "📋 접수 현황", "ℹ️ 사용 안내"])

with tab_new:
    st.subheader("새 민원 접수")
    input_method = st.radio("입력 방식", ["텍스트 입력", "음성 파일 업로드"], horizontal=True)
    raw_text = ""
    source_type = "텍스트"

    if input_method == "텍스트 입력":
        raw_text = st.text_area(
            "민원 내용",
            placeholder="예: 용현동 102-15 육교 쪽 쉼터인데 음식물 수거 후 뒷정리가 안 돼 악취가 심해요.",
            height=130,
        )
        use_ai = st.checkbox("OpenAI API로 분석 (API 키가 설정된 경우)", value=bool(os.getenv("OPENAI_API_KEY", "").strip()))
        if st.button("민원 분석 및 접수", type="primary", disabled=not raw_text.strip()):
            try:
                if use_ai:
                    parsed = analyze_with_openai(raw_text.strip())
                else:
                    parsed = heuristic_parse(raw_text.strip())
                complaint_id = save_complaint(source_type, raw_text.strip(), parsed)
                st.session_state["last_result"] = {"id": complaint_id, "raw_text": raw_text.strip(), **parsed}
                st.success(f"민원 #{complaint_id} 접수 완료")
            except Exception as e:
                st.error(f"처리 중 오류: {e}")

    else:
        uploaded = st.file_uploader("민원 음성 파일", type=["wav", "mp3", "m4a", "mpeg", "mpga", "webm"])
        st.caption("음성 변환은 OpenAI API 키 및 인터넷 연결이 필요하며, API 사용료가 발생할 수 있습니다.")
        use_ai_audio = st.checkbox("변환 후 OpenAI로 민원 정보 분석", value=True)
        if uploaded is not None and st.button("음성 변환 · 분석 · 접수", type="primary"):
            try:
                raw_text = transcribe_audio(uploaded)
                st.text_area("음성 인식 결과(필요 시 수정)", value=raw_text, height=120, key="transcribed_preview")
                if use_ai_audio:
                    parsed = analyze_with_openai(raw_text)
                else:
                    parsed = heuristic_parse(raw_text)
                complaint_id = save_complaint("음성 파일", raw_text, parsed)
                st.session_state["last_result"] = {"id": complaint_id, "raw_text": raw_text, **parsed}
                st.success(f"음성 변환 및 민원 #{complaint_id} 접수 완료")
            except Exception as e:
                st.error(f"처리 중 오류: {e}")

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        st.markdown("---")
        st.subheader(f"분석 결과 · 민원 #{result['id']}")
        st.caption(f"분석 방식: {result.get('analysis_mode', '확인 필요')}")
        c1, c2, c3 = st.columns(3)
        c1.metric("행정동", result.get("dong", "확인 필요"))
        c2.metric("민원 유형", result.get("category", "기타"))
        c3.metric("우선순위", result.get("priority", "MEDIUM"))
        st.write("**세부 위치**", result.get("address_detail", "확인 필요"))
        st.write("**핵심 요약**", result.get("ai_summary", ""))
        message = make_notification(result, result["id"])
        st.text_area("현장 기사 전달용 메시지(자동 발송 아님)", value=message, height=180, key="last_notification")
        st.download_button(
            "알림 메시지 다운로드",
            data=message,
            file_name=f"complaint_{result['id']}_notification.txt",
            mime="text/plain",
        )

with tab_records:
    st.subheader("민원 접수 현황")
    df = load_complaints()
    if df.empty:
        st.info("아직 접수된 민원이 없습니다. '민원 접수' 탭에서 샘플 민원을 등록해 보세요.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("누적 접수", f"{len(df)}건")
        col2.metric("미처리", f"{(df['status'] != '완료').sum()}건")
        col3.metric("긴급(HIGH)", f"{(df['priority'] == 'HIGH').sum()}건")
        visible_cols = ["id", "created_at", "source_type", "dong", "category", "priority", "ai_summary", "status"]
        st.dataframe(df[visible_cols], use_container_width=True, hide_index=True)
        st.download_button(
            "접수 내역 CSV 다운로드",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="complaints_export.csv",
            mime="text/csv",
        )
        st.markdown("#### 처리 상태 변경")
        selected_id = st.selectbox("민원 번호", df["id"].tolist())
        selected_status = st.selectbox("새 상태", ["접수", "전달 대기", "처리 중", "완료"])
        if st.button("상태 저장"):
            update_status(selected_id, selected_status)
            st.success(f"민원 #{selected_id} 상태를 '{selected_status}'(으)로 변경했습니다.")
            st.rerun()
        selected = df[df["id"] == selected_id].iloc[0]
        st.markdown("#### 선택한 민원 상세")
        st.write("**원문:**", selected["raw_text"])
        st.text_area("현장 전달 메시지", value=selected["notification_text"], height=170, key=f"record_message_{selected_id}")

with tab_guide:
    st.subheader("이 프로그램의 기능과 한계")
    st.markdown("""
**현재 포함된 기능**
- 텍스트 민원 입력
- 음성 파일 업로드 후 한국어 음성 인식(OpenAI API 설정 시)
- AI 분석 또는 API 키 없이 실행하는 규칙 기반 데모 분석
- 행정동·위치·민원 유형·요약·우선순위 결과 표시
- 현장 전달 메시지 생성 및 TXT 다운로드
- SQLite 기반 접수 내역 저장, 상태 변경, CSV 다운로드

**현재 포함되지 않은 기능**
- 실제 전화 회선 연결 및 전화 자동 수신
- 카카오톡/텔레그램 자동 발송
- 실제 기사 배정, GPS 위치 추적, 외부 업무 시스템 연동
- 규칙 기반 데모 분석의 높은 정확도 보장

**개인정보 주의**
- 처음에는 실제 주민 이름·전화번호·상세 개인정보가 없는 가상 데이터로 시험하세요.
- 실제 민원 음성을 외부 API로 전송하기 전에는 회사의 개인정보 처리 기준 및 승인 여부를 확인하세요.
- API 키는 코드에 직접 적지 말고 `.env` 파일에 보관하세요.
""")
    st.markdown("#### 빠른 테스트용 예시")
    st.code("용현동 102-15 육교 쪽 쉼터인데 음식물 수거 후 뒷정리가 안 돼 악취가 심해요.", language="text")
    st.caption("이 예시는 실제 민원이 아닌 테스트용 문장입니다.")
