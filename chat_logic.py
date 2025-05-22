import google.generativeai as genai
from google.generativeai import types as genai_types # Aliased to avoid conflict
import pandas as pd
import glob # Used by load_knowledge_data and construct_system_prompt
import requests 
import re 

# Price dictionary
price = {
    'gemini-2.0-flash': {'input': 0.1, 'output': 0.4},
    'gemini-2.5-flash-preview-04-17': {'input': 0.15, 'output': 0.6},
    'gemini-1.0-pro': {'input': 0.05, 'output': 0.15}
}
DEFAULT_MODEL = 'gemini-1.0-pro'

# Global token count variables
prompt_token_count = 0
candidates_token_count = 0
cached_content_token_count = 0
tool_use_prompt_token_count = 0
total_token_count = 0

def accumulate_token_count(usage_metadata):
    global prompt_token_count, candidates_token_count, cached_content_token_count, tool_use_prompt_token_count, total_token_count
    prompt_token_count += usage_metadata.prompt_token_count
    candidates_token_count += usage_metadata.candidates_token_count
    cached_content_token_count += getattr(usage_metadata, 'cached_content_token_count', 0) or 0
    tool_use_prompt_token_count += getattr(usage_metadata, 'tool_use_prompt_token_count', 0) or 0
    total_token_count += usage_metadata.total_token_count

def cost(model_name: str):
    global prompt_token_count, candidates_token_count
    if model_name not in price:
        raise ValueError(f"Model {model_name} not found in price dictionary.")
    input_cost = prompt_token_count * price[model_name]['input']
    output_cost = candidates_token_count * price[model_name]['output']
    return round((input_cost + output_cost) / 1e6, 3)

def generate_content(user_prompt_content, system_prompt, response_type, response_schema, tools, client, model_name: str = None):
    if model_name is None:
        model_name = DEFAULT_MODEL
    if client is None:
        raise ValueError("API client must be provided to generate_content.")
    if model_name not in price:
        original_model_name = model_name
        model_name = DEFAULT_MODEL
        print(f"Warning: Model '{original_model_name}' not found or not supported. Falling back to '{model_name}'.")
    
    api_model_name = f"models/{model_name}"
    try:
        response = client.generate_content(
            model=api_model_name,
            contents=user_prompt_content, 
            generation_config=genai_types.GenerationConfig(
                system_instruction=system_prompt,
                response_mime_type=response_type,
                response_schema=response_schema,
            ),
            tools=tools
        )
        accumulate_token_count(response.usage_metadata)
        return response
    except Exception as e:
        print(f"Error in generate_content: {e}")
        raise

def reset_token_counts():
    global prompt_token_count, candidates_token_count, cached_content_token_count, tool_use_prompt_token_count, total_token_count
    prompt_token_count = 0
    candidates_token_count = 0
    cached_content_token_count = 0
    tool_use_prompt_token_count = 0
    total_token_count = 0

def load_knowledge_data(after_date='2025-04-01'):
    knowledge_base = {}
    for csv_file in glob.glob('knowledge/*.csv') + glob.glob('knowledge/*/*/*.csv'):
        df = pd.read_csv(csv_file)
        if 'date' in df.columns:
            df = df[df['date'] > after_date]
        knowledge_base[csv_file] = df
        knowledge_base[csv_file + ' => df.iloc[:,:2].to_json'] = df.iloc[:,:2].to_json(orient='records', force_ascii=False)
    md_content = ''
    for md_file in glob.glob('knowledge/*.md'):
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content += f.read() + '\n\n---\n'
    knowledge_base['podcast'] = md_content
    return knowledge_base

# --- Retrieval Functions ---
def remove_invalid_urls(response_text: str) -> str:
    urls = re.findall(r'http[^\s)]*', response_text)
    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                response_text = response_text.replace(url, '')
        except requests.exceptions.RequestException:
            response_text = response_text.replace(url, '')
    return response_text

def get_retrieval_from_google_search(user_prompt_text:str, client, model_name: str):
    system_prompt = None 
    response_type = 'text/plain'
    response_schema = None
    tools = [genai_types.Tool(google_search=genai_types.GoogleSearch())]
    try:
        response = generate_content(user_prompt_text, system_prompt, response_type, response_schema, tools, client, model_name)
        return response.text
    except Exception as e:
        print(f"Error in get_retrieval_from_google_search: {e}")
        raise

def get_relevant_ids(user_prompt_text: str, knowledge_subset_json: str, client, model_name: str) -> tuple[list[int] | None, str | None]:
    system_prompt = 'Given a user query, identify up to 5 of the most relevant IDs in the JSON below.\n'
    system_prompt += knowledge_subset_json
    response_type = 'application/json'
    response_schema = list[int]
    tools = None
    try:
        response_parsed = generate_content(user_prompt_text, system_prompt, response_type, response_schema, tools, client, model_name).parsed
        return response_parsed, None
    except Exception as e:
        print(f"Error in get_relevant_ids: {e}")
        return None, str(e)

def get_retrieval(
    user_prompt_text: str, 
    csv_file_key: str,   
    knowledge_base: dict,
    client,
    model_name: str,
    user_prompt_type_pro: bool,
    html_content_loader_func 
) -> tuple[str | None, str | None, str | None]: # (retrieved_json, ids_for_display, error_message)
    json_key_for_ids = csv_file_key + ' => df.iloc[:,:2].to_json'
    if json_key_for_ids not in knowledge_base:
        return None, None, f"Knowledge key '{json_key_for_ids}' not found."

    knowledge_subset_json = knowledge_base[json_key_for_ids]
    relevant_ids, error = get_relevant_ids(user_prompt_text, knowledge_subset_json, client, model_name)

    if error:
        return None, None, f"Error in get_relevant_ids: {error}"
    if not relevant_ids: # No IDs found, not necessarily an error to display in streamlit
        return None, None, None 

    ids_for_display = str(relevant_ids) # For st.code in streamlit_app

    if user_prompt_type_pro: # Pro users get data from main CSVs
        if csv_file_key not in knowledge_base:
             return None, ids_for_display, f"Knowledge key '{csv_file_key}' for DataFrame not found."
        df = knowledge_base[csv_file_key] # This is a DataFrame
        df = df[df['id'].isin(relevant_ids)]
    else: # Non-pro (HC) users get data from HTML files
        df = pd.DataFrame(columns=['id', 'html'])
        df['id'] = relevant_ids
        htmls = []
        for _id in relevant_ids:
            # Construct HTML file path from csv_file_key (which is like 'knowledge/hc/en-001/_log.csv')
            html_file_path_base = csv_file_key.rsplit('/', 1)[0] 
            html_file_path = f"{html_file_path_base}/{_id}.html"
            try:
                htmls.append(html_content_loader_func(html_file_path))
            except Exception as e:
                print(f"Error loading HTML file {html_file_path}: {e}")
                htmls.append(f"Error loading content for ID {_id}.")
        df['html'] = htmls
        
    return df.to_json(orient='records', force_ascii=False), ids_for_display, None # Success, no error message to display

# --- User Prompt Analysis Functions ---
def get_user_prompt_lang(user_prompt_text: str, client, model_name: str) -> int:
    system_prompt_lang = 'Given a user query, identify its language as one of the three: zh-tw, zh-cn, other'
    response_type = 'application/json'
    response_schema = str 
    tools = None
    try:
        response = generate_content(user_prompt_text, system_prompt_lang, response_type, response_schema, tools, client, model_name)
        response_parsed = response.parsed 
        lang_map = {'zh-tw': 0, 'zh-cn': 1, 'other': 2}
        identified_lang = str(response_parsed).lower()
        if identified_lang not in lang_map:
            print(f"Warning: Model returned unexpected language '{identified_lang}'. Defaulting to 'other'.")
            return lang_map['other']
        return lang_map[identified_lang]
    except Exception as e:
        print(f"Error in get_user_prompt_lang: {e}")
        raise

def get_user_prompt_type(user_prompt_history_content: list, client, model_name: str) -> bool:
    system_prompt_type = '問答內容最接近哪一類（二選一）：財經時事類、網站客服及其他類'
    response_type = 'application/json'
    response_schema = str 
    tools = None
    try:
        response = generate_content(user_prompt_history_content, system_prompt_type, response_type, response_schema, tools, client, model_name)
        response_parsed = response.parsed 
        type_map = {'財經時事類': True, '網站客服及其他類': False}
        identified_type = str(response_parsed)
        if identified_type not in type_map:
            print(f"Warning: Model returned unexpected prompt type '{identified_type}'. Defaulting to '網站客服及其他類'.")
            return type_map['網站客服及其他類'] 
        return type_map[identified_type]
    except Exception as e:
        print(f"Error in get_user_prompt_type: {e}")
        raise

# --- System Prompt Construction ---
def construct_system_prompt(
    base_system_prompt: str,
    user_prompt_text: str, # Current user's text query
    user_prompt_type_pro: bool,
    is_paid_user: bool,
    subdomain: str,
    site_language: str, # e.g. "繁體中文"
    # Constants from streamlit_app that define behavior/URLs
    site_languages: list[str], # ['繁體中文', '简体中文', 'English']
    language_prompts: list[str], # ['- 使用繁體中文', ...]
    lang_routes: list[str], # ['zh-tw', 'zh-cn', 'en-001']
    knowledge_base: dict, # Loaded by load_knowledge_data
    client, # Gemini API client
    model_name: str, # Selected model name
    # Feature flags
    has_chart: bool,
    has_quickie: bool,
    has_blog: bool,
    has_edm: bool,
    has_podcast: bool,
    has_stock_etf: bool,
    has_hc: bool,
    has_search: bool,
    html_content_loader_func # Function to load HTML, passed to get_retrieval
) -> tuple[str, list[dict]]: # (final_system_prompt, list_of_display_messages)
    """
    Constructs the dynamic system prompt based on user type, site language, and enabled features.
    Returns the final system prompt string and a list of messages for display in Streamlit (e.g., errors, badge info).
    """
    system_prompt = base_system_prompt
    display_messages = [] # To collect messages for st.code, st.badge

    if user_prompt_type_pro:
        if not is_paid_user:
            system_prompt += f"\n- 你會鼓勵用戶升級成為付費用戶就能享有完整問答服務，並且提供訂閱方案連結\n```\nhttps://{subdomain}.macromicro.me/subscribe\n```\n"
        
        if has_chart:
            csv_key = glob.glob('knowledge/chart-*.csv')[0] 
            retrieved_data_json, ids_for_display, error_msg = get_retrieval(user_prompt_text, csv_key, knowledge_base, client, model_name, user_prompt_type_pro, html_content_loader_func)
            if error_msg: display_messages.append({'type': 'code', 'content': f"Error retrieving chart data: {error_msg}"})
            if ids_for_display: display_messages.append({'type': 'badge', 'icon': "🔍", 'color': "blue", 'text': f"Relevant Chart IDs for {csv_key}: {ids_for_display}"})
            if retrieved_data_json: system_prompt += f"\n- MM圖表的資料，當中時間序列最新兩筆數據（series_last_rows）很重要，務必引用\n```\n{retrieved_data_json}\n網址規則 https://{subdomain}.macromicro.me/charts/{{id}}/{{slug}}\n```\n"

        if has_quickie and site_language in site_languages[:2]: # Assuming site_languages = ['繁體中文', '简体中文', 'English']
            csv_key = glob.glob('knowledge/quickie-*.csv')[0]
            retrieved_data_json, ids_for_display, error_msg = get_retrieval(user_prompt_text, csv_key, knowledge_base, client, model_name, user_prompt_type_pro, html_content_loader_func)
            if error_msg: display_messages.append({'type': 'code', 'content': f"Error retrieving quickie data: {error_msg}"})
            if ids_for_display: display_messages.append({'type': 'badge', 'icon': "🔍", 'color': "blue", 'text': f"Relevant Quickie IDs for {csv_key}: {ids_for_display}"})
            if retrieved_data_json: system_prompt += f"\n- MM短評的資料\n```\n{retrieved_data_json}\n網址規則 https://{subdomain}.macromicro.me/quickie?id={{id}}\n```\n"

        if has_blog and site_language in site_languages[:2]:
            csv_key = glob.glob('knowledge/blog-*.csv')[0]
            # Similar retrieval logic for blog...
            retrieved_data_json, ids_for_display, error_msg = get_retrieval(user_prompt_text, csv_key, knowledge_base, client, model_name, user_prompt_type_pro, html_content_loader_func)
            if error_msg: display_messages.append({'type': 'code', 'content': f"Error retrieving blog data: {error_msg}"})
            if ids_for_display: display_messages.append({'type': 'badge', 'icon':"🔍", 'color':"blue", 'text':f"Relevant Blog IDs for {csv_key}: {ids_for_display}"})
            if retrieved_data_json: system_prompt += f"\n- MM部落格的資料\n```\n{retrieved_data_json}\n網址規則 https://{subdomain}.macromicro.me/blog/{{slug}}\n```\n"
            
        if has_blog and site_language == 'English':
            csv_key = glob.glob('knowledge/blog_en-*.csv')[0]
            # Similar retrieval logic for English blog...
            retrieved_data_json, ids_for_display, error_msg = get_retrieval(user_prompt_text, csv_key, knowledge_base, client, model_name, user_prompt_type_pro, html_content_loader_func)
            if error_msg: display_messages.append({'type': 'code', 'content': f"Error retrieving English blog data: {error_msg}"})
            if ids_for_display: display_messages.append({'type': 'badge', 'icon':"🔍", 'color':"blue", 'text':f"Relevant English Blog IDs for {csv_key}: {ids_for_display}"})
            if retrieved_data_json: system_prompt += f"\n- MM部落格的資料\n```\n{retrieved_data_json}\n網址規則 https://{subdomain}.macromicro.me/blog/{{slug}}\n```\n"

        if has_edm and site_language in site_languages[:2]:
            csv_key = glob.glob('knowledge/edm-*.csv')[0]
            # Similar retrieval logic for EDM...
            retrieved_data_json, ids_for_display, error_msg = get_retrieval(user_prompt_text, csv_key, knowledge_base, client, model_name, user_prompt_type_pro, html_content_loader_func)
            if error_msg: display_messages.append({'type': 'code', 'content': f"Error retrieving EDM data: {error_msg}"})
            if ids_for_display: display_messages.append({'type': 'badge', 'icon':"🔍", 'color':"blue", 'text':f"Relevant EDM IDs for {csv_key}: {ids_for_display}"})
            if retrieved_data_json: 
                edm_lang_code = 'tc' if site_language == site_languages[0] else 'sc'
                system_prompt += f"\n- MM獨家報告的資料\n```\n{retrieved_data_json}\n網址規則 https://{subdomain}.macromicro.me/mails/edm/{edm_lang_code}/display/{{id}}\n```\n"

        if has_podcast:
            system_prompt += f"\n- MM Podcast( https://podcasts.apple.com/tw/podcast/macromicro-財經m平方/id1522682178 )的資料\n```\n{knowledge_base.get('podcast', '')}\n```\n"
        
        if has_stock_etf:
            system_prompt += f"\n- MM美股財報、ETF專區\n```\n美股財報資料網址規則 https://{subdomain}.macromicro.me/stocks/info/{{ticker_symbol}}\n美國ETF專區網址規則 https://{subdomain}.macromicro.me/etf/us/intro/{{ticker_symbol}}\n台灣ETF專區網址規則 https://{subdomain}.macromicro.me/etf/tw/intro/{{ticker_symbol}}\n```\n"

        if has_search:
            try:
                retrieved_text = get_retrieval_from_google_search(user_prompt_text, client, model_name)
                if retrieved_text:
                    system_prompt += f"\n- 網路搜尋的資料\n```\n{retrieved_text}\n```\n"
            except Exception as e:
                display_messages.append({'type': 'code', 'content': f"Error during Google search: {e}"})
    
    else: # Not user_prompt_type_pro (Website Customer Service type)
        if has_hc:
            current_lang_route = dict(zip(site_languages, lang_routes))[site_language]
            csv_key = f'knowledge/hc/{current_lang_route}/_log.csv'
            retrieved_data_json, ids_for_display, error_msg = get_retrieval(user_prompt_text, csv_key, knowledge_base, client, model_name, user_prompt_type_pro, html_content_loader_func)
            
            if error_msg: display_messages.append({'type': 'code', 'content': f"Error retrieving HC data: {error_msg}"})
            if ids_for_display: display_messages.append({'type': 'badge', 'icon': "🔍", 'color': "blue", 'text': f"Relevant HC IDs for {csv_key}: {ids_for_display}"})

            if retrieved_data_json:
                system_prompt += f"\n- MM幫助中心的資料\n```\n{retrieved_data_json}\n網址規則 https://support.macromicro.me/hc/{current_lang_route}/articles/{{id}}\n不要提供來信或來電的客服聯繫方式\n```\n"
            else: # No specific HC articles found or error in retrieval
                system_prompt += f"\n- 提供用戶MM幫助中心網址 https://support.macromicro.me/hc/{current_lang_route}\n"
        else: # No HC toggle
            current_lang_route = dict(zip(site_languages, lang_routes))[site_language] # Still need lang_route for the URL
            system_prompt += f"\n- 提供用戶MM幫助中心網址 https://support.macromicro.me/hc/{current_lang_route}\n"
        
        system_prompt += "\n- 若非網站客服相關問題，你會婉拒回答\n"

    # Append the final language instruction
    system_prompt += "\n" + dict(zip(site_languages, language_prompts))[site_language]
    
    return system_prompt, display_messages
