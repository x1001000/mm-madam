document.addEventListener('DOMContentLoaded', () => {
    const chatbox = document.getElementById('chatbox');
    const openWidgetBtn = document.getElementById('open-widget-btn');
    const closeWidgetBtn = document.getElementById('close-widget-btn');
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');
    const messagesContainer = document.getElementById('chatbox-messages');

    // API endpoint for the chatbot
    // IMPORTANT: This assumes the Flask API is running on port 5001.
    // If deployed, this URL will need to be the actual API endpoint.
    const API_ENDPOINT = '/chat'; // If widget.html is served by Flask, this relative path works.
                                   // Otherwise, use full URL: 'http://localhost:5001/chat'

    // Function to toggle chatbox visibility
    function toggleChatbox() {
        // Use a class to control visibility for CSS animations
        if (chatbox.classList.contains('visible')) {
            chatbox.classList.remove('visible');
            openWidgetBtn.classList.remove('hidden');
        } else {
            chatbox.classList.add('visible');
            openWidgetBtn.classList.add('hidden');
            userInput.focus();
        }
    }

    // Add message to chatbox
    function addMessage(text, type, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', type + '-message');
        if (isError) {
            messageDiv.classList.add('error-message');
            messageDiv.classList.remove(type + '-message'); // remove user/bot specific style for error
        }
        
        const p = document.createElement('p');
        p.textContent = text;
        messageDiv.appendChild(p);
        
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight; // Auto-scroll to latest message
    }

    // Send message to API
    async function sendMessage() {
        const messageText = userInput.value.trim();
        if (messageText === '') return;

        addMessage(messageText, 'user');
        userInput.value = ''; // Clear input field

        try {
            // Display typing indicator (optional)
            addMessage("Bot is typing...", 'bot', true); // Use error class for temporary styling
            const typingIndicator = messagesContainer.lastChild;

            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: messageText,
                    // You can add more parameters here if your API supports them
                    // e.g., session_id, is_paid_user, etc.
                    // For now, using API defaults for those.
                }),
            });
            
            if (typingIndicator) {
                messagesContainer.removeChild(typingIndicator); // Remove typing indicator
            }

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `API request failed with status ${response.status}`);
            }

            const data = await response.json();
            addMessage(data.response, 'bot');

        } catch (error) {
            console.error('Error sending message:', error);
            addMessage(`Error: ${error.message}`, 'bot', true);
             if (messagesContainer.querySelector('.error-message:not(:last-child)')) {
                const oldError = messagesContainer.querySelector('.error-message:not(:last-child)');
                if(oldError && oldError.textContent.includes("Bot is typing...")) {
                    messagesContainer.removeChild(oldError);
                }
            }
        }
    }

    // Event Listeners
    if (openWidgetBtn) {
        openWidgetBtn.addEventListener('click', toggleChatbox);
    }
    if (closeWidgetBtn) {
        closeWidgetBtn.addEventListener('click', toggleChatbox);
    }
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    if (userInput) {
        userInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                sendMessage();
            }
        });
    }
    
    // Initial state: widget is closed by default, open button is visible
    if (chatbox) chatbox.classList.remove('visible'); // Ensure it's hidden initially
    if (openWidgetBtn) openWidgetBtn.classList.remove('hidden'); // Ensure open button is visible


    // --- Embedding Snippet Generation (Conceptual) ---
    // This part is to show how a user would embed this.
    // The actual widget loader script would be more complex if it's to be truly standalone.
    // For now, widget.html, widget.css, and widget.js are expected to be in the same directory.

    const generateEmbedSnippet = () => {
        const snippet = `
<!-- Start AI Chat Widget -->
<div id="ai-chat-widget-embed-container"></div>
<script>
  (function() {
    const container = document.getElementById('ai-chat-widget-embed-container');
    const iframe = document.createElement('iframe');
    iframe.src = "PATH_TO_YOUR_WIDGET/widget.html"; // User needs to replace this path
    iframe.style.width = "400px"; // Or make it responsive
    iframe.style.height = "550px";
    iframe.style.border = "none";
    iframe.style.position = "fixed";
    iframe.style.bottom = "20px";
    iframe.style.right = "20px";
    iframe.style.zIndex = "9999";
    // More sophisticated styling and interaction might be needed
    container.appendChild(iframe);
  })();
</script>
<!-- End AI Chat Widget -->
        `;
        console.log("Embed this snippet into your website's HTML:");
        console.log(snippet.trim());
        
        // For demonstration, add it to the widget.html page itself if a placeholder exists
        const snippetPlaceholder = document.getElementById('embed-snippet-placeholder');
        if(snippetPlaceholder) {
            snippetPlaceholder.textContent = snippet.trim();
        }
    };

    // generateEmbedSnippet(); // Call this if you want to log the snippet to console when widget.html loads
});
