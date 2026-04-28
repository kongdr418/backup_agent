const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, LevelFormat } = require('docx');
const fs = require('fs');

function createQuizDocx(quizData, outputPath) {
  const doc = new Document({
    styles: {
      default: { document: { run: { font: "微软雅黑", size: 22 } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 28, bold: true, color: "1F4E79" },
          paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 24, bold: true, color: "2E75B6" },
          paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } }
      ]
    },
    numbering: {
      config: [
        { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } } }] },
        { reference: "options", levels: [{ level: 0, format: LevelFormat.BULLET, text: "", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } } }] }
      ]
    },
    sections: [{
      properties: {
        page: { size: { width: 11906, height: 16838 }, margin: { top: 1418, right: 1418, bottom: 1418, left: 1418 } }
      },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
          children: [new TextRun({ text: quizData.title || '课堂测验', font: "微软雅黑", size: 44, bold: true, color: "1F4E79" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
          children: [new TextRun({ text: `生成时间：${quizData.created || new Date().toISOString().split('T')[0]}`, font: "微软雅黑", size: 18, color: "666666" })] }),

        ...quizData.modules.map(module => [
          new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(module.title)] }),
          ...module.questions.map(q => [
            new Paragraph({ spacing: { before: 120, after: 40 },
              children: [new TextRun({ text: `${q.num}.（${q.type}）`, font: "微软雅黑", size: 22, bold: true, color: "1F4E79" }),
                        new TextRun({ text: ` ${q.text}`, font: "微软雅黑", size: 22 })] }),
            ...(q.options || []).map(opt => new Paragraph({
              numbering: { reference: "options", level: 0 },
              spacing: { after: 20 },
              children: [new TextRun({ text: opt, font: "微软雅黑", size: 22 })] })),
            new Paragraph({ spacing: { after: 160 },
              children: [new TextRun({ text: `答案：${q.answer}`, font: "微软雅黑", size: 22, color: "C00000", bold: true })] })
          ]).flat()
        ]).flat()
      ]
    }]
  });

  Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputPath, buffer);
    console.log('课堂测验 docx 已生成：' + outputPath);
  });
}

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('用法: node create_quiz_docx.js <json_file> <output_path>');
  process.exit(1);
}

const quizData = JSON.parse(fs.readFileSync(args[0], 'utf-8'));
createQuizDocx(quizData, args[1]);
