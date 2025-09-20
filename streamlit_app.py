import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
import pycountry
import pandas as pd
import time
import io

# Set page configuration
st.set_page_config(
    page_title="DMC Professional Hreflang Analyzer",
    page_icon="🌐",
    layout="wide"
)

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = []
if 'processing' not in st.session_state:
    st.session_state.processing = False

class AdvancedHreflangChecker:
    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
    
    def fetch_http(self, url, method="Auto"):
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Rotate user agents for better success rate
            user_agent = self.ua.chrome
            headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://www.google.com/"
            }
            
            # Add cookies first
            self.session.get("https://www.google.com/", headers=headers, timeout=10, verify=True)
            time.sleep(1)  # Be polite
            
            # Main request
            response = self.session.get(
                url,
                headers=headers,
                timeout=20,
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
    
    def try_all_methods(self, url):
        """Try different approaches to fetch content"""
        response = self.fetch_http(url)
        
        if not response or self.is_blocked(response):
            # Try with different user agent
            try:
                user_agent = self.ua.firefox
                headers = {"User-Agent": user_agent}
                response = self.session.get(url, headers=headers, timeout=15, verify=True)
                if response.status_code == 200:
                    return {
                        "method": "HTTP (Alternate UA)",
                        "url": response.url,
                        "status": response.status_code,
                        "html": response.text,
                        "headers": dict(response.headers),
                        "user_agent": user_agent
                    }
            except:
                pass
        return response
        
    def is_blocked(self, response):
        if not response:
            return True
            
        html = response.get("html", "").lower()
        status = response.get("status", 200)
        
        return (
            status == 403 or
            status == 429 or
            "access denied" in html or
            "cloudflare" in html or
            "captcha" in html or
            "security" in html
        )
    
    def process_url(self, url, method="Auto"):
        if not st.session_state.processing:
            return None
            
        if method == "Auto":
            response = self.try_all_methods(url)
        else:
            response = self.fetch_http(url)
            
        if not response:
            return {
                "URL": url,
                "Status": "Failed",
                "Title": "",
                "Language": "",
                "Indexable": "❌",
                "Method": "Failed",
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
        
        # Prepare comprehensive result (ALL the fields you wanted)
        result = {
            "URL": url,
            "Status": f"{response.get('status', '200')}",
            "Title": title,
            "Language": lang,
            "Indexable": indexable,
            "Method": method,
            "User-Agent": response.get("user_agent", "N/A"),
            "Issues": ", ".join(issues) if issues else "Valid",
            "Hreflang Count": len(hreflang_tags)
        }
        
        # Add ALL hreflang pairs (not just 3)
        for i in range(1, 11):  # Support up to 10 hreflang tags
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
            
        try:
            if parts[0]:
                try:
                    pycountry.languages.get(alpha_2=parts[0])
                except:
                    # Try alternative lookup
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
            
        # Check for canonical issues
        canonicals = soup.find_all('link', rel='canonical')
        if len(canonicals) > 1:
            return False
            
        return True

# Create the Streamlit interface
def main():
    st.title("🌐 DMC Professional Hreflang Analyzer")
    st.markdown("### Complete hreflang analysis with all desktop app features")
    
    # Initialize checker
    if 'checker' not in st.session_state:
        st.session_state.checker = AdvancedHreflangChecker()
    
    # Input section with ALL options
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        analysis_type = st.radio("Analysis Type", 
                                ["Single URL", "Bulk URLs (File Upload)", "Multiple URLs (Text)"],
                                help="Choose how to input URLs for analysis")
        
        if analysis_type == "Single URL":
            url_input = st.text_input("Enter URL", placeholder="https://example.com")
            urls = [url_input.strip()] if url_input and url_input.strip() else []
            
        elif analysis_type == "Bulk URLs (File Upload)":
            uploaded_file = st.file_uploader("Upload URLs file", 
                                           type=["txt", "csv"], 
                                           help="Upload TXT (one URL per line) or CSV (URLs in first column)")
            if uploaded_file:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                        urls = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
                    else:
                        content = uploaded_file.read().decode("utf-8")
                        urls = [line.strip() for line in content.split('\n') if line.strip()]
                    st.success(f"Loaded {len(urls)} URLs from file")
                except Exception as e:
                    st.error(f"Error reading file: {e}")
                    urls = []
            else:
                urls = []
                
        else:  # Multiple URLs (Text)
            url_input = st.text_area("Enter URLs (one per line)", 
                                   placeholder="https://example.com\nhttps://example.org", 
                                   height=100)
            if url_input:
                urls = [url.strip() for url in url_input.split('\n') if url.strip()]
            else:
                urls = []
    
    with col2:
        method = st.selectbox("Method", ["Auto", "Direct HTTP"], 
                             help="Auto tries multiple approaches if blocked")
        max_urls = st.slider("Max URLs to process", 1, 50, 10,
                            help="Limit to avoid timeouts")
    
    with col3:
        st.write("### Controls")
        analyze_btn = st.button("🚀 Analyze URLs", type="primary", use_container_width=True)
        stop_btn = st.button("⏹️ Stop Processing", type="secondary", 
                           disabled=not st.session_state.processing,
                           use_container_width=True)
        export_btn = st.button("📊 Export Results", 
                             disabled=len(st.session_state.results) == 0,
                             use_container_width=True)
    
    # Handle controls
    if stop_btn:
        st.session_state.processing = False
        st.warning("Processing stopped by user")
    
    # Process URLs
    if analyze_btn and urls:
        st.session_state.processing = True
        urls_to_process = urls[:max_urls]
        total_urls = len(urls_to_process)
        
        if total_urls == 0:
            st.warning("Please enter at least one valid URL")
            return
            
        st.session_state.results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.empty()
        
        # Process each URL
        for i, url in enumerate(urls_to_process):
            if not st.session_state.processing:
                break
                
            status_text.text(f"🔍 Processing {i+1}/{total_urls}: {url}")
            result = st.session_state.checker.process_url(url, method)
            
            if result:
                st.session_state.results.append(result)
                progress_bar.progress((i + 1) / total_urls)
                
                # Show intermediate results
                if st.session_state.results:
                    with results_container.container():
                        st.subheader("Current Results")
                        current_df = pd.DataFrame(st.session_state.results)
                        st.dataframe(current_df[["URL", "Status", "Title", "Hreflang Count", "Issues"]], 
                                   use_container_width=True)
            
            time.sleep(1)  # Be nice to servers
        
        if st.session_state.processing:
            st.success(f"✅ Analysis complete! Processed {len(st.session_state.results)} URLs")
        st.session_state.processing = False
    
    # Display comprehensive results
    if st.session_state.results:
        st.subheader("📋 Detailed Analysis Results")
        results_df = pd.DataFrame(st.session_state.results)
        
        # Show full data
        st.dataframe(results_df, use_container_width=True, height=500)
        
        # Summary statistics
        st.subheader("📊 Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        successful = len(results_df[~results_df["Status"].str.contains("Failed")])
        total_hreflangs = results_df["Hreflang Count"].sum()
        
        with col1:
            st.metric("Total URLs", len(results_df))
        with col2:
            st.metric("Successful", successful)
        with col3:
            failed = len(results_df) - successful
            st.metric("Failed", failed)
        with col4:
            avg_hreflangs = results_df["Hreflang Count"].mean()
            st.metric("Avg Hreflangs", f"{avg_hreflangs:.1f}")
        
        # Export functionality
        if export_btn or st.session_state.results:
            csv = results_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Full CSV Report",
                data=csv,
                file_name="dmc_hreflang_analysis.csv",
                mime="text/csv",
                use_container_width=True
            )

if __name__ == "__main__":
    main()
