import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pycountry
from fake_useragent import UserAgent
import re

# Set page configuration
st.set_page_config(
    page_title="Professional Hreflang Analyzer",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App title and description
st.title("🌐 Professional Hreflang Analyzer")
st.markdown("""
This tool analyzes hreflang tags for international SEO. 
Hreflang tags tell search engines what language and regional URLs you have for your content, 
helping them serve the right version to users.
""")

# Initialize session state for results
if 'results' not in st.session_state:
    st.session_state.results = []
if 'processing' not in st.session_state:
    st.session_state.processing = False

def validate_hreflang(hreflang):
    """Validate if a hreflang value is properly formatted"""
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

def url_matches(href, base_url):
    """Check if two URLs match after normalization"""
    def normalize_url(url):
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/').lower()
        
    norm_href = normalize_url(href)
    norm_base = normalize_url(base_url)
    return norm_href == norm_base

def check_indexable(soup):
    """Check if a page is indexable by search engines"""
    robots = soup.find('meta', attrs={'name': 'robots'})
    return not (robots and 'noindex' in robots.get('content', '').lower())

def fetch_url(url, method="auto"):
    """Fetch URL content using specified method"""
    try:
        if method in ["auto", "http"]:
            session = requests.Session()
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
            
            response = session.get(
                url,
                headers=headers,
                timeout=15,
                allow_redirects=True,
                verify=True
            )
            
            response.raise_for_status()
            
            # Check if blocked
            html_content = response.text.lower()
            is_blocked = (
                response.status_code == 403 or
                "access denied" in html_content or
                "cloudflare" in html_content
            )
            
            if not is_blocked or method == "http":
                return {
                    "method": "HTTP",
                    "url": response.url,
                    "status": response.status_code,
                    "html": response.text,
                    "user_agent": user_agent
                }
        
        # If HTTP failed or we need browser method
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            time.sleep(3)
            
            user_agent = driver.execute_script("return navigator.userAgent;")
                
            return {
                "method": "Browser",
                "url": driver.current_url,
                "status": 200,
                "html": driver.page_source,
                "user_agent": user_agent
            }
        except:
            return None
            
    except Exception as e:
        return None

def process_url(url, method="auto"):
    """Process a single URL and extract hreflang information"""
    response = fetch_url(url, method)
    
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
            "hreflang 1": "", "URL 1": "",
            "hreflang 2": "", "URL 2": "",
            "hreflang 3": "", "URL 3": ""
        }
    
    html = response["html"]
    method_used = response["method"]
    user_agent = response["user_agent"]
    
    soup = BeautifulSoup(html, 'lxml')
    title = soup.title.string if soup.title else "No Title"
    lang = soup.html.get('lang', '-') if soup.html else '-'
    indexable = "✔️" if check_indexable(soup) else "❌"
    
    # Extract hreflang tags
    hreflang_tags = []
    issues = []
    for link in soup.find_all('link', rel='alternate'):
        hreflang = link.get('hreflang', '').lower()
        href = urljoin(url, link.get('href', ''))
        if hreflang and href:
            hreflang_tags.append((hreflang, href))
            
            # Validate hreflang
            if not validate_hreflang(hreflang):
                issues.append(f"Invalid hreflang: {hreflang}")
            if not url_matches(href, url):
                issues.append(f"URL mismatch: {href}")
    
    # Prepare result
    result = {
        "URL": url,
        "Status": f"{response.get('status', '200')} OK",
        "Title": title,
        "Language": lang,
        "Indexable": indexable,
        "Method": method_used,
        "User-Agent": user_agent,
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
    
    return result

def main():
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        analysis_method = st.selectbox(
            "Method:",
            ["Auto", "Direct HTTP", "Browser Automation"],
            help="Auto will try HTTP first and fall back to browser if needed"
        )
        
        max_threads = st.slider(
            "Max Threads:",
            min_value=1,
            max_value=10,
            value=3,
            help="Number of URLs to process simultaneously"
        )
    
    # Main content area
    tab1, tab2 = st.tabs(["Single URL Analysis", "Bulk URL Analysis"])
    
    with tab1:
        st.subheader("Analyze a Single URL")
        single_url = st.text_input("Enter URL:", placeholder="https://example.com")
        
        if st.button("Analyze Single URL", type="primary"):
            if not single_url:
                st.error("Please enter a URL")
            else:
                st.session_state.processing = True
                with st.spinner("Analyzing URL..."):
                    result = process_url(single_url, analysis_method.lower())
                    st.session_state.results = [result]
                st.session_state.processing = False
                st.success("Analysis completed!")
    
    with tab2:
        st.subheader("Analyze Multiple URLs")
        uploaded_file = st.file_uploader(
            "Upload a file with URLs (one per line)", 
            type=['txt', 'csv']
        )
        
        if st.button("Analyze Bulk URLs", type="primary") and uploaded_file is not None:
            # Read URLs from file
            content = uploaded_file.getvalue().decode("utf-8")
            urls = [line.strip() for line in content.splitlines() if line.strip()]
            
            if not urls:
                st.error("No URLs found in the file")
            else:
                st.session_state.processing = True
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                results = []
                with ThreadPoolExecutor(max_workers=max_threads) as executor:
                    # Start processing
                    future_to_url = {
                        executor.submit(process_url, url, analysis_method.lower()): url 
                        for url in urls
                    }
                    
                    # Process completed tasks
                    for i, future in enumerate(as_completed(future_to_url)):
                        try:
                            result = future.result()
                            results.append(result)
                        except Exception as e:
                            url = future_to_url[future]
                            results.append({
                                "URL": url,
                                "Status": "Error",
                                "Title": "",
                                "Language": "",
                                "Indexable": "❌",
                                "Method": "Error",
                                "User-Agent": "N/A",
                                "Issues": f"Processing error: {str(e)}",
                                "hreflang 1": "", "URL 1": "",
                                "hreflang 2": "", "URL 2": "",
                                "hreflang 3": "", "URL 3": ""
                            })
                        
                        # Update progress
                        progress = (i + 1) / len(urls)
                        progress_bar.progress(progress)
                        status_text.text(f"Processed {i+1} of {len(urls)} URLs")
                
                st.session_state.results = results
                st.session_state.processing = False
                st.success(f"Completed analysis of {len(urls)} URLs!")
    
    # Display results if available
    if st.session_state.results:
        st.subheader("Results")
        
        # Convert to DataFrame
        df = pd.DataFrame(st.session_state.results)
        
        # Show summary statistics
        st.subheader("Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total URLs", len(df))
        with col2:
            successful = len(df[df['Status'] != 'Failed'])
            st.metric("Successful", successful)
        with col3:
            errors = len(df) - successful
            st.metric("Errors", errors)
        
        # Display data table
        st.dataframe(df, use_container_width=True)
        
        # Export options
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="hreflang_analysis.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
