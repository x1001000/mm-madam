import streamlit as st
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Content, Part
import pandas as pd
import json
import glob
import re

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

def get_relevant_ids_json(csv) -> str:
    system_prompt = 'Given a user question, identify relevant records in the CSV file, output only ids\n\n'
    system_prompt += st.session_state.knowledge[csv]
    response = client.models.generate_content(
        model=model,
        contents=st.session_state.contents[-1:],
        config=GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        )
    )
    print(csv, response.text)
    return response.text

def initialize_client():
    st.session_state.client = genai.Client(api_key=st.secrets['GEMINI_API_KEY'])

if 'client' not in st.session_state:
    st.session_state.contents = []
    st.session_state.knowledge = {}
    for csv in glob.glob('data/*.csv'):
        with open(csv) as f:
            st.session_state.knowledge[csv] = ''.join(f.readlines())
        st.session_state.knowledge['DataFrame of '+csv] = pd.read_csv(csv)
    with st.container():
        st.subheader("財經時事相關問題，例如：美債殖利率為何飆高？")
        user_prompt = st.chat_input('Ask Madam', on_submit=initialize_client)
else:
    client = st.session_state.client
    user_prompt = st.chat_input('Ask Madam')

with st.sidebar:
    st.title('👩🏻‍💼 MM Madam')
    has_chart = st.toggle('📊 MM圖表', value=True)
    has_quickie = st.toggle('💡 MM短評', value=True)
    has_blog = st.toggle('📝 MM部落格', value=True)
    has_edm = st.toggle('📮 MM獨家報告', value=True)
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

    system_prompt = '# 妳是「財經M平方（MacroMicro）」的AI研究員：Madam，妳會提供總體經濟、財經資訊、金融市場等相關知識的科普及專業問答，儘量使用Markdown表格進行論述，當提及『財經M平方』或『MacroMicro』時，務必使用『我們』。\n'
    user_prompt_type = get_user_prompt_type()
    if user_prompt_type == '1':
        if has_chart:
            csv = glob.glob('data/chart*.csv')[-1]
            ids = json.loads(get_relevant_ids_json(csv))
            ids = [int(id_) for id_ in ids if id_.isdigit()]
            df = st.session_state.knowledge['DataFrame of '+csv]
            retrieval_dict = df[df['id'].isin(ids)].to_dict(orient='records')
            system_prompt += '\n\n## 妳會依據以下MM圖表的資料回答問題，並且提供MM圖表超連結 https://www.macromicro.me/charts/{id}/{slug} ，超連結前後要空格或換行。\n'
            system_prompt += json.dumps(retrieval_dict, ensure_ascii=False)
        if has_quickie:
            csv = glob.glob('data/quickie*.csv')[-1]
            ids = json.loads(get_relevant_ids_json(csv))[:1]
            ids = [int(id_) for id_ in ids if id_.isdigit()]
            df = st.session_state.knowledge['DataFrame of '+csv]
            retrieval_dict = df[df['id'].isin(ids)].to_dict(orient='records')
            system_prompt += '\n\n## 妳會依據以下MM短評的資料回答問題，並且提供MM短評超連結 https://www.macromicro.me/quickie?id={id} ，超連結前後要空格或換行。\n'
            system_prompt += json.dumps(retrieval_dict, ensure_ascii=False)
        if has_blog:
            csv = glob.glob('data/blog*.csv')[-1]
            ids = json.loads(get_relevant_ids_json(csv))[:1]
            ids = [int(id_) for id_ in ids if id_.isdigit()]
            df = st.session_state.knowledge['DataFrame of '+csv]
            retrieval_dict = df[df['id'].isin(ids)].to_dict(orient='records')
            system_prompt += '\n\n## 妳會依據以下MM部落格的資料回答問題，並且提供MM部落格超連結 https://www.macromicro.me/blog/{slug} ，超連結前後要空格或換行。\n'
            system_prompt += json.dumps(retrieval_dict, ensure_ascii=False)
        if has_edm:
            csv = glob.glob('data/edm*.csv')[-1]
            ids = json.loads(get_relevant_ids_json(csv))[:1]
            ids = [int(id_) for id_ in ids if id_.isdigit()]
            df = st.session_state.knowledge['DataFrame of '+csv]
            retrieval_dict = df[df['id'].isin(ids)].to_dict(orient='records')
            system_prompt += '\n\n## 妳會依據以下MM獨家報告的資料回答問題。\n'
            system_prompt += json.dumps(retrieval_dict, ensure_ascii=False)
        if has_search:
            system_prompt += '\n\n## 妳最終會以Google搜尋做為事實依據。'
    if user_prompt_type == '2':
        system_prompt += '\n\n## 妳會提供財經M平方的客戶服務、商務合作等相關資訊。'
    if user_prompt_type == '3':
        system_prompt += '\n\n## 若非財經時事相關問題，妳會婉拒回答。'
    print(system_prompt)
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
    response_text = re.sub(r'\[\d+\]', '', response.text)
    with st.chat_message("assistant", avatar='👩🏻‍💼'):
        st.markdown(response_text)
    st.session_state.contents.append(Content(role="model", parts=[Part.from_text(text=response_text)]))