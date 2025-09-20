import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent
import pycountry
import time
from threading import Thread
import queue
import pandas as pd

class AdvancedHreflangChecker:
    def __init__(self, root):
        self.root = root
        self.setup_gui()
        self.driver = None
        self.setup_selenium()
        self.task_queue = queue.Queue()
        self.processing = False
        self.current_url_index = 0
        self.total_urls = 0
        self.results = []
        
    def setup_selenium(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        self.driver = webdriver.Chrome(options=chrome_options)
        
    def setup_gui(self):
        self.root.title("Professional hreflang Analyzer")
        self.root.geometry("1600x900")
        
        style = ttk.Style()
        style.configure("TFrame", background="#f5f5f5")
        style.configure("TLabel", background="#f5f5f5", font=('Segoe UI', 9))
        style.configure("Treeview.Heading", font=('Segoe UI', 9, "bold"))
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Input panel
        input_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        input_frame.pack(fill=tk.X, pady=5)
        
        # URL input section
        url_frame = ttk.Frame(input_frame)
        url_frame.grid(row=0, column=0, columnspan=5, sticky="ew")
        
        ttk.Label(url_frame, text="Single URL:").pack(side=tk.LEFT, padx=5)
        self.url_entry = ttk.Entry(url_frame, width=60)
        self.url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Bulk URL section
        bulk_frame = ttk.Frame(input_frame)
        bulk_frame.grid(row=1, column=0, columnspan=5, sticky="ew", pady=5)
        
        ttk.Label(bulk_frame, text="Bulk URLs:").pack(side=tk.LEFT, padx=5)
        self.bulk_entry = ttk.Entry(bulk_frame, width=60)
        self.bulk_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.browse_btn = ttk.Button(bulk_frame, text="Browse...", command=self.browse_file)
        self.browse_btn.pack(side=tk.LEFT, padx=5)
        
        # Options section
        ttk.Label(input_frame, text="Method:").grid(row=2, column=0, padx=5, sticky=tk.W)
        self.method_combo = ttk.Combobox(input_frame, values=["Auto", "Direct HTTP", "Browser Automation"], width=15)
        self.method_combo.current(0)
        self.method_combo.grid(row=2, column=1, padx=5, sticky=tk.W)
        
        ttk.Label(input_frame, text="Threads:").grid(row=2, column=2, padx=5, sticky=tk.W)
        self.threads_spin = ttk.Spinbox(input_frame, from_=1, to=10, width=5)
        self.threads_spin.set(3)
        self.threads_spin.grid(row=2, column=3, padx=5, sticky=tk.W)
        
        # Buttons
        self.run_single_btn = ttk.Button(input_frame, text="Analyze Single", command=lambda: self.start_analysis(single=True))
        self.run_single_btn.grid(row=2, column=4, padx=5, sticky=tk.E)
        
        self.run_bulk_btn = ttk.Button(input_frame, text="Analyze Bulk", command=lambda: self.start_analysis(single=False))
        self.run_bulk_btn.grid(row=2, column=5, padx=5, sticky=tk.E)
        
        self.stop_btn = ttk.Button(input_frame, text="Stop", command=self.stop_processing, state=tk.DISABLED)
        self.stop_btn.grid(row=2, column=6, padx=5, sticky=tk.E)
        
        self.export_btn = ttk.Button(input_frame, text="Export CSV", command=self.export_to_csv, state=tk.DISABLED)
        self.export_btn.grid(row=2, column=7, padx=5, sticky=tk.E)
        
        # Progress bar
        self.progress_frame = ttk.Frame(input_frame)
        self.progress_frame.grid(row=3, column=0, columnspan=7, sticky="ew", pady=5)
        
        self.progress_label = ttk.Label(self.progress_frame, text="Ready")
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Results panel - Single table for consolidated output
        results_frame = ttk.Frame(main_frame)
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        # Define columns for single-row output (ADDED User-Agent COLUMN)
        columns = [
            "URL", "Status", "Title", "Language", "Indexable", "Method",
            "User-Agent",  # NEW COLUMN
            "hreflang 1", "URL 1", "hreflang 2", "URL 2", "hreflang 3", "URL 3",
            "Issues"
        ]
        
        self.results_table = ttk.Treeview(results_frame, columns=columns, show="headings", height=25)
        
        # Configure columns
        column_widths = {
            "URL": 200, "Status": 80, "Title": 150, "Language": 80, 
            "Indexable": 80, "Method": 100, "User-Agent": 250,  # User-Agent wider
            "hreflang 1": 80, "URL 1": 200, "hreflang 2": 80, "URL 2": 200,
            "hreflang 3": 80, "URL 3": 200, "Issues": 150
        }
        
        for col in columns:
            self.results_table.heading(col, text=col)
            self.results_table.column(col, width=column_widths.get(col, 100), anchor=tk.W)
        
        # Scrollbars
        scroll_y = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_table.yview)
        scroll_x = ttk.Scrollbar(results_frame, orient="horizontal", command=self.results_table.xview)
        self.results_table.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        self.results_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        self.status_bar.pack(fill=tk.X)
    
    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select URL file",
            filetypes=(("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*"))
        )
        if file_path:
            self.bulk_entry.delete(0, tk.END)
            self.bulk_entry.insert(0, file_path)
    
    def log(self, message, level="info"):
        timestamp = time.strftime("%H:%M:%S")
        self.status_var.set(f"[{timestamp}] {message}")
        self.root.update_idletasks()
    
    def start_analysis(self, single=True):
        self.results_table.delete(*self.results_table.get_children())
        self.results = []
        
        if single:
            url = self.url_entry.get().strip()
            if not url:
                messagebox.showerror("Error", "Please enter a URL")
                return
            urls = [url]
        else:
            file_path = self.bulk_entry.get().strip()
            if not file_path:
                messagebox.showerror("Error", "Please select a bulk URL file")
                return
            try:
                with open(file_path, 'r') as f:
                    urls = [line.strip() for line in f if line.strip()]
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read file: {str(e)}")
                return
        
        if not urls:
            messagebox.showerror("Error", "No URLs found to process")
            return
            
        self.total_urls = len(urls)
        self.current_url_index = 0
        self.processing = True
        
        self.run_single_btn.config(state=tk.DISABLED)
        self.run_bulk_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.export_btn.config(state=tk.DISABLED)
        
        self.progress_var.set(0)
        self.progress_label.config(text=f"Processing 0 of {self.total_urls}")
        self.status_var.set(f"Processing {self.total_urls} URLs...")
        
        for url in urls:
            self.task_queue.put(url)
            
        num_threads = min(int(self.threads_spin.get()), len(urls))
        for i in range(num_threads):
            Thread(target=self.worker_thread, daemon=True).start()
    
    def worker_thread(self):
        while self.processing and not self.task_queue.empty():
            try:
                url = self.task_queue.get_nowait()
                self.current_url_index += 1
                
                self.root.after(0, self.update_progress, self.current_url_index, url)
                
                method = self.method_combo.get()
                
                if method == "Auto":
                    response = self.try_all_methods(url)
                elif method == "Direct HTTP":
                    response = self.fetch_http(url)
                else:
                    response = self.fetch_browser(url)
                    
                if not response:
                    self.root.after(0, self.add_result_row, {
                        "URL": url,
                        "Status": "Failed",
                        "Title": "",
                        "Language": "",
                        "Indexable": "❌",
                        "Method": "Failed",
                        "User-Agent": "N/A",
                        "Issues": "Failed to fetch URL"
                    })
                    continue
                    
                self.root.after(0, self.process_response, url, response)
                
            except queue.Empty:
                break
            except Exception as e:
                self.root.after(0, self.log, f"Error processing URL {url}: {str(e)}", "error")
            finally:
                self.task_queue.task_done()
                
        if self.task_queue.empty():
            self.root.after(0, self.finish_processing)
    
    def update_progress(self, current, url):
        progress = (current / self.total_urls) * 100
        self.progress_var.set(progress)
        self.progress_label.config(text=f"Processing {current} of {self.total_urls}: {url[:50]}...")
    
    def stop_processing(self):
        self.processing = False
        self.status_var.set("Processing stopped by user")
        self.log("Processing stopped by user")
        self.finish_processing()
    
    def finish_processing(self):
        self.processing = False
        self.run_single_btn.config(state=tk.NORMAL)
        self.run_bulk_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.export_btn.config(state=tk.NORMAL)
        self.status_var.set(f"Completed {self.current_url_index} of {self.total_urls} URLs")
        self.progress_label.config(text=f"Completed {self.current_url_index} of {self.total_urls} URLs")
    
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
            "User-Agent": response.get("user_agent", "N/A"),  # ADDED User-Agent
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
        
        self.add_result_row(result)
        self.log(f"Processed: {url} ({len(hreflang_tags)} hreflang tags)")
    
    def add_result_row(self, result):
        self.results.append(result)
        
        # Prepare values for treeview
        values = [
            result["URL"],
            result["Status"],
            result["Title"],
            result["Language"],
            result["Indexable"],
            result["Method"],
            result.get("User-Agent", "N/A"),  # ADDED User-Agent value
            result.get("hreflang 1", ""),
            result.get("URL 1", ""),
            result.get("hreflang 2", ""),
            result.get("URL 2", ""),
            result.get("hreflang 3", ""),
            result.get("URL 3", ""),
            result["Issues"]
        ]
        
        self.results_table.insert("", tk.END, values=values)
    
    def export_to_csv(self):
        if not self.results:
            messagebox.showerror("Error", "No results to export")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="Save CSV Report",
            defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )
        
        if file_path:
            try:
                df = pd.DataFrame(self.results)
                
                # Ensure all columns exist
                for i in range(1, 4):
                    if f"hreflang {i}" not in df.columns:
                        df[f"hreflang {i}"] = ""
                    if f"URL {i}" not in df.columns:
                        df[f"URL {i}"] = ""
                
                # Reorder columns (ADDED User-Agent)
                columns = [
                    "URL", "Status", "Title", "Language", "Indexable", "Method",
                    "User-Agent",  # ADDED User-Agent to export
                    "hreflang 1", "URL 1", "hreflang 2", "URL 2", "hreflang 3", "URL 3",
                    "Issues"
                ]
                df = df[columns]
                
                df.to_csv(file_path, index=False)
                self.log(f"Exported results to: {file_path}")
                messagebox.showinfo("Success", f"CSV exported to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def try_all_methods(self, url):
        self.log("Trying direct HTTP request...")
        response = self.fetch_http(url)
        
        if not response or self.is_blocked(response):
            self.log("Falling back to browser automation...")
            response = self.fetch_browser(url)
            
        return response
        
    def fetch_http(self, url):
        try:
            session = requests.Session()
            ua = UserAgent()
            user_agent = ua.chrome  # Generate random Chrome UA
            headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://www.google.com/"
            }
            
            # Log the User-Agent being used
            self.log(f"Using User-Agent: {user_agent}")
            
            session.get("https://www.google.com/", headers=headers, timeout=10)
            time.sleep(1)
            
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
                "user_agent": user_agent  # RETURN User-Agent
            }
            
        except Exception as e:
            self.log(f"HTTP request failed for {url}: {str(e)}", "error")
            return None
            
    def fetch_browser(self, url):
        try:
            self.driver.get(url)
            time.sleep(3)
            
            if "challenge" in self.driver.page_source.lower():
                self.log("Cloudflare challenge detected", "error")
                return None
                
            # Get browser's actual User-Agent
            user_agent = self.driver.execute_script("return navigator.userAgent;")
            self.log(f"Browser User-Agent: {user_agent}")
                
            return {
                "method": "Browser",
                "url": self.driver.current_url,
                "status": 200,
                "html": self.driver.page_source,
                "headers": {},
                "user_agent": user_agent  # RETURN Browser UA
            }
            
        except Exception as e:
            self.log(f"Browser automation failed for {url}: {str(e)}", "error")
            return None
            
    def is_blocked(self, response):
        if not response:
            return True
            
        return (
            response.get("status") == 403 or
            "access denied" in response.get("html", "").lower() or
            "cloudflare" in response.get("html", "").lower()
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

if __name__ == "__main__":
    root = tk.Tk()
    app = AdvancedHreflangChecker(root)
    root.mainloop()
