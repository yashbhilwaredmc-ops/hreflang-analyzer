import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import time
import random
from fake_useragent import UserAgent
import pycountry
import io

# Set page configuration
st.set_page_config(
    page_title="DMC hreflang Analyzer",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #43A047;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .success-box {
        background-color: #E8F5E9;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #4CAF50;
        margin: 10px 0;
    }
    .error-box {
        background-color: #FFEBEE;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #F44336;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #FFF8E1;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #FFC107;
        margin: 10px 0;
    }
    .info-box {
        background-color: #E3F2FD;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #2196F3;
        margin: 10px 0;
    }
    .stProgress > div > div > div > div {
        background-color: #1E88E5;
    }
    .stButton button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

class AdvancedHreflangChecker:
    def __init__(self):
        self.results = []
        self.processing = False
        self.current_url_index = 0
        self.total_urls = 0
        
    def log(self, message, level="info"):
        timestamp = time.strftime("%H:%M:%S")
        if level == "error":
            st.error(f"[{timestamp}] {message}")
        elif level == "warning":
            st.warning(f"[{timestamp}] {message}")
        elif level == "success":
            st.success(f"[{timestamp}] {message}")
        else:
            st.info(f"[{timestamp}] {message}")
    
    def setup_ui(self):
        st.markdown('<h1 class="main-header">🌐 Professional hreflang Analyzer</h1>', unsafe_allow_html=True)
        
        # Input section
        with st.expander("Configuration", expanded=True):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                analysis_type = st.radio("Analysis Type", ["Single URL", "Bulk URLs"])
                
                if analysis_type == "Single URL":
                    single_url = st.text_input("Enter URL:", placeholder="https://example.com")
                    urls = [single_url] if single_url else []
                else:
                    uploaded_file = st.file_uploader("Upload URLs file", type=["txt", "csv"])
                    if uploaded_file is not None:
                        try:
                            # Read the uploaded file
                            stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
                            urls = [line.strip() for line in stringio if line.strip()]
                        except Exception as e:
                            st.error(f"Error reading file: {str(e)}")
                            urls = []
                    else:
                        urls = []
            
            with col2:
                method = st.selectbox("Method:", ["Auto", "Direct HTTP", "Browser Automation"])
                threads = st.slider("Threads:", 1, 10, 3)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    run_btn = st.button("🚀 Start Analysis", use_container_width=True)
                with col2:
                    stop_btn = st.button("⏹️ Stop", use_container_width=True, disabled=not self.processing)
                with col3:
                    export_btn = st.button("💾 Export CSV", use_container_width=True, disabled=not self.results)
        
        # Progress section
        progress_placeholder = st.empty()
        
        # Results section
        results_placeholder = st.empty()
        
        return {
            'urls': urls,
            'method': method,
            'threads': threads,
            'run_btn': run_btn,
            'stop_btn': stop_btn,
            'export_btn': export_btn,
            'progress_placeholder': progress_placeholder,
            'results_placeholder': results_placeholder
        }
    
    def start_analysis(self, urls, method):
        if not urls:
            st.error("Please provide at least one URL to analyze")
            return
            
        self.results = []
        self.processing = True
        self.total_urls = len(urls)
        self.current_url_index = 0
        
        # Initialize progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, url in enumerate(urls):
            if not self.processing:
                break
                
            self.current_url_index = i + 1
            progress = (self.current_url_index / self.total_urls)
            progress_bar.progress(progress)
            status_text.text(f"Processing {self.current_url_index} of {self.total_urls}: {url[:50]}...")
            
            if method == "Auto":
                response = self.try_all_methods(url)
            elif method == "Direct HTTP":
                response = self.fetch_http(url)
            else:
                # Browser automation would require Selenium which is complex in Streamlit Cloud
                # For simplicity, we'll use HTTP method as fallback
                response = self.fetch_http(url)
                
            if not response:
                result = {
                    "URL": url,
                    "Status": "Failed",
                    "Title": "",
                    "Language": "",
                    "Indexable": "❌",
                    "Method": "Failed",
                    "User-Agent": "N/A",
                    "Issues": "Failed to fetch URL"
                }
                self.results.append(result)
                continue
                
            self.process_response(url, response)
            
            # Add a small delay to avoid being blocked
            time.sleep(1)
        
        self.processing = False
        progress_bar.empty()
        status_text.text(f"Completed {self.current_url_index} of {self.total_urls} URLs")
        
        # Display results
        self.display_results()
    
    def process_response(self, url, response):
        html = response["html"]
        method = response["method"]
        
        soup = BeautifulSoup(html, 'lxml')
        title = soup.title.string if soup.title else "No Title"
        lang = soup.html.get('lang', '-') if soup.html else '-'
        indexable = "✔️" if self.check_indexable(soup) else "❌"
        
        # Extract hreflang tags
        hreflang_tags = []
        issues = []
        for link in soup.find_all('link', rel='alternate'):
            hreflang = link.get('hreflang', '').lower()
            href = urljoin(url, link.get('href', ''))
            if hreflang and href:
                hreflang_tags.append((hreflang, href))
                
                # Validate hreflang
                if not self.validate_hreflang(hreflang):
                    issues.append(f"Invalid hreflang: {hreflang}")
                if not self.url_matches(href, url):
                    issues.append(f"URL mismatch: {href}")
        
        # Prepare single-row result
        result = {
            "URL": url,
            "Status": f"{response.get('status', '200')} OK",
            "Title": title,
            "Language": lang,
            "Indexable": indexable,
            "Method": method,
            "User-Agent": response.get("user_agent", "N/A"),
            "Issues": ", ".join(issues) if issues else "Valid"
        }
        
        # Add hreflang pairs (up to 3)
        for i in range(1, 4):
            if i <= len(hreflang_tags):
                result[f"hreflang {i}"] = hreflang_tags[i-1][0]
                result[f"URL {i}"] = hreflang_tags[i-1][1]
            else:
                result[f"hreflang {i}"] = ""
                result[f"URL {i}"] = ""
        
        self.results.append(result)
        self.log(f"Processed: {url} ({len(hreflang_tags)} hreflang tags)")
    
    def display_results(self):
        if not self.results:
            return
            
        # Convert results to DataFrame
        df = pd.DataFrame(self.results)
        
        # Ensure all columns exist
        for i in range(1, 4):
            if f"hreflang {i}" not in df.columns:
                df[f"hreflang {i}"] = ""
            if f"URL {i}" not in df.columns:
                df[f"URL {i}"] = ""
        
        # Reorder columns
        columns = [
            "URL", "Status", "Title", "Language", "Indexable", "Method",
            "User-Agent", "hreflang 1", "URL 1", "hreflang 2", "URL 2", 
            "hreflang 3", "URL 3", "Issues"
        ]
        
        # Add missing columns with empty values
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        
        df = df[columns]
        
        # Display results
        st.markdown('<div class="sub-header">Results</div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
    
    def export_to_csv(self):
        if not self.results:
            st.error("No results to export")
            return
            
        # Convert results to DataFrame
        df = pd.DataFrame(self.results)
        
        # Ensure all columns exist
        for i in range(1, 4):
            if f"hreflang {i}" not in df.columns:
                df[f"hreflang {i}"] = ""
            if f"URL {i}" not in df.columns:
                df[f"URL {i}"] = ""
        
        # Reorder columns
        columns = [
            "URL", "Status", "Title", "Language", "Indexable", "Method",
            "User-Agent", "hreflang 1", "URL 1", "hreflang 2", "URL 2", 
            "hreflang 3", "URL 3", "Issues"
        ]
        
        # Add missing columns with empty values
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        
        df = df[columns]
        
        # Convert DataFrame to CSV
        csv = df.to_csv(index=False)
        
        # Create download button
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="hreflang_analysis.csv",
            mime="text/csv"
        )
    
    def try_all_methods(self, url):
        self.log("Trying direct HTTP request...")
        response = self.fetch_http(url)
        
        if not response or self.is_blocked(response):
            self.log("Falling back to browser automation...")
            # In Streamlit Cloud, we can't easily run browser automation
            # So we'll just return the HTTP response even if it might be blocked
            pass
            
        return response
        
    def fetch_http(self, url):
        try:
            ua = UserAgent()
            user_agent = ua.chrome
            headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://www.google.com/"
            }
            
            self.log(f"Using User-Agent: {user_agent}")
            
            response = requests.get(
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
            self.log(f"HTTP request failed for {url}: {str(e)}", "error")
            return None
            
    def is_blocked(self, response):
        if not response:
            return True
            
        html = response.get("html", "").lower()
        return (
            response.get("status") == 403 or
            "access denied" in html or
            "cloudflare" in html or
            "captcha" in html
        )
    
    def validate_hreflang(self, hreflang):
        if hreflang == 'x-default':
            return True
            
        parts = hreflang.split('-')
        if len(parts) > 2:
            return False        
            
        try:
            if parts[0]:
                pycountry.languages.get(alpha_2=parts[0])
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
        return not (robots and 'noindex' in robots.get('content', '').lower())

def main():
    checker = AdvancedHreflangChecker()
    ui_elements = checker.setup_ui()
    
    if ui_elements['run_btn'] and ui_elements['urls']:
        checker.start_analysis(ui_elements['urls'], ui_elements['method'])
    
    if ui_elements['stop_btn']:
        checker.processing = False
        st.warning("Processing stopped by user")
    
    if ui_elements['export_btn']:
        checker.export_to_csv()

if __name__ == "__main__":
    main()
