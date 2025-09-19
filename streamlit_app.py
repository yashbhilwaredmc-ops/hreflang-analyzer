import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import time
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

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        margin-bottom: 1rem;
        text-align: center;
    }
    .results-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
        font-size: 0.9rem;
        font-family: Arial, sans-serif;
    }
    .results-table th {
        background-color: #1E88E5;
        color: white;
        padding: 10px;
        text-align: left;
        position: sticky;
        top: 0;
        font-weight: bold;
    }
    .results-table td {
        padding: 8px;
        border-bottom: 1px solid #ddd;
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .results-table tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    .results-table tr:hover {
        background-color: #f1f1f1;
    }
    .status-success {
        color: #4CAF50;
        font-weight: bold;
    }
    .status-error {
        color: #F44336;
        font-weight: bold;
    }
    .indexable-yes {
        color: #4CAF50;
        font-weight: bold;
    }
    .indexable-no {
        color: #F44336;
        font-weight: bold;
    }
    .config-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'results' not in st.session_state:
    st.session_state.results = []
if 'current_url_index' not in st.session_state:
    st.session_state.current_url_index = 0
if 'total_urls' not in st.session_state:
    st.session_state.total_urls = 0
if 'urls_to_process' not in st.session_state:
    st.session_state.urls_to_process = []

def log(message, level="info"):
    timestamp = time.strftime("%H:%M:%S")
    if level == "error":
        st.error(f"[{timestamp}] {message}")
    elif level == "warning":
        st.warning(f"[{timestamp}] {message}")
    elif level == "success":
        st.success(f"[{timestamp}] {message}")
    else:
        st.info(f"[{timestamp}] {message}")

def fetch_http(url):
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
        log(f"HTTP request failed for {url}: {str(e)}", "error")
        return None

def validate_hreflang(hreflang):
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
    norm_href = normalize_url(href)
    norm_base = normalize_url(base_url)
    return norm_href == norm_base
    
def normalize_url(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/').lower()
    
def check_indexable(soup):
    robots = soup.find('meta', attrs={'name': 'robots'})
    return not (robots and 'noindex' in robots.get('content', '').lower())

def process_response(url, response):
    html = response["html"]
    method = response["method"]
    
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
    
    # Prepare single-row result
    result = {
        "URL": url,
        "Status": f"{response.get('status', '200')} OK",
        "Title": title[:50] + "..." if len(title) > 50 else title,
        "Language": lang,
        "Indexable": indexable,
        "Method": method,
        "User-Agent": response.get("user_agent", "N/A")[:30] + "..." if len(response.get("user_agent", "N/A")) > 30 else response.get("user_agent", "N/A"),
        "Issues": ", ".join(issues) if issues else "Valid"
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

def display_results_table():
    if not st.session_state.results:
        return
        
    st.markdown("### Analysis Results")
    
    # Create HTML table
    table_html = """
    <table class="results-table">
        <thead>
            <tr>
                <th>URL</th>
                <th>Status</th>
                <th>Title</th>
                <th>Language</th>
                <th>Indexable</th>
                <th>Method</th>
                <th>User-Agent</th>
                <th>hreflang 1</th>
                <th>URL 1</th>
                <th>hreflang 2</th>
                <th>URL 2</th>
                <th>hreflang 3</th>
                <th>URL 3</th>
                <th>Issues</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for result in st.session_state.results:
        status_class = "status-success" if "200" in result["Status"] else "status-error"
        indexable_class = "indexable-yes" if result["Indexable"] == "✔️" else "indexable-no"
        
        table_html += f"""
        <tr>
            <td title="{result['URL']}">{result['URL'][:30]}{'...' if len(result['URL']) > 30 else ''}</td>
            <td class="{status_class}">{result['Status']}</td>
            <td title="{result['Title']}">{result['Title']}</td>
            <td>{result['Language']}</td>
            <td class="{indexable_class}">{result['Indexable']}</td>
            <td>{result['Method']}</td>
            <td title="{result['User-Agent']}">{result['User-Agent']}</td>
            <td>{result.get('hreflang 1', '')}</td>
            <td title="{result.get('URL 1', '')}">{result.get('URL 1', '')[:30]}{'...' if len(result.get('URL 1', '')) > 30 else ''}</td>
            <td>{result.get('hreflang 2', '')}</td>
            <td title="{result.get('URL 2', '')}">{result.get('URL 2', '')[:30]}{'...' if len(result.get('URL 2', '')) > 30 else ''}</td>
            <td>{result.get('hreflang 3', '')}</td>
            <td title="{result.get('URL 3', '')}">{result.get('URL 3', '')[:30]}{'...' if len(result.get('URL 3', '')) > 30 else ''}</td>
            <td>{result['Issues']}</td>
        </tr>
        """
    
    table_html += "</tbody></table>"
    
    # Display the table
    st.markdown(table_html, unsafe_allow_html=True)

def export_to_csv():
    if not st.session_state.results:
        st.error("No results to export")
        return
        
    # Convert results to DataFrame
    df = pd.DataFrame(st.session_state.results)
    
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
        mime="text/csv",
        use_container_width=True
    )

def main():
    st.markdown('<h1 class="main-header">🌐 DMC hreflang Analyzer</h1>', unsafe_allow_html=True)
    
    # Configuration section
    st.markdown("### Configuration")
    with st.container():
        col1, col2 = st.columns([1, 1])
        
        with col1:
            analysis_type = st.radio("Analysis Type", ["Single URL", "Bulk URLs"])
            
            if analysis_type == "Single URL":
                single_url = st.text_input("Single URL:", placeholder="https://example.com")
                urls = [single_url] if single_url else []
            else:
                uploaded_file = st.file_uploader("Bulk URLs:", type=["txt"])
                if uploaded_file is not None:
                    try:
                        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
                        urls = [line.strip() for line in stringio if line.strip()]
                    except Exception as e:
                        st.error(f"Error reading file: {str(e)}")
                        urls = []
                else:
                    urls = []
        
        with col2:
            method = st.selectbox("Method:", ["Auto", "Direct HTTP"])
            threads = st.slider("Threads:", 1, 10, 3)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                run_single_btn = st.button("Analyze Single", use_container_width=True)
            with col2:
                run_bulk_btn = st.button("Analyze Bulk", use_container_width=True)
            with col3:
                stop_btn = st.button("Stop", use_container_width=True, disabled=not st.session_state.processing)
            with col4:
                export_btn = st.button("Export CSV", use_container_width=True, disabled=not st.session_state.results)
    
    # Handle button clicks
    if run_single_btn and analysis_type == "Single URL" and urls:
        st.session_state.urls_to_process = urls
        st.session_state.processing = True
        st.session_state.results = []
        st.session_state.current_url_index = 0
        st.session_state.total_urls = len(urls)
    
    if run_bulk_btn and analysis_type == "Bulk URLs" and urls:
        st.session_state.urls_to_process = urls
        st.session_state.processing = True
        st.session_state.results = []
        st.session_state.current_url_index = 0
        st.session_state.total_urls = len(urls)
    
    if stop_btn:
        st.session_state.processing = False
        st.warning("Processing stopped by user")
    
    if export_btn:
        export_to_csv()
    
    # Process URLs if processing is enabled
    if st.session_state.processing and st.session_state.urls_to_process:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Process one URL at a time
        if st.session_state.current_url_index < st.session_state.total_urls:
            url = st.session_state.urls_to_process[st.session_state.current_url_index]
            
            # Update progress
            progress = (st.session_state.current_url_index / st.session_state.total_urls)
            progress_bar.progress(progress)
            status_text.text(f"Processing {st.session_state.current_url_index + 1} of {st.session_state.total_urls}: {url[:50]}...")
            
            # Process the URL
            response = fetch_http(url)
            
            if not response:
                result = {
                    "URL": url,
                    "Status": "Failed",
                    "Title": "",
                    "Language": "",
                    "Indexable": "❌",
                    "Method": "Failed",
                    "User-Agent": "N/A",
                    "hreflang 1": "",
                    "URL 1": "",
                    "hreflang 2": "",
                    "URL 2": "",
                    "hreflang 3": "",
                    "URL 3": "",
                    "Issues": "Failed to fetch URL"
                }
                st.session_state.results.append(result)
            else:
                result = process_response(url, response)
                st.session_state.results.append(result)
                log(f"Processed: {url}")
            
            # Move to next URL
            st.session_state.current_url_index += 1
            
            # Add a small delay to avoid being blocked
            time.sleep(0.5)
            
            # Rerun to update UI
            st.rerun()
        else:
            # Processing complete
            st.session_state.processing = False
            progress_bar.empty()
            status_text.text(f"Completed {st.session_state.total_urls} URLs")
            log("Analysis completed successfully!", "success")
    
    # Display results
    display_results_table()

if __name__ == "__main__":
    main()
