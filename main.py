import os
import time
import streamlit as st
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from dotenv import load_dotenv
from groq import Groq

# Load API key
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

# Set up Groq client
client = Groq(api_key=api_key)

# Selenium setup
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=chrome_options)

# Get top 10 Bing links
def get_top_bing_links(query):
    driver = get_driver()
    search_url = f"https://www.bing.com/search?q={query}"
    driver.get(search_url)
    time.sleep(2)

    links = []
    results = driver.find_elements(By.CSS_SELECTOR, 'li.b_algo h2 a')
    for r in results[:10]:
        url = r.get_attribute('href')
        if url:
            links.append(url)

    driver.quit()
    return links

# Extract content from a URL
def extract_text_from_url(url):
    try:
        driver = get_driver()
        driver.get(url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        paragraphs = soup.find_all('p')
        text = ' '.join(p.get_text() for p in paragraphs)
        driver.quit()
        return text[:2000]  # Limit size per URL
    except Exception as e:
        return f"Failed to extract from {url}: {e}"

# Query Groq model for summary
def get_summary_from_llm(content):
    prompt = f"Summarize the following content:\n\n{content}"
    response = client.chat.completions.create(
        messages=[
            {"role": "user", "content": prompt}
        ],
        model="llama-3.3-70b-versatile",
        stream=False,
    )
    return response.choices[0].message.content

# Streamlit UI
st.title("Search Summarizer using Bing + LLM")

query = st.text_input("Enter your search query:")

if st.button("Search and Summarize") and query:
    with st.spinner("Searching Bing..."):
        links = get_top_bing_links(query)
    
    all_content = ""
    with st.spinner("Extracting content from links..."):
        for url in links:
            content = extract_text_from_url(url)
            all_content += content + "\n\n"

    st.success("Content extracted. Generating summary...")

    summary = get_summary_from_llm(all_content)

    st.subheader("🔍 Summary:")
    st.write(summary)
