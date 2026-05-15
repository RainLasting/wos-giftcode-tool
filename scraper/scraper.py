import requests
from .extractors import CodeExtractors, BS4_AVAILABLE

SOURCE_URLS = [
    {
        "url": "https://wosgiftcodes.com/rss.php",
        "name": "RSS Feed",
        "priority": 1,
        "type": "rss",
    },
    {
        "url": "https://www.whiteoutsurvival.wiki/giftcodes/",
        "name": "Official Wiki",
        "priority": 2,
        "type": "html",
    },
]

RSS_FEED_URL = "https://wosgiftcodes.com/rss.php"
WIKI_FEED_URL = "https://www.whiteoutsurvival.wiki/giftcodes/"


class CloudflareBlockError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"Cloudflare block (HTTP {status_code})")


class GiftCodeScraper:
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.running = False

    def _status(self, message, level='info'):
        if self.status_callback:
            self.status_callback(message, level)

    def _fetch_page(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="131", "Google Chrome";v="131"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=20, allow_redirects=True)

        if response.status_code == 403:
            server = response.headers.get('Server', '').lower()
            title_text = ''
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                title_text = soup.title.string.lower() if soup.title else ''
            except Exception:
                pass
            if 'cloudflare' in server or 'just a moment' in title_text:
                raise CloudflareBlockError(response.status_code)
            raise requests.exceptions.HTTPError(response=response)

        if response.status_code == 503:
            server = response.headers.get('Server', '').lower()
            if 'cloudflare' in server:
                raise CloudflareBlockError(response.status_code)

        if response.status_code >= 400:
            raise requests.exceptions.HTTPError(response=response)

        return response.text, response.status_code

    def _parse_rss(self, xml_content):
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            self._status(f"RSS 解析失败: XML 格式错误", level='error')
            return None, None, f"XML 解析错误: {str(e)[:50]}"
        except Exception as e:
            self._status(f"RSS 解析失败: {e}", level='error')
            return None, None, str(e)[:100]

        codes = []
        for item in root.findall('.//item'):
            title = item.find('title')
            if title is not None and title.text:
                code_text = title.text.strip()
                if code_text:
                    codes.append(code_text)

        if not codes:
            self._status("RSS 未找到有效礼包码", level='warn')
            return [], None, None

        self._status(f"从 RSS 获取到 {len(codes)} 个礼包码")
        return codes, None, None

    def _scrape_source(self, source):
        url = source["url"]
        name = source["name"]
        source_type = source.get("type", "html")
        self._status(f"正在从 {name} 获取礼包码...")

        try:
            content, status_code = self._fetch_page(url)
        except CloudflareBlockError as e:
            self._status(f"{name} 被 Cloudflare 防护拦截（HTTP {e.status_code}），跳过", level='warn')
            return None, None, f"Cloudflare 防护拦截（HTTP {e.status_code}）"
        except requests.exceptions.HTTPError as e:
            sc = e.response.status_code if e.response is not None else '未知'
            self._status(f"{name} 请求失败（HTTP {sc}）", level='error')
            return None, None, f"HTTP {sc}"
        except requests.exceptions.ConnectionError:
            self._status(f"{name} 连接失败，请检查网络", level='error')
            return None, None, "连接失败"
        except requests.exceptions.Timeout:
            self._status(f"{name} 请求超时", level='error')
            return None, None, "请求超时"
        except Exception as e:
            self._status(f"{name} 爬取出错: {e}", level='error')
            return None, None, str(e)[:100]

        if source_type == "rss":
            return self._parse_rss(content)

        if not BS4_AVAILABLE:
            return None, None, "beautifulsoup4 未安装"

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")

        title_text = soup.title.string.lower() if soup.title else ''
        if 'just a moment' in title_text or 'checking your browser' in title_text:
            self._status(f"{name} 返回 Cloudflare 验证页面，跳过", level='warn')
            return None, None, "Cloudflare 验证页面"

        article_date = CodeExtractors.extract_date(soup)

        working = CodeExtractors.extract_codes_from_section(soup,
            ['working', 'active', 'new codes', 'valid', 'available', 'active codes'])
        expired = CodeExtractors.extract_codes_from_section(soup,
            ['expired', 'inactive', 'old codes', 'no longer', 'expired codes'])

        if not working and name == "Official Wiki":
            working = CodeExtractors.extract_codes_from_wiki(soup)

        if not working and not expired:
            self._status(f"{name} 未找到分类礼包码，尝试全文提取...", level='warn')
            all_codes = CodeExtractors.extract_all_codes(soup)
            if all_codes:
                working = all_codes

        return working, expired, article_date

    def scrape(self, source_type=None):
        if not BS4_AVAILABLE and source_type != "rss":
            self._status("错误：beautifulsoup4 未安装，无法爬取 Wiki 礼包码", level='error')
            return {"codes": [], "error": "beautifulsoup4 未安装"}

        self.running = True
        working_codes = []
        last_error = None

        sources_to_scrape = SOURCE_URLS
        if source_type:
            sources_to_scrape = [s for s in SOURCE_URLS if s.get("type", "html") == source_type]
            if not sources_to_scrape:
                sources_to_scrape = SOURCE_URLS

        for source in sources_to_scrape:
            if not self.running:
                break

            working, expired, date_or_error = self._scrape_source(source)
            name = source["name"]

            if working is None:
                last_error = date_or_error
                continue

            expired_set = set(expired) if expired else set()
            working_set = set(working) - expired_set

            if working_set:
                self._status(f"从 {name} 获取到 {len(working_set)} 个有效礼包码")
                working_codes = sorted(working_set)
            elif expired:
                self._status(f"{name} 仅找到已过期礼包码", level='warn')
            else:
                self._status(f"{name} 未找到礼包码", level='warn')

        if not working_codes and last_error:
            self._status(f"获取礼包码失败: {last_error}", level='error')
        elif working_codes:
            self._status(f"共获取到 {len(working_codes)} 个有效礼包码")

        self.running = False
        return {
            "codes": working_codes,
            "error": last_error if not working_codes else None,
        }
