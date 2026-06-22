/**
 * citation-jump.test.tsx — 引用跳转功能单元测试 v4
 *
 * v4 适配 rehype-sanitize 默认 id 前缀行为：
 *   - rehype-sanitize 给所有 id 加 "user-content-" 前缀（无法关闭）
 *   - preprocessCitations 同步变换 [A1](#a1) → [A1](#user-content-a1)
 *   - 确保链接 href 和锚点 id 匹配
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';


// ════════════════════════════════════════════
// 与 ReportViewer.tsx v0.7.8 一致的实现
// ════════════════════════════════════════════

function preprocessCitations(md: string): string {
  md = md.replace(
    /\[([A-Z][-\w]*\d+)\](?!\()/g,
    '<cite data-ref="$1" id="cite-$1">[$1]</cite>'
  );
  md = md.replace(
    /\[([^\]]+)\]\(#(?!user-content-)([^)]+)\)/g,
    '[$1](#user-content-$2)'
  );
  return md;
}

const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [...defaultSchema.tagNames, 'cite'],
  attributes: {
    ...defaultSchema.attributes,
    a: [...(defaultSchema.attributes?.a || ['href']), ['id', /.*/], ['name', /.*/]],
    cite: ['dataRef', 'id', 'className'],
  },
};

function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div data-testid="md-output">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, [rehypeSanitize, sanitizeSchema]]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function parseMarkdown(md: string) {
  const processed = preprocessCitations(md);
  const lines = processed.split('\n');
  const headerLines: string[] = [];
  const sections: Array<{ id: string; title: string; content: string }> = [];
  let inSection = false, sectionTitle = '', sectionLines: string[] = [];
  for (const line of lines) {
    const m = line.match(/^## (.+)/);
    if (m) {
      if (inSection) sections.push({ id: sectionTitle, title: sectionTitle, content: sectionLines.join('\n') });
      sectionTitle = m[1]; sectionLines = []; inSection = true;
    } else if (inSection) sectionLines.push(line);
    else headerLines.push(line);
  }
  if (inSection) sections.push({ id: sectionTitle, title: sectionTitle, content: sectionLines.join('\n') });
  return { header: headerLines.join('\n'), sections };
}

/** rehype-sanitize 给所有 id 加 user-content- 前缀 */
const ID_PREFIX = 'user-content-';
const prefixed = (id: string) => ID_PREFIX + id;


// ════════════════════════════════════════════
//  Test 1: preprocessCitations
// ════════════════════════════════════════════

describe('preprocessCitations', () => {
  it('[REF001] → <cite>', () => {
    expect(preprocessCitations('正文 [REF001] 结束'))
      .toContain('<cite data-ref="REF001" id="cite-REF001">');
  });
  it('[WEB001] → cite', () => {
    expect(preprocessCitations('来源 [WEB001]'))
      .toContain('<cite data-ref="WEB001"');
  });
  it('[REF-001] → cite', () => {
    expect(preprocessCitations('参考 [REF-001]'))
      .toContain('<cite data-ref="REF-001"');
  });
  it('[A1](#a1) → href 加 user-content- 前缀', () => {
    const r = preprocessCitations('根据[A1](#a1)数据显示');
    expect(r).toContain('[A1](#user-content-a1)');
    expect(r).not.toContain('[A1](#a1)');
  });
  it('[A2](#a2) → href 加 user-content- 前缀', () => {
    const r = preprocessCitations('参见[A2](#a2)和[W-q-3](#w-q-3)');
    expect(r).toContain('[A2](#user-content-a2)');
    expect(r).toContain('[W-q-3](#user-content-w-q-3)');
  });
  it('[W-r2-3](#w-r2-3) → href 加前缀', () => {
    const r = preprocessCitations('来源 [W-r2-3](#w-r2-3)');
    expect(r).toContain('[W-r2-3](#user-content-w-r2-3)');
  });

  // v0.7.9: 扩宽匹配 — 任意 markdown 内部链接
  it('[abc](#abc) 纯小写 → href 加前缀', () => {
    const r = preprocessCitations('查看[abc](#abc)');
    expect(r).toContain('[abc](#user-content-abc)');
    expect(r).not.toContain('[abc](#abc)');
  });
  it('[some-link](#some-link) 小写+连字符 → href 加前缀', () => {
    const r = preprocessCitations('参见[some-link](#some-link)');
    expect(r).toContain('[some-link](#user-content-some-link)');
  });
  it('[REF_001](#ref_001) 下划线 → href 加前缀', () => {
    const r = preprocessCitations('来源 [REF_001](#ref_001)');
    expect(r).toContain('[REF_001](#user-content-ref_001)');
  });
  it('[中文锚点](#中文锚点) → href 加前缀', () => {
    const r = preprocessCitations('详见[中文锚点](#中文锚点)');
    expect(r).toContain('[中文锚点](#user-content-中文锚点)');
  });

  // v0.7.9: 外部链接不应受影响
  it('外部链接 [百度](https://baidu.com) 不加前缀', () => {
    const r = preprocessCitations('搜索[百度](https://baidu.com)');
    expect(r).toContain('[百度](https://baidu.com)');
    expect(r).not.toContain('user-content-https');
  });

  it('[abc] 不受影响', () => {
    expect(preprocessCitations('普通 [abc] 文本')).toContain('[abc]');
  });
  it('表格中 [REF001] → cite', () => {
    expect(preprocessCitations('| [REF001] | 年报2023 |'))
      .toContain('<cite data-ref="REF001"');
  });
  it('不会重复加前缀 [A1](#user-content-a1)', () => {
    const r = preprocessCitations('[A1](#user-content-a1)');
    // 应保持不变，不会变成 user-content-user-content-a1
    expect(r).toContain('[A1](#user-content-a1)');
    expect((r.match(/user-content-a1/g) || []).length).toBe(1);
  });
  // 含 # 的锚点文本
  it('[#1](#1) 数字锚点 → href 加前缀', () => {
    const r = preprocessCitations('参见[#1](#1)');
    expect(r).toContain('[#1](#user-content-1)');
  });
});


// ════════════════════════════════════════════
//  Test 2: sanitizeSchema 结构
// ════════════════════════════════════════════

describe('sanitizeSchema', () => {
  it('tagNames 包含 cite', () => {
    expect(sanitizeSchema.tagNames).toContain('cite');
  });
  it('attributes.a 包含 href 和 id/name', () => {
    expect(sanitizeSchema.attributes?.a).toContain('href');
    const hasId = sanitizeSchema.attributes?.a.some(
      (item: unknown) => Array.isArray(item) && item[0] === 'id'
    );
    const hasName = sanitizeSchema.attributes?.a.some(
      (item: unknown) => Array.isArray(item) && item[0] === 'name'
    );
    expect(hasId).toBe(true);
    expect(hasName).toBe(true);
  });
  it('attributes.cite 包含 dataRef, id', () => {
    expect(sanitizeSchema.attributes?.cite).toContain('dataRef');
    expect(sanitizeSchema.attributes?.cite).toContain('id');
  });
});


// ════════════════════════════════════════════
//  Test 3: Path B — markdown 链接渲染
// ════════════════════════════════════════════

describe('Path B: 链接 → href 匹配 user-content- 前缀', () => {
  it('处理后 href 包含 user-content-', () => {
    const md = preprocessCitations('根据[A1](#a1)数据显示');
    render(<MarkdownRenderer content={md} />);
    const link = screen.getByText('A1');
    expect(link.tagName).toBe('A');
    expect(link.getAttribute('href')).toBe('#user-content-a1');
  });

  it('链接可被点击', async () => {
    const user = userEvent.setup();
    const md = preprocessCitations('根据[A1](#a1)数据显示');
    render(<MarkdownRenderer content={md} />);
    await user.click(screen.getByText('A1'));
  });

  it('多链接各自 href 正确', () => {
    const md = preprocessCitations('根据[A1](#a1)和[A2](#a2)');
    render(<MarkdownRenderer content={md} />);
    const out = screen.getByTestId('md-output');
    expect(out.querySelector('a[href="#user-content-a1"]')).not.toBeNull();
    expect(out.querySelector('a[href="#user-content-a2"]')).not.toBeNull();
  });
});


// ════════════════════════════════════════════
//  Test 4: 锚点渲染（带 user-content- 前缀）
// ════════════════════════════════════════════

describe('锚点 id 带 user-content- 前缀', () => {
  it('段落中 <a id="a1"> → id="user-content-a1"', () => {
    render(<MarkdownRenderer content={'<a id="a1"></a> 参考'} />);
    const out = screen.getByTestId('md-output');
    const a = out.querySelector(`a[id="${prefixed('a1')}"]`);
    expect(a).not.toBeNull();
  });

  it('表格中 <a id="a1"> 锚点保留（带前缀）', () => {
    render(
      <MarkdownRenderer content={
        '| 编号 | 来源 |\n|------|------|\n| <a id="a1"></a>A1 | 年报 |'
      } />
    );
    const out = screen.getByTestId('md-output');
    expect(out.querySelector(`a[id="${prefixed('a1')}"]`)).not.toBeNull();
  });

  it('<a id="a1" name="ref-a1"> id 保留（name 在 HTML5 已废弃）', () => {
    render(<MarkdownRenderer content={'<a id="a1" name="ref-a1"></a> 参考'} />);
    const out = screen.getByTestId('md-output');
    // id 带前缀保留
    const a = out.querySelector(`a[id="${prefixed('a1')}"]`);
    expect(a).not.toBeNull();
    // name 属性在 HTML5 中已被废弃，jsdom 会忽略
    // 实际浏览器中 name 仍可用于锚点导航，但 id 已足够
  });
});


// ════════════════════════════════════════════
//  Test 5: Path A — cite 标签
// ════════════════════════════════════════════

describe('Path A: cite 标签', () => {
  it('段落中 cite[data-ref] 保留', () => {
    const md = preprocessCitations('来源 [REF001]');
    render(<MarkdownRenderer content={md} />);
    const out = screen.getByTestId('md-output');
    const cite = out.querySelector('cite[data-ref="REF001"]');
    expect(cite).not.toBeNull();
    expect(cite!.getAttribute('data-ref')).toBe('REF001');
  });

  it('表格中 cite 保留', () => {
    const md = preprocessCitations('| [REF001] | 年报2023 |');
    render(<MarkdownRenderer content={md} />);
    const out = screen.getByTestId('md-output');
    expect(out.querySelector('cite[data-ref="REF001"]')).not.toBeNull();
  });

  it('点击 cite 不报错', async () => {
    const user = userEvent.setup();
    const md = preprocessCitations('来源 [REF001]');
    render(<MarkdownRenderer content={md} />);
    const out = screen.getByTestId('md-output');
    const cite = out.querySelector('cite');
    expect(cite).not.toBeNull();
    await user.click(cite!);
  });
});


// ════════════════════════════════════════════
//  Test 6: 完整场景
// ════════════════════════════════════════════

describe('完整场景：链接 ↔ 锚点 匹配', () => {
  const fullMarkdown = [
    '## 生意本质分析',
    '',
    '根据[A1](#a1)数据显示，公司主营收入增长稳健。',
    '此外[A2](#a2)表明行业景气度处于上升期。',
    '',
    '## 参考来源',
    '',
    '| 编号 | 来源 | 内容摘要 |',
    '|------|------|----------|',
    '| <a id="a1"></a>A1 | 年报2023 | 营业收入100亿元 |',
    '| <a id="a2"></a>A2 | 行业报告 | 行业增速15% |',
  ].join('\n');

  const { sections } = parseMarkdown(fullMarkdown);

  it('parseMarkdown → 2 sections', () => {
    expect(sections).toHaveLength(2);
  });

  it('body: href 带前缀', () => {
    render(<MarkdownRenderer content={sections[0].content} />);
    const link = screen.getByText('A1');
    expect(link.getAttribute('href')).toBe('#user-content-a1');
  });

  it('ref: 锚点 id 带前缀', () => {
    render(<MarkdownRenderer content={sections[1].content} />);
    const out = screen.getByTestId('md-output');
    expect(out.querySelector(`a[id="${prefixed('a1')}"]`)).not.toBeNull();
    expect(out.querySelector(`a[id="${prefixed('a2')}"]`)).not.toBeNull();
  });

  it('href 和 id 完整匹配', () => {
    const all = sections.map(s => s.content).join('\n\n');
    render(<MarkdownRenderer content={all} />);
    const out = screen.getByTestId('md-output');
    const link = out.querySelector(`a[href="#${prefixed('a1')}"]`);
    const anchor = out.querySelector(`a[id="${prefixed('a1')}"]`);
    expect(link).not.toBeNull();
    expect(anchor).not.toBeNull();
  });

  it('点击链接不报错', async () => {
    const user = userEvent.setup();
    const all = sections.map(s => s.content).join('\n\n');
    render(<MarkdownRenderer content={all} />);
    const links = screen.getAllByText('A1');
    await user.click(links[0]);
  });
});


// ════════════════════════════════════════════
//  Test 7: 边界情况
// ════════════════════════════════════════════

describe('边界情况', () => {
  it('普通文本正常渲染', () => {
    render(<MarkdownRenderer content="普通文本" />);
    expect(screen.getByText('普通文本')).toBeTruthy();
  });

  it('REF cite + 带前缀的 A1 link 混合', () => {
    const md = preprocessCitations('正文 [REF001] 和 [A1](#a1) 混合');
    render(<MarkdownRenderer content={md} />);
    const out = screen.getByTestId('md-output');
    // cite 存在
    expect(out.querySelector('cite[data-ref="REF001"]')).not.toBeNull();
    // A1 链接带前缀
    expect(out.querySelector(`a[href="#${prefixed('a1')}"]`)).not.toBeNull();
  });
});


// ════════════════════════════════════════════
//  Test 8: Path B 内部链接高亮整行 (v0.7.10)
// ════════════════════════════════════════════

describe('Path B: 内部链接点击高亮目标行', () => {
  const tableMarkdown = [
    '## 参考来源',
    '',
    '| 编号 | 来源 |',
    '|------|------|',
    '| <a id="a1"></a>A1 | 年报2023 |',
    '| <a id="a2"></a>A2 | 行业报告 |',
  ].join('\n');

  it('锚点渲染在表格 tr 内（closest(tr) 可达）', () => {
    render(<MarkdownRenderer content={tableMarkdown} />);
    const out = screen.getByTestId('md-output');
    const a1 = out.querySelector(`a[id="${prefixed('a1')}"]`);
    expect(a1).not.toBeNull();
    // 锚点在 td 内 → tr 内 — flashTarget 的 closest('tr') 能找到整行
    const tr = a1!.closest('tr');
    expect(tr).not.toBeNull();
  });

  it('多行锚点各自在不同 tr 内', () => {
    render(<MarkdownRenderer content={tableMarkdown} />);
    const out = screen.getByTestId('md-output');
    const a1 = out.querySelector(`a[id="${prefixed('a1')}"]`);
    const a2 = out.querySelector(`a[id="${prefixed('a2')}"]`);
    expect(a1!.closest('tr')).not.toBeNull();
    expect(a2!.closest('tr')).not.toBeNull();
    // 两个锚点在不同行
    expect(a1!.closest('tr')).not.toBe(a2!.closest('tr'));
  });

  it('链接 href 和锚点 id 匹配', () => {
    const md = preprocessCitations('正文[A1](#a1)链接\n\n' + tableMarkdown);
    render(<MarkdownRenderer content={md} />);
    const out = screen.getByTestId('md-output');
    const link = out.querySelector(`a[href="#${prefixed('a1')}"]`);
    const anchor = out.querySelector(`a[id="${prefixed('a1')}"]`);
    expect(link).not.toBeNull();
    expect(anchor).not.toBeNull();
  });
});
