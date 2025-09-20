import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
import pycountry
import pandas as pd
import time

# Set page configuration
st.set_page_config(
    page_title="DMC hreflang Analyzer",
    page_icon="🌐",
    layout="wide"
)

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = []

class HreflangChecker:
    def fetch_http(self, url):
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            session = requests.Session()
            ua = UserAgent()
            user_agent = ua.chrome
            headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://www.google.com/"
            }
            
            response = session.get(
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
                "user_agent": user_agent
            }
            
        except Exception as e:
            st.error(f"HTTP request failed for {url}: {str(e)}")
            return None
    
    def process_url(self, url):
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
        
        soup = BeautifulSoup(html, 'lxml')
        title = soup.title.string if soup.title else "No Title"
        if title and len(title) > 60:
            title = title[:57] + "..."
            
        lang = soup.html.get('lang', '-') if soup.html else '-'
        indexable = "✔️" if self.check_indexable(soup) else "❌"
        
        # Extract hreflang tags
        hreflang_tags = []
        issues = []
        for link in soup.find_all('link', rel='alternate'):
            hreflang = link.get('hreflang', '')
            if hreflang:
                hreflang = hreflang.lower()
            href = urljoin(url, link.get('href', ''))
            if hreflang and href:
                hreflang_tags.append((hreflang, href))
                
                # Validate hreflang
                if not self.validate_hreflang(hreflang):
                    issues.append(f"Invalid hreflang: {hreflang}")
                if not self.url_matches(href, url):
                    issues.append(f"URL mismatch: {href}")
        
        # Prepare result
        result = {
            "URL": url,
            "Status": f"{response.get('status', '200')}",
            "Title": title,
            "Language": lang,
            "Indexable": indexable,
            "Method": method,
            "User-Agent": response.get("user_agent", "N/A")[:30] + "..." if len(response.get("user_agent", "")) > 30 else response.get("user_agent", "N/A"),
            "Issues": ", ".join(issues) if issues else "None",
            "Hreflang Count": len(hreflang_tags)
        }
        
        # Add hreflang pairs (up to 3)
        for i in range(1, 4):
            if i <= len(hreflang_tags):
                result[f"hreflang {i}"] = hreflang_tags[i-1][0]
                result[f"URL {i}"] = hreflang_tags[i-1][1][:50] + "..." if len(hreflang_tags[i-1][1]) > 50 else hreflang_tags[i-1][1]
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
            
        try:
            if parts[0]:
                try:
                    pycountry.languages.get(alpha_2=parts[0])
                except:
                    found = False
                    for lang in pycountry.languages:
                        if hasattr(lang, 'alpha_2') and lang.alpha_2 == parts[0]:
                            found = True
                            break
                    if not found:
                        return False
            if len(parts) > 1 and parts[1]:
                pycountry.countries.get(alpha_2=parts[1].upper())
            return True
        except:
            return False
            
    def url_matches(self, href, base_url):
        norm_href = self.normalize_url(href)
        norm_base = self.normalize_url(base_url)
        return norm_href == norm_base
        
    def normalize_url(self, url):
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/').lower()
        
    def check_indexable(self, soup):
        robots = soup.find('meta', attrs={'name': 'robots'})
        if robots and 'noindex' in robots.get('content', '').lower():
            return False
        return True

# Create the Streamlit interface
def main():
    st.title("🌐 DMC Hreflang Analyzer")
    st.markdown("Analyze hreflang implementation for international SEO")
    
    # Initialize checker
    if 'checker' not in st.session_state:
        st.session_state.checker = HreflangChecker()
    
    # Input section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        analysis_type = st.radio("Analysis Type", ["Single URL", "Multiple URLs"])
        
        if analysis_type == "Single URL":
            url_input = st.text_input("Enter URL", placeholder="https://example.com")
            urls = [url_input.strip()] if url_input and url_input.strip() else []
        else:
            url_input = st.text_area("Enter URLs (one per line)", placeholder="https://example.com\nhttps://example.org", height=100)
            if url_input:
                urls = [url.strip() for url in url_input.split('\n') if url.strip()]
            else:
                urls = []
    
    with col2:
        max_urls = st.number_input("Max URLs to process", min_value=1, max_value=20, value=5)
    
    # Process button
    if st.button("Analyze URLs", type="primary") and urls:
        urls_to_process = urls[:max_urls]
        total_urls = len(urls_to_process)
        
        if total_urls == 0:
            st.warning("Please enter at least one valid URL")
            return
            
        st.session_state.results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, url in enumerate(urls_to_process):
            status_text.text(f"Processing {i+1}/{total_urls}: {url}")
            result = st.session_state.checker.process_url(url)
            st.session_state.results.append(result)
            progress_bar.progress((i + 1) / total_urls)
            time.sleep(0.5)  # Be nice to servers
        
        status_text.text("Analysis complete!")
        st.success(f"Processed {len(st.session_state.results)} URLs")
    
    # Display results
    if st.session_state.results:
        st.subheader("Results")
        results_df = pd.DataFrame(st.session_state.results)
        
        # Ensure all columns exist
        for i in range(1, 4):
            if f"hreflang {i}" not in results_df.columns:
                results_df[f"hreflang {i}"] = ""
            if f"URL {i}" not in results_df.columns:
                results_df[f"URL {i}"] = ""
        
        st.dataframe(results_df, use_container_width=True)
        
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
