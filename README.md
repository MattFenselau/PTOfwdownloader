# **USPTO File Wrapper Downloader**

A robust, GUI-based Python tool for bulk downloading Patent File Wrappers (PDFs) from the USPTO Open Data API.

This tool is specifically engineered to overcome common issues found when attempting to download patent documents programmatically, including **SSL handshake failures**, **403 Forbidden errors**, and **corrupted PDF downloads** caused by Amazon S3 redirection handling.

## **🚀 Key Features**

* **Smart Corruption Prevention:** Automatically handles the complex redirect flow between the USPTO API and Amazon S3 storage. It correctly strips API keys during the S3 handoff to prevent "Access Denied" XML errors from being saved as PDFs.  
* **SSL/TLS Bypass:** Uses the system's native curl command for downloads, bypassing strict Python SSL context errors often encountered on corporate networks or specific OS configurations.  
* **Bulk Processing:** Accepts lists of hundreds of Application Numbers (comma-separated, newline-separated, or mixed) and processes them in a queue.  
* **JSON Parse Fix:** Correctly parses the nested downloadOptionBag structure in the USPTO API 2.0 response to find the valid PDF link, rather than guessing.  
* **Auto-Cleanup:** Scans for and deletes 0-byte or corrupted non-PDF files from previous failed attempts before re-downloading.  
* **User-Friendly GUI:** Built with tkinter, featuring a responsive UI that runs heavy network tasks in a background thread to prevent freezing.

## **🛠 Prerequisites**

1. **Python 3.6+** installed on your system.  
2. **cURL**: This tool relies on the system's curl command to handle network requests reliably.  
   * **macOS/Linux:** Pre-installed by default.  
   * **Windows:** Included in Windows 10/11 (Command Prompt).  
3. **USPTO API Key**: You must register for a free account at [data.uspto.gov](https://data.uspto.gov/) to generate an API key.

## **📦 Installation**

1. Clone this repository or download the source code.  
   git clone \[https://github.com/yourusername/uspto-file-wrapper-downloader.git\](https://github.com/yourusername/uspto-file-wrapper-downloader.git)  
   cd uspto-file-wrapper-downloader

2. No external Python dependencies (pip install) are required\! The tool uses only standard libraries included with Python:  
   * tkinter  
   * urllib  
   * json  
   * subprocess  
   * ssl  
   * threading

## **🖥️ How to Use**

1. **Run the script:**  
   python3 PTOfwdownloader.py

2. Enter your USPTO API Key:  
   Paste your key into the designated field.  
3. Input Application Numbers:  
   Paste your list of Application numbers into the text box. The tool is smart enough to handle various formats:  
   * 12345678  
   * 12/345,678  
   * List format (one per line)  
   * Mixed text/CSV format  
4. **Start Download:**  
   * Click **"Select Folder & Start"**.  
   * Choose a destination directory on your computer.  
   * The tool will create a subfolder for each application (e.g., App\_12345678) and save the PDFs inside.

## **🔧 Technical Details (How it Fixes Corruption)**

Many standard downloaders fail with USPTO data because the API workflow looks like this:

1. **Request:** GET api.uspto.gov/.../doc.pdf (Requires X-API-KEY header)  
2. **Response:** 302 Redirect \-\> https://s3.amazon.com/.../doc.pdf  
3. **Follow:** The client follows the redirect to Amazon.

**The Bug:** Standard HTTP clients (and curl by default) forward the X-API-KEY header to Amazon. Amazon S3 rejects requests containing unknown headers, resulting in an XML error file being saved with a .pdf extension.

**The Fix:** This tool performs a "Two-Step Curl":

1. It dumps the headers of the first request to find the Location redirect URL.  
2. It initiates a *new*, clean request to the Amazon URL **without** the API key, ensuring a valid PDF download.

## **⚠️ Disclaimer**

This tool is an independent project and is not affiliated with, endorsed by, or sponsored by the United States Patent and Trademark Office (USPTO). Use this tool responsibly and in accordance with the USPTO Open Data API Terms of Service.

## **📄 License**

This project is licensed under the MIT License \- see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.