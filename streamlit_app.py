import streamlit as st
from openai import OpenAI

import glob
csvs = glob.glob('*.csv')

import os
models = {
    'gemini-2.0-flash': {
        'api_key': os.environ.get('GEMINI_API_KEY'),
        'base_url': "https://generativelanguage.googleapis.com/v1beta/openai/"
        },
    'gemini-2.0-flash-lite': {
        'api_key': os.environ.get('GEMINI_API_KEY'),
        'base_url': "https://generativelanguage.googleapis.com/v1beta/openai/"
        },
    # 'grok-2': {
    #     'api_key': os.environ.get('XAI_API_KEY'),
    #     'base_url': "https://api.x.ai/v1"
    #     },
    }

st.title('👩🏻‍💼 MM Madame')

col1, col2 = st.columns(2)
with col1:
    csv = st.selectbox("知識庫", csvs)
with col2:
    model = st.selectbox("語言模型", models.keys())

# Create session state variables
if 'client' not in st.session_state:
    st.session_state.client = OpenAI(**models[model])
    st.session_state.messages = []
    st.session_state.knowledge = {}
    for csv in csvs:
        with open(csv) as f:
            st.session_state.knowledge[csv] = ''.join(f.readlines())

retrieval_prompt = '使用者提問與下方資料表中有關的id，輸出成JSON\n\n\n' + st.session_state.knowledge[csv]

# Display the existing chat messages via `st.chat_message`.
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=None if message["role"] == "user" else '👩🏻‍💼'):
        st.markdown(message["content"])

# Create a chat input field to allow the user to enter a message. This will display
# automatically at the bottom of the page.
if user_prompt := st.chat_input("問我總經相關的問題吧"):

    # Store and display the current user_prompt.
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Last 5 rounds of conversation queued
    st.session_state.messages = st.session_state.messages[-11:]
    # Generate a response using the OpenAI API.
    response = st.session_state.client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': retrieval_prompt},
            ] + st.session_state.messages,
        # stream=True,
        response_format={"type": "json_object"},
    )

    system_prompt = '妳是總經投資平台「財經M平方（MacroMicro）」的AI研究員：Madame。妳會依據平台知識庫搜尋結果回答問題，並提供圖表連結（https://www.macromicro.me/charts/{id}/{slug}）。若非總經相關問題，妳會告知不便回答。\n\n搜尋結果如下：\n' + response.choices[0].message.content
    print(system_prompt)
    stream = st.session_state.client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system_prompt},
            ] + st.session_state.messages,
        stream=True,
    )
    # Stream the response to the chat using `st.write_stream`, then store it in 
    # session state.
    with st.chat_message("assistant", avatar='👩🏻‍💼'):
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})
