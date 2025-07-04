import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import glob
import requests
import re

# MANUALLY MONTHLY UPDATE
AFTER_DATE = '2025-06-01'
PRICE = {
    # 'gemini-2.5-flash-lite-preview-06-17': {'input': 0.1, 'output': 0.4, 'thinking': 0.4, 'caching': 0.025}, TOO SMALL
    'gemini-2.5-flash': {'input': 0.3, 'output': 2.5, 'thinking': 2.5, 'caching': 0.075},
    'gemini-2.5-pro-preview-06-05': {'input': 1.25, 'output': 10, 'thinking': 10, 'caching': 0.31},
}

prompt_token_count = 0
candidates_token_count = 0
cached_content_token_count = 0
thoughts_token_count = 0
tool_use_prompt_token_count = 0
total_token_count = 0
def accumulate_token_count(usage_metadata):
    global prompt_token_count, candidates_token_count, cached_content_token_count, thoughts_token_count, tool_use_prompt_token_count, total_token_count
    prompt_token_count += usage_metadata.prompt_token_count
    candidates_token_count += usage_metadata.candidates_token_count
    cached_content_token_count += usage_metadata.cached_content_token_count or 0
    thoughts_token_count += usage_metadata.thoughts_token_count or 0
    tool_use_prompt_token_count += usage_metadata.tool_use_prompt_token_count or 0
    total_token_count += usage_metadata.total_token_count
def cost():
    return round((
        prompt_token_count * PRICE[model]['input'] + 
        candidates_token_count * PRICE[model]['output'] + 
        cached_content_token_count * PRICE[model]['caching'] + 
        thoughts_token_count * PRICE[model]['thinking']) / 1e6, 3)

def generate_content(user_prompt, system_prompt, response_type, response_schema, tools, thinking_config=None):
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type=response_type,
            response_schema=response_schema,
            tools=tools,
            thinking_config=thinking_config,
        )
    )
    accumulate_token_count(response.usage_metadata)
    return response

# 1st API call
def get_site_language_idx():
    system_prompt = 'Given a user query, identify its language code'
    response_type = 'application/json'
    response_schema = str # int does not work
    tools = None
    try:
        response_parsed = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).parsed
        lang_idx_map = {
            'zh': 0,
            'zh-tw': 0, 'tw': 0,
            'zh-cn': 1, 'cn': 1,
            }
        site_language_idx = lang_idx_map.get(response_parsed.lower(), 2)
        return site_language_idx # site_language = 'English' for other languages
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()

# 2nd API call
def get_user_prompt_type():
    user_prompt = st.session_state.contents[-2:]
    system_prompt = '用戶輸入分類（二選一）：總經財經時事類、網站客服或其他類'
    response_type = 'application/json'
    response_schema = str # int does not work
    tools = None
    try:
        response_parsed = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).parsed
        # response_parsed
        return True if response_parsed == '總經財經時事類' else False
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()

# 3rd ~ 7th API calls
def get_relevant_ids(csv_df_json):
    system_prompt = 'Given a user query, identify up to 5 of the most relevant IDs in the JSON below.\n'
    system_prompt += knowledge[csv_df_json]
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

def get_retrieval_from_charts_data_api(csv_file):
    if ids := get_relevant_ids(csv_file + ' => df.iloc[:,:2].to_json'):
        data = []
        for _id in ids:
            r = requests.get(f'{st.secrets['CHARTS_DATA_API']}/{_id}')
            d = r.json()
            series = d['data'][f'c:{_id}']['series']
            for i in range(len(series)):
                series[i] = series[i][-2:]
            data.append(d['data'][f'c:{_id}'])
        return json.dumps(d['data'][f'c:{_id}'], ensure_ascii=False)

def get_retrieval(csv_file):
    if ids := get_relevant_ids(csv_file + ' => df.iloc[:,:2].to_json'):
        df = knowledge[csv_file]
        df = df[df['id'].isin(ids)]
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

def google_search_site(query):
    results = []
    from googlesearch import search
    for result in search(f"{query} site:macromicro.me", advanced=True):
        results.append(f'[{result.title}]({result.url})')
    return '\n\n'.join(results)
function_declarations = [
    types.FunctionDeclaration(
        name='google_search_site',
        description='Search Google for a query on macromicro.me site',
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to use when searching macromicro.me site",
                },
            },
            "required": ["query"],
        },
    ),
]

def get_retrieval_from_help_center(csv_file):
    if ids := get_relevant_ids(csv_file + ' => df.iloc[:,:2].to_json'):
        df = pd.DataFrame(columns=['id', 'html'])
        df['id'] = ids
        htmls = []
        for _id in ids:
            with open('knowledge/' + csv_file.replace('_log', str(_id)).replace('csv', 'html')) as f:
                htmls.append(''.join(f.readlines()))
        df['html'] = htmls
        return df.to_json(orient='records', force_ascii=False)

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
    has_hc = st.toggle('❓ MM幫助中心', value=True)
    has_search = st.toggle('🔍 Google搜尋', value=True)
    has_memory = st.toggle('🧠 記得前五次問答', value=False)
    '---'
    model = st.selectbox('Model', PRICE.keys())
    st.link_button('Gemini API Pricing', 'https://ai.google.dev/gemini-api/docs/pricing', icon='💰')

# initialize the conversation history
if 'contents' not in st.session_state:
    st.session_state.contents = []
if has_memory:
    # include and display the last 5 turns of conversation before the current turn
    st.session_state.contents = st.session_state.contents[-10:]
    for content in st.session_state.contents:
        with st.chat_message(content.role, avatar=None if content.role == "user" else '👩🏻‍💼'):
            st.markdown(content.parts[0].text)
else:
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

@st.cache_data
def get_knowledge():
    knowledge = {}
    knowledge_csv_api = st.secrets['KNOWLEDGE_CSV_API']
    csv_files = [
        'knowledge/chart.csv',
        f'{knowledge_csv_api}/quickie.csv',
        f'{knowledge_csv_api}/post.csv',
        f'{knowledge_csv_api}/post_en.csv',
        f'{knowledge_csv_api}/edm.csv',
        ] + glob.glob('knowledge/hc/*/_log.csv')
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        # quickie, blog, edm
        if 'date' in df.columns:
            df = df[df['date'] > AFTER_DATE]
        csv_file = csv_file.split('knowledge/')[-1].split('csv/')[-1]
        knowledge[csv_file] = df
        knowledge[csv_file + ' => df.iloc[:,:2].to_json'] = df.iloc[:,:2].to_json(orient='records', force_ascii=False)
    return knowledge
knowledge = get_knowledge()

if user_prompt:
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]))

    site_language = site_languages[get_site_language_idx()]
    subdomain = dict(zip(site_languages, subdomains))[site_language]
    system_prompt = requests.get(st.secrets['SYSTEM_PROMPT_URL']).text
    user_prompt_type_pro = get_user_prompt_type()
    if user_prompt_type_pro:
        if is_paid_user:
            st.badge('此次問答檢索的MM文本', icon="🔍", color="blue")
        else:
            system_prompt += '- 你會鼓勵用戶升級成為付費用戶就能享有完整問答服務，並且提供訂閱方案連結  \n'
            system_prompt += f'`https://{subdomain}.macromicro.me/subscribe`  \n'
        if has_chart:
            if retrieval := get_retrieval_from_charts_data_api('chart.csv'):
                system_prompt += '- MM圖表的資料，當中時間序列（series）包含前值及最新數據，務必引用  \n'
                system_prompt += f'網址規則 `https://{subdomain}.macromicro.me/charts/{{id}}/{{slug}}`  \n'
                system_prompt += f'```\n{retrieval}\n```\n'
        if has_quickie:
            if retrieval := get_retrieval('quickie.csv'):
                system_prompt += '- MM短評的資料  \n'
                system_prompt += f'網址規則 `https://{'www' if subdomain == 'en' else subdomain}.macromicro.me/quickie?id={{id}}`  \n'
                system_prompt += f'```\n{retrieval}\n```\n'
        if has_blog:
            if retrieval := get_retrieval('post.csv'):
                system_prompt += '- MM部落格的資料  \n'
                system_prompt += f'網址規則 `https://{'www' if subdomain == 'en' else subdomain}.macromicro.me/blog/{{slug}}`  \n'
                system_prompt += f'```\n{retrieval}\n```\n'
            if retrieval := get_retrieval('post_en.csv'):
                system_prompt += '- MM英文部落格的資料  \n'
                system_prompt += f'網址規則 `https://en.macromicro.me/blog/{{slug}}`  \n'
                system_prompt += f'```\n{retrieval}\n```\n'
        if has_edm:
            if retrieval := get_retrieval('edm.csv'):
                system_prompt += '- MM獨家報告的資料  \n'
                # system_prompt += f'網址規則 `https://{subdomain}.macromicro.me/mails/edm/{'tc' if site_language[0] == '繁' else 'sc'}/display/{{id}}`  \n' if subdomain != 'en' else ''
                system_prompt += f'```\n{retrieval}\n```\n'
        if has_search:
            if retrieval := get_retrieval_from_google_search():
                system_prompt += '- 網路搜尋的資料  \n'
                system_prompt += f'```\n{retrieval}\n```\n'
    else:
        if has_hc:
            lang_route = dict(zip(site_languages, lang_routes))[site_language]
            if retrieval := get_retrieval_from_help_center(f'hc/{lang_route}/_log.csv'):
                system_prompt += '- MM幫助中心的資料  \n'
                system_prompt += '不要提供來信或來電的客服聯繫方式  \n'
                system_prompt += f'網址規則 `https://support.macromicro.me/hc/{lang_route}/articles/{{id}}`  \n'
                system_prompt += f'```\n{retrieval}\n```\n'
        system_prompt += f'- MM幫助中心網址 `https://support.macromicro.me/hc/{lang_route}`  \n'
        system_prompt += '- 若非網站客服相關問題，你會婉拒回答  \n'

    system_prompt += f'- `subdomain = "{subdomain}"`\n'
    system_prompt += f'- You MUST NOT reference to any edm{', quickie and blog' if subdomain == 'en' else ''}.\n'
    system_prompt += f'- You MUST respond in {site_language}, regardless of the language used in this system prompt.\n'
    st.badge('此次問答輸入的系統提示詞', icon="📝", color="blue")
    system_prompt
    '---'
    response_type = 'text/plain'
    response_schema = None
    # tools = [types.Tool(function_declarations=function_declarations)]
    tools = None
    try:
        response = generate_content(user_prompt, system_prompt, response_type, response_schema, tools, thinking_config=types.ThinkingConfig(thinking_budget=2000))
        tool_call = response.candidates[0].content.parts[0].function_call
        if tool_call:
            if tool_call.name == 'google_search_site':
                response_text = google_search_site(**tool_call.args)
        else:
            response_text = response.text
        # response_text = remove_invalid_urls(response_text)    doesn't work due to cloudflare js challenge
        if subdomain == 'en':   # hard fix hallucination
            response_text = re.sub(r'https://(www|sc)\.macromicro', f'https://en.macromicro', response_text)
    except Exception as e:
        st.code(f"Errrr: {e}")
        st.stop()
    finally:
        with st.chat_message("assistant", avatar='👩🏻‍💼'):
            st.markdown(response_text)
        st.session_state.contents.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))

        st.badge(f'{prompt_token_count} input + {candidates_token_count} output + {thoughts_token_count} thinking + {cached_content_token_count} caching ≒ {cost()} USD ( when Google Search < 1500 Requests/Day )', icon="💰", color="green")

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
