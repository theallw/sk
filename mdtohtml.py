import re
import html
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict, Optional

def get_app_icon(term: str) -> Optional[str]:
    """
    从 Apple App Store 获取应用图标
    返回图标 URL，如果获取失败则返回 None
    """
    try:
        url = "https://apps.apple.com/cn/iphone/search"
        params = {'term': term.strip()}
        headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            'Accept-Language': "zh-CN,zh;q=0.9",
            'Accept-Encoding': "gzip, deflate, br",
            'sec-ch-ua': '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
            'sec-ch-ua-mobile': "?0",
            'sec-ch-ua-platform': '"Windows"',
            'upgrade-insecure-requests': "1",
            'sec-fetch-site': "same-origin",
            'sec-fetch-mode': "navigate",
            'sec-fetch-user': "?1",
            'sec-fetch-dest': "document",
            'referer': "https://apps.apple.com/",
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 使用 BeautifulSoup 解析 HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找第一个应用图标
        # Apple Store 使用 webfeatures 组件，图标通常以 webp 格式出现
        # 方法1: 查找带有 webp 图标的 img 标签
        icons = soup.find_all('img', src=re.compile(r'\.webp$'))
        
        for img in icons:
            src = img.get('src')
            if src and 'Purple' in src and '48x48' in src:
                # 确保是完整的 URL
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = 'https://is1-ssl.mzstatic.com' + src
                return src
        
        # 方法2: 查找 picture 标签中的 webp 源
        picture_tags = soup.find_all('picture')
        for picture in picture_tags:
            source = picture.find('source', {'type': 'image/webp'})
            if source:
                srcset = source.get('srcset', '')
                if srcset:
                    # 取第一个 URL
                    first_url = srcset.split(',')[0].strip().split()[0]
                    if first_url.startswith('//'):
                        first_url = 'https:' + first_url
                    return first_url
        
        # 方法3: 查找任意包含 icon 的 img
        icons = soup.find_all('img', src=re.compile(r'(icon|logo|app)'))
        for img in icons:
            src = img.get('src')
            if src and ('is1-ssl.mzstatic.com' in src or 'is2-ssl.mzstatic.com' in src):
                if src.startswith('//'):
                    src = 'https:' + src
                return src
                
    except Exception as e:
        print(f"获取 {term} 图标失败: {e}")
    
    return None

def get_favicon_url(url: str) -> str:
    """获取网站 favicon URL（保留原方法作为备用）"""
    try:
        if '://' in url:
            domain = url.split('/')[2]
        else:
            domain = url.split('/')[0]
        domain = domain.replace('www.', '')
        return f"https://favicon.im/{domain}"
    except:
        return ""

def enrich_search_engines_with_icons(search_engines: List[Dict]) -> List[Dict]:
    """
    为搜索引擎列表添加从 App Store 获取的图标
    如果获取失败，使用 emoji 作为备用
    """
    enriched = []
    
    for engine in search_engines:
        name = engine['name']
        print(f"正在获取 {name} 的图标...")
        
        # 尝试从 App Store 获取图标
        icon_url = get_app_icon(name)
        
        if icon_url:
            print(f"  ✅ 获取到 {name} 图标: {icon_url[:80]}...")
            enriched.append({
                'name': name,
                'url': engine['url'],
                'icon': icon_url  # 使用真实的图片 URL
            })
        else:
            print(f"  ⚠️ 使用备用 emoji 图标: {engine['icon']}")
            # 如果获取失败，使用原有的 emoji 或生成占位
            if engine['icon']:
                enriched.append(engine)
            else:
                # 如果原本没有 emoji，使用首字母作为占位
                enriched.append({
                    'name': name,
                    'url': engine['url'],
                    'icon': f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23999' stroke-width='2'%3E%3Crect x='3' y='3' width='18' height='18' rx='4'/%3E%3Ctext x='12' y='16' text-anchor='middle' font-size='12' fill='%23999'%3E{name[0].upper()}%3C/text%3E%3C/svg%3E"
                })
    
    return enriched

def generate_html(bookmarks: List[Dict], title: str = "我的导航页") -> str:
    """生成苹果风格导航HTML页面"""
    
    categories = {}
    for bm in bookmarks:
        if bm['category'] not in categories:
            categories[bm['category']] = []
        categories[bm['category']].append(bm)
    
    # 搜索引擎配置 - 先定义基础配置
    base_search_engines = [
        {'name': 'Google', 'url': 'https://www.google.com/search?q=', 'icon': '🌐'},
        {'name': 'Bing', 'url': 'https://cn.bing.com/search?q=', 'icon': '🔍'},
        {'name': 'Baidu', 'url': 'https://kaifa.baidu.com/searchPage?wd=', 'icon': ''},
        {'name': '搜狗', 'url': 'https://www.sogou.com/web?query=', 'icon': ''},
        {'name': 'Github', 'url': 'https://github.com/search?q=', 'icon': ''},
        {'name': 'Bilibili', 'url': 'https://search.bilibili.com/all?keyword=', 'icon': ''},
        {'name': '360', 'url': 'https://www.so.com/s?q=', 'icon': ''},
        {'name': '神马', 'url': 'https://m.sm.cn/s?q=', 'icon': ''},
        {'name': '安全内参', 'url': 'https://www.secrss.com/search?keywords=', 'icon': ''},
    ]
    
    # 从 App Store 获取真实图标
    print("\n=== 开始获取搜索引擎图标 ===")
    search_engines = enrich_search_engines_with_icons(base_search_engines)
    print("=== 图标获取完成 ===\n")
    
    # 生成分类区域
    category_list = list(categories.items())
    
    # 生成左侧分类导航
    sidebar_items = []
    for idx, (cat_name, cat_bookmarks) in enumerate(category_list):
        count = len(cat_bookmarks)
        sidebar_items.append(f'''
            <a href="#{html.escape(cat_name)}" class="sidebar-item" data-target="{html.escape(cat_name)}">
                <span class="sidebar-name">{html.escape(cat_name)}</span>
                <span class="sidebar-badge">{count}</span>
            </a>
        ''')
    
    # 生成右侧内容
    sections_html = []
    for cat_name, cat_bookmarks in category_list:
        links_html = []
        for bm in cat_bookmarks:
            favicon = get_favicon_url(bm['url'])
            links_html.append(f'''
                <a href="{html.escape(bm['url'])}" class="bookmark-link" target="_blank" rel="noopener noreferrer">
                    <div class="bookmark-item">
                        <img class="bookmark-favicon" src="{favicon}" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'16\' height=\'16\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%23999\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'%3E%3Cpath d=\'M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z\'%3E%3C/path%3E%3Cpolyline points=\'22,6 12,13 2,6\'%3E%3C/polyline%3E%3C/svg%3E'">
                        <span class="bookmark-title">{html.escape(bm['title'])}</span>
                    </div>
                </a>
            ''')
        
        sections_html.append(f'''
            <section class="content-section" id="{html.escape(cat_name)}">
                <h2 class="section-title">{html.escape(cat_name)}</h2>
                <div class="bookmarks-grid">
                    {''.join(links_html)}
                </div>
            </section>
        ''')
    
    # 生成搜索引擎按钮 - 使用图片图标
    search_buttons = []
    for engine in search_engines:
        icon = engine['icon']
        # 如果是 URL 图片，使用 img 标签
        if icon.startswith('http') or icon.startswith('data:'):
            icon_html = f'<img src="{html.escape(icon)}" alt="{html.escape(engine["name"])}" style="width:20px;height:20px;border-radius:4px;vertical-align:middle;">'
        else:
            icon_html = html.escape(icon)
        
        search_buttons.append(f'''
            <button class="search-engine-btn" data-engine="{html.escape(engine['url'])}" title="{html.escape(engine['name'])}">
                {icon_html}
                <span style="margin-left:4px;">{html.escape(engine['name'])}</span>
            </button>
        ''')
    
    search_buttons_html = ''.join(search_buttons)
    
    # ... 后续 HTML 模板代码保持不变 ...
    # (使用之前的 HTML 模板，但需要更新 search_engines 相关部分)
    
    html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>{html.escape(title)}</title>
    <style>
        /* ... 所有样式保持不变 ... */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --sidebar-width: 260px;
            --header-height: 60px;
            --radius: 14px;
            --bg-primary: #f5f5f7;
            --bg-secondary: #ffffff;
            --bg-sidebar: #f8f8fa;
            --text-primary: #1d1c1f;
            --text-secondary: #6e6e73;
            --text-muted: #8e8e93;
            --border-color: #e5e5ea;
            --accent-color: #007aff;
            --accent-hover: #0066d9;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.04);
            --shadow-md: 0 4px 16px rgba(0,0,0,0.06);
            --shadow-lg: 0 8px 30px rgba(0,0,0,0.08);
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", 
                         "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            display: flex;
            min-height: 100vh;
        }}

        .sidebar {{
            position: fixed;
            top: 0;
            left: 0;
            width: var(--sidebar-width);
            height: 100vh;
            background: var(--bg-sidebar);
            border-right: 1px solid var(--border-color);
            padding: 20px 0 30px;
            overflow-y: auto;
            z-index: 100;
            display: flex;
            flex-direction: column;
        }}

        .sidebar-header {{
            padding: 0 20px 16px;
            border-bottom: 1px solid var(--border-color);
            flex-shrink: 0;
        }}

        .sidebar-header h1 {{
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.3px;
            background: linear-gradient(135deg, #1d1c1f 0%, #3a3a3e 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .sidebar-header p {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 2px;
            font-weight: 400;
        }}

        .sidebar-search {{
            padding: 12px 16px;
            flex-shrink: 0;
        }}

        .sidebar-search input {{
            width: 100%;
            padding: 10px 14px;
            font-size: 14px;
            font-family: inherit;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            background: var(--bg-secondary);
            transition: all 0.2s ease;
            outline: none;
            color: var(--text-primary);
        }}

        .sidebar-search input:focus {{
            border-color: var(--accent-color);
            box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.08);
        }}

        .sidebar-search input::placeholder {{
            color: var(--text-muted);
        }}

        .sidebar-nav {{
            flex: 1;
            overflow-y: auto;
            padding: 8px 12px;
        }}

        .sidebar-item {{
            display: flex;
            align-items: center;
            padding: 10px 14px;
            border-radius: 10px;
            text-decoration: none;
            color: var(--text-primary);
            transition: all 0.15s ease;
            cursor: pointer;
            gap: 10px;
            font-size: 14px;
            font-weight: 450;
            position: relative;
        }}

        .sidebar-item:hover {{
            background: rgba(0, 0, 0, 0.04);
        }}

        .sidebar-item.active {{
            background: rgba(0, 122, 255, 0.08);
            color: var(--accent-color);
        }}

        .sidebar-item.active .sidebar-icon {{
            color: var(--accent-color);
        }}

        .sidebar-icon {{
            font-size: 16px;
            width: 24px;
            text-align: center;
            flex-shrink: 0;
            color: var(--text-muted);
        }}

        .sidebar-name {{
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .sidebar-badge {{
            font-size: 11px;
            font-weight: 500;
            color: var(--text-muted);
            background: rgba(0,0,0,0.05);
            padding: 2px 10px;
            border-radius: 12px;
            flex-shrink: 0;
        }}

        .sidebar-item.active .sidebar-badge {{
            background: rgba(0, 122, 255, 0.12);
            color: var(--accent-color);
        }}

        .sidebar-footer {{
            padding: 12px 12px 8px;
            border-top: 1px solid var(--border-color);
            flex-shrink: 0;
        }}

        .main-content {{
            margin-left: var(--sidebar-width);
            flex: 1;
            padding: 30px 40px 60px;
            min-height: 100vh;
        }}

        .content-header {{
            padding: 8px 0 24px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 32px;
        }}

        .content-header h2 {{
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.3px;
            color: var(--text-primary);
        }}

        .content-header p {{
            font-size: 15px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}

        .search-engines-wrapper {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }}

        .search-engines-label {{
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            margin-right: 4px;
        }}

        .search-engine-btn {{
            display: inline-flex;
            align-items: center;
            padding: 6px 14px;
            font-size: 12px;
            font-family: inherit;
            font-weight: 500;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-secondary);
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s ease;
            gap: 4px;
        }}

        .search-engine-btn:hover {{
            background: rgba(0, 122, 255, 0.06);
            border-color: var(--accent-color);
            color: var(--accent-color);
        }}

        .search-engine-btn.active {{
            background: var(--accent-color);
            border-color: var(--accent-color);
            color: #fff;
        }}

        .search-engine-btn img {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
            vertical-align: middle;
        }}

        .main-search-wrapper {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }}

        .main-search-wrapper .search-input {{
            flex: 1;
            min-width: 200px;
            padding: 12px 18px;
            font-size: 15px;
            font-family: inherit;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            background: var(--bg-secondary);
            transition: all 0.2s ease;
            outline: none;
            color: var(--text-primary);
        }}

        .main-search-wrapper .search-input:focus {{
            border-color: var(--accent-color);
            box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.08);
        }}

        .main-search-wrapper .search-input::placeholder {{
            color: var(--text-muted);
        }}

        .search-shortcut {{
            font-size: 12px;
            color: var(--text-muted);
            background: rgba(0,0,0,0.04);
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 500;
            letter-spacing: 0.3px;
            white-space: nowrap;
        }}

        .content-section {{
            margin-bottom: 40px;
            scroll-margin-top: 20px;
        }}

        .content-section:last-child {{
            margin-bottom: 0;
        }}

        .section-title {{
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--accent-color);
            display: inline-block;
        }}

        .bookmarks-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 10px;
        }}

        .bookmark-link {{
            text-decoration: none;
            display: block;
        }}

        .bookmark-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: var(--bg-secondary);
            border-radius: var(--radius);
            transition: all 0.2s cubic-bezier(0.2, 0.9, 0.4, 1);
            border: 1px solid var(--border-color);
            cursor: pointer;
        }}

        .bookmark-item:hover {{
            transform: translateY(-1px);
            box-shadow: var(--shadow-md);
            border-color: transparent;
        }}

        .bookmark-favicon {{
            width: 20px;
            height: 20px;
            flex-shrink: 0;
            border-radius: 4px;
        }}

        .bookmark-title {{
            font-size: 14px;
            font-weight: 450;
            color: var(--text-primary);
            line-height: 1.3;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex: 1;
        }}

        .bookmark-item:hover .bookmark-title {{
            color: var(--accent-color);
        }}

        .bookmark-link.hidden {{
            display: none;
        }}

        .content-section.hidden {{
            display: none;
        }}

        .no-results {{
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }}

        .no-results p:first-child {{
            font-size: 18px;
            font-weight: 500;
        }}

        .back-to-top {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            width: 44px;
            height: 44px;
            background: rgba(255, 255, 255, 0.92);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            opacity: 0;
            transition: opacity 0.3s ease, transform 0.2s ease;
            box-shadow: var(--shadow-md);
            border: 1px solid rgba(0,0,0,0.04);
            cursor: pointer;
            z-index: 99;
        }}

        .back-to-top.show {{
            opacity: 1;
        }}

        .back-to-top:hover {{
            transform: scale(1.05);
        }}

        .back-to-top svg {{
            width: 20px;
            height: 20px;
            stroke: var(--text-primary);
            stroke-width: 2;
        }}

        /* 滚动条美化 */
        .sidebar::-webkit-scrollbar,
        .sidebar-nav::-webkit-scrollbar {{
            width: 4px;
        }}

        .sidebar::-webkit-scrollbar-track,
        .sidebar-nav::-webkit-scrollbar-track {{
            background: transparent;
        }}

        .sidebar::-webkit-scrollbar-thumb,
        .sidebar-nav::-webkit-scrollbar-thumb {{
            background: var(--border-color);
            border-radius: 4px;
        }}

        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: var(--bg-primary);
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: #c6c6c8;
            border-radius: 4px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: #86868b;
        }}

        /* 响应式 */
        @media (max-width: 1024px) {{
            :root {{
                --sidebar-width: 220px;
            }}
            .main-content {{
                padding: 20px 24px 40px;
            }}
        }}

        @media (max-width: 820px) {{
            .sidebar {{
                transform: translateX(-100%);
                transition: transform 0.3s cubic-bezier(0.2, 0.9, 0.4, 1);
                width: 280px;
            }}
            .sidebar.open {{
                transform: translateX(0);
            }}
            .main-content {{
                margin-left: 0;
                padding: 16px 20px 40px;
            }}
            .menu-toggle {{
                display: flex !important;
            }}
        }}

        @media (max-width: 640px) {{
            .bookmarks-grid {{
                grid-template-columns: 1fr 1fr;
            }}
            .main-search-wrapper {{
                flex-direction: column;
                align-items: stretch;
            }}
            .search-shortcut {{
                align-self: flex-end;
            }}
            .search-engines-wrapper {{
                gap: 6px;
            }}
            .search-engine-btn {{
                padding: 4px 10px;
                font-size: 11px;
            }}
        }}

        @media (max-width: 480px) {{
            .bookmarks-grid {{
                grid-template-columns: 1fr;
            }}
            .main-content {{
                padding: 12px 14px 30px;
            }}
            .search-engines-wrapper {{
                justify-content: center;
            }}
        }}

        /* 移动端菜单按钮 */
        .menu-toggle {{
            display: none;
            position: fixed;
            top: 12px;
            left: 12px;
            z-index: 200;
            width: 44px;
            height: 44px;
            background: rgba(255,255,255,0.92);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 50%;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-sm);
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 20px;
        }}

        .menu-toggle:hover {{
            background: rgba(255,255,255,1);
        }}

        .sidebar-overlay {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.2);
            z-index: 99;
        }}

        .sidebar-overlay.show {{
            display: block;
        }}

        @media (max-width: 820px) {{
            .sidebar-overlay.show {{
                display: block;
            }}
        }}
    </style>
</head>
<body>
    <button class="menu-toggle" id="menuToggle" aria-label="切换侧边栏">☰</button>
    <div class="sidebar-overlay" id="sidebarOverlay"></div>

    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h1>📖 {html.escape(title)}</h1>
            <p>{len(bookmarks)} 个网站</p>
        </div>

        <div class="sidebar-search">
            <input type="text" id="sidebarSearch" placeholder="搜索分类..." autocomplete="off">
        </div>

        <nav class="sidebar-nav">
            {''.join(sidebar_items)}
        </nav>

        <div class="sidebar-footer">
        </div>
    </aside>

    <main class="main-content" id="mainContent">
        <div class="search-engines-wrapper">
            <span class="search-engines-label">🔎 搜索：</span>
            {search_buttons_html}
        </div>

        <div class="main-search-wrapper">
            <input type="text" class="search-input" id="searchInput" placeholder="搜索书签..." autocomplete="off">
            <span class="search-shortcut">⌘K</span>
        </div>

        <div id="bookmarksContainer">
            {''.join(sections_html)}
        </div>
    </main>

    <div class="back-to-top" id="backToTop">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="18 15 12 9 6 15"></polyline>
        </svg>
    </div>

    <script>
        (function() {{
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebarOverlay');
            const menuToggle = document.getElementById('menuToggle');

            function toggleSidebar() {{
                sidebar.classList.toggle('open');
                overlay.classList.toggle('show');
            }}

            function closeSidebar() {{
                sidebar.classList.remove('open');
                overlay.classList.remove('show');
            }}

            if (menuToggle) {{
                menuToggle.addEventListener('click', toggleSidebar);
            }}
            if (overlay) {{
                overlay.addEventListener('click', closeSidebar);
            }}

            document.querySelectorAll('.sidebar-item').forEach(item => {{
                item.addEventListener('click', () => {{
                    if (window.innerWidth <= 820) {{
                        closeSidebar();
                    }}
                }});
            }});

            const sidebarSearch = document.getElementById('sidebarSearch');
            const sidebarItems = document.querySelectorAll('.sidebar-item');

            if (sidebarSearch) {{
                sidebarSearch.addEventListener('input', function() {{
                    const keyword = this.value.toLowerCase().trim();
                    sidebarItems.forEach(item => {{
                        const name = item.querySelector('.sidebar-name').textContent.toLowerCase();
                        if (keyword === '' || name.includes(keyword)) {{
                            item.style.display = 'flex';
                        }} else {{
                            item.style.display = 'none';
                        }}
                    }});
                }});
            }}

            const searchInput = document.getElementById('searchInput');
            const sections = document.querySelectorAll('.content-section');

            function searchBookmarks() {{
                const keyword = searchInput.value.toLowerCase().trim();
                let totalMatches = 0;

                sections.forEach(section => {{
                    const bookmarks = section.querySelectorAll('.bookmark-link');
                    let sectionMatches = 0;

                    bookmarks.forEach(bookmark => {{
                        const title = bookmark.querySelector('.bookmark-title').textContent.toLowerCase();
                        if (keyword === '' || title.includes(keyword)) {{
                            bookmark.classList.remove('hidden');
                            sectionMatches++;
                        }} else {{
                            bookmark.classList.add('hidden');
                        }}
                    }});

                    totalMatches += sectionMatches;

                    if (keyword === '' || sectionMatches > 0) {{
                        section.classList.remove('hidden');
                    }} else {{
                        section.classList.add('hidden');
                    }}
                }});

                let noResultsDiv = document.getElementById('noResults');
                if (totalMatches === 0 && keyword !== '') {{
                    if (!noResultsDiv) {{
                        noResultsDiv = document.createElement('div');
                        noResultsDiv.id = 'noResults';
                        noResultsDiv.className = 'no-results';
                        noResultsDiv.innerHTML = '<p>🔍 没有找到相关书签</p><p style="font-size: 14px; color: var(--text-muted);">试试其他关键词</p>';
                        document.getElementById('bookmarksContainer').appendChild(noResultsDiv);
                    }}
                }} else if (noResultsDiv) {{
                    noResultsDiv.remove();
                }}
            }}

            if (searchInput) {{
                searchInput.addEventListener('input', searchBookmarks);
            }}

            document.addEventListener('keydown', (e) => {{
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
                        searchBookmarks();
                        searchInput.blur();
                    }}
                }}
            }});

            const engineBtns = document.querySelectorAll('.search-engine-btn');
            let currentEngine = 'https://cn.bing.com/search?q=';

            try {{
                const saved = localStorage.getItem('selectedEngine');
                if (saved) {{
                    currentEngine = saved;
                }}
            }} catch(e) {{}}

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
                        try {{
                            localStorage.setItem('selectedEngine', url);
                        }} catch(ex) {{}}
                        engineBtns.forEach(b => b.classList.remove('active'));
                        this.classList.add('active');

                        if (searchInput && searchInput.value.trim()) {{
                            const query = searchInput.value.trim();
                            window.open(currentEngine + encodeURIComponent(query), '_blank');
                        }}
                    }}
                }});
            }});

            if (searchInput) {{
                searchInput.addEventListener('keydown', (e) => {{
                    if (e.key === 'Enter') {{
                        const query = searchInput.value.trim();
                        if (query) {{
                            window.open(currentEngine + encodeURIComponent(query), '_blank');
                        }}
                    }}
                }});
            }}

            const navItems = document.querySelectorAll('.sidebar-item');

            function highlightNav() {{
                let currentId = '';
                const scrollY = window.scrollY + 100;
                sections.forEach(section => {{
                    const rect = section.getBoundingClientRect();
                    const top = rect.top + window.scrollY;
                    if (scrollY >= top) {{
                        currentId = section.id;
                    }}
                }});

                navItems.forEach(item => {{
                    const target = item.dataset.target;
                    item.classList.toggle('active', target === currentId);
                }});
            }}

            window.addEventListener('scroll', highlightNav);
            setTimeout(highlightNav, 100);

            const backToTop = document.getElementById('backToTop');

            window.addEventListener('scroll', () => {{
                if (window.scrollY > 300) {{
                    backToTop.classList.add('show');
                }} else {{
                    backToTop.classList.remove('show');
                }}
            }});

            if (backToTop) {{
                backToTop.addEventListener('click', () => {{
                    window.scrollTo({{ top: 0, behavior: 'smooth' }});
                }});
            }}

            navItems.forEach(item => {{
                item.addEventListener('click', (e) => {{
                    const targetId = item.dataset.target;
                    if (targetId) {{
                        const targetElement = document.getElementById(targetId);
                        if (targetElement) {{
                            e.preventDefault();
                            const offset = 20;
                            const targetPosition = targetElement.getBoundingClientRect().top + window.scrollY - offset;
                            window.scrollTo({{
                                top: targetPosition,
                                behavior: 'smooth'
                            }});
                        }}
                    }}
                }});
            }});

            if ('IntersectionObserver' in window) {{
                const observerOptions = {{ rootMargin: '100px' }};
                const imageObserver = new IntersectionObserver((entries) => {{
                    entries.forEach(entry => {{
                        if (entry.isIntersecting) {{
                            const img = entry.target;
                            img.src = img.dataset.src || img.src;
                            imageObserver.unobserve(img);
                        }}
                    }});
                }}, observerOptions);
                document.querySelectorAll('.bookmark-favicon').forEach(img => {{
                    imageObserver.observe(img);
                }});
            }}
        }})();
    </script>
</body>
</html>'''
    
    return html_template

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

def main():
    """主函数"""
    input_file = Path(r"C:\Users\Administrator\Downloads\sk.md")
    output_file = Path(r"C:\Users\Administrator\Downloads\nav.html")
    
    if not input_file.exists():
        print(f"错误：找不到文件 {input_file}")
        return
    
    print(f"正在读取文件: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("正在解析书签文件...")
    bookmarks = parse_markdown_bookmarks(content)
    print(f"解析完成，共找到 {len(bookmarks)} 个书签")
    
    if not bookmarks:
        print("警告：未找到任何书签")
        return
    
    categories = set(bm['category'] for bm in bookmarks)
    print(f"共 {len(categories)} 个分类")
    
    print("正在生成HTML页面...")
    html_content = generate_html(bookmarks, title="我的导航页")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ 成功生成导航页面: {output_file}")

if __name__ == "__main__":
    main()
