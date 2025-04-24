import streamlit as st
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Content, Part
import pandas as pd
import json
import glob
import re

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
        contents=st.session_state.contents[-1:],
        config=GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="text/plain",
        )
    )
    return response.text.strip()

# 2nd ~ 6th API calls
def get_relevant_ids(json_file) -> str:
    system_prompt = 'Given a user query, identify relevant ids in the JSON file, output only ids and no other text.\n'
    system_prompt += st.session_state.knowledge[json_file]
    try:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                # http_options=HttpOptions(timeout=30000),
            )
        )
        result = response.text
    except Exception as e:
        print(f"Errrr: {e}")
        result = '[]'
    finally:
        print(json_file, result)
        return result

def get_retrieval(knowledge_type, latest=False) -> str:
    csv_file = sorted(glob.glob(f'{knowledge_type}*.csv'))[-1]
    json_file = sorted(glob.glob(f'{knowledge_type}*.json'))[-1]
    try:
        ids = json.loads(get_relevant_ids(json_file))
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: {e}")
        ids = []
    if ids:
        if type(ids[0]) == str:
            ids = [int(id_) for id_ in ids]
        else:
            ids = [int(id_['id']) for id_ in ids]
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
        st.session_state.knowledge[csv_file] = pd.read_csv(csv_file)
    for json_file in glob.glob('knowledge/*.json'):
        with open(json_file) as f:
            st.session_state.knowledge[json_file] = ''.join(f.readlines())
    with st.container():
        st.subheader("財經時事相關問題，例如：美債殖利率為何飆高？")
        user_prompt = st.chat_input('Ask Madam', on_submit=initialize_client)
else:
    client = st.session_state.client
    user_prompt = st.chat_input('Ask Madam')

with st.sidebar:
    st.title('👩🏻‍💼 MM Madam')
    is_paid_user = st.toggle('💎 付費用戶', value=True)
    has_chart = st.toggle('📊 MM圖表', value=is_paid_user, disabled=not is_paid_user)
    has_quickie = st.toggle('💡 MM短評', value=is_paid_user, disabled=not is_paid_user)
    has_blog = st.toggle('📝 MM部落格', value=is_paid_user, disabled=not is_paid_user)
    has_edm = st.toggle('📮 MM獨家報告', value=is_paid_user, disabled=not is_paid_user)
    has_help = st.toggle('❓ MM幫助中心', value=True)
    has_search = st.toggle('🔍 Google搜尋', value=True)
    model = st.selectbox('Model', ['gemini-2.0-flash', 'gemini-2.5-flash-preview-04-17'])

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

    system_prompt = '# 妳是「財經M平方（MacroMicro）」的AI研究員：Madam，妳會提供總體經濟、財經資訊、金融市場等相關知識的科普及專業問答，使用Markdown語法排版、製作表格及超連結，當提及『財經M平方』或『MacroMicro』時，務必使用『我們』。'
    user_prompt_type = get_user_prompt_type()
    if user_prompt_type == '1':
        if has_chart:
            if retrieval := get_retrieval('knowledge/chart'):
                system_prompt += '\n# 妳會依據以下MM圖表的知識回答用戶提問，並且提供MM圖表超連結 https://www.macromicro.me/charts/{id}/{slug} 。'
                system_prompt += '\n'+retrieval
        if has_quickie:
            if retrieval := get_retrieval('knowledge/quickie', latest=True):
                system_prompt += '\n# 妳會依據以下MM短評的知識回答用戶提問，並且提供MM短評超連結 https://www.macromicro.me/quickie?id={id} 。'
                system_prompt += '\n'+retrieval
        if has_blog:
            if retrieval := get_retrieval('knowledge/blog', latest=True):
                system_prompt += '\n# 妳會依據以下MM部落格的知識回答用戶提問，並且提供MM部落格超連結 https://www.macromicro.me/blog/{slug} 。'
                system_prompt += '\n'+retrieval
        if has_edm:
            if retrieval := get_retrieval('knowledge/edm', latest=True):
                system_prompt += '\n# 妳會依據以下MM獨家報告的知識回答用戶提問。'
                system_prompt += '\n'+retrieval
        if has_search:
            system_prompt += '\n# 妳最終會以Google搜尋做為事實依據回答用戶提問。'
    if user_prompt_type == '2':
        system_prompt += '\n# 妳會提供財經M平方的客戶服務、商務合作等相關資訊。'
    if user_prompt_type == '3':
        system_prompt += '\n# 若非財經時事相關問題，妳會婉拒回答。'
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
    except Exception as e:
        print(f"Errrr: {e}")
        result = '抱歉，請稍後再試。'
    finally:
        with st.chat_message("assistant", avatar='👩🏻‍💼'):
            st.markdown(result)
        st.session_state.contents.append(Content(role="model", parts=[Part.from_text(text=result)]))