/**
 * 使用 Mermaid + Puppeteer 渲染 SVG 思维导图
 * 输入：JSON字符串 { topic: "主题", content: "markdown内容" }
 * 输出：SVG 文件路径
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const EXECUTABLE_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function renderMindmap(topic, markdownContent) {
  // 将 Markdown 转换为 Mermaid mindmap 语法
  const mermaidCode = markdownToMermaid(topic, markdownContent);

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: EXECUTABLE_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  const html = `<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body { margin: 0; background: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
    #container { text-align: center; }
  </style>
</head>
<body>
  <div id="container"></div>
  <script>
    mermaid.initialize({ startOnLoad: false, theme: 'default', mindmap: { padding: 16 } });
    async function render() {
      try {
        const { svg } = await mermaid.render('mindmap-svg', \`${mermaidCode.replace(/`/g, '\\`')}\`);
        document.querySelector('#container').innerHTML = svg;
        console.log('SVG_RENDERED:' + svg.length);
      } catch(e) {
        console.error('ERROR:' + e.message);
        document.querySelector('#container').innerHTML = '<p style="color:red">Error: ' + e.message + '</p>';
      }
    }
    render();
  </script>
</body>
</html>`;

  await page.setContent(html, { waitUntil: 'networkidle0', timeout: 30000 });

  // Wait for mermaid to render
  await new Promise(r => setTimeout(r, 3000));

  const svgElement = await page.$('#container svg');
  let svgContent;

  if (svgElement) {
    svgContent = await page.evaluate(el => el.outerHTML, svgElement);
  } else {
    // Fallback: get any SVG
    svgContent = await page.evaluate(() => {
      const svg = document.querySelector('svg');
      return svg ? svg.outerHTML : '';
    });
  }

  await browser.close();

  if (!svgContent || svgContent.length < 100) {
    throw new Error('Failed to render SVG');
  }

  return svgContent;
}

function markdownToMermaid(topic, content) {
  const lines = content.split('\n');
  const root = { children: [] };
  const stack = [root];

  for (const line of lines) {
    const stripped = line.trim();
    if (!stripped || stripped.startsWith('---') || stripped.startsWith('title:') ||
        stripped.startsWith('created:') || stripped.startsWith('type:') || stripped.startsWith('>')) {
      continue;
    }

    let depth = 0;
    let text = '';

    if (stripped.startsWith('# ') && !stripped.startsWith('##')) {
      continue; // Skip main title
    } else if (stripped.startsWith('## ')) {
      depth = 1;
      text = stripped.slice(3).trim();
    } else if (stripped.startsWith('### ')) {
      depth = 2;
      text = stripped.slice(4).trim();
    } else if (stripped.startsWith('#### ')) {
      depth = 3;
      text = stripped.slice(5).trim();
    } else if (stripped.startsWith('- ')) {
      // Calculate indent-based depth
      const indent = line.length - line.trimLeft().length;
      depth = 4 + Math.floor(indent / 2);
      text = stripped.slice(2).trim();
      // Remove markdown formatting
      text = text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/`(.*?)`/g, '$1');
    } else {
      continue;
    }

    if (!text) continue;

    // Clean text - remove emojis and variation selectors at start
    // This handles composed emojis like 📌 (emoji + variation selector)
    text = text.replace(/^[\u{1F300}-\u{1F9FF}\u{FE0F}\u{200D}]+/gu, '').trim();

    // Also skip lines that look like they're from a mermaid block or other non-content
    if (text.includes('Mermaid') || text.includes('```')) {
      continue;
    }

    // Pop stack to appropriate depth
    while (stack.length > 1 && stack[stack.length - 1].depth >= depth) {
      stack.pop();
    }

    const node = { content: text, children: [], depth };
    stack[stack.length - 1].children.push(node);
    stack.push(node);
  }

  // Handle multiple root children - find the actual root node
  const actualRoot = root.children.length > 0 ? root : { content: topic, children: [] };

  // Build mermaid with all root children
  let mermaidParts = [];
  for (const child of actualRoot.children) {
    mermaidParts.push(buildMermaidNode(child));
  }

  return 'mindmap\n' + mermaidParts.join('\n');
}

function buildMermaidNode(node) {
  if (!node) return '';

  // Root node uses ((content))
  const prefix = node.depth === 0 ? '((' : '  ';
  const suffix = node.depth === 0 ? '))' : '';
  const content = node.content;

  if (!node.children || node.children.length === 0) {
    return prefix + content + suffix;
  }

  const childParts = node.children.map(child => buildMermaidNode(child)).join('\n');
  return prefix + content + suffix + '\n' + childParts;
}

// Main execution
async function main() {
  try {
    // Read input from stdin
    let input = '';
    process.stdin.setEncoding('utf8');

    for await (const chunk of process.stdin) {
      input += chunk;
    }

    const { topic, content, outputPath } = JSON.parse(input);

    if (!topic || !content) {
      throw new Error('Missing topic or content');
    }

    const svg = await renderMindmap(topic, content);

    // Save SVG to file
    fs.writeFileSync(outputPath, svg, 'utf8');

    console.log('SUCCESS:' + outputPath);
  } catch (error) {
    console.error('FAILED:' + error.message);
    process.exit(1);
  }
}

main();
