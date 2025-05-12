import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import glob
import requests

from pydantic import BaseModel, Field
class UserPromptLanguage(BaseModel):
    language: str = Field(description="The language of the user prompt. Please note: Chinese is divided into Traditional Chinese and Simplified Chinese.")
class UserPromptType(BaseModel):
    type: int = Field(description="The type of the user prompt. 1: Economics, Finance, Market, News, 2: Customer Service, 3: Other")

# to update
after = '2025-04-01'
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

def generate_content(user_prompt, system_prompt, response_type, response_schema, tools):
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type=response_type,
            response_schema=response_schema,
            tools=tools,
        )
    )
    accumulate_token_count(response.usage_metadata)
    return response

# 1st API call
def get_user_prompt_lang():
    system_prompt = None
    response_type = 'application/json'
    response_schema = UserPromptLanguage
    tools = None
    try:
        response_parsed = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).parsed.language
        st.code('用戶提問使用的語言：' + response_parsed)
        return response_parsed
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()

# 2nd API call
def get_user_prompt_type():
    user_prompt = st.session_state.contents[-2:]
    system_prompt = None
    response_type = 'application/json'
    response_schema = UserPromptType
    tools = None
    try:
        response_parsed = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).parsed.type
        st.code({1: '用戶提問主要關於財經', 2: '用戶提問主要關於客服', 3: '用戶提問與財經或客服無關'}[response_parsed])
        return response_parsed
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()

# 3rd ~ 7th API calls
def get_relevant_ids(csv_df_json):
    system_prompt = 'Given a user query, identify up to 5 of the most relevant IDs in the JSON below.\n'
    system_prompt += st.session_state.knowledge[csv_df_json]
    response_type = 'application/json'
    response_schema = list[int]
    tools = None
    try:
        response_parsed = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).parsed
        st.code(csv_df_json.replace('df.iloc[:,:2].to_json', str(response_parsed)))
        return response_parsed
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()

def get_retrieval(csv_file):
    if ids := get_relevant_ids(csv_file + ' => df.iloc[:,:2].to_json'):
        if user_prompt_type == 1:
            df = st.session_state.knowledge[csv_file]
            df = df[df['id'].isin(ids)]
        if user_prompt_type == 2:
            df = pd.DataFrame(columns=['id', 'html'])
            df['id'] = ids
            htmls = []
            for _id in ids:
                with open(csv_file.replace('_log', str(_id)).replace('csv', 'html')) as f:
                    htmls.append(''.join(f.readlines()))
            df['html'] = htmls
        return df.to_json(orient='records', force_ascii=False)

# 8th API call
def get_retrieval_from_google_search():
    system_prompt = None
    response_type = 'text/plain'
    response_schema = None
    tools = [types.Tool(google_search=types.GoogleSearch())]
    try:
        response_text = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).text
        return response_text
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()

# 10th ~ 11th API calls
def add_hyperlink(user_prompt):
    system_prompt = f'''將輸入的文本中提到的美股、美國ETF、台灣ETF的網址，依序加入陣列，輸出JSON
    美股網址規則 https://{subdomain}.macromicro.me/stocks/info/{{ticker_symbol}}
    美國ETF網址規則 https://{subdomain}.macromicro.me/etf/us/intro/{{ticker_symbol}}
    台灣ETF網址規則 https://{subdomain}.macromicro.me/etf/tw/intro/{{ticker_symbol}}'''
    response_type = 'application/json'
    response_schema = list[str]
    tools = None
    try:
        response_parsed = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).parsed
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()
    valid_urls = []
    for url in response_parsed:
        if 'stocks/info' in url or 'etf/us/intro' in url or 'etf/tw/intro' in url:
            if requests.get(url).status_code == 200:
                valid_urls.append(url)
    if valid_urls:
        system_prompt = '將輸入的文本中提到的美股、美國ETF、台灣ETF，使用以下網址，製成markdown超連結，其餘一字不改回傳。\n' + '\n'.join(valid_urls)
    else:
        return user_prompt
    st.code(system_prompt)
    response_type = 'text/plain'
    response_schema = None
    tools = None
    try:
        response_text = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).text
        return response_text
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()

site_languages = [
    '繁體中文',
    '简体中文',
    'English']
subheader_texts = [
    "財經時事相關問題，例如：美債殖利率為何飆升？",
    "财经时事相关问题，例如：美债收益率为何飙升？",
    "Financial and economic questions, e.g.: Why are US Treasury yields surging?"]
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
    st.markdown('---')
    site_language = st.radio('網站語系', site_languages, horizontal=True)
    is_paid_user = st.toggle('💎 付費用戶', value=True)
    has_chart = st.toggle('📊 MM圖表', value=is_paid_user, disabled=not is_paid_user)
    has_quickie = st.toggle(f'💡 MM短評', value=is_paid_user, disabled=not is_paid_user)
    has_blog = st.toggle(f'📝 MM部落格', value=is_paid_user, disabled=not is_paid_user)
    has_edm = st.toggle(f'📮 MM獨家報告', value=is_paid_user, disabled=not is_paid_user)
    has_hyperlink = st.toggle('📈 MM美股、美國ETF、台灣ETF（連結）', value=True)
    has_hc = st.toggle('❓ MM幫助中心', value=True)
    has_search = st.toggle('🔍 Google搜尋', value=True)
    has_memory = st.toggle('🧠 記得前五次問答', value=False)
    st.markdown('---')
    model = st.selectbox('Model', price.keys())
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

def get_started():
    st.session_state.get_started = ...
if 'get_started' not in st.session_state:
    with st.container():
        subheader_text = dict(zip(site_languages, subheader_texts))[site_language]
        st.subheader(subheader_text)
        user_prompt = st.chat_input('Ask Madam', on_submit=get_started)
else:
    client = genai.Client(api_key=st.secrets['GEMINI_API_KEY'])
    # When st.chat_input is used in the main body of an app, it will be pinned to the bottom of the page.
    user_prompt = st.chat_input('Ask Madam')

if 'knowledge' not in st.session_state:
    st.session_state.knowledge = {}
    for csv_file in glob.glob('knowledge/*.csv') + glob.glob('knowledge/*/*/*.csv'):
        df = pd.read_csv(csv_file)
        # quickie, blog, edm
        if 'date' in df.columns:
            df = df[df['date'] > after]
        st.session_state.knowledge[csv_file] = df
        st.session_state.knowledge[csv_file + ' => df.iloc[:,:2].to_json'] = df.iloc[:,:2].to_json(orient='records', force_ascii=False)

if user_prompt:
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]))

    user_prompt_lang = get_user_prompt_lang()
    user_prompt_type = get_user_prompt_type()
    system_prompt = requests.get(st.secrets['SYSTEM_PROMPT_URL']).text.format(user_prompt_lang, user_prompt_lang)
    if user_prompt_type == 1:
        if not is_paid_user:
            system_prompt += f'\n\n- 你會鼓勵用戶升級成為付費用戶就能享有完整問答服務，並且提供訂閱方案連結 https://{subdomain}.macromicro.me/subscribe'
        if has_chart:
            if retrieval := get_retrieval(glob.glob('knowledge/chart-*.csv')[0]):
                system_prompt += f'\n\n- MM圖表的資料，當中時間序列最新兩筆數據（series_last_rows）很重要，務必引用\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/charts/{{id}}/{{slug}}'
        if has_quickie and site_language in site_languages[:2]:
            if retrieval := get_retrieval(glob.glob('knowledge/quickie-*.csv')[0]):
                system_prompt += f'\n\n- MM短評的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/quickie?id={{id}}'
        if has_blog and site_language in site_languages[:2]:
            if retrieval := get_retrieval(glob.glob('knowledge/blog-*.csv')[0]):
                system_prompt += f'\n\n- MM部落格的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/blog/{{slug}}'
        if has_blog and site_language == 'English':
            if retrieval := get_retrieval(glob.glob('knowledge/blog_en-*.csv')[0]):
                system_prompt += f'\n\n- MM部落格的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/blog/{{slug}}'
        if has_edm and site_language in site_languages[:2]:
            if retrieval := get_retrieval(glob.glob('knowledge/edm-*.csv')[0]):
                system_prompt += f'\n\n- MM獨家報告的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/mails/edm/{'tc' if site_language[0] == '繁' else 'sc'}/display/{{id}}'
        # if has_stocks:
        #     system_prompt += f'\n\n- 若用戶或你提及美國上市公司，你會提供MM美股財報資料庫中該公司的網頁 https://{subdomain}.macromicro.me/stocks/info/{{股票代號}}'
        if has_search:
            if retrieval := get_retrieval_from_google_search():
                system_prompt += f'\n\n- 網路搜尋的資料\n```{retrieval}```'
    if user_prompt_type == 2:
        if has_hc:
            lang_route = dict(zip(site_languages, lang_routes))[site_language]
            if retrieval := get_retrieval(f'knowledge/hc/{lang_route}/_log.csv'):
                system_prompt += f'\n\n- MM幫助中心的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://support.macromicro.me/hc/{lang_route}/articles/{{id}}'
                system_prompt += '\n不要提到來信或來電聯繫的做法，只有當用戶詢問客服信箱時，才會告知 support@macrmicro.me'
            else:
                system_prompt += '\n- 提供用戶MM幫助中心網址 https://support.macromicro.me/hc/{lang_route}'
        else:
            system_prompt += '\n- 提供用戶MM幫助中心網址 https://support.macromicro.me/hc/{lang_route}'
    if user_prompt_type == 3:
        system_prompt += '\n- 若非財經時事相關問題，你會婉拒回答'
    st.code(system_prompt)
    response_type = 'text/plain'
    response_schema = None
    tools = None
    try:
        response_text = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).text
        if has_hyperlink:
            response_text = add_hyperlink(response_text)
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()
    finally:
        with st.chat_message("assistant", avatar='👩🏻‍💼'):
            st.markdown(response_text)
        st.session_state.contents.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))

        st.badge(f'{prompt_token_count} input tokens + {candidates_token_count} output tokens ≒ {cost()} USD ( when Google Search < 1500 Requests/Day )', icon="💰", color="green")

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