# Fonts

## MiSans

主 UI 字体,小米开源,免费商用(需注明使用 MiSans 字体)。

- 来源: 小米官方 https://hyperos.mi.com/font
- License: 《MiSans 字体知识产权许可协议》— 非排他、可撤销、全球范围免费使用,使用时需在适当位置标注"使用了 MiSans 字体"
- 当前 self-host 的字重(覆盖 90% 用例):
  - `MiSans-Regular.ttf` (400) — 正文
  - `MiSans-Medium.ttf` (500) — 标签 / 高亮
  - `MiSans-Semibold.ttf` (600) — 小标题
  - `MiSans-Bold.ttf` (700) — 大标题
- 如需更轻字重(Thin/Light/ExtraLight)或更重字重(Heavy),从小米官网下载对应 ttf 放入本目录,并在 `tailwind.css` 添加 `@font-face`

## 优化建议(后期)

每个 ttf ~8MB,4 档共 ~32MB。生产环境建议用 [fonttools](https://github.com/fonttools/fonttools) 做中文 subset:

```bash
pip install fonttools brotli
pyftsubset MiSans-Regular.ttf \
  --unicodes="U+0020-007F,U+4E00-9FFF,U+3000-303F,U+FF00-FFEF" \
  --output-file=MiSans-Regular.subset.woff2 \
  --flavor=woff2
```

预计每个文件可降至 800KB-1.2MB,共 ~3-5MB,加 `font-display: swap` 后首屏不阻塞。

## License Attribution

应用内需在某处显示字体出处(本项目放在 Settings 页脚或 About 弹层)。
