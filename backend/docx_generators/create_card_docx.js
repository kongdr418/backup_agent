const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, LevelFormat } = require('docx');
const fs = require('fs');

function createCardDocx(cardData, outputPath) {
  const doc = new Document({
    styles: {
      default: { document: { run: { font: "微软雅黑", size: 22 } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 28, bold: true, color: "1F4E79" },
          paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 24, bold: true, color: "2E75B6" },
          paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 22, bold: true, color: "333333" },
          paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } }
      ]
    },
    numbering: {
      config: [
        { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } } }] },
        { reference: "checks", levels: [{ level: 0, format: LevelFormat.BULLET, text: "✅", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } } }] },
        { reference: "crosses", levels: [{ level: 0, format: LevelFormat.BULLET, text: "❌", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } } }] }
      ]
    },
    sections: [{
      properties: {
        page: { size: { width: 11906, height: 16838 }, margin: { top: 1418, right: 1418, bottom: 1418, left: 1418 } }
      },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
          children: [new TextRun({ text: cardData.title || '知识卡片', font: "微软雅黑", size: 44, bold: true, color: "1F4E79" })] }),

        ...cardData.cards.map(card => [
          // 卡片标题
          new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(card.title)] }),

          // 一句话定义
          new Paragraph({ spacing: { after: 60 },
            children: [new TextRun({ text: "📌 一句话定义：", font: "微软雅黑", size: 22, bold: true }),
                      new TextRun({ text: card.definition || '', font: "微软雅黑", size: 22 })] }),

          // 核心逻辑/底层原理
          new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 80 },
            children: [new TextRun("🧩 核心逻辑 / 底层原理")] }),
          new Paragraph({ spacing: { after: 40 },
            children: [new TextRun({ text: "运作机制：", font: "微软雅黑", size: 22, bold: true }),
                      new TextRun({ text: card.mechanism?.mechanism || '', font: "微软雅黑", size: 22 })] }),
          card.mechanism?.formula ? new Paragraph({ spacing: { after: 80 },
            children: [new TextRun({ text: "关键公式/模型：", font: "微软雅黑", size: 22, bold: true }),
                      new TextRun({ text: card.mechanism.formula || '', font: "微软雅黑", size: 22 })] }) : null,

          // 深度洞察
          new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 80 },
            children: [new TextRun("💡 深度洞察")] }),
          ...(card.insights || []).map(insight => new Paragraph({
            numbering: { reference: "bullets", level: 0 },
            children: [new TextRun({ text: insight, font: "微软雅黑", size: 22 })] })),

          // 典型应用
          new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 80 },
            children: [new TextRun("🛠 典型应用")] }),
          ...(card.applications || []).map(app => new Paragraph({
            numbering: { reference: "checks", level: 0 },
            children: [new TextRun({ text: app, font: "微软雅黑", size: 22 })] })),

          // 避坑指南
          new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 80 },
            children: [new TextRun("🛠 避坑指南")] }),
          ...(card.pitfalls || []).map(pitfall => new Paragraph({
            numbering: { reference: "crosses", level: 0 },
            children: [new TextRun({ text: pitfall, font: "微软雅黑", size: 22 })] })),

          // 记忆金句
          card.memory ? new Paragraph({ spacing: { before: 160, after: 200 },
            children: [new TextRun({ text: "🔔 记忆金句：", font: "微软雅黑", size: 22, bold: true, color: "C00000" }),
                      new TextRun({ text: `★ "${card.memory}"`, font: "微软雅黑", size: 22, color: "C00000", italic: true })] }) : null,

          new Paragraph({ spacing: { after: 200 }, children: [] })
        ]).flat().filter(p => p !== null)
      ]
    }]
  });

  Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputPath, buffer);
    console.log('知识卡片 docx 已生成：' + outputPath);
  });
}

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('用法: node create_card_docx.js <json_file> <output_path>');
  process.exit(1);
}

const cardData = JSON.parse(fs.readFileSync(args[0], 'utf-8'));
createCardDocx(cardData, args[1]);
