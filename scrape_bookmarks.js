/**
 * 爬取 https://shouku123.com/keep/ 的所有书签
 * 在浏览器控制台中运行此脚本
 */

function extractBookmarks() {
  const bookmarks = {
    groups: {}
  };

  // 获取所有分组
  const groupItems = document.querySelectorAll('.urlGroupItem');
  
  groupItems.forEach((group) => {
    const groupName = group.querySelector('.panel-heading .myfont').textContent.trim();
    const urls = [];

    // 获取该分组下的所有链接
    const listItems = group.querySelectorAll('.list-group-item');
    listItems.forEach((item) => {
      const link = item.querySelector('a[target="_blank"]');
      if (link) {
        urls.push({
          name: link.textContent.trim(),
          url: link.getAttribute('href'),
          title: link.getAttribute('title')
        });
      }
    });

    bookmarks.groups[groupName] = urls;
  });

  return bookmarks;
}

// 执行并打印结果
const result = extractBookmarks();
console.log(JSON.stringify(result, null, 2));

// 生成 Markdown 格式
function generateMarkdown(bookmarks) {
  let markdown = '';
  
  Object.entries(bookmarks.groups).forEach(([groupName, urls]) => {
    markdown += `\n## ${groupName}\n\n`;
    urls.forEach((item) => {
      markdown += `- [${item.name}](${item.url})\n`;
    });
  });

  return markdown;
}

const markdown = generateMarkdown(result);
console.log(markdown);

// 复制到剪贴板
navigator.clipboard.writeText(markdown).then(() => {
  console.log('Markdown 已复制到剪贴板！');
});
