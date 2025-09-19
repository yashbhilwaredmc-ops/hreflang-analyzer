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

# Set page configuration with DMC branding
st.set_page_config(
    page_title="DMC Href_lang Tool",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for DMC branding
st.markdown("""
<style>
    .main {
        background-color: #f0f2f6;
    }
    .dmc-header {
        background-color: #1E3A8A;
        color: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 2rem;
        text-align: center;
    }
    .dmc-header h1 {
        color: white;
        margin-bottom: 0.5rem;
    }
    .stButton button {
        background-color: #1E3A8A;
        color: white;
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# DMC Header
st.markdown("""
<div class="dmc-header">
    <h1>🌐 DMC Href_lang Tool</h1>
    <p>Professional hreflang analysis for international SEO</p>
</div>
""", unsafe_allow_html=True)

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

# [Keep all your existing functions here: validate_hreflang, url_matches, check_indexable, fetch_url, process_url]

def main():
    # Sidebar for configuration with DMC branding
    with st.sidebar:
        st.image("https://placehold.co/200x60/1E3A8A/FFFFFF/png?text=DMC+Logo", use_column_width=True)
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
            file_name="dmc_hreflang_analysis.csv",
            mime="text/csv"
        )
    
    # DMC Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #1E3A8A;'><p>DMC Href_lang Tool • Professional SEO Analysis</p></div>", 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
