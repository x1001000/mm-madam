import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import glob
import requests
import re

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
    return round((prompt_token_count * price[model]['input'] + candidates_token_count * price[model]['output'])/1e6, 3)

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
    system_prompt = 'Given a user query, identify its language as one of the three: zh-tw, zh-cn, other'
    response_type = 'application/json'
    response_schema = str # int does not work
    tools = None
    try:
        response_parsed = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).parsed
        # response_parsed
        return {'zh-tw': 0, 'zh-cn': 1, 'other': 2}[response_parsed.lower()]
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()

# 2nd API call
def get_user_prompt_type():
    user_prompt = st.session_state.contents[-2:]
    system_prompt = '問答內容最接近哪一類（二選一）：財經時事類、網站客服及其他類'
    response_type = 'application/json'
    response_schema = str # int does not work
    tools = None
    try:
        response_parsed = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).parsed
        # response_parsed
        return {'財經時事類': True, '網站客服及其他類': False}[response_parsed]
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
        st.badge('檢索csv資料中相關id，再用id查詢語料', icon="🔍", color="blue")
        st.code(csv_df_json.replace('df.iloc[:,:2].to_json', str(response_parsed)))
        return response_parsed
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()

def get_retrieval(csv_file):
    if ids := get_relevant_ids(csv_file + ' => df.iloc[:,:2].to_json'):
        if user_prompt_type_pro:
            df = st.session_state.knowledge[csv_file]
            df = df[df['id'].isin(ids)]
        else:
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

def remove_invalid_urls(response_text):
    urls = re.findall(r'http[^\s)]*', response_text)
    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                response_text = response_text.replace(url, '')
        except:
            response_text = response_text.replace(url, '')
    return response_text

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
    st.session_state.knowledge = {}
    for csv_file in glob.glob('knowledge/*.csv') + glob.glob('knowledge/*/*/*.csv'):
        df = pd.read_csv(csv_file)
        # quickie, blog, edm
        if 'date' in df.columns:
            df = df[df['date'] > after]
        st.session_state.knowledge[csv_file] = df
        st.session_state.knowledge[csv_file + ' => df.iloc[:,:2].to_json'] = df.iloc[:,:2].to_json(orient='records', force_ascii=False)
    md = ''
    for md_file in glob.glob('knowledge/*.md'):
        with open(md_file) as f:
            md += ''.join(f.readlines()) + '\n\n---\n'
    st.session_state.knowledge['podcast'] = md

if user_prompt:
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]))

    site_language = site_languages[get_user_prompt_lang()]
    system_prompt = requests.get(st.secrets['SYSTEM_PROMPT_URL']).text
    user_prompt_type_pro = get_user_prompt_type()
    if user_prompt_type_pro:
        if not is_paid_user:
            system_prompt += f"""
- 你會鼓勵用戶升級成為付費用戶就能享有完整問答服務，並且提供訂閱方案連結
```
https://{subdomain}.macromicro.me/subscribe
```
"""
        if has_chart:
            if retrieval := get_retrieval(glob.glob('knowledge/chart-*.csv')[0]):
                system_prompt += f"""
- MM圖表的資料，當中時間序列最新兩筆數據（series_last_rows）很重要，務必引用
```
{retrieval}
網址規則 https://{subdomain}.macromicro.me/charts/{{id}}/{{slug}}
```
"""
        if has_quickie and site_language in site_languages[:2]:
            if retrieval := get_retrieval(glob.glob('knowledge/quickie-*.csv')[0]):
                system_prompt += f"""
- MM短評的資料
```
{retrieval}
網址規則 https://{subdomain}.macromicro.me/quickie?id={{id}}
```
"""
        if has_blog and site_language in site_languages[:2]:
            if retrieval := get_retrieval(glob.glob('knowledge/blog-*.csv')[0]):
                system_prompt += f"""
- MM部落格的資料
```
{retrieval}
網址規則 https://{subdomain}.macromicro.me/blog/{{slug}}
```
"""
        if has_blog and site_language == 'English':
            if retrieval := get_retrieval(glob.glob('knowledge/blog_en-*.csv')[0]):
                system_prompt += f"""
- MM部落格的資料
```
{retrieval}
網址規則 https://{subdomain}.macromicro.me/blog/{{slug}}
```
"""
        if has_edm and site_language in site_languages[:2]:
            if retrieval := get_retrieval(glob.glob('knowledge/edm-*.csv')[0]):
                system_prompt += f"""
- MM獨家報告的資料
```
{retrieval}
網址規則 https://{subdomain}.macromicro.me/mails/edm/{'tc' if site_language[0] == '繁' else 'sc'}/display/{{id}}
```
"""
        if has_podcast:
            system_prompt += f"""
- MM Podcast( https://podcasts.apple.com/tw/podcast/macromicro-財經m平方/id1522682178 )的資料
```
{st.session_state.knowledge['podcast']}
```
"""
        if has_stock_etf:
            system_prompt += f"""
- MM美股財報、ETF專區
```
美股財報資料網址規則 https://{subdomain}.macromicro.me/stocks/info/{{ticker_symbol}}
美國ETF專區網址規則 https://{subdomain}.macromicro.me/etf/us/intro/{{ticker_symbol}}
台灣ETF專區網址規則 https://{subdomain}.macromicro.me/etf/tw/intro/{{ticker_symbol}}
```
"""
        if has_search:
            if retrieval := get_retrieval_from_google_search():
                system_prompt += f"""
- 網路搜尋的資料
```
{retrieval}
```
"""
    else:
        if has_hc:
            lang_route = dict(zip(site_languages, lang_routes))[site_language]
            if retrieval := get_retrieval(f'knowledge/hc/{lang_route}/_log.csv'):
                system_prompt += f"""
- MM幫助中心的資料
```
{retrieval}
網址規則 https://support.macromicro.me/hc/{lang_route}/articles/{{id}}
不要提供來信或來電的客服聯繫方式
```
"""
            else:
                system_prompt += f"""
- 提供用戶MM幫助中心網址 https://support.macromicro.me/hc/{lang_route}
"""
        else:
            system_prompt += f"""
- 提供用戶MM幫助中心網址 https://support.macromicro.me/hc/{lang_route}
"""
        system_prompt += f"""
- 若非網站客服相關問題，你會婉拒回答
"""
    st.badge('此次問答採用的系統提示詞', icon="📝", color="blue")
    system_prompt += dict(zip(site_languages, language_prompts))[site_language]
    system_prompt
    '---'
    response_type = 'text/plain'
    response_schema = None
    tools = None
    try:
        response_text = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).text
        response_text = remove_invalid_urls(response_text)
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