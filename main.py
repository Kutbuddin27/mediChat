from key_functionality import PathologyBot
import os
from google.generativeai import configure

# API key configuration
API_KEY = os.getenv("google_api_key") # Replace with your actual API key
configure(api_key=API_KEY)

# Main interaction loop
def main():
    user_id = "user123"  # In a real app, this would be dynamic
    bot = PathologyBot(API_KEY)

    print("Welcome to the Pathology AI Chatbot!")
    print("Type 'exit' to quit.\n")

    # Initial greeting
    print("Bot: Hi")
    response = bot.get_response(user_id, "Hi")
    print(f"Bot: {response}")

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ('exit','bye'):
            print("Thank you for using Pathology AI Chatbot. Goodbye!")
            break

        response = bot.get_response(user_id, user_input)
        print(f"Bot: {response}")

if __name__ == "__main__":
    main()
