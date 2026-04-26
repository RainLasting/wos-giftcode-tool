import re
from datetime import datetime

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

CODE_REGEX = re.compile(r'\b[A-Za-z0-9]{4,20}\b')

KNOWN_FALSE_POSITIVES = {
    'HTTP', 'HTTPS', 'HTML', 'JSON', 'UTF', 'POST', 'GET', 'DELETE', 'UPDATE',
    'PATCH', 'HEAD', 'OPTIONS', 'PUT', 'CONNECT', 'TRACE', 'PNG', 'JPEG', 'GIF',
    'SVG', 'WEBP', 'MP4', 'MP3', 'AVI', 'MOV', 'PDF', 'DOCX', 'XLSX', 'PPTX',
    'ZIP', 'RAR', 'TAR', 'GZIP', 'BZIP', 'SEVEN', 'ANDROID', 'WINDOWS', 'APPLE',
    'LINUX', 'CHROME', 'FIREFOX', 'SAFARI', 'OPERA', 'MOZILLA', 'GOOGLE', 'YAHOO',
    'BING', 'BAIDU', 'DUCKDUCK', 'AMAZON', 'MICROSOFT', 'FACEBOOK', 'TWITTER',
    'INSTAGRAM', 'TIKTOK', 'SNAPCHAT', 'PINTEREST', 'REDDIT', 'DISCORD', 'TELEGRAM',
    'WHATSAPP', 'YOUTUBE', 'TWITCH', 'STEAM', 'EPIC', 'PLAYSTATION', 'XBOX',
    'NINTENDO', 'SWITCH', 'MOBILE', 'TABLET', 'DESKTOP', 'LAPTOP', 'SERVER',
    'CLIENT', 'PROXY', 'VPN', 'DNS', 'SMTP', 'FTP', 'SSH', 'TELNET', 'SOCKET',
    'WEBSOCKET', 'API', 'REST', 'GRAPHQL', 'GRPC', 'RPC', 'SDK', 'IDE', 'CLI',
    'GUI', 'CSS', 'SCSS', 'LESS', 'SASS', 'WEBPACK', 'ROLLUP', 'VITE', 'ESBUILD',
    'BABEL', 'TYPESCRIPT', 'JAVASCRIPT', 'PYTHON', 'RUBY', 'PERL', 'PHP', 'JAVA',
    'KOTLIN', 'SWIFT', 'DART', 'RUST', 'GOLANG', 'SCALA', 'HASKELL', 'ERLANG',
    'CLOJURE', 'ELIXIR', 'LUA', 'JULIA', 'MATLAB', 'DOCKER', 'KUBERNETES',
    'JENKINS', 'TRAVIS', 'CIRCLECI', 'GITHUB', 'GITLAB', 'BITBUCKET', 'HEROKU',
    'VERCEL', 'NETLIFY', 'CLOUDFLARE', 'NGINX', 'APACHE', 'TOMCAT', 'MYSQL',
    'POSTGRESQL', 'MONGODB', 'REDIS', 'ELASTIC', 'KAFKA', 'RABBITMQ', 'ZOOKEEPER',
    'CENTURY', 'SURVIVAL', 'WHITEOUT', 'GIFTCODE', 'REDEEM', 'REWARD', 'BONUS',
    'SPEEDUP', 'SPEED', 'GEMS', 'VIP', 'MEAT', 'WOOD', 'COAL', 'IRON', 'HERO',
    'CHIEF', 'FURNACE', 'ALLIANCE', 'STATE', 'KINGDOM', 'EVENT', 'UPDATE',
    'WOSGIFTCODE', 'GIFTCODES', 'CODES', 'WORKING', 'EXPIRED', 'ACTIVE',
    'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER',
    'NOVEMBER', 'DECEMBER', 'JANUARY', 'FEBRUARY', 'MONDAY', 'TUESDAY', 'WEDNESDAY',
    'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY', 'UPDATED', 'LATEST', 'NEW',
    'FREE', 'CLAIM', 'REDEEM', 'ENTER', 'CLICK', 'SHARE', 'FOLLOW', 'SUBSCRIBE',
    'LIKE', 'COMMENT', 'DOWNLOAD', 'INSTALL', 'REGISTER', 'LOGIN', 'SIGNUP',
    'COPY', 'IPHONE', 'IOS', 'ANDROID', 'MOBILE', 'GIFTCODECENTER', 'AVATAR',
    'SETTINGS', 'COGWHEEL', 'REWARDS', 'MAILBOX', 'MAIL', 'INBOX', 'PROFILE',
    'PLAYER', 'FROST', 'STAR', 'FROSTSTAR', 'TOPUP', 'PURCHASE', 'SECURE',
    'EXPIRES', 'EXPIRE', 'VALID', 'REMAIN', 'UPCOMING', 'ANNOUNCED', 'RELEASED',
    'ARTICLE', 'GUIDE', 'TUTORIAL', 'STEP', 'STEPS', 'METHOD', 'PLATFORM',
    'DEVICE', 'BROWSER', 'WEBSITE', 'PAGE', 'LINK', 'URL', 'SITE', 'BLOG',
    'ALUCARE', 'LOOTBAR', 'TRYHARDGUIDES', 'MRGUIDER', 'WIKI', 'ORANGEJUICE',
    'YATIN', 'AUTHOR', 'ADMIN', 'MODERATOR', 'DEVELOPER', 'PUBLISHER', 'STUDIO',
    'GAMES', 'CENTURY', 'PRIVATE', 'LTD', 'COPYRIGHT', 'RESERVED', 'RIGHTS',
    'DISCLAIMER', 'AFFILIATE', 'SPONSORED', 'PROMOTIONAL', 'PROMOTION',
}

_COMMON_ENGLISH_WORDS = {
    w.upper() for w in
    "able about after again also any area back been best better big book both "
    "bring brought build building case catch cause certain change check clear "
    "close code come common could day does done down each early either else "
    "end enough even every example face fact find first follow for form found "
    "from full further get give going gone good great group hand have help "
    "here high hold home house just keep kind know large last late later lay "
    "lead learn leave left less life like line live long look make many may "
    "mean might mind more most move much must name need never new next none "
    "note number offer only open order other over part past pay per point "
    "power problem put question right same say see set show side small some "
    "stand start still study such sure system take tell test that them then "
    "there these they thing think this time turn type use used using very "
    "want water way well went were what when where which while who will with "
    "word work world would year young your ensure could contact customer "
    "support double entered already redeemed correctly persist problems "
    "ensure check code been have".split()
}


class CodeExtractors:
    @staticmethod
    def is_valid_code(candidate):
        if len(candidate) < 4 or len(candidate) > 20:
            return False
        upper = candidate.upper()
        if upper in KNOWN_FALSE_POSITIVES:
            return False
        if candidate.isdigit():
            return False
        if re.match(r'^[A-Z]+$', upper) and len(upper) > 6:
            return False
        if re.match(r'^[a-z]+$', candidate) and len(candidate) > 8:
            return False
        has_digit = any(c.isdigit() for c in candidate)
        has_upper = any(c.isupper() for c in candidate)
        has_lower = any(c.islower() for c in candidate)
        if not has_digit and not has_lower and len(candidate) > 6:
            return False
        if not has_digit and has_upper and not has_lower and len(candidate) <= 6:
            if upper in _COMMON_ENGLISH_WORDS:
                return False
        return True

    @staticmethod
    def extract_date(soup):
        date_str = None

        for meta in soup.find_all('meta'):
            prop = meta.get('property', '') or meta.get('name', '')
            if prop in ('article:published_time', 'article:modified_time', 'datePublished', 'dateModified'):
                content = meta.get('content', '')
                if content:
                    date_str = content
                    break

        if not date_str:
            time_tag = soup.find('time')
            if time_tag:
                date_str = time_tag.get('datetime') or time_tag.get('content') or time_tag.get_text(strip=True)

        if not date_str:
            for tag in soup.find_all(['span', 'div', 'p']):
                cls = ' '.join(tag.get('class', []))
                if any(k in cls.lower() for k in ['date', 'time', 'updated', 'published', 'posted']):
                    text = tag.get_text(strip=True)
                    if text and len(text) < 100:
                        date_str = text
                        break

        if not date_str:
            text = soup.get_text(separator=' ', strip=True)
            date_patterns = [
                r'(?:Updated?|Published|Posted|Modified)[:\s]+(\w+ \d{1,2},?\s*\d{4})',
                r'(\w+ \d{1,2},?\s*\d{4}\s+at\s+\d{1,2}:\d{2}\s*[ap]m\s*\w*)',
                r'(\d{4}-\d{2}-\d{2})',
                r'(\w+ \d{1,2},?\s*\d{4})',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    break

        if date_str:
            try:
                for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d',
                            '%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y']:
                    try:
                        dt = datetime.strptime(date_str.strip()[:26], fmt)
                        return dt.strftime('%Y-%m-%d %H:%M')
                    except ValueError:
                        continue
            except Exception:
                pass

        return date_str

    @staticmethod
    def extract_codes_from_section(soup, section_keywords):
        codes = set()
        headings = soup.find_all(['h2', 'h3', 'h4', 'h5'])
        target_heading = None

        for heading in headings:
            text = heading.get_text(strip=True).lower()
            if any(kw.lower() in text for kw in section_keywords):
                target_heading = heading
                break

        if target_heading:
            sibling = target_heading.find_next_sibling()
            while sibling and sibling.name not in ['h2', 'h3', 'h4', 'h5']:
                if sibling.name in ['ul', 'ol']:
                    for li in sibling.find_all('li'):
                        code_text = li.get_text(strip=True)
                        for match in CODE_REGEX.finditer(code_text):
                            candidate = match.group(0)
                            if CodeExtractors.is_valid_code(candidate):
                                codes.add(candidate)
                elif sibling.name == 'p':
                    code_text = sibling.get_text(strip=True)
                    for match in CODE_REGEX.finditer(code_text):
                        candidate = match.group(0)
                        if CodeExtractors.is_valid_code(candidate):
                            codes.add(candidate)
                elif sibling.name == 'table':
                    for td in sibling.find_all('td'):
                        code_text = td.get_text(strip=True)
                        for match in CODE_REGEX.finditer(code_text):
                            candidate = match.group(0)
                            if CodeExtractors.is_valid_code(candidate):
                                codes.add(candidate)
                sibling = sibling.find_next_sibling()

        return codes

    @staticmethod
    def extract_codes_from_wiki(soup):
        codes = set()

        for tag in soup.find_all(class_='code'):
            text = tag.get_text(strip=True)
            if text and 3 <= len(text) <= 20:
                codes.add(text)

        if codes:
            return codes

        headings = soup.find_all(['h2', 'h3'])
        active_heading = None
        for h in headings:
            if 'active' in h.get_text(strip=True).lower():
                active_heading = h
                break

        if active_heading:
            sibling = active_heading.find_next_sibling()
            while sibling and sibling.name not in ['h2', 'h3']:
                for tag in sibling.find_all(['span', 'div', 'p', 'li']):
                    cls = ' '.join(tag.get('class', []))
                    text = tag.get_text(strip=True)
                    if not text or len(text) > 25:
                        continue
                    if 'copy' in text.lower():
                        continue
                    if any(c in cls.lower() for c in ['code', 'gift', 'coupon']):
                        codes.add(text)
                    elif 3 <= len(text) <= 20 and not text.isdigit():
                        if CodeExtractors.is_valid_code(text):
                            codes.add(text)
                sibling = sibling.find_next_sibling()

        return codes

    @staticmethod
    def extract_all_codes(soup):
        codes = set()
        text = soup.get_text(separator=' ', strip=True)
        for match in CODE_REGEX.finditer(text):
            candidate = match.group(0)
            if CodeExtractors.is_valid_code(candidate):
                codes.add(candidate)
        return codes
