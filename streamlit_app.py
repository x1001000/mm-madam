import streamlit as st
from openai import OpenAI
import os
import gdown
from markitdown import MarkItDown

url = os.getenv('SYSTEM_PROMPT_URL')
docx = 'SYSTEM_PROMPT.DOCX'
if not os.path.exists(docx):
    gdown.download(url, output=docx, fuzzy=True)

# Create a session state variable to store the chat messages. This ensures that the
# messages persist across reruns.
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.client = client = OpenAI()
    st.session_state.prompt = prompt = dict()
    for line in MarkItDown().convert(docx).text_content.split('\n'):
        if '更新日期'  in line:
            prompt[line] = ''
        else:
            prompt[list(prompt.keys())[-1]] += line + '\n'
else:
    client = st.session_state.client
    prompt = st.session_state.prompt

st.title('🧚‍♀️ Lilien')

col1, col2 = st.columns(2)
with col1:
    version = st.selectbox("系統提示選單", list(prompt.keys()))
with col2:
    model = st.selectbox("模型選單", ['gpt-4o', 'o3-mini'])

system_prompt = prompt[version]
print(system_prompt)
print(model)

# Display the existing chat messages via `st.chat_message`.
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=None if message["role"] == "user" else '🧚‍♀️'):
        st.markdown(message["content"])

# Create a chat input field to allow the user to enter a message. This will display
# automatically at the bottom of the page.
if user_prompt := st.chat_input("你說 我聽"):

    # Store and display the current user_prompt.
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Generate a response using the OpenAI API.
    stream = client.chat.completions.create(
        model=model,
        messages=[{'role': 'system', 'content': system_prompt}] + [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[-20:]
        ],
        stream=True,
    )

    # Stream the response to the chat using `st.write_stream`, then store it in 
    # session state.
    with st.chat_message("assistant", avatar='🧚‍♀️'):
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})
