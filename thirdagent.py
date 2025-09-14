from phi.model.groq import Groq
from phi.agent import Agent, RunResponse
import os
#Try to use this (Recommended)

# Option 2: Load from environment variable
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq model
agent = Agent(
    model=Groq(
        id="llama-3.3-70b-versatile",
        api_key=GROQ_API_KEY
    ),
    markdown=False
)

def agent_answer(history, language='en'):
    system_prompt = (
        "You are an expert Ayurvedic doctor. "
        "You provide natural home remedies and traditional herbal solutions for common ailments "
        "like cough, cold, indigestion, stress, and skin issues. "
        "Avoid recommending modern medicine. "
        "Focus on lifestyle tips, dietary suggestions, and ancient Indian health practices. "
        "Give very short (1 sentence response max), practical responses with remedies first and given in plain text "
        "(Do not use any symbols). "
        "Respond in the same language in which the question is asked. "
        "User selected language is " + language + "."
        "Only provide response regarding Ayurveda. If the question is not related to Ayurveda, politely refuse to answer."
    )

    # ✅ Run agent
    response = agent.run(
        history,
        system=system_prompt
    )

    # ✅ Extract text
    return response.content.strip() if response.content else str(response)

if __name__ == "__main__":
    # Example in Tamil
    print(agent_answer("எனக்கு சளி காய்ச்சல் இருக்கு, நான் என்ன செய்ய வேண்டும்?", "tamil"))
