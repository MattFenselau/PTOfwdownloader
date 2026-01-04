import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import time
import json
import urllib.request
import ssl
import subprocess
import re

class USPTOFileWrapperDownloader(tk.Tk):
    """
    A Tkinter-based GUI application to download Patent File Wrappers in bulk from the USPTO API.
    
    This application addresses several specific challenges with the USPTO API:
    1. TLS/SSL Handshake issues (uses system curl to bypass Python's stricter SSL context).
    2. File Corruption (handles the redirect from USPTO to Amazon S3 correctly by stripping the API key).
    3. UI Responsiveness (runs the heavy download loop in a separate thread).
    """
    
    def __init__(self):
        super().__init__()
        self.title("USPTO File Wrapper Downloader")
        self.geometry("900x900")
        self.configure(bg="#f5f6fa")
        
        # SSL Context creation
        # We create a permissive SSL context for the initial Python-based list fetching.
        # This helps avoid "Certificate Verify Failed" errors on some corporate networks.
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # --- UI Configuration ---
        style = ttk.Style(self)
        style.theme_use('clam')
        
        # Define custom styles for Labels
        style.configure("TLabel", background="#f5f6fa", foreground="#2f3640", font=("Segoe UI", 11))
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#005ea2")
        
        # Main container frame with padding
        main_frame = ttk.Frame(self, padding="30")
        main_frame.pack(fill="both", expand=True)

        # Title Label
        ttk.Label(main_frame, text="USPTO File Wrapper Downloader", style="Header.TLabel").pack(anchor="w", pady=(0, 25))

        # API Key Input
        ttk.Label(main_frame, text="USPTO API Key:", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.entry_key = ttk.Entry(main_frame, font=("Consolas", 11))
        self.entry_key.pack(fill="x", pady=(5, 20))

        # Application List Input (Multi-line text area)
        ttk.Label(main_frame, text="Application Numbers:", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.txt_list = scrolledtext.ScrolledText(main_frame, height=12, font=("Consolas", 11), borderwidth=1, relief="solid")
        self.txt_list.pack(fill="both", expand=True, pady=(5, 20))
        
        # Progress Bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x", pady=(0, 20))

        # Button Frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(0, 25))
        
        # Start Button
        # Note: fg="black" ensures visibility on Mac/Windows default button backgrounds.
        self.btn_start = tk.Button(btn_frame, text="Select Folder & Start", command=self.start_thread,
                                   bg="#005ea2", fg="black", font=("Segoe UI", 12, "bold"), 
                                   padx=20, pady=12, relief="raised", cursor="hand2")
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Stop Button (Disabled by default)
        self.btn_stop = tk.Button(btn_frame, text="Stop", command=self.stop_process,
                                  bg="#d32f2f", fg="black", font=("Segoe UI", 12, "bold"), 
                                  padx=20, pady=12, relief="raised", state="disabled")
        self.btn_stop.pack(side="right", fill="x")

        # Status Log Area
        ttk.Label(main_frame, text="Status Log:", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.txt_log = scrolledtext.ScrolledText(main_frame, height=15, bg="#2d3436", fg="#00d2d3", font=("Consolas", 10), state='disabled')
        self.txt_log.pack(fill="both", expand=True, pady=(5, 0))

        # Threading control flags
        self.is_running = False
        self.stop_flag = False

    def log(self, message):
        """Helper to append timestamped messages to the log window safely."""
        self.txt_log.config(state='normal') # Enable editing
        self.txt_log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.txt_log.see(tk.END) # Auto-scroll to bottom
        self.txt_log.config(state='disabled') # Disable editing
        print(message) 

    def start_thread(self):
        """Starts the download process in a separate thread to prevent UI freezing."""
        if self.is_running: return
        self.stop_flag = False
        # Daemon=True ensures the thread dies if the main app closes
        t = threading.Thread(target=self.run_process, daemon=True)
        t.start()

    def stop_process(self):
        """Signals the running thread to stop at the next safe opportunity."""
        if self.is_running:
            self.stop_flag = True
            self.log("Stopping...")
            self.btn_stop.config(state="disabled")

    # --- HELPERS ---
    def verify_pdf(self, filepath):
        """
        Checks if a file exists, has content, and starts with the PDF magic bytes (%PDF).
        This detects if we accidentally downloaded an XML error message or HTML page.
        """
        if not os.path.exists(filepath): return False
        if os.path.getsize(filepath) < 100: return False # Too small to be a valid PDF
        try:
            with open(filepath, 'rb') as f:
                header = f.read(4)
            return header == b'%PDF'
        except:
            return False

    def get_redirect_url(self, url, api_key, temp_header_file):
        """
        Uses system 'curl' to check where a USPTO URL redirects to.
        
        Why this is needed:
        1. USPTO files redirect to Amazon S3.
        2. If we simply follow the redirect with our API key attached, Amazon rejects it (Corruption).
        3. We need to find the destination URL first, then download from THERE without the key.
        
        Args:
            url: The initial USPTO download URL.
            api_key: The user's key (needed for the first hop).
            temp_header_file: Path to store the headers for inspection.
            
        Returns:
            The redirect URL string, or None if not found.
        """
        if os.path.exists(temp_header_file): os.remove(temp_header_file)

        # Construct curl command
        # -s: Silent mode
        # -D: Dump headers to file
        # -o /dev/null: Discard the body content (we only want headers)
        cmd = [
            'curl', '-s', 
            '-D', temp_header_file, 
            '-o', '/dev/null',      
            '-H', f'X-API-KEY: {api_key}',
            '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--max-time', '20',
            url
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if not os.path.exists(temp_header_file): return None

            with open(temp_header_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Regex search for the 'Location' header which contains the redirect URL
            match = re.search(r'^[Ll]ocation:\s*(.+)\r?$', content, re.MULTILINE)
            if match:
                return match.group(1).strip()
            
            return None 

        except Exception as e:
            self.log(f"  > Redirect Check Error: {e}")
            return None

    def download_final(self, url, filepath, use_key=False, api_key=None):
        """
        Performs the actual file download using system 'curl'.
        
        Args:
            url: The URL to download (either S3 or direct USPTO).
            filepath: Local path to save the file.
            use_key: Boolean, whether to attach the X-API-KEY header.
                     (True for direct USPTO links, False for Amazon S3 links).
            api_key: The key string.
        """
        cmd = [
            'curl', '-L', '-s', # -L follows internal redirects, -s silent
            '-o', filepath,
            '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--max-time', '120',
            '--retry', '2'
        ]
        
        # Only add the API Key if explicitly requested (Direct downloads)
        if use_key and api_key:
            cmd.extend(['-H', f'X-API-KEY: {api_key}'])

        cmd.append(url)
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0
        except Exception:
            return False

    def run_process(self):
        """
        The main worker logic running in the background thread.
        """
        # Get inputs
        api_key = self.entry_key.get().strip()
        raw_list = self.txt_list.get("1.0", tk.END).strip()

        if not api_key:
            messagebox.showerror("Error", "Please enter API Key.")
            return

        # Clean up the list input: handle newlines, commas, slashes
        app_numbers = [x.replace('/','').replace(',','') for x in raw_list.replace('\n',' ').replace(',',' ').split() if x.strip()]
        if not app_numbers:
            messagebox.showerror("Error", "No numbers found.")
            return

        # Ask user for destination folder
        root_dir = filedialog.askdirectory()
        if not root_dir: return
        
        # Temp file for storing header dumps during redirect checks
        temp_header_file = os.path.join(root_dir, "temp_headers_debug.txt")

        # UI Updates
        self.is_running = True
        self.btn_start.config(state="disabled", text="Running...", fg="#555")
        self.btn_stop.config(state="normal", fg="black")
        self.log(f"Starting Download...")

        processed_count = 0
        success_count = 0

        # Main Loop over Application Numbers
        for app_num in app_numbers:
            if self.stop_flag: break
            processed_count += 1
            
            # Update Progress Bar
            self.progress_var.set((processed_count / len(app_numbers)) * 100)
            self.log(f"--- Processing {app_num} [{processed_count}/{len(app_numbers)}] ---")

            # Create Sub-folder for this specific application
            app_folder = os.path.join(root_dir, f"App_{app_num}")
            if not os.path.exists(app_folder): os.makedirs(app_folder)

            # A. Get Document List (JSON)
            # We use Python's urllib here because it handles JSON parsing easily.
            try:
                list_url = f"https://api.uspto.gov/api/v1/patent/applications/{app_num}/documents"
                req = urllib.request.Request(list_url, headers={"X-API-KEY": api_key, "Accept": "application/json"})
                with urllib.request.urlopen(req, context=self.ssl_context) as response:
                    data = json.loads(response.read().decode())
                # Handle different API response structures
                docs = data if isinstance(data, list) else data.get('documentBag', [])
            except Exception as e:
                self.log(f"API List Error: {e}")
                continue

            if not docs:
                self.log(f"No documents found.")
                continue

            self.log(f"Found {len(docs)} documents.")

            # B. Iterate over documents in this application
            for doc in docs:
                if self.stop_flag: break
                
                # Extract metadata
                doc_id = doc.get('documentIdentifier')
                doc_code = doc.get('documentCode', 'DOC')
                date = doc.get('officialDate', 'nodate').split('T')[0]
                
                # Construct Filename: AppNum_Date_Type_ID.pdf
                filename = f"{app_num}_{date}_{doc_code}_{doc_id}.pdf"
                filepath = os.path.join(app_folder, filename)

                # C. Check if file already exists and is valid
                if os.path.exists(filepath):
                    if self.verify_pdf(filepath):
                        # self.log(f"Skipping {filename} (Valid)") # Uncomment for verbose logging
                        continue
                    else:
                        self.log(f"Replacing corrupt file: {filename}")
                        try: os.remove(filepath)
                        except: pass

                # D. Find the correct Download URL
                # The USPTO API sometimes buries the PDF link inside 'downloadOptionBag'
                official_url = None
                options = doc.get('downloadOptionBag', [])
                for opt in options:
                    if opt.get('mimeTypeIdentifier', '').upper() == 'PDF':
                        official_url = opt.get('downloadUrl')
                        break
                
                # Fallback to top-level URL if bag is empty
                if not official_url:
                    official_url = doc.get('downloadUrl', f"{list_url}/{doc_id}")

                self.log(f"Fetching: {filename}")

                # E. Download Strategy
                # STEP 1: Check for Redirect (Get S3 Link)
                s3_url = self.get_redirect_url(official_url, api_key, temp_header_file)

                if s3_url:
                    # STEP 2a: DOWNLOAD FROM S3 (NO API KEY)
                    # We strip the API key here so Amazon doesn't reject the request.
                    if self.download_final(s3_url, filepath, use_key=False):
                        if self.verify_pdf(filepath):
                            self.log(f"  > Success (via S3).")
                            success_count += 1
                        else:
                            self.log(f"  > Failed. File Corrupt.")
                    else:
                        self.log(f"  > Download Command Failed.")
                else:
                    # STEP 2b: DOWNLOAD DIRECT (WITH API KEY)
                    # If no redirect, it's a direct file served by USPTO (requires Key).
                    self.log(f"  > No redirect. Downloading direct...")
                    if self.download_final(official_url, filepath, use_key=True, api_key=api_key):
                        if self.verify_pdf(filepath):
                             self.log(f"  > Success (Direct).")
                             success_count += 1
                        else:
                             self.log(f"  > Failed. File Corrupt/Auth Missing.")

                # Small delay to prevent rate limiting issues
                time.sleep(0.1)

        # Cleanup temp header file
        if os.path.exists(temp_header_file): os.remove(temp_header_file)

        # Reset UI state
        self.is_running = False
        self.btn_start.config(state="normal", text="Select Folder & Start", fg="black")
        self.btn_stop.config(state="disabled")
        self.log(f"Finished. Saved {success_count} NEW valid files.")
        messagebox.showinfo("Complete", f"Done.\nValid Files: {success_count}")

if __name__ == "__main__":
    app = USPTOFileWrapperDownloader()
    app.mainloop()