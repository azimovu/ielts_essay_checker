import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

async def analyze_essay(topic: str, essay: str) -> str:
    """Analyze the essay using the Anthropic API."""
    prompt = f"\n\nHuman: You are an expert IELTS essay examiner. You give an essay detailed feedback on topics like 'Coherence and Cohesion', 'Lexical Recourse', 'Grammatical range and Accuracy'. You give band score ranging from 1 to 9 in each area and overall. At the end you give feedback on how to improve this essay also give some examples where they could improve. You write only the above-mentioned and nothing more. If it doesn't seem to be an essay, you say \"Sorry, there's something wrong with your essay\". If essay is less than 250 words, you make comment about it and lower overall band score. You are given topic and essay about this topic.\n\nTopic: {topic}\nEssay: {essay}\n\nAssistant:"

    messages = [
        {"role": "user", "content": prompt}
    ]

    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1024,
        messages=messages,
    )

    if response and response.content:
        return response.content[0].text
    else:
        return "Failed to analyze the essay. Please try again later."