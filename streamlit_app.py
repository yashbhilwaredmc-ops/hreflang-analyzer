import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pycountry
import pandas as pd
import time

# Set page configuration
st.set_page_config(
    page_title="DMC Hreflang Analyzer",
    page_icon="🌐",
    layout="wide"
)

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = []
if 'processing' not in st.session_state:
    st.session_state.processing = False

class HreflangChecker:
    def __init__(self):
        self.session = requests.Session()
    
    def fetch_http(self, url):
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            
            response = self.session.get(
                url,
                headers=headers,
                timeout=15,
                allow_redirects=True,
                verify=True
            )
            
            response.raise_for_status()
            return {
                "method": "HTTP",
                "url": response.url,
                "status": response.status_code,
                "html": response.text,
                "headers": dict(response.headers),
                "user_agent": headers["User-Agent"]
            }
            
        except Exception as e:
            st.error(f"HTTP request failed for {url}: {str(e)}")
            return None
    
    def process_url(self, url):
        if not st.session_state.processing:
            return None
            
        response = self.fetch_http(url)
            
        if not response:
            return {
                "URL": url,
                "Status": "Failed",
                "Title": "",
                "Language": "",
                "Indexable": "❌",
                "Method": "HTTP",
                "User-Agent": "N/A",
                "Issues": "Failed to fetch URL",
                "Hreflang Count": 0
            }
            
        return self.process_response(url, response)
    
    def process_response(self, url, response):
        html = response["html"]
        method = response["method"]
        
        soup = BeautifulSoup(html, 'html.parser')  # Use html.parser instead of lxml
        title = soup.title.string if soup.title else "No Title"
        if title and len(title) > 60:
            title = title[:57] + "..."
            
        lang = soup.html.get('lang', '-') if soup.html else '-'
        
        # Check if indexable
        indexable = "✔️"
        robots = soup.find('meta', attrs={'name': 'robots'})
        if robots and 'noindex' in robots.get('content', '').lower():
            indexable = "❌"
        
        # Extract hreflang tags
        hreflang_tags = []
        issues = []
        for link in soup.find_all('link', rel='alternate'):
            hreflang = link.get('hreflang', '')
            href = link.get('href', '')
            if hreflang and href:
                full_url = urljoin(url, href)
                hreflang_tags.append((hreflang.lower(), full_url))
                
                # Validate hreflang
                if not self.validate_hreflang(hreflang):
                    issues.append(f"Invalid hreflang: {hreflang}")
        
        # Prepare result
        result = {
            "URL": url,
            "Status": f"{response.get('status', '200')}",
            "Title": title,
            "Language": lang,
            "Indexable": indexable,
            "Method": method,
            "User-Agent": response.get("user_agent", "N/A"),
            "Issues": ", ".join(issues) if issues else "None",
            "Hreflang Count": len(hreflang_tags)
        }
        
        # Add hreflang pairs
        for i in range(1, 4):
            if i <= len(hreflang_tags):
                result[f"hreflang {i}"] = hreflang_tags[i-1][0]
                result[f"URL {i}"] = hreflang_tags[i-1][1]
            else:
                result[f"hreflang {i}"] = ""
                result[f"URL {i}"] = ""
        
        return result
    
    def validate_hreflang(self, hreflang):
        if hreflang == 'x-default':
            return True
            
        parts = hreflang.split('-')
        if len(parts) > 2:
            return False
        
        # Simple validation - check if it looks like a language code
        if len(parts[0]) != 2:
            return False
            
        if len(parts) > 1 and len(parts[1]) != 2:
            return False
            
        return True

# Create the Streamlit interface
def main():
    st.title("🌐 DMC Hreflang Analyzer")
    st.markdown("Analyze hreflang implementation for SEO")
    
    # Initialize checker
    if 'checker' not in st.session_state:
        st.session_state.checker = HreflangChecker()
    
    # Input section
    analysis_type = st.radio("Analysis Type", ["Single URL", "Multiple URLs"])
    
    if analysis_type == "Single URL":
        url_input = st.text_input("Enter URL", placeholder="https://example.com")
        urls = [url_input.strip()] if url_input and url_input.strip() else []
    else:
        url_input = st.text_area("Enter URLs (one per line)", placeholder="https://example.com\nhttps://example.org", height=100)
        urls = [url.strip() for url in url_input.split('\n') if url.strip()] if url_input else []
    
    max_urls = st.slider("Max URLs to process", 1, 20, 5)
    
    if st.button("Analyze URLs") and urls:
        st.session_state.processing = True
        urls_to_process = urls[:max_urls]
        total_urls = len(urls_to_process)
        
        if total_urls == 0:
            st.warning("Please enter at least one valid URL")
            return
            
        st.session_state.results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, url in enumerate(urls_to_process):
            if not st.session_state.processing:
                break
                
            status_text.text(f"Processing {i+1}/{total_urls}: {url}")
            result = st.session_state.checker.process_url(url)
            if result:
                st.session_state.results.append(result)
            progress_bar.progress((i + 1) / total_urls)
            time.sleep(1)  # Be nice to servers
        
        status_text.text("Analysis complete!")
        st.success(f"Processed {len(st.session_state.results)} URLs")
        st.session_state.processing = False
    
    # Display results
    if st.session_state.results:
        st.subheader("Results")
        results_df = pd.DataFrame(st.session_state.results)
        st.dataframe(results_df)
        
        # Download button
        csv = results_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="hreflang_analysis.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
