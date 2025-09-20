import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import time
import re

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
        # Multiple user agents to rotate through
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
    
    def fetch_http(self, url, retry_count=2):
        for attempt in range(retry_count + 1):
            try:
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                # Rotate user agents
                user_agent = self.user_agents[attempt % len(self.user_agents)]
                
                headers = {
                    "User-Agent": user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0"
                }
                
                # First, get the page to establish session
                self.session.get("https://www.google.com/", headers=headers, timeout=10, verify=True)
                time.sleep(1)
                
                # Then request the target URL
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
                if attempt == retry_count:
                    st.error(f"HTTP request failed for {url}: {str(e)}")
                    return None
                time.sleep(2)  # Wait before retry
    
    def try_all_methods(self, url):
        """Try different approaches to fetch content"""
        response = self.fetch_http(url)
        
        if not response or self.is_blocked(response):
            # Try with different approach
            try:
                # Alternative headers approach
                alt_headers = {
                    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                response = requests.get(url, headers=alt_headers, timeout=15, verify=True)
                if response.status_code == 200:
                    return {
                        "method": "HTTP (Googlebot)",
                        "url": response.url,
                        "status": response.status_code,
                        "html": response.text,
                        "headers": dict(response.headers),
                        "user_agent": alt_headers["User-Agent"]
                    }
            except:
                pass
        return response
        
    def is_blocked(self, response):
        if not response:
            return True
            
        html = response.get("html", "").lower()
        status = response.get("status", 200)
        
        blocked_indicators = [
            status == 403, status == 429, status == 503,
            "access denied" in html, "cloudflare" in html,
            "captcha" in html, "security" in html, "bot" in html,
            "blocked" in html, "denied" in html
        ]
        
        return any(blocked_indicators)
    
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
        
        # Try lxml first, fallback to html.parser
        try:
            soup = BeautifulSoup(html, 'lxml')
        except:
            soup = BeautifulSoup(html, 'html.parser')
        
        title = soup.title.string if soup.title else "No Title"
        if title and len(title) > 60:
            title = title[:57] + "..."
            
        lang = soup.html.get('lang', '-') if soup.html else '-'
        indexable = "✔️" if self.check_indexable(soup) else "❌"
        
        # Extract hreflang tags with comprehensive search
        hreflang_tags = []
        issues = []
        
        # Check link tags
        for link in soup.find_all('link', rel='alternate'):
            hreflang = link.get('hreflang', '')
            href = link.get('href', '')
            if hreflang and href:
                full_url = urljoin(url, href)
                hreflang_tags.append((hreflang.lower(), full_url))
                
                # Validate hreflang
                if not self.validate_hreflang(hreflang):
                    issues.append(f"Invalid hreflang: {hreflang}")
                if not self.url_matches(full_url, url):
                    issues.append(f"URL mismatch: {full_url}")
        
        # Also check meta tags and HTTP headers for hreflang
        if not hreflang_tags:
            issues.append("No hreflang tags found")
        
        # Prepare comprehensive result
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
        
        # Add ALL hreflang pairs (up to 10)
        for i in range(1, 11):
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
            
        # Basic validation without pycountry
        parts = hreflang.split('-')
        if len(parts) > 2:
            return False
        
        # Language code should be 2-3 letters
        if not (2 <= len(parts[0]) <= 3):
            return False
            
        # Country code should be 2 letters if present
        if len(parts) > 1 and len(parts[1]) != 2:
            return False
            
        return True
            
    def url_matches(self, href, base_url):
        try:
            norm_href = self.normalize_url(href)
            norm_base = self.normalize_url(base_url)
            return norm_href == norm_base
        except:
            return False
        
    def normalize_url(self, url):
        parsed = urlparse(url)
        # Remove www. subdomain for comparison
        netloc = parsed.netloc.replace('www.', '')
        return f"{parsed.scheme}://{netloc}{parsed.path}".rstrip('/').lower()
        
    def check_indexable(self, soup):
        # Check robots meta tag
        robots = soup.find('meta', attrs={'name': 'robots'})
        if robots and 'noindex' in robots.get('content', '').lower():
            return False
            
        # Check for noindex in X-Robots-Tag (would be in headers)
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
                                ["Single URL", "Bulk URLs (Text)"],
                                help="Choose how to input URLs for analysis")
        
        if analysis_type == "Single URL":
            url_input = st.text_input("Enter URL", placeholder="https://example.com")
            urls = [url_input.strip()] if url_input and url_input.strip() else []
        else:
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
        max_urls = st.slider("Max URLs", 1, 20, 5,
                            help="Limit to avoid timeouts")
    
    with col3:
        st.write("### Controls")
        analyze_btn = st.button("🚀 Analyze URLs", type="primary", use_container_width=True)
        stop_btn = st.button("⏹️ Stop", type="secondary", 
                           disabled=not st.session_state.processing,
                           use_container_width=True)
    
    # Handle stop button
    if stop_btn and st.session_state.processing:
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
                        display_cols = ["URL", "Status", "Title", "Hreflang Count", "Issues"]
                        available_cols = [col for col in display_cols if col in current_df.columns]
                        st.dataframe(current_df[available_cols], use_container_width=True)
            
            time.sleep(1)  # Be nice to servers
        
        if st.session_state.processing:
            st.success(f"✅ Analysis complete! Processed {len(st.session_state.results)} URLs")
        st.session_state.processing = False
    
    # Display comprehensive results
    if st.session_state.results:
        st.subheader("📋 Detailed Analysis Results")
        results_df = pd.DataFrame(st.session_state.results)
        
        # Show full data
        st.dataframe(results_df, use_container_width=True, height=400)
        
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
