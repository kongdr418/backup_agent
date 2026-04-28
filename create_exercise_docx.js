const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, LevelFormat, Table, TableRow, TableCell, WidthType, BorderStyle } = require('docx');
const fs = require('fs');

function createExerciseDocx(exerciseData, outputPath) {
  const doc = new Document({
    styles: {
      default: {
        document: {
          run: { font: "微软雅黑", size: 22 }
        }
      },
      paragraphStyles: [
        {
          id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 28, bold: true, color: "1F4E79" },
          paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 }
        },
        {
          id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "微软雅黑", size: 24, bold: true, color: "2E75B6" },
          paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 }
        }
      ]
    },
    numbering: {
      config: [{
        reference: "bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } }
        }]
      }]
    },
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1418, right: 1418, bottom: 1418, left: 1418 }
        }
      },
      children: [
        // 标题
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: exerciseData.title || '习题集', font: "微软雅黑", size: 44, bold: true, color: "1F4E79" })]
        }),

        // 选择题
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("一、选择题")] }),
        ...exerciseData.choiceQuestions.map((q, idx) => [
          new Paragraph({
            spacing: { after: 60 },
            children: [new TextRun({ text: `${q.num}. ${q.text}`, font: "微软雅黑", size: 22 })]
          }),
          ...q.options.map(opt => new Paragraph({
            numbering: { reference: "bullets", level: 0 },
            children: [new TextRun({ text: opt, font: "微软雅黑", size: 22 })]
          })),
          new Paragraph({
            spacing: { after: 160 },
            children: [new TextRun({ text: `答案：${q.answer}`, font: "微软雅黑", size: 22, color: "C00000", bold: true })]
          })
        ]).flat(),

        // 填空题
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("二、填空题")] }),
        ...exerciseData.fillQuestions.map(q => [
          new Paragraph({
            spacing: { after: 60 },
            children: [new TextRun({ text: `${q.num}. ${q.text}`, font: "微软雅黑", size: 22 })]
          }),
          new Paragraph({
            spacing: { after: 160 },
            children: [new TextRun({ text: `答案：${q.answer}`, font: "微软雅黑", size: 22, color: "C00000", bold: true })]
          })
        ]).flat(),

        // 简答题
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("三、简答题")] }),
        ...exerciseData.essayQuestions.map(q => [
          new Paragraph({
            spacing: { after: 60 },
            children: [new TextRun({ text: `${q.num}. ${q.text}`, font: "微软雅黑", size: 22 })]
          }),
          ...(q.points || []).map(point => new Paragraph({
            numbering: { reference: "bullets", level: 0 },
            children: [new TextRun({ text: point, font: "微软雅黑", size: 22 })]
          })),
          new Paragraph({
            spacing: { after: 160 },
            children: [new TextRun({ text: `参考答案：${q.answer || '无'}`, font: "微软雅黑", size: 22, color: "C00000", bold: true })]
          })
        ]).flat(),

        // 答案汇总
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("答案汇总")], spacing: { before: 400 } }),

        // 选择题答案表格
        new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("选择题答案")] }),
        createAnswerTable(exerciseData.choiceQuestions),
        new Paragraph({ spacing: { after: 200 }, children: [] }),

        // 填空题答案表格
        new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("填空题答案")] }),
        createAnswerTable(exerciseData.fillQuestions),
      ]
    }]
  });

  Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputPath, buffer);
    console.log('习题集 docx 已生成：' + outputPath);
  });
}

function createAnswerTable(questions) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
  const borders = { top: border, bottom: border, left: border, right: border };

  function createCell(text, isBold = false) {
    return new TableCell({
      borders,
      width: { size: 2000, type: WidthType.DXA },
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      children: [new Paragraph({
        children: [new TextRun({ text, font: "微软雅黑", size: 20, bold: isBold })]
      })]
    });
  }

  return new Table({
    width: { size: 4000, type: WidthType.DXA },
    columnWidths: [1000, 3000],
    rows: [
      new TableRow({
        children: [createCell("题号", true), createCell("答案", true)]
      }),
      ...questions.map(q => new TableRow({
        children: [createCell(q.num), createCell(q.answer)]
      }))
    ]
  });
}

// 主程序
const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('用法: node create_exercise_docx.js <json_file> <output_path>');
  process.exit(1);
}

const jsonFile = args[0];
const outputPath = args[1];

const exerciseData = JSON.parse(fs.readFileSync(jsonFile, 'utf-8'));
createExerciseDocx(exerciseData, outputPath);
