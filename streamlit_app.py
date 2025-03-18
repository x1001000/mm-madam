import streamlit as st
from openai import OpenAI

import glob
csvs = glob.glob('*.csv')

# Create session state variables
if 'client' not in st.session_state:
    st.session_state.client = OpenAI()
    st.session_state.messages = []
    st.session_state.database = {}
    for csv in csvs:
        with open(csv) as f:
            st.session_state.database[csv] = ''.join(f.readlines())

st.title('👩🏻‍💼 MM Madame')

col1, col2 = st.columns(2)
with col1:
    version = st.selectbox("知識庫選單", csvs)
with col2:
    model = st.selectbox("模型選單", ['gpt-4o-mini', 'gemini-2.0-flash-lite', 'grok-2'])

system_prompt = '妳是最專業的總經投資平台「財經M平方（MacroMicro）」的AI研究員：Madame。妳會依據下列csv的知識庫回答問題，並且標註出處id。若非總經相關問題，妳會告知不便回答。\n\n' + st.session_state.database[version]
print(system_prompt)

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

    tool_calls = st.session_state.client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_prompt}],
    ).choices[0].message.tool_calls

    # Last 10 rounds of conversation queued before the current_time/user_prompt.
    st.session_state.messages = st.session_state.messages[-10:]
    # Generate a response using the OpenAI API.
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
