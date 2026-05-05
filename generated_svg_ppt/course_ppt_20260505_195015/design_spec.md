# Design Specification

## I. Project Information

- **Project name**: 微信小程序开发入门  
- **Canvas format**: PPT 16:9 (16:9), viewBox: `0 0 1280 720`  
- **Page count**: 8  
- **Design style**: Education (light, clean, modern)  
- **Target audience**: 有前端基础（HTML/CSS/JS）的初学者  

## II. Canvas Specification

- **Format**: PPT 16:9  
- **Dimensions**: 1280 × 720 px  
- **viewBox**: `0 0 1280 720`  
- **Margins**: 60 px top, 60 px bottom, 60 px left, 60 px right  
- **Content area**: 1160 × 600 px (left: 60, top: 60, width: 1160, height: 600)  

## III. Visual Theme

- **Style**: Clean, modern educational, high contrast, generous whitespace  
- **Theme**: Light  
- **Color scheme (11 roles)**:
  - **background**: #FFFFFF
  - **secondary bg**: #F8FAFC
  - **primary**: #2563EB
  - **accent**: #3B82F6
  - **secondary accent**: #DBEAFE
  - **body text**: #1E293B
  - **secondary text**: #64748B
  - **tertiary text**: #94A3B8
  - **border**: #E2E8F0
  - **success**: #10B981
  - **warning**: #F59E0B

## IV. Typography System

- **Font plan**:
  - Heading font: `Inter`, fallback `Arial`, `Helvetica Neue`, `sans-serif` (bold weights)
  - Body font: `Inter`, fallback `Arial`, `Helvetica Neue`, `sans-serif` (regular)
  - Code font: `Courier New`, `monospace`
- **Size hierarchy**:
  - H1: 48px bold
  - H2: 36px bold
  - H3: 28px bold
  - Body: 20px regular
  - Caption: 16px regular
  - Footer: 14px regular (slide number, source)

## V. Layout Principles

- **Grid system**: 12-column invisible grid; column width ~97px, gutter 16px  
- **Spacing rules**:
  - Margins between sections: 32px
  - Padding inside containers: 24px
  - List item spacing: 16px
- **Alignment guidelines**:
  - All text left-aligned (except title slides which are centered)
  - Icons align with text baseline (inline) or centered in decorative blocks
  - Diagrams and tables centered horizontally within content area

## VI. Icon Usage

- **Icon library**: `tabler-filled` (solid, simple, high visibility)  
- **Icon style**: 24px × 24px, primary blue (#2563EB), rounded corners  
- **Size constraints**:
  - Inline with body text: 1.2em
  - Standalone decorative icons: 32×32 px or 48×48 px for emphasis
  - Use SVG path `d` attributes; wrap in `<g transform="translate(x,y) scale(size/24)">` for flexibility

## VII. Visualization Reference List

| Manuscript Element | Recommended Chart/Visual |
|-------------------|--------------------------|
| 六步流程箭头图 | Horizontal arrow flow chart with 6 numbered boxes (SVG) |
| 项目文件树结构图 | Indented tree diagram: folder icons + file names, aligned vertically (SVG) |
| 组件名称 + 功能描述表 | Two‑column table: Column 1 – Component/API name, Column 2 – Description (SVG) |
| 开发者工具界面截图 | Placeholder rectangle with mock‑up of code editor (SVG shapes + text) |
| 图标 (mobile, lightning, code, etc.) | Use `tabler-filled` icons as SVG paths |

## VIII. Visual Asset Plan

All visuals will be generated as native SVG inside the slide markup. No external images.

1. **Title Slide Decoration**  
   - Background: large subtle circle and diagonal lines (secondary bg + accent with low opacity)  
   - App icon representation: stylised wechat mini program logo (SVG path inside a rounded square)

2. **Course Outline – Flow Diagram**  
   - 6 rounded rectangles (#DBEAFE with #2563EB border) connected by arrows  
   - Numbered ①‑⑥, each containing one keyword (e.g. 什么是, 环境, 项目结构, 开发流程, 组件, 总结)  
   - Arrow heads: polygon fill #3B82F6

3. **What is Mini Program – Icon Feature Boxes**  
   - Two squares (120×120 px) side by side: one with mobile icon, one with lightning icon  
   - Inside each: icon in #2563EB, label below in secondary text

4. **Environment Setup – Screenshot Placeholder**  
   - Rounded rectangle (600×380 px) with light grey (#E2E8F0) background  
   - Inside: mock‑up of developer tool window with menu bar, code pane, preview pane (SVG paths and text)

5. **Project Structure – File Tree**  
   - Indented list using folder icons (tabler‑filled folder) and file icons (tabler‑filled file)  
   - Vertical lines indicating depth (SVG lines)

6. **Development Flow – Numbered Steps**  
   - Three columns of two steps each, or vertical list with large numbers and icons  
   - Each step: number circle (#2563EB, white text), title, brief explanation, optional icon (mouse_click, bug)

7. **Components & API – Table + Callout Box**  
   - Table: 6 rows (header + 5 data rows), alternating row fill (#F8FAFC / white)  
   - Right‑side callout box (#DBEAFE rounded, 3‑line note about 鉴权)

8. **Summary & Q&A – Decorative Icons Section**  
   - Two large icons (question mark, hand wave) centered with thank‑you text  
   - Subtle background accent circle

## IX. Content Outline

### Page 1 – Title
- **Layout type**: title
- **Elements**:
  - Background: SVG decorative circles (secondary accent, low opacity)
  - H1: 微信小程序开发入门
  - Subtitle: 有前端基础（HTML/CSS/JS）的初学者
  - Meta line: 学习目标 | 掌握开发流程、核心文件结构及常用组件
  - Two icons (wechat_mini_program, code) placed below, 48×48 px

### Page 2 – Course Outline
- **Layout type**: section (with diagram)
- **Elements**:
  - H2: 课程大纲
  - SVG flow diagram: six steps, each with number and label
  - No bullet list; the diagram serves as the content

### Page 3 – What is WeChat Mini Program
- **Layout type**: content-bullets
- **Elements**:
  - H2: 什么是微信小程序
  - Bullet list (4 items) with bold key terms
  - Two icon boxes (mobile, lightning) aligned right or bottom

### Page 4 – Development Environment Setup
- **Layout type**: content-two-column (text left, placeholder right)
- **Elements**:
  - H2: 开发环境搭建
  - Text left: numbered steps (1. 注册账号, 2. 下载工具, 3. 创建项目)
  - Right: screenshot placeholder SVG (mock-up of developer tool)

### Page 5 – Project Structure & Core Files
- **Layout type**: diagram
- **Elements**:
  - H2: 项目结构与核心文件
  - SVG file tree diagram showing `miniprogram/`, `app.json`, `pages/index/...`, etc.
  - Callout box: “数据绑定：`{{}}`” (secondary accent background)

### Page 6 – Development Flow Demonstration
- **Layout type**: content-bullets (numbered steps)
- **Elements**:
  - H2: 开发流程演示
  - Four steps, each with a number (1–4) and description
  - Two inline icons (mouse_click, bug) after the corresponding steps

### Page 7 – Common Components & API
- **Layout type**: content-two-column (table left, callout right)
- **Elements**:
  - H2: 常用组件与 API
  - SVG table left: 2 columns (组件/API, 功能描述), 5 data rows
  - Right callout box: “注意：小程序 API 需鉴权，部分接口需用户授权”

### Page 8 – Summary & Q&A
- **Layout type**: closing
- **Elements**:
  - H2: 总结与 Q&A
  - Three summary statements (bullet style)
  - “下一步” line with suggestions
  - Two large icons (question_mark, hand_wave) centered
  - Footer text: “感谢聆听，欢迎提问探讨！”

## X. Speaker Notes Requirements

- **Tone**: 亲切、启发式，鼓励学生在听讲时思考自己的项目。使用“你”拉近距离，偶尔抛出小问题。  
- **Length**: 每页2–4句即可，用于补充知识点或提醒关键点，不重复屏幕上已有文字。  
- **Style**:
  - 对初学者友好，避免术语堆砌，必要时简要解释。
  - 用“你可以试试……”、“注意这里容易错……”引导实践。
  - 在总结页可以快速回顾核心概念，并给出进阶方向。

**示例（Page 3）**：
> “小程序本质上是一个轻量级的应用容器。注意它有两个独立线程：渲染层负责页面展示，逻辑层处理业务。因为不需要安装，用户扫一扫就能用，转化率特别高。”

## XI. Technical Constraints Reminder

- **Banned features** (must NOT be used):
  - `<mask>`, `<style>`, `class` attribute, `<foreignObject>`, `<symbol>` + `<use>` (except SVG icon placeholders stored as `<g id="icon-xxx">` and referenced with `<use href="#icon-xxx"/>`)
  - `<textPath>`, `@font-face`, animations (`<animate>`, `<set>`), `<script>`, `<iframe>`
- **Allowed features**:
  - `<defs>` with `<linearGradient>`, `<radialGradient>`, `<stop>` (use `stop-opacity` instead of `stop-color`’s alpha)
  - `<clipPath>` only on `<image>` elements
- **PowerPoint compatibility**:
  - Use `fill-opacity` attribute instead of `rgba()` in `fill`
  - Apply `opacity` on individual child elements instead of wrapping them in `<g opacity="...">`
- **Icon approach**:
  - Define each icon as a `<g id="icon-name">` inside `<defs>`; content is a `<path>` with `d` value from tabler-filled
  - Reference via `<use href="#icon-name" x="..." y="..." transform="scale(...)"/>` (ensure `<use>` does not include `href` with spaces; use `href` lowercase, not `xlink:href`)
- **Color value style**: always using hex (`#RRGGBB`) or named colors; no `hsla` or `rgba` in attribute values; use separate `opacity` or `fill-opacity` attributes.