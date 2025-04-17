import streamlit as st
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Content, Part
# import pandas as pd
import glob
csvs =  glob.glob('data/*.csv')

def get_user_prompt_type() -> str:
    system_prompt = """
    用戶提問與下列選項何者最相關？
    1. 總體經濟、財經資訊、金融市場等相關知識或時事
    2. 財經M平方客戶服務、商務合作
    3. 其他
    回傳數字，無其他文字
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

def get_relevant_json(csv) -> str:
    system_prompt = 'Given a user question, identify relevant CSVs.\n' + st.session_state.knowledge[csv]
    response = client.models.generate_content(
        model=model,
        contents=st.session_state.contents[-1:],
        config=GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        )
    )
    return response.text

# Create session state variables
if 'client' not in st.session_state:
    st.session_state.client = genai.Client(api_key=st.secrets['GEMINI_API_KEY'])
    st.session_state.contents = []
    st.session_state.knowledge = {}
    for csv in csvs:
        with open(csv) as f:
            st.session_state.knowledge[csv] = ''.join(f.readlines())
        # st.session_state.knowledge['DataFrame of '+csv] = pd.read_csv(csv)
    with st.container():
        st.subheader("財經時事相關問題，例如：為何美債殖利率大漲？")
        user_prompt = st.chat_input('Ask Madam')
else:
    user_prompt = st.chat_input('Ask Madam')
client = st.session_state.client
model = 'gemini-2.0-flash'

with st.sidebar:
    st.title('👩🏻‍💼 MM Madam')
    st.badge('Gemini 2.0 Flash', icon=":material/stars_2:", color="green")
    has_search = st.toggle('🔍 Google搜尋', value=True)
    has_chart = st.toggle('📊 MM圖表', value=True)
    has_quickie = st.toggle('💡 MM短評', value=True)
    has_blog = st.toggle('📝 MM部落格', value=False)
    has_edm = st.toggle('📮 MM獨家報告', value=False)

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

    system_prompt = '妳是「財經M平方（MacroMicro）」的AI研究員：Madam，妳會提供總體經濟、財經資訊、金融市場等相關知識的專業問答。'
    user_prompt_type = get_user_prompt_type()
    if user_prompt_type == '1':
        if has_search:
            system_prompt += '\n妳會參考Google搜尋結果回答問題。'
        if has_chart:
            csv = [csv for csv in csvs if 'chart' in csv][0]
            retrieval = get_relevant_json(csv)
            system_prompt += '\n並且引用以下MacroMicro圖表相關內容，提供MM圖表超連結 https://www.macromicro.me/charts/{id}/{slug} ，超連結前後空格或換行。\n' + retrieval
        if has_quickie:
            csv = [csv for csv in csvs if 'quickie' in csv][0]
            retrieval = get_relevant_json(csv)
            system_prompt += '\n並且引用以下MacroMicro短評相關內容，提供MM短評超連結 https://www.macromicro.me/quickie?id={id} ，超連結前後空格或換行。\n' + retrieval
        if has_blog:
            csv = [csv for csv in csvs if 'blog' in csv][0]
            retrieval = get_relevant_json(csv)
            system_prompt += '\n並且引用以下MacroMicro部落格相關內容，提供MM部落格超連結 https://www.macromicro.me/blog/{slug} ，超連結前後空格或換行。\n' + retrieval
        if has_edm:
            csv = [csv for csv in csvs if 'edm' in csv][0]
            retrieval = get_relevant_json(csv)
            system_prompt += '\n並且引用以下MacroMicro獨家報告相關內容回答問題。\n' + retrieval
    if user_prompt_type == '2':
        system_prompt += '妳會提供財經M平方的客戶服務、商務合作等相關資訊。'
    if user_prompt_type == '3':
        system_prompt += '若非財經時事相關問題，妳會婉拒回答。'
    print(system_prompt)
    response = client.models.generate_content(
        model=model,
        contents=st.session_state.contents,
        config=GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[Tool(google_search=GoogleSearch())] if has_search else None,
            response_mime_type="text/plain",
        ),
    )
    # Stream the response to the chat using `st.write_stream`, then store it in 
    # session state.
    with st.chat_message("assistant", avatar='👩🏻‍💼'):
        st.markdown(response.text)
    st.session_state.contents.append(Content(role="model", parts=[Part.from_text(text=response.text)]))