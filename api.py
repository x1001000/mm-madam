from flask import Flask, request, jsonify
import os
import google.generativeai as genai # Modern SDK import style
from google.generativeai import types as genai_types # Modern SDK import style, aliased for clarity
import requests 
import logging

# Imports from chat_logic 
from chat_logic import (
    load_knowledge_data,
    # get_user_prompt_lang, # Not imported as API uses direct 'site_language' parameter per task simplification
    # get_user_prompt_type, # Not imported as API uses direct 'user_prompt_type_pro' parameter per task simplification
    construct_system_prompt,
    generate_content,
    remove_invalid_urls,
    reset_token_counts,
    cost,
    price, # Direct import of 'price' as exported by chat_logic.py
    DEFAULT_MODEL,
    prompt_token_count, 
    candidates_token_count,
    total_token_count as cl_total_token_count 
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO) 
app.logger.setLevel(logging.INFO)

# Initialize GenAI Client & Load .env
try:
    from dotenv import load_dotenv
    if load_dotenv(): app.logger.info("Loaded .env file.")
    else: app.logger.info(".env file not found/empty. Using global env vars.")
except ImportError:
    app.logger.info("python-dotenv not installed. Using global env vars.")

# Using os.environ.get for robustness, rather than os.environ[] which raises KeyError
gemini_api_key = os.environ.get('GEMINI_API_KEY') 
if not gemini_api_key:
    app.logger.critical("GEMINI_API_KEY environment variable not set.")
    raise RuntimeError("GEMINI_API_KEY environment variable not set.")

try:
    client = genai.Client(api_key=gemini_api_key)
    app.logger.info("GenAI client initialized.")
except Exception as e:
    app.logger.critical(f"Failed to initialize GenAI client: {e}", exc_info=True)
    raise RuntimeError(f"Failed to initialize GenAI client: {e}")

# Load knowledge data (using 'knowledge_data' as variable name per current task)
try:
    knowledge_data = load_knowledge_data() 
    app.logger.info("Knowledge data loaded.")
except Exception as e:
    app.logger.error(f"Failed to load knowledge data: {e}", exc_info=True)
    knowledge_data = {} 

# HTML content loader for API context (placeholder as per task)
# file_path is the direct path to the HTML file, constructed by chat_logic.get_retrieval
def api_html_content_loader(file_path: str) -> str: 
    app.logger.info(f"API HTML Loader attempting to load with path: {file_path}")
    # This is a placeholder. Actual functionality for HC depends on deployment.
    if 'knowledge/hc/' in file_path: 
         app.logger.warning(f"API HTML Loader: HC path detected ({file_path}). Functionality depends on correct path and deployment structure and may be limited.")
    try:
        # This simplified loader assumes api.py is at project root.
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        app.logger.warning(f"API HTML loader: File not found: {file_path}")
        return f"Content for {os.path.basename(file_path)} not found (API context placeholder)." # User-friendly message
    except Exception as e:
        app.logger.error(f"API HTML loader: Error for {file_path}: {e}", exc_info=True)
        return f"Error loading content from {os.path.basename(file_path)} (API context placeholder)."

# API Default Settings & Constants (aligning with current task's naming)
API_DEFAULT_SITE_LANGUAGE = 'English'
SITE_LANGUAGES_AVAILABLE = ['繁體中文', '简体中文', 'English'] 

# Mappings for language settings
LANGUAGE_PROMPTS_MAP = {lang: prompt for lang, prompt in zip(SITE_LANGUAGES_AVAILABLE, ['- 使用繁體中文', '- 使用简体中文', '- Use English.'])}
API_LANG_ROUTES = {lang: route for lang, route in zip(SITE_LANGUAGES_AVAILABLE, ['zh-tw', 'zh-cn', 'en-001'])} # As per task
API_DEFAULT_LANG_ROUTE = API_LANG_ROUTES[API_DEFAULT_SITE_LANGUAGE] # As per task
SUBDOMAINS_MAP = {lang: subdomain for lang, subdomain in zip(SITE_LANGUAGES_AVAILABLE, ['www', 'sc', 'en'])}
API_DEFAULT_SUBDOMAIN = SUBDOMAINS_MAP[API_DEFAULT_SITE_LANGUAGE] # As per task

# Base system prompt
DEFAULT_SYSTEM_PROMPT_URL_CONST = "https://docs.google.com/document/d/1HOS7nntBTgfuSlUpHgDIfBed5M_bq4dH0H8kqXUO9PE/export?format=txt"
SYSTEM_PROMPT_URL_ACTUAL = os.environ.get('SYSTEM_PROMPT_URL', DEFAULT_SYSTEM_PROMPT_URL_CONST)
BASE_SYSTEM_PROMPT_TEXT = "You are a helpful AI assistant." # Fallback defined first, as per task
try:
    response = requests.get(SYSTEM_PROMPT_URL_ACTUAL, timeout=10)
    response.raise_for_status() 
    BASE_SYSTEM_PROMPT_TEXT = response.text
    app.logger.info(f"Base system prompt fetched from {SYSTEM_PROMPT_URL_ACTUAL}")
except requests.exceptions.RequestException as e:
    app.logger.error(f"Failed to fetch base system prompt from URL: {SYSTEM_PROMPT_URL_ACTUAL}. Error: {e}. Using fallback.", exc_info=True)


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data:
        app.logger.warning("Request has invalid JSON payload.")
        return jsonify({'error': 'Invalid JSON payload'}), 400
        
    user_message_text = data.get('message')
    if not user_message_text:
        app.logger.warning("Request is missing 'message' parameter.")
        return jsonify({'error': 'Missing message parameter'}), 400

    # Parameters from request or defaults (aligning with task description)
    site_language_for_api = data.get('site_language', API_DEFAULT_SITE_LANGUAGE) # Default to English
    if site_language_for_api not in SITE_LANGUAGES_AVAILABLE:
        app.logger.warning(f"Invalid 'site_language' in request: {site_language_for_api}")
        return jsonify({'error': f"Invalid site_language. Supported: {', '.join(SITE_LANGUAGES_AVAILABLE)}"}), 400

    is_paid_user = data.get('is_paid_user', True) # Defaulting as per task example
    user_prompt_type_pro = data.get('user_prompt_type_pro', True) # Simplified for API as per task
    current_model = data.get('model', DEFAULT_MODEL)
    if current_model not in price: 
        app.logger.warning(f"Invalid 'model' in request: {current_model}. Defaulting to {DEFAULT_MODEL}.")
        current_model = DEFAULT_MODEL
        
    feature_flags = { # Matching the structure expected by **feature_flags in construct_system_prompt
        'has_chart': data.get('has_chart', True), 'has_quickie': data.get('has_quickie', True),
        'has_blog': data.get('has_blog', True), 'has_edm': data.get('has_edm', True),
        'has_podcast': data.get('has_podcast', True), 'has_stock_etf': data.get('has_stock_etf', True),
        'has_hc': data.get('has_hc', True), 'has_search': data.get('has_search', True),
    }

    reset_token_counts()
    # user_prompt_content for generate_content (list of Content objects)
    # For API, history is simplified to just the current message.
    user_prompt_content_for_llm = [genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=user_message_text)])]

    try:
        subdomain_for_api = SUBDOMAINS_MAP.get(site_language_for_api, API_DEFAULT_SUBDOMAIN)
        
        # Prepare ordered lists for language settings for construct_system_prompt
        ordered_site_languages = SITE_LANGUAGES_AVAILABLE
        ordered_language_prompts = [LANGUAGE_PROMPTS_MAP[lang] for lang in ordered_site_languages]
        ordered_lang_routes = [API_LANG_ROUTES[lang] for lang in ordered_site_languages]

        # Call construct_system_prompt from chat_logic.py
        # Ensure arguments match chat_logic.construct_system_prompt signature
        system_prompt_str, display_messages = construct_system_prompt(
            base_system_prompt=BASE_SYSTEM_PROMPT_TEXT, 
            user_prompt_text=user_message_text, # Raw user message string for retrieval context
            user_prompt_type_pro=user_prompt_type_pro,
            is_paid_user=is_paid_user,
            subdomain=subdomain_for_api,
            site_language=site_language_for_api, 
            site_languages=ordered_site_languages, 
            language_prompts=ordered_language_prompts, 
            lang_routes=ordered_lang_routes, 
            knowledge_base=knowledge_data, 
            client=client,
            model_name=current_model,
            html_content_loader_func=api_html_content_loader,
            **feature_flags 
        )
        
        # Call generate_content from chat_logic.py
        # Ensure arguments match chat_logic.generate_content signature (client and model_name are positional)
        final_response_obj = generate_content(
            user_prompt_content=user_prompt_content_for_llm, 
            system_prompt=system_prompt_str,
            response_type='text/plain', 
            response_schema=None,
            tools=None, 
            client=client, 
            model_name=current_model
        )
            
        response_text_cleaned = remove_invalid_urls(final_response_obj.text) 
        current_cost_val = cost(current_model)
        
        return jsonify({
            'response': response_text_cleaned,
            'prompt_tokens': prompt_token_count, 
            'candidates_tokens': candidates_token_count, 
            'total_tokens': cl_total_token_count, 
            'cost_usd': current_cost_val,
            'model_used': current_model,
            'system_prompt_debug': system_prompt_str if data.get('debug_mode', False) else "Debug mode off", 
            'display_messages_debug': display_messages if data.get('debug_mode', False) else "Debug mode off"
        })

    except Exception as e:
        app.logger.error(f"Critical error in /chat endpoint: {e}", exc_info=True)
        return jsonify({'error': 'An internal error occurred', 'details': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5001)) # Default to 5001 if not set
    debug_mode_env = os.environ.get('FLASK_DEBUG', '0').lower() in ['true', '1', 't', 'yes']
    app.logger.info(f"Starting Flask app on 0.0.0.0:{port}, debug mode: {debug_mode_env}")
    app.run(debug=debug_mode_env, port=port, host='0.0.0.0')
