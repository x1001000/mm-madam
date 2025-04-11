import streamlit as st
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Content, Part
import pandas as pd
import glob
csvs = glob.glob('*.csv')
models = [
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
]

def is_economics_related() -> bool:
    """
    Determine if a question is related to economics or finance.
    
    Args:
        client: Gemini API client
        question: User's question to evaluate
        model: Gemini model name to use
        
    Returns:
        bool: True if question is economics/finance related, False otherwise
    """
    
    system_prompt = """
    Determine if the input question is related to:
    - Economics
    - Finance
    - Markets
    - Trading
    - Banking
    - Monetary policy
    - Fiscal policy
    - Economic indicators
    
    Output only 'true' or 'false'. No other text.
    """
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=st.session_state.contents[-1:],
            config=GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="text/plain",
            )
        )
        
        # return response.text.strip().lower() == 'true'
        return 'true' in response.text.strip().lower()
        
    except Exception as e:
        print(f"Error checking question relevance: {e}")
        return False

def get_relevant_chart_ids() -> list[int]:
    """
    Get relevant MacroMicro chart IDs based on user question using Gemini model.
    
    Args:
        client: Gemini API client
        user_question: User's question about economic/financial topics
        model: Gemini model name to use
        
    Returns:
        list of relevant chart IDs
    """
    
    system_prompt = """
    Given a user question, identify relevant MacroMicro chart IDs.
    Return ONLY a comma-separated list of chart IDs. Do not include any other text.
    
    MacroMicro_charts.csv:
    """ + st.session_state.knowledge[csv]
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=st.session_state.contents[-1:],
            config=GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="text/plain",
            )
        )
        
        # Extract chart IDs from response
        chart_ids = [
            int(chart_id.strip())
            for chart_id in response.text.split(',')
            if chart_id.strip().isdigit()
        ]
        
        return chart_ids
        
    except Exception as e:
        print(f"Error getting chart IDs: {e}")
        return []

st.title('👩🏻‍💼 MM Madam')

col1, col2 = st.columns(2)
with col1:
    csv = st.selectbox("MacroMicro 圖表資料", csvs)
with col2:
    model = st.selectbox("Gemini 語言模型", models)

# Add search toggle
enable_search = st.toggle("啟用網路搜尋", value=True, help="開啟後，MM Madam 將使用 Google 搜尋來輔助回答")

# Create session state variables
if 'client' not in st.session_state:
    st.session_state.client = genai.Client(api_key=st.secrets['GEMINI_API_KEY'])
    st.session_state.contents = []
    st.session_state.knowledge = {}
    for csv in csvs:
        with open(csv) as f:
            st.session_state.knowledge[csv] = ''.join(f.readlines())
        st.session_state.knowledge['DataFrame of '+csv] = pd.read_csv(csv)
client = st.session_state.client

# include and display the last 5 turns of conversation before the current turn
st.session_state.contents = st.session_state.contents[-10:]
for content in st.session_state.contents:
    with st.chat_message(content.role, avatar=None if content.role == "user" else '👩🏻‍💼'):
        st.markdown(content.parts[0].text)

# Create a chat input field to allow the user to enter a message. This will display
# automatically at the bottom of the page.
if user_prompt := st.chat_input("財經時事相關問題，例如：川普關稅最新進展與對台衝擊？"):
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.contents.append(Content(role="user", parts=[Part.from_text(text=user_prompt)]))

    system_prompt = '妳是「財經M平方（MacroMicro）」的AI研究員：Madam，妳目前的工作是回答財經時事相關問題。'
    if is_economics_related():
        df = st.session_state.knowledge['DataFrame of '+csv]
        if chart_ids := get_relevant_chart_ids():
            retrieval = df[df['id'].isin(chart_ids)].to_csv(index=False, quoting=1)
            system_prompt += '''妳會依據MacroMicro圖表資料及Google搜尋結果回答問題，並且提供MacroMicro圖表超連結 https://www.macromicro.me/charts/{id}/{slug} ，超連結前後空格或換行。
            
            MacroMicro圖表資料.csv 如下\n''' + retrieval
            print(chart_ids)
    else:
        system_prompt += '若非財經時事相關問題，妳會婉拒回答。'
    print(system_prompt)
    response = client.models.generate_content(
        model=model,
        contents=st.session_state.contents,
        config=GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[Tool(google_search=GoogleSearch())] if enable_search else None,
            response_mime_type="text/plain",
        ),
    )
    # Stream the response to the chat using `st.write_stream`, then store it in 
    # session state.
    with st.chat_message("assistant", avatar='👩🏻‍💼'):
        st.markdown(response.text)
    st.session_state.contents.append(Content(role="model", parts=[Part.from_text(text=response.text)]))