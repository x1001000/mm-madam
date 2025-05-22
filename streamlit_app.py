import streamlit as st
from google.generativeai import types
import pandas as pd
# accumulate_token_count is used internally by chat_logic.generate_content, not directly here.
# prompt_token_count and candidates_token_count are for the badge display.
from chat_logic import (
    generate_content,
    cost,
    price as chat_logic_price,
    DEFAULT_MODEL,
    reset_token_counts,
    prompt_token_count,
    candidates_token_count,
    load_knowledge_data,
    # Import newly moved retrieval functions
    remove_invalid_urls,
    get_retrieval_from_google_search,
    # get_relevant_ids, # Not called directly from streamlit_app anymore, get_retrieval uses the one in chat_logic
    get_retrieval,
    # Import newly moved prompt analysis functions
    get_user_prompt_lang,
    get_user_prompt_type,
    construct_system_prompt # Added import for system prompt construction
)
import google.generativeai as genai
import json
import glob # Re-adding glob as it's used for finding CSV keys
import requests # Still needed for SYSTEM_PROMPT_URL and GITHUB_GIST_API
import re # remove_invalid_urls is now in chat_logic, but re might be used elsewhere. Keep for now.

# 'after' variable is now a default argument in chat_logic.load_knowledge_data

# Token count variables are now managed in chat_logic.py

# Retrieval functions (get_relevant_ids, get_retrieval, get_retrieval_from_google_search, remove_invalid_urls)
# are now in chat_logic.py.
# Functions get_user_prompt_lang and get_user_prompt_type are now in chat_logic.py.

# Helper function for loading HTML content, to be passed to chat_logic.get_retrieval
# This remains in streamlit_app.py as it's UI/file-system interaction specific to the app's environment.
def load_html_file_content(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        # st.error(f"Failed to load HTML file {file_path}: {e}")
        print(f"Failed to load HTML file {file_path}: {e}") # Print to console for now
        return f"Error loading content from {file_path}."


site_languages = [
    '繁體中文',
    '简体中文',
    'English']
language_prompts = [
    '- 使用繁體中文',
    '- 使用简体中文',
    '- Use English.']
subheader_texts = [
    "財經時事或網站客服問題，試試：請介紹MM Max方案",
    "财经时事或网站客服问题，试试：请介绍MM Max方案",
    "Financial news or website customer service issues, try: Please introduce MM Max"]
subdomains = [
    'www',
    'sc',
    'en']
lang_routes = [
    'zh-tw',
    'zh-cn',
    'en-001']

with st.sidebar:
    st.title('👩🏻‍💼 MM Madam')
    st.link_button('系統提示詞共筆，原則只增不刪，如需刪除請以註解方式說明原因，編輯同時問答立即生效，無需重新整理此網頁', 'https://docs.google.com/document/d/1HOS7nntBTgfuSlUpHgDIfBed5M_bq4dH0H8kqXUO9PE/edit?usp=sharing', icon='📝')
    st.link_button('請協助使用優化過的系統提示詞，對題庫進行一輪實測，到GitHub Gist下方comment，提供AI專案會議討論', 'https://docs.google.com/spreadsheets/d/1pe3d54QEyU0xQ_vJe_308UK9FzLYQJl7EQZkSyYgLeA/edit?usp=sharing', icon='💬')
    '---'
    site_language = st.radio('網站語系', site_languages, horizontal=True)
    is_paid_user = st.toggle('💎 付費用戶', value=True)
    has_chart = st.toggle('📊 MM圖表', value=is_paid_user, disabled=not is_paid_user)
    has_quickie = st.toggle(f'💡 MM短評', value=is_paid_user, disabled=not is_paid_user)
    has_blog = st.toggle(f'📝 MM部落格', value=is_paid_user, disabled=not is_paid_user)
    has_edm = st.toggle(f'📮 MM獨家報告', value=is_paid_user, disabled=not is_paid_user)
    has_podcast = st.toggle(f'🎙️ MM Podcast', value=is_paid_user, disabled=not is_paid_user)
    has_stock_etf = st.toggle('📈 MM美股財報、ETF專區', value=True)
    has_hc = st.toggle('❓ MM幫助中心', value=True)
    has_search = st.toggle('🔍 Google搜尋', value=True)
    has_memory = st.toggle('🧠 記得前五次問答', value=False)
    '---'
    # Use chat_logic_price for the selectbox, and DEFAULT_MODEL as the default selection
    # The model variable here will hold the name of the selected model, e.g., 'gemini-1.0-pro'
    model_name_selected = st.selectbox(
        'Model',
        options=list(chat_logic_price.keys()), # Corrected typo here from ऑप्शन्स to options
        index=list(chat_logic_price.keys()).index(DEFAULT_MODEL) if DEFAULT_MODEL in chat_logic_price else 0
    )
subdomain = dict(zip(site_languages, subdomains))[site_language]
if has_memory:
    # include and display the last 5 turns of conversation before the current turn
    st.session_state.contents = st.session_state.contents[-10:]
    for content in st.session_state.contents:
        with st.chat_message(content.role, avatar=None if content.role == "user" else '👩🏻‍💼'):
            st.markdown(content.parts[0].text)
else:
    # initialize the conversation history when has_memory defaults to False
    # clear the conversation history
    st.session_state.contents = []

client = genai.Client(api_key=st.secrets['GEMINI_API_KEY'])
def get_started():
    st.session_state.get_started = ...
if 'get_started' not in st.session_state:
    with st.container():
        subheader_text = dict(zip(site_languages, subheader_texts))[site_language]
        st.subheader(subheader_text)
        user_prompt = st.chat_input('Ask Madam', on_submit=get_started)
else:
    # When st.chat_input is used in the main body of an app, it will be pinned to the bottom of the page.
    user_prompt = st.chat_input('Ask Madam')

if 'knowledge' not in st.session_state:
    # Load knowledge data using the function from chat_logic.py
    # The 'after' date is handled by the default argument in load_knowledge_data
    st.session_state.knowledge = load_knowledge_data()

if user_prompt:
    # Reset token counts at the beginning of a new user interaction
    reset_token_counts()
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])) # user_prompt is the text from chat_input

    # Pass client and selected model_name to these functions from chat_logic
    try:
        # user_prompt is the text from st.chat_input
        site_language_idx = get_user_prompt_lang(user_prompt, client, model_name_selected)
        site_language = site_languages[site_language_idx]
        
        # For get_user_prompt_type, pass the relevant part of session history
        history_for_type_check = st.session_state.contents[-2:] if len(st.session_state.contents) >= 2 else st.session_state.contents
        user_prompt_type_pro = get_user_prompt_type(history_for_type_check, client, model_name_selected)
        
    except Exception as e:
        st.code(f"Error analyzing user prompt: {e}")
        st.stop()
        
    base_system_prompt = requests.get(st.secrets['SYSTEM_PROMPT_URL']).text
    
    # Call construct_system_prompt from chat_logic.py
    system_prompt, display_messages = construct_system_prompt(
        base_system_prompt=base_system_prompt,
        user_prompt_text=user_prompt, # The user's text input
        user_prompt_type_pro=user_prompt_type_pro,
        is_paid_user=is_paid_user,
        subdomain=subdomain,
        site_language=site_language, # String like "繁體中文"
        site_languages=site_languages, # List of language names
        language_prompts=language_prompts, # List of language-specific prompt additions
        lang_routes=lang_routes, # List of language route codes like 'zh-tw'
        knowledge_base=st.session_state.knowledge,
        client=client,
        model_name=model_name_selected,
        has_chart=has_chart,
        has_quickie=has_quickie,
        has_blog=has_blog,
        has_edm=has_edm,
        has_podcast=has_podcast,
        has_stock_etf=has_stock_etf,
        has_hc=has_hc,
        has_search=has_search,
        html_content_loader_func=load_html_file_content
    )

    # Display messages returned by construct_system_prompt (errors, badge info)
    for msg in display_messages:
        if msg['type'] == 'code':
            st.code(msg['content'])
        elif msg['type'] == 'badge':
            st.badge(msg['text'], icon=msg.get('icon'), color=msg.get('color', "blue"))
            # If badge content also needs st.code for IDs, that needs to be handled
            # For now, assuming badge text is self-contained or construct_system_prompt formats it fully.
            # The current construct_system_prompt returns badge text like "Relevant Chart IDs for key: [ids]"
            # This might be too long for st.badge's main text.
            # A better approach might be for construct_system_prompt to return structured data for badges,
            # e.g. {'type': 'badge', 'title': 'Chart IDs', 'key': csv_key, 'ids': ids_for_display}
            # For now, let's keep it simple and assume the text is suitable or st.code is used for long parts.
            # The current implementation in construct_system_prompt appends "Relevant ... IDs for {csv_key}: {ids_for_display}"
            # to display_messages. This will be displayed by st.badge.

    st.badge('此次問答採用的系統提示詞', icon="📝", color="blue") # This shows the user the final system prompt
    st.text_area("System Prompt", system_prompt, height=200) # Using st.text_area for better display of long prompts
    '---'
    response_type = 'text/plain'
    response_schema = None
    tools = None # Tools for final content generation, not for retrieval.
    try:
        # Call generate_content from chat_logic for the final response
        # user_prompt is the original user input text
        final_response = generate_content(user_prompt, system_prompt, response_type, response_schema, tools, client, model_name_selected)
        response_text = final_response.text
        # Call remove_invalid_urls from chat_logic
        response_text = remove_invalid_urls(response_text) # remove_invalid_urls is from chat_logic
    except Exception as e:
        st.code(f"Error generating final response: {e}")
        st.stop() # Stop execution if final response generation fails
    # The finally block should ideally be outside the try if it must run regardless of st.stop()
    # However, st.stop() halts script execution, so finally might not run as expected if st.stop() is called.
    # For robust logging, consider moving GIST update before potential st.stop() or use a different mechanism.

    # This part will only be reached if no st.stop() was called in the try block.
    with st.chat_message("assistant", avatar='👩🏻‍💼'):
        st.markdown(response_text)
    st.session_state.contents.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))

    # Use cost function from chat_logic, passing the selected model_name
        # prompt_token_count and candidates_token_count are now imported at the top.
        st.badge(f'{prompt_token_count} input tokens + {candidates_token_count} output tokens ≒ {cost(model_name_selected)} USD ( when Google Search < 1500 Requests/Day )', icon="💰", color="green")

        GITHUB_GIST_API = st.secrets['GITHUB_GIST_API']
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {st.secrets['GITHUB_ACCESS_TOKEN']}",
            "X-GitHub-Api-Version": "2022-11-28"}
        r = requests.get(GITHUB_GIST_API, headers=headers)
        if r.status_code == 200:
            chat_log = r.json()['files']['madam-log.md']['content']
            chat_log += st.session_state.contents[-2].parts[0].text + '\n---\n' + response_text + '\n\n---\n'
            payload = {'files': {'madam-log.md': {"content": chat_log}}}
            r = requests.patch(GITHUB_GIST_API, headers=headers, json=payload)