import streamlit as st
import os
import uuid
import datetime
from supabase_helper import supabase
from supabase import create_client
from openai import OpenAI


# -------------------- Supabase 初期化 --------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------- OpenAI 初期化 --------------------
client = OpenAI(
    api_key=st.secrets["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1"
)

# -------------------- ユーザー識別（ニックネーム→UUID） --------------------
def get_or_create_user_uuid(nickname):
    response = supabase.table("user_profiles").select("user_uuid").eq("nickname", nickname).execute()
    if response.data:
        return response.data[0]["user_uuid"]

    new_id = str(uuid.uuid4())
    supabase.table("user_profiles").insert({"nickname": nickname, "user_uuid": new_id}).execute()
    return new_id

# -------------------- 目標の読み書き --------------------
def load_goals(user_uuid):
    response = supabase.table("goals").select("body_mind", "career", "relationships", "others").eq("user_uuid", user_uuid).execute()
    if response.data:
        return response.data[0]
    return {"body_mind": "", "career": "", "relationships": "", "others": ""}

def save_goals(user_uuid, nickname, goals):
    data = {"user_uuid": user_uuid, "nickname": nickname, **goals}
    existing = supabase.table("goals").select("nickname").eq("user_uuid", user_uuid).execute()
    if existing.data:
        supabase.table("goals").update(data).eq("user_uuid", user_uuid).execute()
    else:
        supabase.table("goals").insert(data).execute()

# -------------------- ログの保存と取得 --------------------
def save_log(user_uuid, nickname, date, entry):
    data = {"user_uuid": user_uuid, "nickname": nickname, "date": date, "entry": entry}
    supabase.table("logs").insert(data).execute()

def load_logs(user_uuid):
    response = supabase.table("logs").select("date", "entry").eq("user_uuid", user_uuid).order("date", desc=True).limit(5).execute()
    return response.data if response.data else []

# -------------------- GPT応答生成 --------------------
def get_gpt_reply(entry, goals):
    prompt = f"""
あなたはユーザーをあたたかく励ましたり褒めたりしてくれる前向きで優しいチャットボットです。
堅苦しくなく、やわらかい言葉で話してください。口調はフレンドリーですが丁寧にです・ます調でお願いします。絵文字も使ってください。
一日の出来事を記録するアプリの一部として、ユーザーが今日書いた出来事に対して、活動に対する褒めや労い、ポジティブなフィードバックを自然な言葉で返してください。
ただし直接的な褒め言葉は避け、ユーザーの行動や出来事に対して自然に褒めてください。
もしもユーザーが落ち込んでいるような内容を書いていた場合には、無理に励まさず、共感を示しつつ、一日を過ごしたことに対して褒めてあげてください。
挨拶として冒頭にユーザーが記録をしてくれたことへの感謝の言葉を敬語で入れてください。
例えば、「今日も記録してくれてありがとうございます😊」が挙げられます。
以下はユーザーが今日書いた出来事です：
「{entry}」
この出来事に対して、ユーザーをあたたかく励ましたり褒めたりするようなフィードバックをしてください。
その際、ユーザーが設定している将来の目標を念頭に置き、もしも出来事がユーザーの目標に関連していた時には、それに自然に気づいてあげてください。
ユーザーが設定している将来の目標はこちらです：
身体・心理面：{goals.get('body_mind')}
学業・仕事：{goals.get('career')}
人間関係：{goals.get('relationships')}
その他：{goals.get('others')}
ただし、無理に出来事と目標の関連性を指摘する必要はありませんし、必ずしも目標について言及する必要はありません。
また、ユーザーはまだ目標を達成しているわけではないので、目標を達成したかのような表現は避けてください。
将来の目標に関連する内容がなければ、ユーザーが今日書いた出来事「{entry}」に対するフィードバックだけしてください。
あくまでもユーザーが今日書いた出来事に対するフィードバックが中心で、目標についてはあまり触れないでください。
全体があまり長くならないように、200文字程度に収めてください。
"""

    response = client.chat.completions.create(
        model="openai/gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

# -------------------- Streamlit UI --------------------
st.set_page_config(page_title="ポジティブ習慣アプリ", page_icon="🌟")
st.title("🌟ポジティブ習慣アプリ")

nickname = st.text_input("あなたに割り当てられたIDを入力してください")
if not nickname:
    st.stop()

user_uuid = get_or_create_user_uuid(nickname)

# --- 目標入力 ---
st.header("🎯 あなたの将来の最も理想的な姿について記入しましょう")
st.subheader("なるべく具体的に記入しましょう✨\nいくつでも構いません😊 いつでも変更してOKです👌\n\n変更したら忘れずに保存ボタンを押しましょう！")
goals = load_goals(user_uuid)

with st.form("goal_form"):
    st.subheader("1. 身体・心理面の理想")
    st.caption("例：週に1回は運動し、健康的な生活習慣を続けている。柔軟な考えを持ち、人に優しく接することができる。")
    goals["body_mind"] = st.text_area("", value=goals.get("body_mind", ""), key="body_mind", height=150)

    st.subheader("2. 学業・仕事の理想")
    st.caption("例：統計学をマスターし、どんな解析でも自信を持ってできるようになっている。丁寧で正確に仕事をこなし、周囲から頼られる先輩である。")
    goals["career"] = st.text_area("", value=goals.get("career", ""), key="career", height=150)

    st.subheader("3. 人間関係の理想")
    st.caption("例：信頼できるパートナーと暮らし、両親ともたまに会って良好な関係を築いている。何らかのコミュニティに参加し、常に新しい人との出会いがある。")
    goals["relationships"] = st.text_area("", value=goals.get("relationships", ""), key="relationships", height=150)

    st.subheader("4. その他の理想")
    st.caption("例：趣味のバンド活動を続け、たまにライブを開催している。料理が上手で、家族に美味しいご飯を作っている。")
    goals["others"] = st.text_area("", value=goals.get("others", ""), key="others",height=150)
    if st.form_submit_button("目標を保存する"):
        save_goals(user_uuid, nickname, goals)
        st.success("✅ 目標を保存しました！")

# --- ポジティブ出来事記録 ---
st.header("📖 今日のポジティブな出来事")
today = datetime.date.today().isoformat()

with st.form("log_form"):
    st.subheader("今日嬉しかったこと、できたこと、達成したことなどを自由に書いてください✨")
    st.caption("例：朝余裕をもって出勤でき、清々しい気持ちがした。友達に偶然出会い、ご飯に行く約束をした。")
    entry = st.text_area("", height=150)
    submitted = st.form_submit_button("記録する")

    if submitted and entry:
        save_log(user_uuid, today, entry)
        gpt_reply = get_gpt_reply(entry, goals)
        st.markdown(f"> {gpt_reply}")
        st.success("✅ 記録を保存しました！")


   # if submitted and entry.strip():
   #     save_log(user_uuid, nickname, today, entry)
   #     gpt_reply = get_gpt_reply(entry, goals)  # ← GPT応答関数を呼ぶ
    #    st.session_state["gpt_reply"] = gpt_reply
     #   st.session_state["show_summary"] = True
      #  st.success("✅ 記録を保存しました！")

# --- GPT応答表示と「記録を見る」ボタン ---
#if st.session_state.get("show_summary"):
 #   st.markdown("💬 **GPTの応答：**")
  #  st.markdown(f"> {st.session_state['gpt_reply']}")
   # if st.button("📄 記録を見る"):
    #    st.session_state["show_summary"] = False
     #   st.session_state["show_records"] = True

# --- 現在の目標と過去の記録ページ ---
if st.session_state.get("show_records"):
    st.subheader("📌 現在の目標")
    st.markdown(f"- 身体・心理面：{goals.get('body_mind', '') or '（未入力）'}")
    st.markdown(f"- 学業・仕事：{goals.get('career', '') or '（未入力）'}")
    st.markdown(f"- 人間関係：{goals.get('relationships', '') or '（未入力）'}")
    st.markdown(f"- その他：{goals.get('others', '') or '（未入力）'}")

    st.header("📚 過去の記録（最新5件）")
    logs = load_logs(user_uuid)
    if logs:
        for log in logs:
            st.markdown(f"📅 {log['date']}")
            st.markdown(f"> {log['entry']}")
    else:
        st.info("まだ記録がありません。")

