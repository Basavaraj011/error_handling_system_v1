"""
Web Application - Flask/FastAPI app for chatbot interface
"""
from flask import Flask, request, jsonify
from src.plugins.chatbot.bot import ChatBot
import logging

logger = logging.getLogger(__name__)


def create_app():
    """Create and configure the Flask app"""
    app = Flask(__name__)
    chatbot = ChatBot()
    
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "healthy"}), 200
    
    @app.route('/chat', methods=['POST'])
    def chat():
        """Handle chat messages"""
        try:
            data = request.json
            user_message = data.get("message", "")
            
            if not user_message:
                return jsonify({"error": "Message is required"}), 400
            
            response = chatbot.process_message(user_message)
            
            return jsonify({
                "message": response,
                "status": "success"
            }), 200
        except Exception as e:
            logger.error(f"Error processing chat: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/history', methods=['GET'])
    def get_history():
        """Get conversation history"""
        return jsonify({
            "history": chatbot.get_conversation_history()
        }), 200
    
    @app.route('/reset', methods=['POST'])
    def reset():
        """Reset conversation"""
        chatbot.reset_conversation()
        return jsonify({"status": "reset"}), 200
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=8000, debug=False)
