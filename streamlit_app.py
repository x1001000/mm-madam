import streamlit as st
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Content, Part
import pandas as pd
import json
import glob
import requests

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

# 1st API call
def get_user_prompt_type() -> str:
    system_prompt = """
    用戶提問與下列選項何者最相關？
    1. 總體經濟、財經資訊、金融市場等相關知識或時事
    2. 財經M平方客戶服務、商務合作
    3. 其他
    回傳數字，無其他文字、符號
    """
    try:
        response = client.models.generate_content(
            model=model,
            contents=st.session_state.contents[-2:],
            config=GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="text/plain",
            )
        )
        result = response.text
        accumulate_token_count(response.usage_metadata)
    except Exception as e:
        st.code(f"Errrr: {e}")
        result = '3'
    finally:
        # MUST strip to remove \n
        result = result.strip()
        st.code({'1': '用戶提問主要關於財經', '2': '用戶提問主要關於客服', '3': '用戶提問與財經或客服無關'}[result])
        return result

# 2nd ~ 6th API calls
def get_relevant_ids(csv_df_json) -> str:
    system_prompt = 'Given a user query, identify up to 5 of the most relevant IDs in the JSON below. Output only the IDs, with no additional text.\n'
    system_prompt += st.session_state.knowledge[csv_df_json]
    try:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            )
        )
        result = response.text
        accumulate_token_count(response.usage_metadata)
    except Exception as e:
        st.code(f"Errrr: {e}")
        result = '[]'
    finally:
        st.code(csv_df_json.replace('df.iloc[:,:2].to_json', result))
        return result

def get_retrieval(csv_file) -> str:
    try:
        ids = json.loads(get_relevant_ids(csv_file + ' => df.iloc[:,:2].to_json'))
    except json.JSONDecodeError as e:
        st.code(f"JSONDecodeError: {e}")
        ids = None
    if ids:
        if type(ids[0]) is dict:
            ids = [int(_id['id']) for _id in ids]
        else:
            ids = [int(_id) for _id in ids]

        if user_prompt_type == '1':
            df = st.session_state.knowledge[csv_file]
            df = df[df['id'].isin(ids)]
        if user_prompt_type == '2':
            df = pd.DataFrame(columns=['id', 'html'])
            df['id'] = ids
            htmls = []
            for _id in ids:
                with open(csv_file.replace('_log', str(_id)).replace('csv', 'html')) as f:
                    htmls.append(''.join(f.readlines()))
            df['html'] = htmls
        return df.to_json(orient='records', force_ascii=False)
    else:
        return ''

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
    st.link_button('請協助使用優化過的系統提示詞，對題庫進行一輪實測，複製貼上AI生成答覆，提供AI專案會議討論', 'https://docs.google.com/spreadsheets/d/1pe3d54QEyU0xQ_vJe_308UK9FzLYQJl7EQZkSyYgLeA/edit?usp=sharing', icon='💬')
    st.markdown('---')
    site_language = st.radio('網站語系', site_languages, horizontal=True)
    is_paid_user = st.toggle('💎 付費用戶', value=True)
    has_chart = st.toggle('📊 MM圖表', value=is_paid_user, disabled=not is_paid_user)
    has_quickie = st.toggle(f'💡 MM短評', value=is_paid_user, disabled=not is_paid_user)
    has_blog = st.toggle(f'📝 MM部落格', value=is_paid_user, disabled=not is_paid_user)
    has_edm = st.toggle(f'📮 MM獨家報告', value=is_paid_user, disabled=not is_paid_user)
    has_stocks = st.toggle('📈 MM美股財報資料庫', value=True)
    has_hc = st.toggle('❓ MM幫助中心', value=True)
    has_search = st.toggle('🔍 Google搜尋', value=True)
    has_memory = st.toggle('🧠 記得前五次問答', value=False)
    st.markdown('---')
    model = st.selectbox('Model', price.keys())

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

system_prompt = requests.get(st.secrets['SYSTEM_PROMPT_URL']).text
if user_prompt:
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.contents.append(Content(role="user", parts=[Part.from_text(text=user_prompt)]))

    user_prompt_type = get_user_prompt_type()
    if user_prompt_type == '1':
        subdomain = dict(zip(site_languages, subdomains))[site_language]
        if not is_paid_user:
            system_prompt += f'\n- 你會鼓勵用戶升級成為付費用戶就能享有完整問答服務，並且提供訂閱方案連結 https://{subdomain}.macromicro.me/subscribe'
        if has_chart:
            if retrieval := get_retrieval(glob.glob('knowledge/chart-*.csv')[0]):
                system_prompt += f'\n- MM圖表的資料，當中時間序列最新兩筆數據（series_last_rows）很重要，務必引用\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/charts/{{id}}/{{slug}}'
        if has_quickie and site_language in site_languages[:2]:
            if retrieval := get_retrieval(glob.glob('knowledge/quickie-*.csv')[0]):
                system_prompt += f'\n- MM短評的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/quickie?id={{id}}'
        if has_blog and site_language in site_languages[:2]:
            if retrieval := get_retrieval(glob.glob('knowledge/blog-*.csv')[0]):
                system_prompt += f'\n- MM部落格的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/blog/{{slug}}'
        if has_blog and site_language == 'English':
            if retrieval := get_retrieval(glob.glob('knowledge/blog_en-*.csv')[0]):
                system_prompt += f'\n- MM部落格的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/blog/{{slug}}'
        if has_edm and site_language in site_languages[:2]:
            if retrieval := get_retrieval(glob.glob('knowledge/edm-*.csv')[0]):
                system_prompt += f'\n- MM獨家報告的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://{subdomain}.macromicro.me/mails/edm/{'tc' if site_language[0] == '繁' else 'sc'}/display/{{id}}'
        if has_stocks:
            system_prompt += f'\n- 若用戶或你提及美國上市公司，你會提供MM美股財報資料庫中該公司的網頁 https://{subdomain}.macromicro.me/stocks/info/{{股票代號}}'
        if has_search:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=GenerateContentConfig(
                        tools=[Tool(google_search=GoogleSearch())],
                        response_mime_type="text/plain",
                    ),
                )
                result = response.text
                accumulate_token_count(response.usage_metadata)
            except Exception as e:
                st.code(f"Errrr: {e}")
                result = ''
            finally:
                if retrieval := result:
                    system_prompt += f'\n- 網路搜尋的資料\n```{retrieval}```'
    if user_prompt_type == '2':
        if has_hc:
            lang_route = dict(zip(site_languages, lang_routes))[site_language]
            if retrieval := get_retrieval(f'knowledge/hc/{lang_route}/_log.csv'):
                system_prompt += f'\n- MM幫助中心的資料\n```{retrieval}```'
                system_prompt += f'\n網址規則 https://support.macromicro.me/hc/{lang_route}/articles/{{id}}'
            else:
                system_prompt += '\n- MM幫助中心無相關資料，請用戶來信 support@macromicro.me'
        else:
            system_prompt += '\n- MM幫助中心無相關資料，請用戶來信 support@macromicro.me'
    if user_prompt_type == '3':
        system_prompt += '\n- 若非財經時事相關問題，你會婉拒回答'
    st.code(system_prompt)
    # st.markdown(system_prompt)
    try:
        response = client.models.generate_content(
            model=model,
            contents=st.session_state.contents,
            config=GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="text/plain",
            ),
        )
        result = response.text
        accumulate_token_count(response.usage_metadata)
    except Exception as e:
        st.code(f"Errrr: {e}")
        result = '抱歉，請稍後再試。。。'
    finally:
        with st.chat_message("assistant", avatar='👩🏻‍💼'):
            st.markdown(result)
        st.session_state.contents.append(Content(role="model", parts=[Part.from_text(text=result)]))

        st.badge(f'{prompt_token_count} input tokens + {candidates_token_count} output tokens ≒ {cost()} USD ( when Google Search < 1500 Requests/Day )', icon="💰", color="green")

        hackmd_note_api = st.secrets['HACKMD_NOTE_API']
        headers = {f"Authorization": "Bearer {st.secrets['HACKMD_API_TOKEN']}"}
        r = requests.get(hackmd_note_api, headers=headers)
        if r.status_code == 200:
            payload = r.json()['content'] + '\n\n---\n\n'
            payload += st.session_state.contents[-2]['parts'][0]['text'] + '\n\n---\n\n' + result
            r = requests.patch(hackmd_note_api, headers=headers, json=payload)