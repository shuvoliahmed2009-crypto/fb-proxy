from flask import Flask, request, redirect, session
import requests
from bs4 import BeautifulSoup
import re
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fbproxy_button_phone_2024')

FB_BASE = "https://mbasic.facebook.com"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

def rewrite_url(url):
    url = re.sub(r'https?://(mbasic\.|m\.|www\.)?facebook\.com', '', url)
    if url.startswith('/'):
        return f"/fb{url}"
    return url

def simplify_html(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['script', 'style', 'svg', 'iframe', 'noscript', 'link']):
            tag.decompose()
        KEEP = {'href', 'action', 'method', 'name', 'value', 'type', 'enctype', 'checked', 'selected'}
        for tag in soup.find_all(True):
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in KEEP}
        for a in soup.find_all('a', href=True):
            a['href'] = rewrite_url(a['href'])
        for form in soup.find_all('form', action=True):
            form['action'] = rewrite_url(form['action'])
        for img in soup.find_all('img'):
            img.decompose()
        return str(soup)
    except Exception as e:
        return f"<html><body>Parse error: {str(e)}</body></html>"

SETUP_PAGE = """<html>
<head><title>FB Proxy</title></head>
<body>
<h2>FB Proxy Setup</h2>
<form method="POST" action="/setcookies">
<p><b>Facebook Cookies:</b><br>
<textarea name="cookies" rows="5" cols="50" placeholder="c_user=123456789; xs=AbCdEf..."></textarea>
</p>
<input type="submit" value="Save and Open Facebook">
</form>
<hr>
<p><b>Cookie kivabe pabo (PC te):</b><br>
1. facebook.com e login thako<br>
2. F12 press koro<br>
3. Application tab > Cookies > facebook.com<br>
4. c_user er value copy koro<br>
5. xs er value copy koro<br>
6. Upora box e likho: c_user=VALUE; xs=VALUE</p>
</body></html>"""

@app.route('/')
def index():
    if session.get('fb_cookies'):
        return redirect('/fb/')
    return SETUP_PAGE

@app.route('/setcookies', methods=['POST'])
def setcookies():
    cookies = request.form.get('cookies', '').strip()
    if not cookies:
        return redirect('/')
    session['fb_cookies'] = cookies
    return redirect('/fb/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/fb/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/fb/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    if not session.get('fb_cookies'):
        return redirect('/')

    url = f"{FB_BASE}/{path}"
    qs = request.query_string.decode('utf-8', errors='ignore')
    if qs:
        url += f"?{qs}"

    headers = HEADERS.copy()
    headers['Cookie'] = session.get('fb_cookies', '')

    try:
        if request.method == 'POST':
            r = requests.post(url, data=request.form, headers=headers,
                            allow_redirects=True, timeout=30)
        else:
            r = requests.get(url, headers=headers,
                           allow_redirects=True, timeout=30)

        # Show debug info
        debug = f"""
        <div style="background:#ffffcc;padding:5px;font-size:11px">
        URL: {url}<br>
        Status: {r.status_code}<br>
        Final URL: {r.url}<br>
        <a href="/fb/">Home</a> | <a href="/logout">Logout</a>
        </div>
        """

        if r.status_code in (301, 302):
            loc = r.headers.get('Location', '')
            loc = rewrite_url(loc)
            return redirect(loc)

        simplified = simplify_html(r.text)
        return debug + simplified, 200, {'Content-Type': 'text/html; charset=utf-8'}

    except requests.exceptions.Timeout:
        return '<html><body><b>Timeout!</b> Facebook respond koreni.<br><a href="/fb/">Retry</a></body></html>'
    except requests.exceptions.ConnectionError as e:
        return f'<html><body><b>Connection Error:</b> {str(e)}<br><a href="/fb/">Retry</a></body></html>'
    except Exception as e:
        return f'<html><body><b>Error:</b> {str(e)}<br><a href="/fb/">Retry</a></body></html>'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
