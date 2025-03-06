import streamlit as st
from openai import OpenAI
import requests

from datetime import datetime, timezone, timedelta
tz = timezone(timedelta(hours=+8))

import os
url = os.getenv('SYSTEM_PROMPT_URL')
md = 'SYSTEM_PROMPT.md'
if not os.path.exists(md):
    with open(md, 'wb') as f:
        f.write(requests.get(url).content)
with open(md) as f:
    lines = f.read().split('\n')

# Create session state variables
if 'client' not in st.session_state:
    st.session_state.client = OpenAI()
    st.session_state.system = {}
    st.session_state.messages = []
    for line in lines:
        if '更新日期'  in line:
            st.session_state.system[line] = ''
        else:
            st.session_state.system[list(st.session_state.system.keys())[-1]] += line + '\n'

st.title('🧚‍♀️ Lilien')

col1, col2 = st.columns(2)
with col1:
    version = st.selectbox("系統提示選單", list(st.session_state.system.keys()))
with col2:
    model = st.selectbox("模型選單", ['gpt-4o-mini', 'gpt-4o', 'o3-mini'])

system_prompt = st.session_state.system[version]
print(system_prompt)
print(model)

# Display the existing chat messages via `st.chat_message`.
for message in st.session_state.messages:
    if message["role"] == "system":
        current_time = message["content"]
        st.html(f'<p align="right">{current_time[11:-6]}</p>')
        continue
    with st.chat_message(message["role"], avatar=None if message["role"] == "user" else '🧚‍♀️'):
        st.markdown(message["content"])

# Create a chat input field to allow the user to enter a message. This will display
# automatically at the bottom of the page.
if user_prompt := st.chat_input("你說 我聽"):

    # Store and display the current_time
    current_time = datetime.now(tz).replace(microsecond=0).isoformat()
    st.session_state.messages.append({"role": "system", "content": current_time})
    st.html(f'<p align="right">{current_time[11:-6]}</p>')
    # Store and display the current user_prompt.
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Last 10 rounds of conversation queued before the current_time/user_prompt.
    st.session_state.messages = st.session_state.messages[-32:]
    # Generate a response using the OpenAI API.
    stream = st.session_state.client.chat.completions.create(
        model=model,
        messages=[{'role': 'system', 'content': system_prompt}] + st.session_state.messages,
        stream=True,
    )

    # Stream the response to the chat using `st.write_stream`, then store it in 
    # session state.
    with st.chat_message("assistant", avatar='🧚‍♀️'):
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})
