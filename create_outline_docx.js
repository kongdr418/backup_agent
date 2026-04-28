const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, LevelFormat } = require('docx');
const fs = require('fs');

function createOutlineDocx(outlineData, outputPath) {
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
          children: [new TextRun({ text: outlineData.title || '课程大纲', font: "微软雅黑", size: 44, bold: true, color: "1F4E79" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
          children: [new TextRun({ text: `生成时间：${outlineData.created || new Date().toISOString().split('T')[0]}`, font: "微软雅黑", size: 18, color: "666666" })] }),

        // 一、课程基本信息
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("一、课程基本信息")] }),
        new Paragraph({ spacing: { after: 60 },
          children: [new TextRun({ text: `课程名称：${outlineData.courseInfo?.name || ''}`, font: "微软雅黑", size: 22 })] }),
        new Paragraph({ spacing: { after: 60 },
          children: [new TextRun({ text: `适用专业：${outlineData.courseInfo?.major || ''}`, font: "微软雅黑", size: 22 })] }),
        new Paragraph({ spacing: { after: 60 },
          children: [new TextRun({ text: `课程性质：${outlineData.courseInfo?.nature || ''}`, font: "微软雅黑", size: 22 })] }),
        outlineData.courseInfo?.prerequisites ? new Paragraph({ spacing: { after: 60 },
          children: [new TextRun({ text: `先修课程：${outlineData.courseInfo.prerequisites}`, font: "微软雅黑", size: 22 })] }) : null,

        // 二、课程概述
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("二、课程概述")], spacing: { before: 300 } }),
        new Paragraph({ spacing: { after: 60 },
          children: [new TextRun({ text: outlineData.overview || '', font: "微软雅黑", size: 22 })] }),

        // 三、课程目标
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("三、课程目标")], spacing: { before: 300 } }),
        ...(outlineData.objectives || []).map(obj => new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          children: [new TextRun({ text: obj, font: "微软雅黑", size: 22 })]
        })),

        // 四、教学内容与学时分配
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("四、教学内容与学时分配")], spacing: { before: 300 } }),
        ...(outlineData.chapters || []).map(chapter => [
          new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(chapter.title)] }),
          new Paragraph({ spacing: { after: 40 },
            children: [new TextRun({ text: `课时：${chapter.hours || ''}`, font: "微软雅黑", size: 22, bold: true, color: "2E75B6" })] }),
          ...(chapter.points || []).map(point => new Paragraph({
            numbering: { reference: "bullets", level: 0 },
            children: [new TextRun({ text: point, font: "微软雅黑", size: 22 })]
          })),
          chapter.keyPoints ? new Paragraph({ spacing: { after: 80 },
            children: [new TextRun({ text: `重难点：${chapter.keyPoints}`, font: "微软雅黑", size: 22, italic: true, color: "C00000" })] }) : null
        ]).flat().filter(p => p !== null),

        // 五、考核方式
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("五、考核方式")], spacing: { before: 300 } }),
        ...(outlineData.assessment || []).map(item => new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          children: [new TextRun({ text: item, font: "微软雅黑", size: 22 })]
        })),

        // 六、常见问题FAQ
        ...((outlineData.faq || []).length > 0 ? [
          new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("六、常见问题FAQ")], spacing: { before: 300 } }),
          ...(outlineData.faq || []).map(faq =>
            new Paragraph({ spacing: { after: 80 },
              children: [
                new TextRun({ text: `Q：${faq.q || faq.question || ''}`, font: "微软雅黑", size: 22, bold: true }),
                new TextRun({ text: `\nA：${faq.a || faq.answer || ''}`, font: "微软雅黑", size: 22 })
              ] }))
        ] : [])
      ].flat().filter(p => p !== null)
    }]
  });

  Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputPath, buffer);
    console.log('课程大纲 docx 已生成：' + outputPath);
  });
}

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('用法: node create_outline_docx.js <json_file> <output_path>');
  process.exit(1);
}

const outlineData = JSON.parse(fs.readFileSync(args[0], 'utf-8'));
createOutlineDocx(outlineData, args[1]);
