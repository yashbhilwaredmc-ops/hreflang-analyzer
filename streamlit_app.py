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
    page_title="DMC hreflang Analyzer",
    page_icon=":globe_with_meridians:",
    layout="wide"
)

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = []
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'checker' not in st.session_state:
    st.session_state.checker = None

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
        # Check if processing was stopped
        if not st.session_state.processing:
            return None
            
        response = self.fetch_http(url)
            
        if not response:
            return {
                "URL": url,
                "Status": "Failed",
                "Title": "",
                "Language": "",
                "Indexable": ":x:",
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
        indexable = ":heavy_check_mark:" if self.check_indexable(soup) else ":x:"
        
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
    st.title(":globe_with_meridians: DMC Hreflang Analyzer")
    st.markdown("Analyze hreflang implementation for international SEO")
    
    # Initialize checker
    if st.session_state.checker is None:
        st.session_state.checker = HreflangChecker()
    
    # Input section
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        analysis_type = st.radio("Analysis Type", ["Single URL", "Bulk URLs (File Upload)", "Multiple URLs (Text)"])
        
        if analysis_type == "Single URL":
            url_input = st.text_input("Enter URL", placeholder="https://example.com")
            urls = [url_input.strip()] if url_input and url_input.strip() else []
            
        elif analysis_type == "Bulk URLs (File Upload)":
            uploaded_file = st.file_uploader("Upload URLs file", type=["txt", "csv"], 
                                           help="Upload a text file with one URL per line or a CSV file with URLs in the first column")
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        # Read CSV file
                        df = pd.read_csv(uploaded_file)
                        urls = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
                    else:
                        # Read text file
                        content = uploaded_file.read().decode("utf-8")
                        urls = [line.strip() for line in content.split('\n') if line.strip()]
                except Exception as e:
                    st.error(f"Error reading file: {e}")
                    urls = []
            else:
                urls = []
                
        else:  # Multiple URLs (Text)
            url_input = st.text_area("Enter URLs (one per line)", placeholder="https://example.com\nhttps://example.org", height=100)
            if url_input:
                urls = [url.strip() for url in url_input.split('\n') if url.strip()]
            else:
                urls = []
    
    with col2:
        max_urls = st.number_input("Max URLs to process", min_value=1, max_value=50, value=10,
                                  help="Limit number of URLs to avoid timeouts")
    
    with col3:
        st.write("")  # Spacer
        st.write("")  # Spacer
        analyze_btn = st.button("Analyze URLs", type="primary", use_container_width=True)
        stop_btn = st.button("Stop Processing", type="secondary", use_container_width=True, 
                           disabled=not st.session_state.processing)
    
    # Handle stop button
    if stop_btn and st.session_state.processing:
        st.session_state.processing = False
        st.warning("Processing stopped by user")
    
    # Process button
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
        results_placeholder = st.empty()
        
        for i, url in enumerate(urls_to_process):
            # Check if processing was stopped
            if not st.session_state.processing:
                break
                
            status_text.text(f"Processing {i+1}/{total_urls}: {url}")
            result = st.session_state.checker.process_url(url)
            
            if result:  # Only add if we got a result (not stopped)
                st.session_state.results.append(result)
                
                # Update progress
                progress_bar.progress((i + 1) / total_urls)
                
                # Display intermediate results
                if st.session_state.results:
                    results_df = pd.DataFrame(st.session_state.results)
                    display_cols = ["URL", "Status", "Title", "Hreflang Count", "Issues"]
                    available_cols = [col for col in display_cols if col in results_df.columns]
                    results_placeholder.dataframe(results_df[available_cols], use_container_width=True, height=200)
            
            time.sleep(0.5)  # Be nice to servers
        
        if st.session_state.processing:  # Only show complete if not stopped
            status_text.text("Analysis complete!")
            st.success(f"Processed {len(st.session_state.results)} URLs")
        st.session_state.processing = False
    
    # Display results
    if st.session_state.results:
        st.subheader("Detailed Results")
        results_df = pd.DataFrame(st.session_state.results)
        
        # Ensure all columns exist
        for i in range(1, 4):
            if f"hreflang {i}" not in results_df.columns:
                results_df[f"hreflang {i}"] = ""
            if f"URL {i}" not in results_df.columns:
                results_df[f"URL {i}"] = ""
        
        st.dataframe(results_df, use_container_width=True, height=400)
        
        # Summary statistics
        st.subheader("Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        successful = len(results_df[~results_df["Status"].str.contains("Failed")])
        with col1:
            st.metric("Total URLs", len(results_df))
        with col2:
            st.metric("Successful", successful)
        with col3:
            failed = len(results_df) - successful
            st.metric("Failed", failed)
        with col4:
            avg_hreflangs = results_df["Hreflang Count"].mean()
            st.metric("Avg. Hreflangs", f"{avg_hreflangs:.1f}")
        
        # Export options
        st.subheader("Export Results")
        export_col1, export_col2 = st.columns(2)
        
        with export_col1:
            # Download CSV button
            csv = results_df.to_csv(index=False)
            st.download_button(
                label=":inbox_tray: Download CSV Report",
                data=csv,
                file_name="hreflang_analysis.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with export_col2:
            # Show raw data option
            if st.button(":clipboard: Show Raw Data", use_container_width=True):
                st.text_area("Raw CSV Data", csv, height=200)

if __name__ == "__main__":
    main()


