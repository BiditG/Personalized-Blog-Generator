import subprocess

def generate_blog_ollama(topic, tone, audience, word_count):
    prompt = f"""
    Write a blog on the topic: {topic}.
    Tone: {tone}. Audience: {audience}.
    Make it approximately {word_count} words.
    Include SEO-friendly title, introduction, 3-4 subheadings, conclusion.
    Use natural language and short paragraphs.
    """
    result = subprocess.run(
        ["ollama", "run", "mistral"],
        input=prompt.encode(),
        capture_output=True,
    )
    return result.stdout.decode()
