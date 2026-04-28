const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, LevelFormat } = require('docx');
const fs = require('fs');

function createSpeechDocx(speechData, outputPath) {
  const doc = new Document({
    styles: {
      default: { document: { run: { font: "微软雅黑", size: 22 } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 32, bold: true, color: "1F4E79" },
          paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 26, bold: true, color: "2E75B6" },
          paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 24, bold: true, color: "333333" },
          paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } }
      ]
    },
    numbering: {
      config: [{
        reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } } }]
      }]
    },
    sections: [{
      properties: {
        page: { size: { width: 11906, height: 16838 }, margin: { top: 1418, right: 1418, bottom: 1418, left: 1418 } }
      },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
          children: [new TextRun({ text: speechData.title || '授课讲稿', font: "微软雅黑", size: 44, bold: true, color: "1F4E79" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
          children: [new TextRun({ text: `生成时间：${speechData.created || new Date().toISOString().split('T')[0]}`, font: "微软雅黑", size: 18, color: "666666" })] }),

        // 一、教学导入
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("一、教学导入")] }),
        new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 80 },
          children: [new TextRun("【引发共鸣/争议点】")] }),
        new Paragraph({ spacing: { after: 60 },
          children: [new TextRun({ text: speechData.intro?.opening || '', font: "微软雅黑", size: 22 })] }),
        new Paragraph({ spacing: { after: 200 },
          children: [new TextRun({ text: `互动提问：${speechData.intro?.question || ''}`, font: "微软雅黑", size: 22, italic: true, color: "2E75B6" })] }),

        // 二、知识详解
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("二、知识详解")], spacing: { before: 300 } }),
        ...(speechData.chapters || []).map(chapter => [
          new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(chapter.title)] }),
          new Paragraph({ spacing: { after: 40 },
            children: [new TextRun({ text: chapter.summary || '', font: "微软雅黑", size: 22 })] }),

          // 教学要点
          new Paragraph({ spacing: { before: 80, after: 40 },
            children: [new TextRun({ text: "【教学要点】", font: "微软雅黑", size: 22, bold: true, color: "1F4E79" })] }),
          ...(chapter.points || []).map(point => new Paragraph({
            numbering: { reference: "bullets", level: 0 },
            children: [new TextRun({ text: point, font: "微软雅黑", size: 22 })]
          })),

          // 通俗解释
          chapter.analogy ? new Paragraph({ spacing: { before: 80, after: 40 },
            children: [new TextRun({ text: "【通俗解释】", font: "微软雅黑", size: 22, bold: true, color: "2E75B6" })] }) : null,
          chapter.analogy ? new Paragraph({ spacing: { after: 60 },
            children: [new TextRun({ text: chapter.analogy, font: "微软雅黑", size: 22, italic: true })] }) : null,

          // 重点标注
          chapter.keyPoint ? new Paragraph({ spacing: { before: 60, after: 80 },
            children: [new TextRun({ text: `★ ${chapter.keyPoint}`, font: "微软雅黑", size: 22, color: "C00000", bold: true })] }) : null,

          // 互动提问
          chapter.discussion ? new Paragraph({ spacing: { after: 60 },
            children: [new TextRun({ text: `互动提问：${chapter.discussion}`, font: "微软雅黑", size: 22, color: "2E75B6" })] }) : null,

          // 举例说明
          ...(chapter.examples || []).map(ex => new Paragraph({
            numbering: { reference: "bullets", level: 0 },
            children: [new TextRun({ text: `举例：${ex}`, font: "微软雅黑", size: 22 })]
          })),

          // 讲解话术
          chapter.script ? new Paragraph({ spacing: { before: 80, after: 200 },
            children: [new TextRun({ text: `【讲解话术】${chapter.script}`, font: "微软雅黑", size: 22, color: "555555" })] }) : null
        ]).flat().filter(p => p !== null),

        // 三、课堂总结
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("三、课堂总结")], spacing: { before: 300 } }),
        new Paragraph({ spacing: { after: 80 },
          children: [new TextRun({ text: speechData.summary?.conclusion || '', font: "微软雅黑", size: 22 })] }),
        new Paragraph({ spacing: { after: 200 },
          children: [new TextRun({ text: `使命与担当：${speechData.summary?.mission || ''}`, font: "微软雅黑", size: 22, italic: true, color: "C00000" })] })
      ]
    }]
  });

  Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputPath, buffer);
    console.log('授课讲稿 docx 已生成：' + outputPath);
  });
}

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('用法: node create_speech_docx.js <json_file> <output_path>');
  process.exit(1);
}

const speechData = JSON.parse(fs.readFileSync(args[0], 'utf-8'));
createSpeechDocx(speechData, args[1]);
