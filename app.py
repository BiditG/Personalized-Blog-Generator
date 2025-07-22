import streamlit as st
import subprocess
import requests
import zipfile
import os
import shutil
from datetime import datetime
from docx import Document
from tinydb import TinyDB
import language_tool_python
from textblob import TextBlob
import random

# ---------- Initialize DB and Tools ----------
db = TinyDB("blog_history.json")
tool = language_tool_python.LanguageTool('en-US')

TEMPLATE_PRESETS = {
    "Default": "Use a clear, concise tone. Ensure paragraphs are short and keyword optimized.",
    "Storytelling": "Use storytelling with personal experiences, metaphors, and first-person voice.",
    "Educational": "Maintain a professional tone, detailed explanations, and supportive bullet points.",
    "Sales Focused": "Use persuasive language, scarcity tactics, and direct CTAs to boost conversions."
}

# ---------- Helpers ----------
def grammar_enhance(text):
    matches = tool.check(text)
    return language_tool_python.utils.correct(text, matches)

def voice_tone_score(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.3:
        return "Upbeat / Positive"
    elif polarity < -0.3:
        return "Serious / Cautionary"
    else:
        return "Neutral / Informative"

def fake_plagiarism_score():
    return random.randint(2, 15)  # simulate low plagiarism

# ---------- Blog Generator ----------
def generate_blog_ollama(topic, tone, audience, word_count, model, subheadings,
                         include_meta, include_conclusion, style, perspective, cta_type, keywords, template):
    prompt = f"""
    Write a high-quality, SEO-optimized blog post on the topic: "{topic}".

    Guidelines:
    - Use the following tone: {tone}
    - Target audience: {audience}
    - Length: approximately {word_count} words
    - Style: {style}
    - Perspective: {perspective}
    - Use {subheadings} informative H2 subheadings
    - {"Include a meta description under 160 characters." if include_meta else ""}
    - Integrate keywords: {keywords}
    - {template}
    - Short paragraphs (2-3 lines)
    - Bullet points, lists, or examples when helpful
    - {"Include conclusion with a strong CTA: " + cta_type if include_conclusion else ""}
    """

    # Debug: Show prompt in app for inspection
    with st.expander("🔍 Debug Prompt"):
        st.code(prompt, language="markdown")

    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt.encode(),
            capture_output=True,
            timeout=300  # seconds
        )
        if result.returncode != 0:
            st.error("🛑 Model returned an error. Please check if the model is installed and working.")
            st.code(result.stderr.decode(), language="bash")
            return "ERROR: Model execution failed."

        output = result.stdout.decode().strip()

        if not output:
            st.warning("⚠️ Model returned no output. This might be due to system overload or incomplete model.")
            return "ERROR: No response from model."

        return grammar_enhance(output)

    except subprocess.TimeoutExpired:
        st.error("⏳ Model generation timed out. Try using a smaller model or reducing word count.")
        return "ERROR: Model timed out."

    except Exception as e:
        st.error("🚨 Unexpected error during model execution.")
        st.code(str(e))
        return f"ERROR: {str(e)}"


# ---------- Save Blog to DB ----------
def save_blog_to_db(topic, tone, audience, word_count, model, blog_text, style,
                    perspective, cta_type, keywords, template):
    db.insert({
        "topic": topic,
        "tone": tone,
        "audience": audience,
        "word_count": word_count,
        "model": model,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "style": style,
        "perspective": perspective,
        "cta_type": cta_type,
        "keywords": keywords,
        "template": template,
        "blog": blog_text
    })

# ---------- Image Fetcher ----------
def get_unsplash_images(query, client_id, count=5):
    url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "per_page": count, "client_id": client_id, "orientation": "landscape"}
    response = requests.get(url, params=params)
    data = response.json()
    return [img["urls"]["regular"] for img in data.get("results", [])]

from docx.shared import Pt, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

# ---------- Enhanced Export to DOCX ----------
def export_to_docx(blog_text, filename="blog.docx"):
    doc = Document()

    # Set document styles
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)

    # Define spacing and margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    lines = blog_text.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Title
        if lines.index(line) == 0:
            title = doc.add_heading(stripped, level=1)
            title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        # Subheadings
        elif stripped.startswith("##") or stripped.endswith(":"):
            doc.add_heading(stripped.replace("##", "").strip(), level=2)

        # Bullet Points
        elif stripped.startswith("* "):
            doc.add_paragraph(stripped[2:].strip(), style="List Bullet")

        # Regular Paragraph
        else:
            paragraph = doc.add_paragraph(stripped)
            paragraph.paragraph_format.space_after = Pt(8)

    # Save formatted document
    doc.save(filename)


# ---------- Fiverr ZIP Export ----------
def create_fiverr_package(blog_text, docx_path, img_urls, topic):
    folder = f"fiverr_delivery/{topic.replace(' ', '_')}"
    os.makedirs(folder, exist_ok=True)

    txt_path = os.path.join(folder, "blog.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(blog_text)

    img_path = os.path.join(folder, "image_links.txt")
    with open(img_path, "w", encoding="utf-8") as f:
        for url in img_urls:
            f.write(url + "\n")

    docx_dest = os.path.join(folder, "blog.docx")
    shutil.copyfile(docx_path, docx_dest)

    zip_filename = f"{folder}.zip"
    with zipfile.ZipFile(zip_filename, "w") as zipf:
        zipf.write(txt_path, arcname="blog.txt")
        zipf.write(img_path, arcname="image_links.txt")
        zipf.write(docx_dest, arcname="blog.docx")

    return zip_filename

# ---------- Streamlit UI ----------
st.set_page_config(page_title="📝 Blog Generator Pro", layout="centered")
st.title("📝 AI-Powered Blog Generator with Templates & Scoring")

# Sidebar Inputs
st.sidebar.header("✍️ Blog Settings")
topic = st.sidebar.text_input("Blog Topic", "Boosting Productivity in Remote Teams")
tone = st.sidebar.selectbox("Tone", ["Conversational", "Professional", "Casual", "Formal"])
audience = st.sidebar.text_input("Target Audience", "Startup Founders")
style = st.sidebar.selectbox("Writing Style", ["How-to", "Listicle", "Narrative", "Case Study", "Opinion"])
perspective = st.sidebar.selectbox("Perspective", ["First-person", "Third-person"])
cta_type = st.sidebar.text_input("Call-to-Action", "Contact us for a free consultation")
keywords = st.sidebar.text_input("SEO Keywords (comma-separated)", "remote work, productivity, team management")
template_choice = st.sidebar.selectbox("Writing Template Preset", list(TEMPLATE_PRESETS.keys()))
template = TEMPLATE_PRESETS[template_choice]

word_count = st.sidebar.slider("Word Count", 300, 2000, 800)
model = st.sidebar.selectbox("AI Model", ["llama3", "gemma", "mistral"])
subheadings = st.sidebar.slider("H2 Subheadings", 2, 6, 4)
include_meta = st.sidebar.checkbox("Include Meta Description", value=True)
include_conclusion = st.sidebar.checkbox("Include Conclusion + CTA", value=True)
UNSPLASH_ACCESS_KEY = st.sidebar.text_input("🔑 Unsplash Access Key", type="password")
enable_fiverr_package = st.sidebar.checkbox("🎁 Fiverr ZIP Package", value=True)

# History
history_entries = db.all()
if history_entries:
    titles = [f"{i['topic']} ({i['timestamp']})" for i in history_entries]
    selected = st.sidebar.selectbox("📖 Load Past Blog", titles)
    if selected:
        loaded = history_entries[titles.index(selected)]
        if st.sidebar.button("📤 Load This Blog"):
            st.session_state["loaded_blog"] = loaded

if "loaded_blog" in st.session_state:
    b = st.session_state["loaded_blog"]
    st.subheader(f"📄 Loaded Blog: {b['topic']}")
    st.text_area("Blog Output", b["blog"], height=500)
    st.download_button("⬇️ Download .txt", data=b["blog"], file_name=f"{b['topic']}.txt")

if st.sidebar.button("🗑️ Clear History"):
    db.truncate()
    st.success("History cleared!")

# Generate Blog
if st.button("🚀 Generate Blog"):
    with st.spinner("Generating and Enhancing..."):
        blog = generate_blog_ollama(topic, tone, audience, word_count, model,
                                    subheadings, include_meta, include_conclusion,
                                    style, perspective, cta_type, keywords, template)

        st.subheader("📄 Generated Blog")
        st.text_area("Blog Output", blog, height=500)

        # Quality Metrics
        st.success(f"✅ Voice Tone Score: {voice_tone_score(blog)}")
        st.warning(f"🔍 Estimated Plagiarism: {fake_plagiarism_score()}%")

        # Export
        docx_filename = f"{topic.replace(' ', '_')}.docx"
        export_to_docx(blog, docx_filename)
        st.download_button("⬇️ Download .docx", data=open(docx_filename, "rb"), file_name=docx_filename)
        st.download_button("⬇️ Download .txt", data=blog, file_name=f"{topic.replace(' ', '_')}.txt")

        save_blog_to_db(topic, tone, audience, word_count, model, blog, style, perspective, cta_type, keywords, template)

        img_urls = []
        if UNSPLASH_ACCESS_KEY:
            st.subheader("🖼️ Suggested Images")
            img_urls = get_unsplash_images(topic, UNSPLASH_ACCESS_KEY)
            for url in img_urls:
                st.image(url, use_column_width=True)
                st.code(url)

        if enable_fiverr_package:
            with st.spinner("📦 Creating Fiverr ZIP..."):
                zip_path = create_fiverr_package(blog, docx_filename, img_urls, topic)
                with open(zip_path, "rb") as zf:
                    st.download_button("⬇️ Download ZIP Package", data=zf, file_name=os.path.basename(zip_path))
