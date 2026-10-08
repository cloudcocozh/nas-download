"""Render bilingual offline guides; optionally package a documentation-only ZIP.

Install deploy/docs-requirements.txt, then run from any directory:
    python deploy/render_guides.py --archive /path/to/manuals.zip
This command only writes documentation, never application or NAS state.
"""
from pathlib import Path
from html import escape
from urllib.parse import urlsplit
import argparse
import re
import zipfile

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [(Path(n + '.md'), Path(n + '.en.md')) for n in ('README', 'PRIVACY', 'THIRD_PARTY')]
PAIRS += [(Path('docs') / (n + '.md'), Path('docs') / (n + '_EN.md')) for n in
          ('AUTOMATION', 'SITES', 'BUILDING', 'INSTALL_RELEASE', 'ACCEPTANCE_1_3', 'RELEASE_1_3', 'LICENSE_INVENTORY')]
PAIRS += [(Path('docs') / (n + '_ZH.md'), Path('docs') / (n + '_EN.md')) for n in ('QUICK_START', 'USER_MANUAL')]
MD = MarkdownIt('commonmark', {'html': False}).enable('table')
CSS = (ROOT / 'deploy/guide-style.css').read_text(encoding='utf-8')
SCRIPT = """
const box=document.querySelector('#q'),result=document.querySelector('#result');
box.addEventListener('input',()=>{const q=box.value.trim().toLowerCase();let n=0;
 document.querySelectorAll('main section').forEach(s=>{const hit=!q||s.textContent.toLowerCase().includes(q);s.hidden=!hit;if(hit)n++;const a=document.querySelector('[data-section="'+s.id+'"]');if(a)a.hidden=!hit;});
 result.textContent=q?result.dataset.found.replace('{n}',n):result.dataset.help;});
document.querySelector('#print').addEventListener('click',()=>{box.value='';box.dispatchEvent(new Event('input'));window.print();});
"""


def render(path, english):
    tokens = MD.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    nav = []
    title = ''
    for i, token in enumerate(tokens):
        if token.type == 'heading_open' and token.tag == 'h1' and not title:
            title = tokens[i + 1].content
        if token.type == 'heading_open' and token.tag == 'h2':
            sid = f'section-{len(nav) + 1}'
            token.attrSet('id', 'heading-' + str(len(nav) + 1))
            nav.append((sid, tokens[i + 1].content))
        for child in token.children or []:
            if child.type != 'link_open':
                continue
            href = child.attrGet('href') or ''
            parsed = urlsplit(href)
            if not parsed.scheme and parsed.path.endswith('.md') and (ROOT / path.parent / parsed.path).is_file():
                child.attrSet('href', href.replace('.md', '.html', 1))
    content = MD.renderer.render(tokens, MD.options, {})
    parts = re.split(r'(?=<h2 id="heading-\d+">)', content)
    content = parts[0] + ''.join(f'<section id="section-{i}">{part}</section>' for i, part in enumerate(parts[1:], 1))
    links = ''.join(f'<li data-section="{sid}"><a href="#{sid}">{escape(text)}</a></li>' for sid, text in nav)
    prefix = '' if path.parent == Path('docs') else 'docs/'
    suffix = 'EN' if english else 'ZH'
    acceptance = 'ACCEPTANCE_1_3_EN' if english else 'ACCEPTANCE_1_3'
    lang = 'en' if english else 'zh-CN'
    help_text = 'Filter chapters by keyword, e.g. password, files, check-in.' if english else '输入关键词筛选章节，例如：密码、文件、签到'
    label = 'Find a chapter' if english else '查找章节'
    print_label = 'Print / Save PDF' if english else '打印 / 保存 PDF'
    found = '{n} matching chapters' if english else '找到 {n} 个相关章节'
    subtitle = 'Your own NAS downloader · Built-in engine · Phone and web management' if english else '自己的 NAS 下载助手 · 内置下载引擎 · 手机与网页同步管理'
    footer = ('Works offline, with no external fonts, scripts, or analytics. Replace example addresses and paths with your own. Printing shows every chapter.' if english else '本文件可离线阅读，无外部字体、脚本或统计请求。示例地址和路径须替换成自己的值。打印前会显示全部章节。')
    top = [('QUICK_START_' + suffix, 'Quick start' if english else '第一次使用'),
           ('USER_MANUAL_' + suffix, 'Full manual' if english else '完整说明书'),
           (acceptance, 'Validation' if english else '测试范围')]
    navigation = ''.join(f'<a href="{prefix}{name}.html">{text}</a>' for name, text in top)
    return f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>{escape(title)}</title><style>{CSS}</style></head><body>
<header><div class="tag">NAS DOWNLOAD / 1.3.0 {'BETA' if english else '测试版'}</div><strong>{escape(title)}</strong><p>{subtitle}</p><nav class="top">{navigation}<button id="print" type="button">{print_label}</button></nav></header>
<div class="layout"><aside><label for="q">{label}</label><input id="q" type="search" placeholder="{label}"><div id="result" aria-live="polite" data-found="{found}" data-help="{help_text}">{help_text}</div><ul>{links}</ul></aside><main>{content}<footer>{footer}</footer></main></div><script>{SCRIPT}</script></body></html>'''


def entry(prefix):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nas Download — 中文 / English</title><style>{CSS}.layout{{display:block;max-width:960px}}</style></head><body><header><div class="tag">NAS DOWNLOAD / 1.3.0 BETA</div><strong>使用说明 · User guides</strong><p>选择语言 / Choose your language</p></header><div class="layout"><main><h1>从这里开始 / Start here</h1><p>先解压完整说明书，再打开此页。Extract the entire manuals ZIP before opening this page.</p><table><thead><tr><th>文档 / Guide</th><th>简体中文</th><th>English</th></tr></thead><tbody><tr><td>快速上手 / Quick start</td><td><a lang="zh-CN" href="{prefix}QUICK_START_ZH.html">开始安装</a></td><td><a href="{prefix}QUICK_START_EN.html">Get started</a></td></tr><tr><td>完整说明书 / Full manual</td><td><a lang="zh-CN" href="{prefix}USER_MANUAL_ZH.html">阅读 15 章说明书</a></td><td><a href="{prefix}USER_MANUAL_EN.html">Read all 15 chapters</a></td></tr><tr><td>测试范围 / Validation</td><td><a lang="zh-CN" href="{prefix}ACCEPTANCE_1_3.html">验收记录</a></td><td><a href="{prefix}ACCEPTANCE_1_3_EN.html">Acceptance record</a></td></tr></tbody></table><p>App 界面仍为中文，英文文档附原按钮名称。The app interface is currently in Chinese; English guides include the actual Chinese button labels.</p><p>此包只有说明书，程序请到 <a href="https://github.com/cloudcocozh/nas-download/releases/tag/v1.3.0-beta.1">GitHub Releases</a> 下载。This archive contains documentation only; download the app and NAS installer from the release page.</p><p>支持 / Requirements: Linux x86_64 NAS, Docker Compose, SSH with Docker permissions; Android 8.0+. ARM 暂不支持 / ARM is not supported.</p></main></div></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    files = []
    for zh, en in PAIRS:
        for path, english in ((zh, False), (en, True)):
            output = path.with_suffix('.html')
            (ROOT / output).write_text(render(path, english), encoding='utf-8')
            files.extend((path, output))
    (ROOT / 'docs/START_HERE.html').write_text(entry(''), encoding='utf-8')
    files.append(Path('docs/START_HERE.html'))
    if args.archive:
        args.archive.parent.mkdir(parents=True, exist_ok=True)
        files.extend(p.relative_to(ROOT) for p in (ROOT / 'docs').glob('*.json'))
        files.extend(p.relative_to(ROOT) for p in (ROOT / 'licenses').rglob('*') if p.is_file())
        files.append(Path('LICENSE'))
        with zipfile.ZipFile(args.archive, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(set(files)):
                archive.write(ROOT / path, path.as_posix())
            archive.writestr('START_HERE.html', entry('docs/'))
            archive.writestr('先看这里.html', entry('docs/'))
        print(f'Bilingual manuals archive: {args.archive} ({args.archive.stat().st_size} bytes)')
    print(f'Rendered {len(PAIRS) * 2} guides in Chinese and English.')


if __name__ == '__main__':
    main()
