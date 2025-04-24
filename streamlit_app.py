import streamlit as st
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Content, Part
import pandas as pd
import json
import glob
import re

price = {
    'gemini-2.0-flash': {'input': 0.1, 'output': 0.4},
    'gemini-2.5-flash-preview-04-17': {'input': 0.15, 'output': 0.6},
}
prompt_token_count = 0
candidates_token_count = 0
cached_content_token_count = 0
tool_use_prompt_token_count = 0
total_token_count = 0
def accumulate_token_count(usage_metadata):
    global prompt_token_count, candidates_token_count, cached_content_token_count, tool_use_prompt_token_count, total_token_count
    prompt_token_count += usage_metadata.prompt_token_count
    candidates_token_count += usage_metadata.candidates_token_count
    cached_content_token_count += usage_metadata.cached_content_token_count if usage_metadata.cached_content_token_count else 0
    tool_use_prompt_token_count += usage_metadata.tool_use_prompt_token_count if usage_metadata.tool_use_prompt_token_count else 0
    total_token_count += usage_metadata.total_token_count
def cost():
    return round((prompt_token_count * price[model]['input'] + candidates_token_count * price[model]['output'])/1e6, 2)

# 1st API call
def get_user_prompt_type() -> str:
    system_prompt = """
    用戶提問與下列選項何者最相關？
    1. 總體經濟、財經資訊、金融市場等相關知識或時事
    2. 財經M平方客戶服務、商務合作
    3. 其他
    回傳數字，無其他文字、符號
    """
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="text/plain",
        )
    )
    accumulate_token_count(response.usage_metadata)
    return response.text.strip()

# 2nd ~ 6th API calls
def get_relevant_ids(csv_df_json) -> str:
    system_prompt = 'Given a user query, identify relevant ids in the JSON below, output only ids and no other text.\n'
    system_prompt += st.session_state.knowledge[csv_df_json]
    try:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            )
        )
        result = response.text
        accumulate_token_count(response.usage_metadata)
    except Exception as e:
        print(f"Errrr: {e}")
        result = '[]'
    finally:
        print(csv_df_json, result)
        return result

def get_retrieval(knowledge_type, latest=False) -> str:
    csv_file = sorted(glob.glob(f'{knowledge_type}*.csv'))[-1]
    try:
        ids = json.loads(get_relevant_ids(csv_file + ' => df.iloc[:,:2].to_json'))
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: {e}")
        ids = None
    if ids:
        if type(ids[0]) is dict:
            ids = [int(id_['id']) for id_ in ids]
        else:
            ids = [int(id_) for id_ in ids]
        if latest:
            ids = sorted(ids)[-1:]
        df = st.session_state.knowledge[csv_file]
        retrieval_dict = df[df['id'].isin(ids)].to_dict(orient='records')
        return json.dumps(retrieval_dict, ensure_ascii=False)
    else:
        return ''

def initialize_client():
    st.session_state.client = genai.Client(api_key=st.secrets['GEMINI_API_KEY'])

if 'client' not in st.session_state:
    st.session_state.contents = []
    st.session_state.knowledge = {}
    for csv_file in glob.glob('knowledge/*.csv'):
        df = pd.read_csv(csv_file)
        st.session_state.knowledge[csv_file] = df
        st.session_state.knowledge[csv_file + ' => df.iloc[:,:2].to_json'] = df.iloc[:,:2].to_json(orient='records', force_ascii=False)
    with st.container():
        st.subheader("財經時事相關問題，例如：美債殖利率為何飆高？")
        user_prompt = st.chat_input('Ask Madam', on_submit=initialize_client)
else:
    client = st.session_state.client
    user_prompt = st.chat_input('Ask Madam')

with st.sidebar:
    st.title('👩🏻‍💼 MM Madam')
    system_prompt = '# ' + st.text_area('*系統提示詞，可以調整測試*', '你是財經M平方（MacroMicro）總經投資平台的 AI 研究員 Madam，你會提供總體經濟、財經資訊、金融市場等相關知識的科普及專業問答，使用 Markdown 語法組織內容，設計格式文字、表格及連結，當提及『財經M平方』或『MacroMicro』時，務必使用『我們』。', height=180)
    st.markdown('---')
    is_paid_user = st.toggle('💎 付費用戶', value=True)
    has_chart = st.toggle('📊 MM圖表', value=is_paid_user, disabled=not is_paid_user)
    has_quickie = st.toggle('💡 MM短評', value=is_paid_user, disabled=not is_paid_user)
    has_blog = st.toggle('📝 MM部落格', value=is_paid_user, disabled=not is_paid_user)
    has_edm = st.toggle('📮 MM獨家報告', value=is_paid_user, disabled=not is_paid_user)
    has_help = st.toggle('❓ MM幫助中心', value=True)
    has_search = st.toggle('🔍 Google搜尋', value=True)
    st.markdown('---')
    model = st.selectbox('Model', price.keys())

# include and display the last 5 turns of conversation before the current turn
st.session_state.contents = st.session_state.contents[-10:]
for content in st.session_state.contents:
    with st.chat_message(content.role, avatar=None if content.role == "user" else '👩🏻‍💼'):
        st.markdown(content.parts[0].text)

# Create a chat input field to allow the user to enter a message. This will display
# automatically at the bottom of the page.
if user_prompt:
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.contents.append(Content(role="user", parts=[Part.from_text(text=user_prompt)]))

    user_prompt_type = get_user_prompt_type()
    if user_prompt_type == '1':
        if not is_paid_user:
            system_prompt += '\n# 你會鼓勵用戶升級成為付費用戶就能享有完整問答服務，並且提供訂閱方案連結 https://www.macromicro.me/subscribe 。'
        if has_chart:
            if retrieval := get_retrieval('knowledge/chart'):
                system_prompt += '\n# 你會依據以下MM圖表的知識回答用戶提問，並且提供MM圖表連結 https://www.macromicro.me/charts/{id}/{slug} 。'
                system_prompt += '\n' + retrieval
        if has_quickie:
            if retrieval := get_retrieval('knowledge/quickie', latest=True):
                system_prompt += '\n# 你會依據以下MM短評的知識回答用戶提問，並且提供MM短評連結 https://www.macromicro.me/quickie?id={id} 。'
                system_prompt += '\n' + retrieval
        if has_blog:
            if retrieval := get_retrieval('knowledge/blog', latest=True):
                system_prompt += '\n# 你會依據以下MM部落格的知識回答用戶提問，並且提供MM部落格連結 https://www.macromicro.me/blog/{slug} 。'
                system_prompt += '\n' + retrieval
        if has_edm:
            if retrieval := get_retrieval('knowledge/edm', latest=True):
                system_prompt += '\n# 你會依據以下MM獨家報告的知識回答用戶提問，並且提供MM獨家報告連結 https://www.macromicro.me/mails/monthly_report 。'
                system_prompt += '\n' + retrieval
        if has_search:
            system_prompt += '\n# 你最終會以Google搜尋做為事實依據回答用戶提問。'
    if user_prompt_type == '2':
        system_prompt += '\n# 你會提供財經M平方的客戶服務、商務合作等相關資訊。'
    if user_prompt_type == '3':
        system_prompt += '\n# 若非財經時事相關問題，你會婉拒回答。'
    print(system_prompt)
    try:
        response = client.models.generate_content(
            model=model,
            contents=st.session_state.contents,
            config=GenerateContentConfig(
                tools=[Tool(google_search=GoogleSearch())] if has_search else None,
                system_instruction=system_prompt,
                response_mime_type="text/plain",
            ),
        )
        # remove reference markers
        result = re.sub(r'\[\d+\]', '', response.text)
        accumulate_token_count(response.usage_metadata)
    except Exception as e:
        print(f"Errrr: {e}")
        result = '抱歉，請稍後再試。'
    finally:
        with st.chat_message("assistant", avatar='👩🏻‍💼'):
            st.markdown(result)
        st.session_state.contents.append(Content(role="model", parts=[Part.from_text(text=result)]))

        st.badge(f'{prompt_token_count} input tokens + {candidates_token_count} output tokens ≒ {cost()} USD ( when Google Search < 1500 Requests/Day )', icon="💰", color="green")