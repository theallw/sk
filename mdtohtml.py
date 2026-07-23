import re
import html
import sys
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import hashlib
import subprocess


def auto_install():
    packages = ['requests', 'beautifulsoup4']
    for pkg in packages:
        try:
            __import__(pkg if pkg != 'beautifulsoup4' else 'bs4')
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg])

# 运行安装
auto_install()

# 尝试导入chardet，如果不存在则使用简单编码检测
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

def detect_encoding(file_path: Path) -> str:
    """检测文件编码"""
    if HAS_CHARDET:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return result['encoding'] or 'utf-8'
    return 'utf-8'

def get_color_for_category(category: str) -> str:
    """根据分类名称生成一致的颜色 - BMM风格配色"""
    CATEGORY_COLORS = [
        '#ff1494', '#33bbff', '#ff2e2e', '#a442fa', '#b638ff', '#ebcb63',
        '#0066ff', '#eeefff', '#069b05', '#00ffcb', '#bfbfbf', '#191919',
        '#ffcc14', '#ffb13b', '#f0f0f0', '#fff3e0', '#13ae4f', '#ffffff',
        '#424cff', '#00d8ff', '#41b883', '#fbfbfb', '#f7df1e', '#e43718',
        '#9e9e9e', '#f0bb6e', '#1a97ef', '#e0feff', '#35bfce', '#c70000',
        '#a647ff', '#24a2ff', '#ffaa00', '#3f3fff', '#00ff00', '#ff00a8',
        '#75ffed', '#616161',
    ]
    hash_val = hashlib.md5(category.encode('utf-8')).hexdigest()
    index = int(hash_val[:8], 16) % len(CATEGORY_COLORS)
    return CATEGORY_COLORS[index]

def get_app_icon(term: str, timeout: int = 5) -> Tuple[Optional[str], bool]:
    """从 Apple App Store 获取应用图标"""
    try:
        url = "https://apps.apple.com/cn/iphone/search"
        params = {'term': term.strip()}
        headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            'Accept-Language': "zh-CN,zh;q=0.9",
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        icons = soup.find_all('img', src=re.compile(r'\.webp$'))
        for img in icons:
            src = img.get('src')
            if src and 'Purple' in src and '48x48' in src:
                if src.startswith('//'):
                    src = 'https:' + src
                return src, True
        
        picture_tags = soup.find_all('picture')
        for picture in picture_tags:
            source = picture.find('source', {'type': 'image/webp'})
            if source:
                srcset = source.get('srcset', '')
                if srcset:
                    first_url = srcset.split(',')[0].strip().split()[0]
                    if first_url.startswith('//'):
                        first_url = 'https:' + first_url
                    return first_url, True
                
    except Exception:
        pass
    
    return None, False

def enrich_search_engines_with_icons(search_engines: List[Dict], max_workers: int = 5) -> List[Dict]:
    """使用多线程为搜索引擎列表获取图标"""
    print(f"\n=== 开始获取搜索引擎图标 (使用 {max_workers} 个线程) ===")
    start_time = time.time()
    
    enriched = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_engine = {}
        for engine in search_engines:
            name = engine['name']
            future = executor.submit(get_app_icon, name)
            future_to_engine[future] = engine
        
        completed = 0
        total = len(search_engines)
        for future in as_completed(future_to_engine):
            engine = future_to_engine[future]
            name = engine['name']
            completed += 1
            
            try:
                icon_url, success = future.result(timeout=10)
                if success and icon_url:
                    print(f"  [{completed}/{total}] ✅ 获取到 {name} 图标")
                    enriched.append({
                        'name': name,
                        'url': engine['url'],
                        'icon': icon_url
                    })
                else:
                    print(f"  [{completed}/{total}] ⚠️ 使用备用图标: {name}")
                    enriched.append({
                        'name': name,
                        'url': engine['url'],
                        'icon': f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23999' stroke-width='2'%3E%3Crect x='3' y='3' width='18' height='18' rx='4'/%3E%3Ctext x='12' y='16' text-anchor='middle' font-size='12' fill='%23999'%3E{name[0].upper()}%3C/text%3E%3C/svg%3E"
                    })
            except Exception as e:
                print(f"  [{completed}/{total}] ❌ 获取 {name} 图标失败: {str(e)}")
                enriched.append({
                    'name': name,
                    'url': engine['url'],
                    'icon': f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23999' stroke-width='2'%3E%3Crect x='3' y='3' width='18' height='18' rx='4'/%3E%3Ctext x='12' y='16' text-anchor='middle' font-size='12' fill='%23999'%3E{name[0].upper()}%3C/text%3E%3C/svg%3E"
                })
    
    elapsed = time.time() - start_time
    print(f"=== 图标获取完成，耗时 {elapsed:.2f} 秒 ===\n")
    return enriched

def generate_html(bookmarks: List[Dict], title: str = "我的导航页") -> str:
    """生成BMM风格书签导航HTML页面（带主题切换）"""
    
    # 按分类分组
    categories = {}
    for bm in bookmarks:
        if bm['category'] not in categories:
            categories[bm['category']] = []
        categories[bm['category']].append(bm)
    
    # 为每个分类生成颜色
    category_colors = {cat: get_color_for_category(cat) for cat in categories.keys()}
    
    # 搜索引擎配置
    base_search_engines = [
        {'name': 'Google', 'url': 'https://www.google.com/search?q=', 'icon': ''},
        {'name': 'Bing', 'url': 'https://cn.bing.com/search?q=', 'icon': ''},
        {'name': 'Baidu', 'url': 'https://kaifa.baidu.com/searchPage?wd=', 'icon': ''},
        {'name': '搜狗', 'url': 'https://www.sogou.com/web?query=', 'icon': ''},
        {'name': 'Github', 'url': 'https://github.com/search?q=', 'icon': ''},
        {'name': 'Bilibili', 'url': 'https://search.bilibili.com/all?keyword=', 'icon': ''},
        {'name': '360', 'url': 'https://www.so.com/s?q=', 'icon': ''},
        {'name': '神马', 'url': 'https://m.sm.cn/s?q=', 'icon': ''},
        {'name': '安全内参', 'url': 'https://www.secrss.com/search?keywords=', 'icon': ''},
    ]
    
    # 从 App Store 获取真实图标
    search_engines = enrich_search_engines_with_icons(base_search_engines, max_workers=8)
    
    # 生成分类标签（左侧标签池）
    category_list = list(categories.items())
    
    # 生成左侧标签导航
    sidebar_items = []
    for cat_name, cat_bookmarks in category_list:
        count = len(cat_bookmarks)
        color = category_colors.get(cat_name, '#007aff')
        sidebar_items.append(f'''
            <a href="#{html.escape(cat_name)}" class="sidebar-tag" data-category="{html.escape(cat_name)}">
                <span class="tag-dot" style="background-color: {color};"></span>
                <span class="tag-name">{html.escape(cat_name)}</span>
                <span class="tag-count">{count}</span>
            </a>
        ''')
    
    # 生成右侧书签卡片
    content_html = []
    for cat_name, cat_bookmarks in category_list:
        cards_html = []
        for bm in cat_bookmarks:
            favicon = get_favicon_url(bm['url'])
            # 截取域名作为副标题
            try:
                domain = bm['url'].split('/')[2] if '://' in bm['url'] else bm['url'].split('/')[0]
                domain = domain.replace('www.', '')
            except:
                domain = ''
            cards_html.append(f'''
                <div class="bookmark-card">
                    <a href="{html.escape(bm['url'])}" target="_blank" rel="noopener noreferrer" class="card-link">
                        <div class="card-icon">
                            <img src="{favicon}" alt="" onerror="this.parentElement.innerHTML='<span class=\'fallback-icon\'>🌐</span>'">
                        </div>
                        <div class="card-content">
                            <div class="card-title">{html.escape(bm['title'])}</div>
                            <div class="card-domain">{html.escape(domain)}</div>
                        </div>
                    </a>
                </div>
            ''')
        
        content_html.append(f'''
            <section class="category-section" id="{html.escape(cat_name)}">
                <div class="category-header">
                    <span class="category-dot" style="background-color: {category_colors.get(cat_name, '#007aff')};"></span>
                    <h2 class="category-title">{html.escape(cat_name)}</h2>
                    <span class="category-count">{len(cat_bookmarks)} 个书签</span>
                </div>
                <div class="bookmarks-grid">
                    {''.join(cards_html)}
                </div>
            </section>
        ''')
    
    # 生成搜索引擎按钮
    search_buttons = []
    for engine in search_engines:
        icon = engine['icon']
        if icon.startswith('http') or icon.startswith('data:'):
            icon_html = f'<img src="{html.escape(icon)}" alt="{html.escape(engine["name"])}" class="search-icon">'
        else:
            icon_html = html.escape(icon)
        
        search_buttons.append(f'''
            <button class="search-btn" data-engine="{html.escape(engine['url'])}" title="{html.escape(engine['name'])}">
                {icon_html}
                <span>{html.escape(engine['name'])}</span>
            </button>
        ''')
    
    search_buttons_html = ''.join(search_buttons)
    
    html_template = f'''<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>{html.escape(title)}</title>
    <style>
        /* ===== CSS Variables - 双主题 ===== */
        :root {{
            /* 浅色主题 (默认) */
            --bg-primary: #f0f2f5;
            --bg-secondary: rgba(0,0,0,0.04);
            --bg-card: rgba(0,0,0,0.06);
            --bg-card-hover: rgba(0,0,0,0.10);
            --bg-sidebar: rgba(0,0,0,0.04);
            --text-primary: #1a1a1a;
            --text-secondary: rgba(0,0,0,0.65);
            --text-muted: rgba(0,0,0,0.45);
            --border-color: rgba(0,0,0,0.08);
            --shadow-card: 0 4px 12px rgba(0,0,0,0.1);
            --accent: #4f46e5;
            --accent-hover: #4338ca;
            --sidebar-width: 240px;
        }}

        html.dark {{
            /* 深色主题 */
            --bg-primary: #06111b;
            --bg-secondary: rgba(255,255,255,0.04);
            --bg-card: rgba(255,255,255,0.06);
            --bg-card-hover: rgba(255,255,255,0.10);
            --bg-sidebar: rgba(255,255,255,0.04);
            --text-primary: #ffffff;
            --text-secondary: rgba(255,255,255,0.65);
            --text-muted: rgba(255,255,255,0.45);
            --border-color: rgba(255,255,255,0.08);
            --shadow-card: 0 4px 12px rgba(0,0,0,0.3);
        }}

        /* ===== Reset ===== */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", 
                         "PingFang SC", "Microsoft YaHei", sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            min-height: 100vh;
            transition: background 0.3s ease, color 0.3s ease;
        }}

        /* ===== Background Effects ===== */
        .bg-effects {{
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            overflow: hidden;
        }}
        .bg-effects .glow1 {{
            position: absolute;
            top: -6vmin;
            right: -8vmin;
            width: 52vmin;
            height: 52vmin;
            background: radial-gradient(circle at center, rgba(167,139,250,0.12), transparent 66%);
        }}
        .bg-effects .glow2 {{
            position: absolute;
            bottom: 0;
            left: 0;
            width: 62vmin;
            height: 62vmin;
            transform: translate(-25%, 25%);
            background: radial-gradient(circle at center, rgba(45,212,191,0.08), transparent 68%);
        }}

        /* ===== Layout ===== */
        .app-container {{
            position: relative;
            z-index: 1;
            display: flex;
            min-height: 100vh;
            max-width: 1400px;
            margin: 0 auto;
            padding: 16px 20px 20px;
        }}

        /* ===== Sidebar ===== */
        .sidebar {{
            position: sticky;
            top: 16px;
            width: var(--sidebar-width);
            height: calc(100vh - 32px);
            flex-shrink: 0;
            background: var(--bg-sidebar);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            padding: 16px 12px;
            overflow-y: auto;
            margin-right: 20px;
            display: flex;
            flex-direction: column;
            transition: background 0.3s ease, border-color 0.3s ease;
        }}

        .sidebar::-webkit-scrollbar {{
            width: 3px;
        }}
        .sidebar::-webkit-scrollbar-thumb {{
            background: var(--border-color);
            border-radius: 2px;
        }}

        .sidebar-header {{
            padding: 0 8px 16px;
            border-bottom: 1px solid var(--border-color);
            flex-shrink: 0;
        }}

        .sidebar-header .logo {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.3px;
        }}
        .sidebar-header .logo span {{
            background: linear-gradient(135deg, var(--text-primary) 0%, var(--text-muted) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .sidebar-header .badge {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
            padding-left: 2px;
        }}

        .sidebar-search {{
            padding: 12px 0 8px;
            flex-shrink: 0;
        }}
        .sidebar-search input {{
            width: 100%;
            padding: 8px 12px;
            font-size: 13px;
            font-family: inherit;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            background: var(--bg-secondary);
            color: var(--text-primary);
            outline: none;
            transition: var(--transition);
        }}
        .sidebar-search input:focus {{
            border-color: var(--accent);
            background: var(--bg-card-hover);
        }}
        .sidebar-search input::placeholder {{
            color: var(--text-muted);
        }}

        .sidebar-tags {{
            flex: 1;
            overflow-y: auto;
            padding: 4px 0;
        }}

        .sidebar-tag {{
            display: flex;
            align-items: center;
            padding: 8px 12px;
            border-radius: 10px;
            text-decoration: none;
            color: var(--text-secondary);
            transition: var(--transition);
            cursor: pointer;
            gap: 10px;
            font-size: 13px;
            font-weight: 450;
        }}
        .sidebar-tag:hover {{
            background: var(--bg-card-hover);
            color: var(--text-primary);
            transform: translateX(2px);
        }}
        .sidebar-tag.active {{
            background: rgba(79,70,229,0.15);
            color: var(--text-primary);
        }}

        .tag-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        .tag-name {{
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .tag-count {{
            font-size: 11px;
            color: var(--text-muted);
            background: var(--bg-secondary);
            padding: 0 8px;
            border-radius: 10px;
            line-height: 18px;
            flex-shrink: 0;
        }}

        .sidebar-footer {{
            padding: 12px 8px 0;
            border-top: 1px solid var(--border-color);
            flex-shrink: 0;
            font-size: 11px;
            color: var(--text-muted);
        }}

        /* ===== Main Content ===== */
        .main-content {{
            flex: 1;
            min-width: 0;
            padding: 0 0 40px;
        }}

        /* ===== Header ===== */
        .main-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 0 20px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 24px;
        }}
        .main-header .header-left {{
            flex: 1;
        }}
        .main-header h1 {{
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
            margin-bottom: 4px;
        }}
        .main-header p {{
            font-size: 14px;
            color: var(--text-secondary);
        }}

        /* ===== 主题切换按钮 ===== */
        .theme-toggle {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: var(--transition);
            color: var(--text-secondary);
            flex-shrink: 0;
            margin-left: 16px;
        }}
        .theme-toggle:hover {{
            background: var(--bg-card-hover);
            border-color: var(--text-muted);
        }}
        .theme-toggle .icon-sun,
        .theme-toggle .icon-moon {{
            font-size: 20px;
            line-height: 1;
        }}
        /* 默认（浅色）显示太阳，深色显示月亮 */
        .theme-toggle .icon-moon {{
            display: none;
        }}
        .theme-toggle .icon-sun {{
            display: inline;
        }}
        html.dark .theme-toggle .icon-moon {{
            display: inline;
        }}
        html.dark .theme-toggle .icon-sun {{
            display: none;
        }}

        /* ===== Search Engines ===== */
        .search-engines {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
            margin-bottom: 12px;
        }}
        .search-engines .label {{
            font-size: 12px;
            color: var(--text-muted);
            font-weight: 500;
            margin-right: 4px;
        }}
        .search-btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 12px;
            font-size: 12px;
            font-family: inherit;
            font-weight: 500;
            border: 1px solid var(--border-color);
            border-radius: var(--radius-btn);
            background: var(--bg-secondary);
            color: var(--text-secondary);
            cursor: pointer;
            transition: var(--transition);
        }}
        .search-btn:hover {{
            background: var(--bg-card-hover);
            border-color: rgba(255,255,255,0.15);
            color: var(--text-primary);
        }}
        .search-btn.active {{
            background: var(--accent);
            border-color: var(--accent);
            color: #fff;
        }}
        .search-btn .search-icon {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            object-fit: cover;
        }}

        /* ===== Search Input ===== */
        .search-wrapper {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 12px 0 20px;
        }}
        .search-wrapper input {{
            flex: 1;
            padding: 10px 16px;
            font-size: 14px;
            font-family: inherit;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            background: var(--bg-secondary);
            color: var(--text-primary);
            outline: none;
            transition: var(--transition);
        }}
        .search-wrapper input:focus {{
            border-color: var(--accent);
            background: var(--bg-card-hover);
        }}
        .search-wrapper input::placeholder {{
            color: var(--text-muted);
        }}
        .search-wrapper .shortcut {{
            font-size: 11px;
            color: var(--text-muted);
            background: var(--bg-secondary);
            padding: 2px 10px;
            border-radius: 4px;
            border: 1px solid var(--border-color);
            white-space: nowrap;
        }}

        /* ===== Category Section ===== */
        .category-section {{
            margin-bottom: 32px;
            scroll-margin-top: 16px;
        }}
        .category-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 16px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }}
        .category-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        .category-title {{
            font-size: 18px;
            font-weight: 600;
        }}
        .category-count {{
            font-size: 12px;
            color: var(--text-muted);
            margin-left: auto;
        }}

        /* ===== Bookmarks Grid ===== */
        .bookmarks-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }}

        /* ===== Bookmark Card - BMM Style ===== */
        .bookmark-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-card);
            transition: var(--transition);
            overflow: hidden;
        }}
        .bookmark-card:hover {{
            background: var(--bg-card-hover);
            transform: translateY(-2px);
            border-color: var(--text-muted);
            box-shadow: var(--shadow-card);
        }}

        .card-link {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 16px;
            text-decoration: none;
            color: inherit;
        }}

        .card-icon {{
            width: 36px;
            height: 36px;
            flex-shrink: 0;
            border-radius: 8px;
            background: var(--bg-secondary);
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}
        .card-icon img {{
            width: 20px;
            height: 20px;
            object-fit: contain;
        }}
        .card-icon .fallback-icon {{
            font-size: 18px;
        }}

        .card-content {{
            flex: 1;
            min-width: 0;
        }}
        .card-title {{
            font-size: 14px;
            font-weight: 500;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .card-domain {{
            font-size: 11px;
            color: var(--text-muted);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        /* ===== No Results ===== */
        .no-results {{
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
            grid-column: 1 / -1;
        }}
        .no-results .icon {{
            font-size: 40px;
            display: block;
            margin-bottom: 12px;
        }}

        /* ===== Responsive ===== */
        @media (max-width: 1024px) {{
            .sidebar {{
                width: 200px;
                margin-right: 16px;
            }}
        }}

        @media (max-width: 820px) {{
            .app-container {{
                flex-direction: column;
                padding: 12px 16px;
            }}
            .sidebar {{
                position: relative;
                top: 0;
                width: 100%;
                height: auto;
                max-height: 300px;
                margin-right: 0;
                margin-bottom: 16px;
                border-radius: 16px;
            }}
            .bookmarks-grid {{
                grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            }}
        }}

        @media (max-width: 480px) {{
            .bookmarks-grid {{
                grid-template-columns: 1fr 1fr;
            }}
            .main-header h1 {{
                font-size: 22px;
            }}
            .search-wrapper {{
                flex-direction: column;
                align-items: stretch;
            }}
            .search-wrapper .shortcut {{
                align-self: flex-end;
            }}
            .search-engines {{
                justify-content: center;
            }}
            .theme-toggle {{
                width: 36px;
                height: 36px;
            }}
        }}

        @media (max-width: 380px) {{
            .bookmarks-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* ===== Utility ===== */
        .hidden {{
            display: none !important;
        }}

        /* ===== Scrollbar Global ===== */
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: transparent;
        }}
        ::-webkit-scrollbar-thumb {{
            background: var(--border-color);
            border-radius: 3px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--text-muted);
        }}
    </style>
</head>
<body>
    <!-- 背景光晕 -->
    <div class="bg-effects">
        <div class="glow1"></div>
        <div class="glow2"></div>
    </div>

    <div class="app-container">
        <!-- 侧边栏 -->
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div class="logo">
                    <span>📑</span>
                    <span>{html.escape(title)}</span>
                </div>
                <div class="badge">{len(bookmarks)} 个书签</div>
            </div>

            <div class="sidebar-search">
                <input type="text" id="sidebarSearch" placeholder="过滤标签..." autocomplete="off">
            </div>

            <nav class="sidebar-tags" id="sidebarTags">
                {''.join(sidebar_items)}
            </nav>

            <div class="sidebar-footer">
                共 {len(categories)} 个分类
            </div>
        </aside>

        <!-- 主内容 -->
        <main class="main-content" id="mainContent">
            <div class="main-header">
                <div class="header-left">
                    <h1>📚 我的书签</h1>
                    <p>收纳、分享、探索优质网站</p>
                </div>
                <button id="themeToggle" class="theme-toggle" aria-label="切换主题" title="切换主题">
                    <span class="icon-sun">☀️</span>
                    <span class="icon-moon">🌙</span>
                </button>
            </div>

            <!-- 搜索引擎 -->
            <div class="search-engines">
                <span class="label">🔍 搜索：</span>
                {search_buttons_html}
            </div>

            <!-- 搜索框 -->
            <div class="search-wrapper">
                <input type="text" id="searchInput" placeholder="搜索书签..." autocomplete="off">
                <span class="shortcut">⌘K</span>
            </div>

            <!-- 书签内容 -->
            <div id="bookmarksContainer">
                {''.join(content_html)}
            </div>
        </main>
    </div>

    <script>
        (function() {{
            'use strict';

            // ===== 主题切换 =====
            const htmlEl = document.documentElement;
            const toggleBtn = document.getElementById('themeToggle');

            // 应用主题
            function applyTheme(theme) {{
                if (theme === 'light') {{
                    htmlEl.classList.remove('dark');
                    htmlEl.style.colorScheme = 'light';
                }} else {{
                    htmlEl.classList.add('dark');
                    htmlEl.style.colorScheme = 'dark';
                }}
                localStorage.setItem('theme', theme);
            }}

            // 初始化主题
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme) {{
                applyTheme(savedTheme);
            }} else {{
                // 默认深色（已有 dark 类）
                htmlEl.style.colorScheme = 'dark';
                localStorage.setItem('theme', 'dark');
            }}

            // 切换按钮点击
            if (toggleBtn) {{
                toggleBtn.addEventListener('click', function() {{
                    const isDark = htmlEl.classList.contains('dark');
                    applyTheme(isDark ? 'light' : 'dark');
                }});
            }}

            // ===== DOM 引用 =====
            const sidebar = document.getElementById('sidebar');
            const sidebarSearch = document.getElementById('sidebarSearch');
            const sidebarTags = document.querySelectorAll('.sidebar-tag');
            const searchInput = document.getElementById('searchInput');
            const engineBtns = document.querySelectorAll('.search-btn');
            const sections = document.querySelectorAll('.category-section');

            // ===== 侧边栏标签搜索 =====
            if (sidebarSearch) {{
                sidebarSearch.addEventListener('input', function() {{
                    const keyword = this.value.toLowerCase().trim();
                    sidebarTags.forEach(tag => {{
                        const name = tag.querySelector('.tag-name').textContent.toLowerCase();
                        tag.style.display = (keyword === '' || name.includes(keyword)) ? 'flex' : 'none';
                    }});
                }});
            }}

            // ===== 标签点击 - 滚动到对应分类 =====
            sidebarTags.forEach(tag => {{
                tag.addEventListener('click', function(e) {{
                    e.preventDefault();
                    const category = this.dataset.category;
                    const target = document.getElementById(category);
                    if (target) {{
                        const offset = 20;
                        const top = target.getBoundingClientRect().top + window.scrollY - offset;
                        window.scrollTo({{ top, behavior: 'smooth' }});
                    }}
                    // 更新激活状态
                    sidebarTags.forEach(t => t.classList.remove('active'));
                    this.classList.add('active');
                    // 清空搜索
                    if (searchInput) {{
                        searchInput.value = '';
                        filterBookmarks('');
                    }}
                }});
            }});

            // ===== 滚动高亮标签 =====
            function highlightTag() {{
                let currentId = '';
                const scrollY = window.scrollY + 100;
                sections.forEach(section => {{
                    const rect = section.getBoundingClientRect();
                    const top = rect.top + window.scrollY;
                    if (scrollY >= top) {{
                        currentId = section.id;
                    }}
                }});
                sidebarTags.forEach(tag => {{
                    tag.classList.toggle('active', tag.dataset.category === currentId);
                }});
            }}
            window.addEventListener('scroll', highlightTag);
            setTimeout(highlightTag, 100);

            // ===== 书签搜索 =====
            function filterBookmarks(keyword) {{
                const keywordLower = keyword.toLowerCase().trim();
                let totalMatches = 0;

                sections.forEach(section => {{
                    const cards = section.querySelectorAll('.bookmark-card');
                    let sectionMatches = 0;

                    cards.forEach(card => {{
                        const title = card.querySelector('.card-title').textContent.toLowerCase();
                        const domain = card.querySelector('.card-domain').textContent.toLowerCase();
                        const isMatch = keywordLower === '' || title.includes(keywordLower) || domain.includes(keywordLower);
                        card.classList.toggle('hidden', !isMatch);
                        if (isMatch) sectionMatches++;
                    }});

                    totalMatches += sectionMatches;
                    section.classList.toggle('hidden', keywordLower !== '' && sectionMatches === 0);
                }});

                // 无结果提示
                let noResults = document.getElementById('noResults');
                if (totalMatches === 0 && keywordLower !== '') {{
                    if (!noResults) {{
                        noResults = document.createElement('div');
                        noResults.id = 'noResults';
                        noResults.className = 'no-results';
                        noResults.innerHTML = '<span class="icon">🔍</span><p>没有找到匹配的书签</p>';
                        document.getElementById('bookmarksContainer').appendChild(noResults);
                    }}
                }} else if (noResults) {{
                    noResults.remove();
                }}
            }}

            if (searchInput) {{
                searchInput.addEventListener('input', function() {{
                    filterBookmarks(this.value);
                }});
            }}

            // ===== 快捷键 =====
            document.addEventListener('keydown', function(e) {{
                if ((e.ctrlKey || e.metaKey) && e.key === 'k') {{
                    e.preventDefault();
                    if (searchInput) {{
                        searchInput.focus();
                        searchInput.select();
                    }}
                }}
                if (e.key === 'Escape') {{
                    if (searchInput) {{
                        searchInput.value = '';
                        filterBookmarks('');
                        searchInput.blur();
                    }}
                }}
            }});

            // ===== 搜索引擎切换 =====
            let currentEngine = localStorage.getItem('selectedEngine') || 'https://cn.bing.com/search?q=';

            engineBtns.forEach(btn => {{
                const engineUrl = btn.dataset.engine;
                if (engineUrl === currentEngine) {{
                    btn.classList.add('active');
                }}
                btn.addEventListener('click', function(e) {{
                    e.stopPropagation();
                    const url = this.dataset.engine;
                    if (url) {{
                        currentEngine = url;
                        localStorage.setItem('selectedEngine', url);
                        engineBtns.forEach(b => b.classList.remove('active'));
                        this.classList.add('active');
                        if (searchInput && searchInput.value.trim()) {{
                            window.open(currentEngine + encodeURIComponent(searchInput.value.trim()), '_blank');
                        }}
                    }}
                }});
            }});

            // ===== Enter 搜索 =====
            if (searchInput) {{
                searchInput.addEventListener('keydown', function(e) {{
                    if (e.key === 'Enter') {{
                        const query = this.value.trim();
                        if (query) {{
                            window.open(currentEngine + encodeURIComponent(query), '_blank');
                        }}
                    }}
                }});
            }}
        }})();
    </script>
</body>
</html>'''
    
    return html_template

def get_favicon_url(url: str) -> str:
    """获取网站 favicon URL"""
    try:
        if '://' in url:
            domain = url.split('/')[2]
        else:
            domain = url.split('/')[0]
        domain = domain.replace('www.', '')
        return f"https://api.lcll.cc/favicon?host={domain}"
    except:
        return ""

def parse_markdown_bookmarks(content: str) -> List[Dict]:
    """解析Markdown格式的书签文件"""
    bookmarks = []
    current_category = ""
    
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('## '):
            current_category = line[3:].strip()
        
        elif line.startswith('- ['):
            match = re.match(r'- \[([^\]]+)\]\(([^)]+)\)', line)
            if match and current_category:
                title, url = match.groups()
                bookmarks.append({
                    'category': current_category,
                    'title': title,
                    'url': url
                })
        
        elif line.startswith('-') and not line.startswith('- [') and current_category:
            if i + 1 < len(lines) and '](' in lines[i+1]:
                combined = line + ' ' + lines[i+1].strip()
                match = re.match(r'- \[([^\]]+)\]\(([^)]+)\)', combined)
                if match:
                    title, url = match.groups()
                    bookmarks.append({
                        'category': current_category,
                        'title': title,
                        'url': url
                    })
                    i += 1
        
        i += 1
    
    return bookmarks

def read_file_with_fallback(file_path: Path) -> str:
    """使用多种编码尝试读取文件"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-8-sig', 'latin-1']
    
    try:
        detected = detect_encoding(file_path)
        if detected:
            encodings.insert(0, detected)
    except:
        pass
    
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def main():
    """主函数"""
    input_file = Path(r"C:\Users\Administrator\Downloads\sk.md")
    output_file = Path(r"C:\Users\Administrator\Downloads\nav.html")
    
    if not input_file.exists():
        print(f"错误：找不到文件 {input_file}")
        return
    
    print(f"正在读取文件: {input_file}")
    content = read_file_with_fallback(input_file)
    
    print("正在解析书签文件...")
    bookmarks = parse_markdown_bookmarks(content)
    print(f"解析完成，共找到 {len(bookmarks)} 个书签")
    
    if not bookmarks:
        print("警告：未找到任何书签")
        return
    
    categories = set(bm['category'] for bm in bookmarks)
    print(f"共 {len(categories)} 个分类")
    
    print("正在生成BMM风格HTML页面...")
    html_content = generate_html(bookmarks, title="我的导航页")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ 成功生成导航页面: {output_file}")

if __name__ == "__main__":
    main()
