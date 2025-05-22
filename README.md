# 👩🏻‍💼 MM Madam: AI Assistant with Flask API and Chat Widget

This project provides an AI-powered assistant with multiple interfaces: a Flask-based API, an embeddable web chat widget, and a Streamlit application.

## Prerequisites

*   Python 3.7+ is recommended.
*   A Google Generative AI API key (for the Gemini model).
*   Core dependencies are listed in `requirements.txt`. Install them using:
    ```bash
    pip install -r requirements.txt
    ```
    The key dependencies include:
    ```
    Flask
    google-generativeai
    requests
    python-dotenv
    pandas
    streamlit
    ```
    *(Note: If you encounter issues with `pip install -r requirements.txt` due to tool limitations in this environment, please ensure the above packages are installed manually.)*

## Running the Flask API Server (for the Chat Widget)

The Flask API server provides the backend chat functionality for the web widget.

1.  **Environment Setup:**
    *   Create a `.env` file in the root directory of the project.
    *   Add your Google Generative AI API key to the `.env` file:
        ```env
        GEMINI_API_KEY="YOUR_API_KEY"
        ```
    *   (Optional) You can also specify a custom URL for the base system prompt:
        ```env
        SYSTEM_PROMPT_URL="YOUR_SYSTEM_PROMPT_URL"
        ```
        If not provided, a default URL will be used.
    *   (Optional) Configure the Flask server port and debug mode (defaults to port 5001, debug off unless `FLASK_DEBUG=1`):
        ```env
        FLASK_RUN_PORT=5001
        FLASK_DEBUG=0 
        ```

2.  **Start the Server:**
    *   Run the `api.py` script from the root directory:
        ```bash
        python api.py
        ```
    *   By default, the API server will run on `http://localhost:5001`.

## Using the AI Chat Widget

The chat widget (`widget.html`, `widget.css`, `widget.js`) provides a user interface that interacts with the Flask API.

### Method 1: Direct Hosting (e.g., via Flask)

If the Flask application is configured to serve static files, you can serve `widget.html` directly.

1.  **Serving the Widget (Example - Requires `api.py` modification):**
    You would typically add routes to your `api.py` to serve `widget.html`, `widget.css`, and `widget.js`. For example (this code is illustrative and not automatically added by this agent):
    ```python
    # Example route in api.py to serve widget.html
    # from flask import send_from_directory
    # @app.route('/widget')
    # def serve_widget():
    #     return send_from_directory('.', 'widget.html')
    #
    # # Similar routes would be needed for widget.css and widget.js,
    # # or by configuring a static folder.
    ```
2.  **Accessing the Widget:**
    If hosted by the Flask app (e.g., at a `/widget` route), you would access it at `http://localhost:5001/widget`.
3.  **API Endpoint Configuration:**
    The `widget.js` file is pre-configured with `const API_ENDPOINT = '/chat';`. This relative path works correctly when `widget.html` is served from the same host and port as the Flask API.

### Method 2: Embedding into any Website (Iframe)

You can embed the chat widget into any existing website using an iframe.

1.  **Host Widget Files:**
    *   Ensure `widget.html`, `widget.css`, and `widget.js` are hosted on a web server accessible to your users (this could be a static site hosting service, a CDN, or your existing web server).
2.  **Embed Snippet:**
    *   Add the following HTML snippet to your website where you want the widget to appear:
        ```html
        <!-- Start AI Chat Widget -->
        <div id="ai-chat-widget-embed-container" style="position: fixed; bottom: 20px; right: 20px; z-index: 9999;">
            /* Container for iframe, can be styled or removed if iframe is styled directly */
        </div>
        <script>
          (function() {
            const container = document.getElementById('ai-chat-widget-embed-container');
            const iframe = document.createElement('iframe');
            // IMPORTANT: Replace "PATH_TO_YOUR_WIDGET/widget.html" with the actual URL 
            // where your widget.html is hosted.
            iframe.src = "PATH_TO_YOUR_WIDGET/widget.html"; 
            iframe.style.width = "370px"; // Adjusted for typical widget size including shadow
            iframe.style.height = "530px"; // Adjusted
            iframe.style.border = "none";
            iframe.style.boxShadow = "0 5px 15px rgba(0,0,0,0.2)";
            iframe.style.borderRadius = "10px";
            // Remove iframe styling if #ai-chat-widget-embed-container is used to style the frame
            // iframe.style.position = "fixed"; 
            // iframe.style.bottom = "20px";
            // iframe.style.right = "20px";
            // iframe.style.zIndex = "9999";
            container.appendChild(iframe);
          })();
        </script>
        <!-- End AI Chat Widget -->
        ```
3.  **API Endpoint Configuration (Important):**
    *   If `widget.html` is hosted on a different domain than your Flask API, you **must** update the `API_ENDPOINT` in `widget.js`. Change it from the relative path (`/chat`) to the absolute URL of your Flask API server. For example:
        ```javascript
        // In widget.js, change this line:
        // const API_ENDPOINT = '/chat'; 
        // To something like:
        // const API_ENDPOINT = 'http://localhost:5001/chat'; 
        // Or if your API is deployed:
        // const API_ENDPOINT = 'https://your-api-domain.com/chat';
        ```
    *   Ensure your Flask API server is configured to handle Cross-Origin Resource Sharing (CORS) if the widget is embedded on a different domain. This usually involves adding CORS headers in `api.py` (e.g., using the `flask-cors` extension).

## Streamlit Application (Alternative Interface)

This project also includes a Streamlit application for interacting with the AI.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://mm-madam.streamlit.app/)

### How to run the Streamlit app on your own machine

1.  **Install Requirements:**
    (If not already done, as per the main Prerequisites section)
    ```bash
    pip install -r requirements.txt
    ```
    Ensure your `GEMINI_API_KEY` is set as an environment variable or accessible via Streamlit secrets if deploying. For local Streamlit development, setting it in your shell or a `.env` file (which Streamlit can sometimes pick up with `python-dotenv` if `load_dotenv()` is called early) is common.

2.  **Run the App:**
    ```bash
    streamlit run streamlit_app.py
    ```
