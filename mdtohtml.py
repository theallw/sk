import re
import html
from pathlib import Path
from typing import List, Dict

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

def get_favicon_url(url: str) -> str:
    """获取网站favicon URL"""
    try:
        if '://' in url:
            domain = url.split('/')[2]
        else:
            domain = url.split('/')[0]
        domain = domain.replace('www.', '')
        return f"https://favicon.im/{domain}"
    except:
        return ""

def generate_html(bookmarks: List[Dict], title: str = "我的导航页") -> str:
    """生成苹果风格导航HTML页面"""
    
    categories = {}
    for bm in bookmarks:
        if bm['category'] not in categories:
            categories[bm['category']] = []
        categories[bm['category']].append(bm)
    
    # 生成分类区域（苹果风格2列布局）
    category_list = list(categories.items())
    
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
            <div class="category-section" id="{html.escape(cat_name)}">
                <h2 class="category-title">{html.escape(cat_name)}</h2>
                <div class="bookmarks-grid">
                    {''.join(links_html)}
                </div>
            </div>
        ''')
    
    # 生成分类导航
    nav_items = '\n'.join([
        f'<a href="#{html.escape(cat_name)}" class="nav-item">{html.escape(cat_name)}</a>'
        for cat_name, _ in category_list[:12]
    ])
    
    # 苹果风格HTML模板
    html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>{html.escape(title)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", 
                         "SF Pro Text", "SF Pro Display", "PingFang SC", "Microsoft YaHei", 
                         sans-serif;
            background-color: #f5f5f7;
            color: #1d1c1f;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}

        /* 容器 */
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
        }}

        /* 头部 - 苹果风格 */
        .header {{
            text-align: center;
            padding: 80px 20px 60px;
            background: linear-gradient(135deg, #f5f5f7 0%, #ffffff 100%);
            border-bottom: 1px solid rgba(0,0,0,0.05);
        }}

        .header h1 {{
            font-size: 48px;
            font-weight: 600;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, #1d1c1f 0%, #3a3a3e 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 12px;
        }}

        .header p {{
            font-size: 18px;
            color: #86868b;
            font-weight: 400;
        }}

        /* 导航栏 - 毛玻璃效果 */
        .nav-bar {{
            position: sticky;
            top: 0;
            z-index: 100;
            background: rgba(255, 255, 255, 0.72);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-bottom: 1px solid rgba(0, 0, 0, 0.08);
            padding: 12px 0;
        }}

        .nav-links {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
        }}

        .nav-item {{
            padding: 8px 20px;
            font-size: 14px;
            font-weight: 500;
            color: #1d1c1f;
            text-decoration: none;
            border-radius: 30px;
            transition: all 0.2s ease;
            background: rgba(0,0,0,0.02);
        }}

        .nav-item:hover {{
            background: rgba(0,0,0,0.08);
            color: #007aff;
        }}

        /* 主内容 */
        .main {{
            padding: 40px 0 60px;
        }}

        /* 分类区域 */
        .category-section {{
            margin-bottom: 48px;
        }}

        .category-title {{
            font-size: 28px;
            font-weight: 600;
            letter-spacing: -0.01em;
            color: #1d1c1f;
            margin-bottom: 20px;
            padding-left: 4px;
            position: relative;
        }}

        .category-title::before {{
            content: '';
            position: absolute;
            left: 0;
            bottom: -8px;
            width: 40px;
            height: 3px;
            background: #007aff;
            border-radius: 2px;
        }}

        /* 书签网格 - 苹果风格卡片 */
        .bookmarks-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
        }}

        .bookmark-link {{
            text-decoration: none;
        }}

        .bookmark-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 18px;
            background: #ffffff;
            border-radius: 14px;
            transition: all 0.25s cubic-bezier(0.2, 0.9, 0.4, 1.1);
            border: 1px solid #e9e9ef;
            cursor: pointer;
        }}

        .bookmark-item:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
            border-color: transparent;
            background: #ffffff;
        }}

        .bookmark-favicon {{
            width: 20px;
            height: 20px;
            flex-shrink: 0;
            border-radius: 4px;
        }}

        .bookmark-title {{
            font-size: 15px;
            font-weight: 500;
            color: #1d1c1f;
            line-height: 1.4;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex: 1;
        }}

        .bookmark-item:hover .bookmark-title {{
            color: #007aff;
        }}

        /* 页脚 */
        .footer {{
            text-align: center;
            padding: 40px 20px;
            border-top: 1px solid #e9e9ef;
            color: #86868b;
            font-size: 13px;
        }}

        /* 返回顶部按钮 - 苹果风格 */
        .back-to-top {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            width: 44px;
            height: 44px;
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            opacity: 0;
            transition: opacity 0.3s ease, transform 0.2s ease;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(0, 0, 0, 0.05);
            cursor: pointer;
            z-index: 99;
        }}

        .back-to-top.show {{
            opacity: 1;
        }}

        .back-to-top:hover {{
            transform: scale(1.05);
            background: rgba(255, 255, 255, 1);
        }}

        .back-to-top svg {{
            width: 20px;
            height: 20px;
            stroke: #1d1c1f;
            stroke-width: 2;
        }}

        /* 搜索框 */
        .search-wrapper {{
            max-width: 400px;
            margin: 0 auto 32px;
        }}

        .search-input {{
            width: 100%;
            padding: 14px 20px;
            font-size: 16px;
            font-family: inherit;
            border: 1px solid #e9e9ef;
            border-radius: 12px;
            background: #ffffff;
            transition: all 0.2s ease;
            outline: none;
        }}

        .search-input:focus {{
            border-color: #007aff;
            box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.1);
        }}

        .search-input::placeholder {{
            color: #c6c6c8;
        }}

        /* 搜索结果高亮 */
        .bookmark-link.hidden {{
            display: none;
        }}

        /* 空状态 */
        .no-results {{
            text-align: center;
            padding: 60px 20px;
            color: #86868b;
        }}

        /* 响应式 */
        @media (max-width: 768px) {{
            .container {{
                padding: 0 16px;
            }}
            
            .header {{
                padding: 60px 16px 40px;
            }}
            
            .header h1 {{
                font-size: 32px;
            }}
            
            .header p {{
                font-size: 16px;
            }}
            
            .category-title {{
                font-size: 24px;
            }}
            
            .bookmarks-grid {{
                gap: 10px;
            }}
            
            .bookmark-item {{
                padding: 12px 16px;
            }}
            
            .nav-item {{
                padding: 6px 14px;
                font-size: 13px;
            }}
        }}

        @media (max-width: 640px) {{
            .bookmarks-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* 滚动条 */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: #f5f5f7;
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: #c6c6c8;
            border-radius: 4px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: #86868b;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📖 {html.escape(title)}</h1>
        <p>{len(bookmarks)} 个精选网站 · 快速访问</p>
    </div>

    <div class="nav-bar">
        <div class="nav-links">
            {nav_items}
        </div>
    </div>

    <div class="container main">
        <div class="search-wrapper">
            <input type="text" class="search-input" id="searchInput" placeholder="搜索书签... ⌘K" autocomplete="off">
        </div>

        <div id="bookmarksContainer">
            {''.join(sections_html)}
        </div>
    </div>

    <div class="footer">
        <p>© 2026 {html.escape(title)} · 个性化网址导航</p>
    </div>

    <div class="back-to-top" id="backToTop">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="18 15 12 9 6 15"></polyline>
        </svg>
    </div>

    <script>
        // 搜索功能
        const searchInput = document.getElementById('searchInput');
        const categories = document.querySelectorAll('.category-section');
        
        function searchBookmarks() {{
            const keyword = searchInput.value.toLowerCase().trim();
            let totalMatches = 0;
            
            categories.forEach(category => {{
                const bookmarks = category.querySelectorAll('.bookmark-link');
                let categoryMatches = 0;
                
                bookmarks.forEach(bookmark => {{
                    const title = bookmark.querySelector('.bookmark-title').textContent.toLowerCase();
                    if (keyword === '' || title.includes(keyword)) {{
                        bookmark.classList.remove('hidden');
                        categoryMatches++;
                    }} else {{
                        bookmark.classList.add('hidden');
                    }}
                }});
                
                totalMatches += categoryMatches;
                
                // 如果分类下有匹配结果则显示分类，否则隐藏
                if (keyword === '' || categoryMatches > 0) {{
                    category.style.display = 'block';
                }} else {{
                    category.style.display = 'none';
                }}
            }});
            
            // 显示无结果提示
            let noResultsDiv = document.getElementById('noResults');
            if (totalMatches === 0 && keyword !== '') {{
                if (!noResultsDiv) {{
                    noResultsDiv = document.createElement('div');
                    noResultsDiv.id = 'noResults';
                    noResultsDiv.className = 'no-results';
                    noResultsDiv.innerHTML = '<p>🔍 没有找到相关书签</p><p style="font-size: 14px;">试试其他关键词</p>';
                    document.getElementById('bookmarksContainer').appendChild(noResultsDiv);
                }}
            }} else if (noResultsDiv) {{
                noResultsDiv.remove();
            }}
        }}
        
        searchInput.addEventListener('input', searchBookmarks);
        
        // 快捷键 Ctrl+K / Cmd+K 聚焦搜索框
        document.addEventListener('keydown', (e) => {{
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {{
                e.preventDefault();
                searchInput.focus();
            }}
            // ESC 清空搜索
            if (e.key === 'Escape') {{
                searchInput.value = '';
                searchBookmarks();
                searchInput.blur();
            }}
        }});
        
        // 返回顶部按钮
        const backToTop = document.getElementById('backToTop');
        
        window.addEventListener('scroll', () => {{
            if (window.scrollY > 300) {{
                backToTop.classList.add('show');
            }} else {{
                backToTop.classList.remove('show');
            }}
        }});
        
        backToTop.addEventListener('click', () => {{
            window.scrollTo({{
                top: 0,
                behavior: 'smooth'
            }});
        }});
        
        // 平滑滚动到分类
        document.querySelectorAll('.nav-item').forEach(link => {{
            link.addEventListener('click', (e) => {{
                e.preventDefault();
                const targetId = link.getAttribute('href').substring(1);
                const targetElement = document.getElementById(targetId);
                if (targetElement) {{
                    const navBarHeight = document.querySelector('.nav-bar').offsetHeight;
                    const targetPosition = targetElement.getBoundingClientRect().top + window.scrollY - navBarHeight - 20;
                    window.scrollTo({{
                        top: targetPosition,
                        behavior: 'smooth'
                    }});
                }}
            }});
        }});
        
        // 懒加载favicon（可选）
        const observerOptions = {{
            rootMargin: '50px'
        }};
        
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
    </script>
</body>
</html>'''
    
    return html_template

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
