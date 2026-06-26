from flask import Flask, request, redirect, session
import requests
from bs4 import BeautifulSoup
import re
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fbproxy_button_phone_2024')

FB_BASE = "https://mbasic.facebook.com"

# Old phone browser header — tricks Facebook into serving basic HTML
HEADERS = {
    'User-Agent': 'Opera/9.80 (S60; SymbOS; Opera Mobi/SYB-1107071606; U; en) Presto/2.7.81 Version/10.5',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en',
    'Accept-Encoding': 'identity',
}

def fetch_fb(path, method='GET', form_data=None):
    url = f"{FB_BASE}/{path}"
    qs = request.query_string.decode('utf-8', errors='ignore')
    if qs:
        url += f"?{qs}"

    headers = HEADERS.copy()
    cookies_str = session.get('fb_cookies', '')
    if cookies_str:
        headers['Cookie'] = cookies_str

    try:
        if method == 'POST':
            r = requests.post(url, data=form_data, headers=headers,
                              allow_redirects=True, timeout=20)
        else:
            r = requests.get(url, headers=headers,
                             allow_redirects=True, timeout=20)
        return r
    except Exception as e:
        return None


def rewrite_url(url):
    """Convert any facebook.com URL into a /fb/... proxy URL."""
    url = re.sub(r'https?://(mbasic\.|m\.|www\.)?facebook\.com', '', url)
    if url.startswith('/'):
        return f"/fb{url}"
    return url


def simplify_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove heavy / unsupported tags
    for tag in soup(['script', 'style', 'svg', 'iframe',
                     'noscript', 'link', 'meta']):
        tag.decompose()

    # Strip ALL attributes except the safe ones — keeps HTML tiny
    KEEP = {'href', 'action', 'method', 'name', 'value',
            'type', 'src', 'enctype', 'checked', 'selected', 'for', 'id'}
    for tag in soup.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in KEEP}

    # Rewrite <a href>
    for a in soup.find_all('a', href=True):
        a['href'] = rewrite_url(a['href'])

    # Rewrite <form action>
    for form in soup.find_all('form', action=True):
        form['action'] = rewrite_url(form['action'])

    # Remove images (too heavy for old browsers / GPRS)
    for img in soup.find_all('img'):
        img.decompose()

    # Add a tiny nav bar at the top
    nav = soup.new_tag('div')
    nav.string = '[ '
    home_a = soup.new_tag('a', href='/fb/')
    home_a.string = 'Home'
    logout_a = soup.new_tag('a', href='/logout')
    logout_a.string = 'Logout'
    nav.append(home_a)
    nav.append(' | ')
    nav.append(logout_a)
    nav.append(' ]')

    if soup.body:
        soup.body.insert(0, nav)

    return str(soup)


# ── Routes ────────────────────────────────────────────────────────────────────

SETUP_PAGE = """<html>
<head><title>FB Proxy</title></head>
<body>
<h2>FB Proxy — Setup</h2>
<p>Facebook cookies dao niche. Cookies niye ashte hobe PC theke.</p>
<form method="POST" action="/setcookies">
<p><b>Cookies:</b><br>
<textarea name="cookies" rows="5" cols="45" placeholder="c_user=123456789; xs=AbCdEf..."></textarea>
</p>
<input type="submit" value="Save and Open Facebook">
</form>
<hr>
<h3>Cookie kothay pabo? (PC te koro):</h3>
<ol>
<li>Chrome/Firefox e facebook.com e login koro</li>
<li>F12 chap (DevTools khulbe)</li>
<li>Application (Chrome) ba Storage (Firefox) tab e jao</li>
<li>Left side e Cookies &gt; https://www.facebook.com click koro</li>
<li><b>c_user</b> er value copy koro</li>
<li><b>xs</b> er value copy koro</li>
<li>Upora textarea te likho: <code>c_user=VALUE; xs=VALUE</code></li>
</ol>
</body>
</html>"""


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

    if request.method == 'POST':
        r = fetch_fb(path, method='POST', form_data=request.form)
    else:
        r = fetch_fb(path, method='GET')

    if r is None:
        return ('<html><body>Connection error.<br>'
                '<a href="/fb/">Retry</a> | <a href="/">Setup</a>'
                '</body></html>')

    # Handle redirects manually
    if r.status_code in (301, 302):
        loc = r.headers.get('Location', '')
        loc = rewrite_url(loc)
        return redirect(loc)

    simplified = simplify_html(r.text)
    return simplified, 200, {'Content-Type': 'text/html; charset=utf-8'}


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
