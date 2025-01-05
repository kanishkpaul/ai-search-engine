import streamlit as st
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from groq import Groq
import time
import re

class AISearchEngine:
    def __init__(self, groq_api_key):
        self.groq_client = Groq(api_key=groq_api_key)
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--disable-gpu')
        self.driver = webdriver.Chrome(options=self.chrome_options)
        
    def search_bing(self, query):
        """Search Bing and return list of URLs."""
        self.driver.get(f"https://www.bing.com/search?q={query}")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "b_results"))
        )
        links = self.driver.find_elements(By.CSS_SELECTOR, "#b_results h2 a")
        return [link.get_attribute('href') for link in links if link.get_attribute('href')]
    
    def clean_and_limit_text(self, text, max_words=1500):
        """Clean and limit text to a specified number of words."""
        # Remove extra whitespace and split into words
        words = text.split()
        
        # Limit to max_words
        limited_text = ' '.join(words[:max_words])
        
        # Remove any non-standard characters that might cause issues
        limited_text = re.sub(r'[^\x00-\x7F]+', ' ', limited_text)
        limited_text = re.sub(r'\s+', ' ', limited_text).strip()
        
        return limited_text
    
    def scrape_content(self, url, progress_bar=None):
        """Scrape and clean content from a URL."""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Get main content (if available)
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            
            # Get text and clean it
            text = main_content.get_text() if main_content else soup.get_text()
            
            # Clean and limit the text
            return self.clean_and_limit_text(text)
            
        except Exception as e:
            st.error(f"Error scraping {url}: {str(e)}")
            return ""
    
    def summarize_content(self, content):
        """Summarize content using Groq LLM."""
        try:
            # Create a more focused prompt to help with token management
            prompt = f"""Summarize the following text in 1-2 concise sentences, focusing on the core message:

{content}"""
            
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama-3.3-70b-versatile",
                stream=False,
                temperature=0.3,  # Lower temperature for more focused summaries
                max_tokens=100    # Limit response length
            )
            
            return chat_completion.choices[0].message.content
        except Exception as e:
            st.error(f"Error summarizing content: {str(e)}")
            return ""
    
    def search_and_summarize(self, query, max_results=5):
        """Main function to search, scrape, and summarize content."""
        results = {
            'summaries': [],
            'citations': []
        }
        
        # Get URLs from Bing
        urls = self.search_bing(query)[:max_results]
        
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Process each URL
        for i, url in enumerate(urls):
            status_text.text(f"Processing URL {i+1}/{len(urls)}: {url}")
            content = self.scrape_content(url)
            
            if content:
                # Display content length for debugging
                word_count = len(content.split())
                status_text.text(f"Processing URL {i+1}/{len(urls)}: {url} ({word_count} words)")
                
                summary = self.summarize_content(content)
                if summary:
                    results['summaries'].append(summary)
                    results['citations'].append(url)
            
            progress_bar.progress((i + 1) / len(urls))
            
            # Add delay between API calls to respect rate limits
            time.sleep(1)
            
        status_text.text("Processing complete!")
        time.sleep(1)
        status_text.empty()
        progress_bar.empty()
        
        return results
    
    def cleanup(self):
        """Clean up resources."""
        self.driver.quit()

# Streamlit interface
def main():
    st.set_page_config(page_title="AI Search Engine", layout="wide")
    
    st.title("AI Search Engine")
    st.write("Enter a search query to get AI-powered summaries from multiple sources.")
    
    # Initialize session state for button control
    if 'search_clicked' not in st.session_state:
        st.session_state.search_clicked = False
    
    # Sidebar for API key
    with st.sidebar:
        st.header("Settings")
        api_key = st.text_input("Enter your Groq API Key:", type="password")
        max_results = st.slider("Maximum number of results:", min_value=1, max_value=10, value=5)
    
    # Main search interface
    query = st.text_input("Enter your search query:")
    
    # Single search button with error handling
    if st.button("Search", key="search_button"):
        st.session_state.search_clicked = True
        
    if st.session_state.search_clicked:
        if not api_key:
            st.error("Please enter your Groq API key in the sidebar.")
        elif not query:
            st.error("Please enter a search query.")
        else:
            try:
                with st.spinner("Initializing search engine..."):
                    search_engine = AISearchEngine(api_key)
                
                try:
                    # Perform search and summarization
                    results = search_engine.search_and_summarize(query, max_results)
                    
                    # Display results
                    st.header("Results")
                    
                    if not results['summaries']:
                        st.warning("No results found or all summaries failed.")
                    else:
                        # Display summaries with citations
                        for i, (summary, citation) in enumerate(zip(results['summaries'], results['citations']), 1):
                            with st.container():
                                st.markdown(f"**Summary {i}:**")
                                st.write(summary)
                                st.markdown(f"*Source: [{citation}]({citation})*")
                                st.divider()
                    
                except Exception as e:
                    st.error(f"An error occurred during search: {str(e)}")
                    
                finally:
                    search_engine.cleanup()
                    
            except Exception as e:
                st.error(f"Failed to initialize search engine: {str(e)}")
        
        # Reset search state
        st.session_state.search_clicked = False

if __name__ == "__main__":
    main()