"""生成前门禁：局部生成读取 getNodes；整片审查读取完整 full 画布快照。

用法：
    python3 scripts/film_gate_check.py canvas.json
    python3 scripts/film_gate_check.py batch.json --scope batch --nodes <id>,<id>

canvas.json 可以是完整 full 回执，或 {"pages": [同一版本的全部分页回执]}；也兼容旧版完整回执。
batch.json 为 {"reads": [同一项目/版本的 getNodes 回执], "contextNodeIds": [本批色卡等节点ID]}。
FAIL 为强制关卡，存在未豁免的 FAIL 时退出码为 1；WARN 只提示。
用户明确要求跳过某项时，用 --skip 传入关卡名，输出里会标为「用户豁免」。
"""
import argparse
import json
import re
import sys

FAIL, WARN = 'FAIL', 'WARN'
COLOR_CARD = '色卡'
MENTION = re.compile(r'\[@([^\]]+)\]')
IMG_INDEX = re.compile(r'【图(\d+)】')
AUDIO_INDEX = re.compile(r'【音频(\d+)】')
BLOCK = re.compile(r'(\d+(?:\.\d+)?)\s*[—–\-~至到]\s*(\d+(?:\.\d+)?)\s*(?:秒|s)')
CUT = re.compile(r'HARD CUT|Cut on action', re.I)
PATH = re.compile(r'/Users/|[A-Za-z]:[\\/]|\S+\.(?:png|jpe?g|webp|mp4|mov|wav|mp3)\b', re.I)
CONTEXT_WORDS = ('上一段', '上一镜', '同上', '保持之前', '和前面一样', '如前所述')
AXIS_WORDS = ('轴线', '画面左', '画面右', '画左', '画右')
MUSIC = re.compile(r'(背景音乐|配乐|BGM)', re.I)
OPAQUE_REF = re.compile(r'^[A-Za-z0-9_-]{32,}$')
CARD_LINE = re.compile(r'【色卡】\s*\[@')


def unwrap_canvas(data):
    if isinstance(data, list):
        for item in data:
            try:
                data = json.loads(item.get('text', ''))
                break
            except (ValueError, AttributeError):
                continue
    for key in ('structuredContent', 'output'):
        if isinstance(data, dict) and key in data and isinstance(data[key], dict):
            data = data[key]
    if not isinstance(data, dict) or not isinstance(data.get('nodes'), list):
        raise ValueError('缺少画布 nodes；请保存真实 MCP 回执')
    return data


def load_canvas(path):
    """Full snapshot or {pages:[...]}; reject partial/brief reads instead of passing an incomplete gate."""
    with open(path, encoding='utf-8') as f:
        source = json.load(f)
    if isinstance(source, dict) and 'pages' in source:
        raw_pages = source['pages']
        if not isinstance(raw_pages, list) or not raw_pages:
            raise ValueError('pages 必须是完整 full 上下文分页回执')
        pages = [unwrap_canvas(page) for page in raw_pages]
        first = pages[0]
        if not isinstance(first.get('project'), dict) or 'currentVersion' not in first['project']:
            raise ValueError('分页缺少项目或画布版本')
        nodes, subjects, seen = [], {}, set()
        for index, page in enumerate(pages):
            if page.get('project') != first['project'] or page.get('scope') != first.get('scope'):
                raise ValueError('分页项目、版本或筛选范围不一致；请重新读取')
            if page.get('detail') != 'full' or (page.get('scope') or {}).get('kind') != 'FULL':
                raise ValueError('门禁需要 full 的完整范围，brief/compact 或类型筛选页不能冒充全量')
            if page.get('totalNodes') != first.get('totalNodes') or page.get('complete') is not (index == len(pages) - 1):
                raise ValueError('分页未读完或计数不一致；请继续 nextCursor')
            if index < len(pages) - 1 and not page.get('nextCursor'):
                raise ValueError('分页缺少 nextCursor')
            if index == len(pages) - 1 and page.get('nextCursor') is not None:
                raise ValueError('最后一页仍有 nextCursor')
            for node in page['nodes']:
                if node['id'] in seen:
                    raise ValueError('分页节点重复；请重新读取')
                seen.add(node['id'])
                nodes.append(node)
            if page.get('subjects'):
                subjects = page['subjects']
        if len(nodes) != first.get('totalNodes'):
            raise ValueError('分页节点数量不完整，不能执行门禁')
        return nodes, subjects
    data = unwrap_canvas(source)
    if data.get('complete') is False:
        raise ValueError('上下文只有一页；局部生成请用 getNodes 回执和 --scope batch --nodes；只有整片审查才收齐 full 的 pages')
    if data.get('detail') in ('brief', 'compact'):
        raise ValueError('概要不含生成参数；门禁需要 full 回执')
    return data['nodes'], data.get('subjects') or {}


def load_nodes(path):
    return load_canvas(path)[0]


def load_batch(path, only):
    """Normalize field-projected getNodes receipts, keeping only targets and their dependencies."""
    if not only:
        raise ValueError('batch 必须用 --nodes 明确本批生成节点')
    with open(path, encoding='utf-8') as f:
        source = json.load(f)
    reads = source.get('reads') if isinstance(source, dict) else None
    if not isinstance(reads, list) or not reads:
        raise ValueError('batch 需要 reads 数组，保存真实 getNodes 回执；不需要整张 full 画布')
    merged, aliases, project = {}, [], None
    for raw in reads:
        read = unwrap_canvas(raw)
        p = read.get('project') or {}
        identity = (p.get('id'), p.get('currentVersion'))
        if None in identity or read.get('detail') != 'full' or not isinstance(read.get('fields'), list):
            raise ValueError('batch 需要带项目版本和 fields 的 getNodes(detail="full") 真实回执')
        if project is not None and project != identity:
            raise ValueError('本批读取的项目或版本不一致；只重新读取本批受影响节点')
        project = identity
        aliases.extend(read.get('mentionSubjects') or [])
        for n in read['nodes']:
            if not isinstance(n.get('id'), str) or not n['id']:
                raise ValueError('节点 ID 必须保留为字符串')
            existing = merged.setdefault(n['id'], {})
            for key, value in n.items():
                if key in existing and existing[key] != value:
                    raise ValueError(f'节点 {n["id"]} 的重复回执冲突')
                existing[key] = value
    by = {}
    for id, n in merged.items():
        details = n.get('details')
        if not isinstance(details, dict) or not {'type', 'label', 'subType', 'parentNode', 'parentIds'} <= details.keys():
            raise ValueError(f'节点 {id} 缺少完整 details')
        if not isinstance(details['parentIds'], list) or ('media' in n and not isinstance(n['media'], list)):
            raise ValueError(f'节点 {id} 的关系或媒体格式无效')
        node = dict(n, **details)
        if 'media' in n:
            for media_type, field in [('IMAGE', 'frameFiles'), ('VIDEO', 'videoFiles'), ('AUDIO', 'audioFiles')]:
                node[field] = [m['fileRef'] for m in n['media'] if m.get('mediaType') == media_type]
        if node['type'] == 'element' and 'subjects' in node and node['subjects'] is None:
            node['subjects'] = {'subject': None}
        by[id] = node
    contexts = source.get('contextNodeIds') or []
    if not isinstance(contexts, list) or any(not isinstance(id, str) for id in contexts):
        raise ValueError('contextNodeIds 必须是本批上下文节点的字符串 ID 数组')
    needed = set(only) | set(contexts)
    missing = needed - by.keys()
    if missing:
        raise ValueError(f'未读取本批节点：{", ".join(sorted(missing))}')
    alias_nodes = {}
    for a in aliases:
        for key in ('mentionId', 'elementId', 'label'):
            if a.get(key) and a.get('elementNodeId'):
                alias_nodes[a[key]] = a['elementNodeId']
    for id in only:
        n = by[id]
        if n['type'] not in ('frame', 'video'):
            raise ValueError(f'本批节点 {id} 不是分镜或视频')
        needed.update(n.get('parentIds') or [])
        if n.get('parentNode'):
            needed.add(n['parentNode'])
        for r in (n.get('generationParams') or {}).get('referenceResources') or []:
            if r.get('sourceNodeId'):
                needed.add(r['sourceNodeId'])
        for r in (n.get('subjects') or {}).get('references') or []:
            if r.get('elementNodeId'):
                needed.add(r['elementNodeId'])
        for ref in MENTION.findall(prompt_of(n)):
            if ref in alias_nodes:
                needed.add(alias_nodes[ref])
            else:
                needed.update(e['id'] for e in by.values() if e['type'] == 'element' and ref in (e['id'], e['label']))
    missing = needed - by.keys()
    if missing:
        raise ValueError(f'未读取本批依赖：{", ".join(sorted(missing))}；用 getNodes 补读，不要读取全画布')
    # Asset pictures and the parent of a source picture are relevant; unrelated subject libraries are not.
    needed.update(n['parentNode'] for id, n in by.items() if id in needed and n.get('parentNode') in by)
    elements = {id for id in needed if by[id]['type'] == 'element'}
    needed.update(id for id, n in by.items() if n.get('parentNode') in elements)
    for id in needed:
        n = by[id]
        required = {'details'}
        if id in only:
            required |= {'content', 'generationParams', 'media', 'subjects'}
        elif n['type'] == 'element':
            required |= {'media', 'subjects'}
        elif n['type'] in ('frame', 'video', 'audio'):
            required.add('media')
            if n['type'] == 'audio':
                required.add('content')
        missing = required - n.keys()
        if missing:
            raise ValueError(f'节点 {id} 缺少字段 {", ".join(sorted(missing))}；用 getNodes 补读，缺失不能当作空值')
    return [n for id, n in by.items() if id in needed], {'elements': aliases}


def subject_aliases(subjects):
    """主体库里的 subject id / elementId → 主体名；兼容新旧两种快照格式。"""
    groups = []
    for t in subjects.get('subjectTypes') or []:
        groups.extend(t.get('subjects') or [])
    for key, value in subjects.items():
        if key not in ('project', 'subjectTypes', 'unlinked') and isinstance(value, list):
            groups.extend(value)
    aliases = {}
    for item in groups:
        for ref in (item.get('id'), item.get('elementId'), item.get('subjectNodeId'), item.get('mentionId')):
            if ref and item.get('label'):
                aliases[str(ref)] = item['label']
    return aliases


def norm(text):
    return re.sub(r'[\W_]+', '', text or '').lower()


def prompt_of(node):
    gp = node.get('generationParams') or {}
    return gp.get('prompt') or node.get('content') or ''


class Checker:
    def __init__(self, nodes, max_images, max_audios, max_duration, skip, subjects=None):
        self.nodes = nodes
        self.by = {n['id']: n for n in nodes}
        self.max_images, self.max_audios, self.max_duration = max_images, max_audios, max_duration
        self.skip = skip
        self.results = []
        self.elements = {n.get('label') or n['id']: n for n in nodes if n['type'] == 'element'}
        self.element_by_ref = dict(self.elements)
        self.element_by_ref.update({e['id']: e for e in self.elements.values()})
        for element in self.elements.values():
            subject = (element.get('subjects') or {}).get('subject') or {}
            ref = subject.get('elementId') or element.get('elementId')
            if ref and str(ref) != '0':
                self.element_by_ref[str(ref)] = element
        for ref, label in subject_aliases(subjects or {}).items():
            if label in self.elements:
                self.element_by_ref[ref] = self.elements[label]
        for alias in (subjects or {}).get('elements') or []:
            element = self.by.get(alias.get('elementNodeId'))
            if element and element['type'] == 'element':
                for key in ('mentionId', 'elementId', 'id', 'label'):
                    if alias.get(key):
                        self.element_by_ref[alias[key]] = element
        self.subject_ids = set(e['id'] for e in self.elements.values())
        self.subject_ids |= {n['id'] for n in nodes if n.get('parentNode') in self.subject_ids}
        self.card = next((e for name, e in self.elements.items() if COLOR_CARD in name), None)

    def add(self, level, gate, node, msg):
        if gate in self.skip:
            level = 'SKIP'
        self.results.append((level, gate, node['label'] if node else '项目', msg))

    def children(self, element):
        return [n for n in self.nodes if n.get('parentNode') == element['id'] and n['type'] == 'frame']

    def mentions(self, text):
        return [self.element_by_ref.get(m) for m in MENTION.findall(text)], MENTION.findall(text)

    @staticmethod
    def unlinked(element):
        """Only reject explicit missing links; absent fields need a fresh subject read."""
        detail = element.get('subjects')
        if isinstance(detail, dict) and 'subject' in detail:
            return not detail['subject'] or str(detail['subject'].get('elementId')) == '0'
        if 'elementId' in element:
            return element['elementId'] is None or str(element['elementId']) == '0'
        return False

    def check_project(self):
        for e in self.elements.values():
            if not self.children(e) and not e.get('frameFiles'):
                self.add(WARN, 'subject-images', e, '快照里看不到这个主体的图片（主体库图片不随快照返回），生成前请在画布上确认已上传')
        if self.card is not None and self.unlinked(self.card):
            self.add(FAIL, 'subject-link', self.card, '色卡容器未关联有效正式主体，请先核对主体库登记')
        if self.card is not None and not self.card.get('frameFiles') \
                and not any(n.get('frameFiles') for n in self.children(self.card)):
            self.add(FAIL, 'color-card', self.card, '色卡主体里没有已生成的图片，分镜前必须先有色卡')
        for e in self.elements.values():
            if e.get('subType') != 'character' or not self.children(e):
                continue
            views = 0
            for n in self.children(e):
                if n.get('frameFiles'):
                    views += 3 if n.get('subType') == 'tri_view' else 1
            if views < 3:
                self.add(FAIL, 'character-views', e, f'只有 {views} 个视角，视频前每个角色至少 3 个视角')

    def check_common(self, node, asset=False, strict_mentions=False):
        text = prompt_of(node)
        found, raw = self.mentions(text)
        opaque = 0
        for element, name in zip(found, raw):
            if element is None and OPAQUE_REF.match(name) and not strict_mentions:
                opaque += 1
            elif element is None:
                self.add(FAIL, 'unknown-subject', node, f'提及的主体 [@{name}] 不存在')
            elif self.unlinked(element):
                self.add(FAIL, 'subject-link', node, f'提及的主体「{element["label"]}」未关联有效主体库记录')
        if opaque:
            self.add(WARN, 'unverified-mention', node, f'{opaque} 处 @ 是站点保存后的编码 ID，脚本无法核对对应哪个主体，请在画布上确认')
        if not asset and self.card is not None and self.card not in found and not CARD_LINE.search(text):
            self.add(FAIL, 'color-card-mention', node, f'提示词没有 [@{self.card["label"]}]')
        parent = self.by.get(node.get('parentNode') or '')
        if not asset and (not parent or parent['type'] != 'group'):
            self.add(FAIL, 'group', node, '没有放进本镜组')
        for pid in node.get('parentIds') or []:
            if pid in self.subject_ids:
                self.add(FAIL, 'subject-edge', node, f'连线到了主体「{self.by[pid]["label"]}」，主体只 @ 不连线')
        if PATH.search(text):
            self.add(FAIL, 'prompt-hygiene', node, '提示词里出现了本地路径或文件名')
        for word in CONTEXT_WORDS:
            if word in text:
                self.add(WARN, 'standalone', node, f'出现依赖上下文的说法「{word}」，每段提示词应独立成立')

    def check_video(self, node):
        text = prompt_of(node)
        gp = node.get('generationParams') or {}
        refs = gp.get('referenceResources') or []
        images = [r for r in refs if r.get('mediaType') == 'IMAGE']
        audios = [r for r in refs if r.get('mediaType') == 'AUDIO']
        if len(images) > self.max_images:
            self.add(FAIL, 'ref-limit', node, f'参考图 {len(images)} 张，超过上限 {self.max_images}')
        if len(audios) > self.max_audios:
            self.add(FAIL, 'ref-limit', node, f'参考音频 {len(audios)} 条，超过上限 {self.max_audios}')
        top_img = max(map(int, IMG_INDEX.findall(text)), default=0)
        top_audio = max(map(int, AUDIO_INDEX.findall(text)), default=0)
        if top_img > len(images):
            self.add(FAIL, 'ref-index', node, f'提示词引用到【图{top_img}】，实际只传了 {len(images)} 张图')
        if top_audio > len(audios):
            self.add(FAIL, 'ref-index', node, f'提示词引用到【音频{top_audio}】，实际只传了 {len(audios)} 条音频')
        labels = []
        for r in images:
            src = self.by.get(r.get('sourceNodeId') or '')
            label = (src or {}).get('label') or r.get('label') or ''
            labels.append(label)
            if src and src['type'] == 'frame' and src['id'] not in self.subject_ids and '站位' not in label:
                self.add(WARN, 'shot-frame-ref', node, f'垫了镜头画面「{label[:20]}」；默认只垫资产，正反打写进提示词')
        if not any('站位' in lb for lb in labels):
            self.add(WARN, 'blocking', node, '没有垫站位图')
        characters = {e['id'] for e in self.mentions(text)[0] if e and e.get('subType') == 'character'}
        if len(characters) >= 2 and not any(w in text for w in AXIS_WORDS):
            self.add(WARN, 'axis', node, '多人戏没有写轴线或谁在画左、谁在画右')
        for m in MUSIC.finditer(text):
            before = text[max(0, m.start() - 6):m.start()]
            if not re.search(r'无|禁止|不要|不|没有', before):
                self.add(WARN, 'music', node, '提示词要求了背景音乐；默认不加音乐')
                break
        self.check_timing(node, text, gp.get('duration'))
        for r in audios:
            src = self.by.get(r.get('sourceNodeId') or '')
            line = re.sub(r'^[^:：]{1,20}[:：]\s*', '', (src or {}).get('content') or '')
            if line and norm(line) not in norm(text):
                self.add(WARN, 'dialogue', node, f'音频「{(src or {}).get("label", "")[:16]}」的台词没有逐字出现在提示词里')

    def check_timing(self, node, text, duration):
        blocks = [(float(a), float(b)) for a, b in BLOCK.findall(text)]
        if duration and duration > self.max_duration:
            self.add(FAIL, 'duration-limit', node, f'时长 {duration} 秒，超过模型上限 {self.max_duration} 秒')
        if not blocks:
            return
        if abs(blocks[0][0]) > 0.05:
            self.add(FAIL, 'timing', node, f'第一个镜头块从 {blocks[0][0]} 秒开始，应从 0 开始')
        for (a1, b1), (a2, b2) in zip(blocks, blocks[1:]):
            if abs(b1 - a2) > 0.05:
                self.add(FAIL, 'timing', node, f'镜头块 {a1}-{b1} 与 {a2}-{b2} 不连续')
        if duration and abs(blocks[-1][1] - duration) > 0.05:
            self.add(FAIL, 'timing', node, f'镜头块结束于 {blocks[-1][1]} 秒，节点时长是 {duration} 秒')
        lengths = [round(b - a, 2) for a, b in blocks]
        if len(lengths) >= 3 and len(set(lengths)) == 1:
            self.add(WARN, 'equal-durations', node, f'{len(lengths)} 个镜头都是 {lengths[0]} 秒，时长应随台词和动作错落')
        for length in lengths:
            if length > 8 or length < 1.5:
                self.add(WARN, 'shot-length', node, f'有镜头块 {length} 秒，单镜通常 2–8 秒')
                break
        if len(blocks) >= 2 and 'NO CUT' not in text and len(CUT.findall(text)) < len(blocks) - 1:
            self.add(WARN, 'hard-cut', node, f'{len(blocks)} 个镜头块，镜头块之间应独立一行写 HARD CUT')

    def is_shot_frame(self, node):
        shots = {n['id'] for n in self.nodes if n['type'] == 'shot'}
        if any(p in shots for p in node.get('parentIds') or []):
            return True
        group = node.get('parentNode')
        return any(n.get('parentNode') == group and any(p in shots for p in n.get('parentIds') or [])
                   for n in self.nodes)

    def run(self, only=None, batch=False):
        if only and only - self.by.keys():
            self.add(FAIL, 'missing-node', None, '待检查节点不存在：' + ', '.join(sorted(only - self.by.keys())))
        self.check_project()
        for node in self.nodes:
            if only and node['id'] not in only:
                continue
            if node['type'] == 'video':
                self.check_common(node, strict_mentions=batch)
                self.check_video(node)
            elif node['type'] == 'frame' and batch:
                self.check_common(node, asset=node['id'] in self.subject_ids, strict_mentions=True)
            elif node['type'] == 'frame' and not node.get('subType') and node['id'] not in self.subject_ids \
                    and self.is_shot_frame(node):
                self.check_common(node)
        return self.results


def main(argv=None):
    parser = argparse.ArgumentParser(description='分镜与视频生成前门禁')
    parser.add_argument('canvas', help='本批 getNodes 回执 JSON，或完整画布快照 JSON')
    parser.add_argument('--scope', choices=('project', 'batch'), default='project', help='batch 只检查本批及真实依赖；project 审查整片')
    parser.add_argument('--nodes', help='只检查这些节点 ID（逗号分隔），默认检查全部分镜与视频')
    parser.add_argument('--skip', default='', help='用户明确豁免的关卡名（逗号分隔）')
    parser.add_argument('--max-images', type=int, default=30, help='模型参考图上限，以 listGenerationModels 为准')
    parser.add_argument('--max-audios', type=int, default=10)
    parser.add_argument('--max-duration', type=float, default=30)
    parser.add_argument('--json', action='store_true', help='以 JSON 输出结果')
    args = parser.parse_args(argv)
    skip = {s.strip() for s in args.skip.split(',') if s.strip()}
    only = {s.strip() for s in args.nodes.split(',')} if args.nodes else None
    try:
        nodes, subjects = load_batch(args.canvas, only) if args.scope == 'batch' else load_canvas(args.canvas)
    except (ValueError, KeyError, TypeError) as exc:
        if args.json:
            code = 'incomplete_batch_context' if args.scope == 'batch' else 'incomplete_canvas_context'
            print(json.dumps({'error': code, 'message': str(exc)}, ensure_ascii=False))
        else:
            print(f'无法执行门禁：{exc}', file=sys.stderr)
        return 2
    results = Checker(nodes, args.max_images, args.max_audios, args.max_duration, skip, subjects).run(only, batch=args.scope == 'batch')
    fails = [r for r in results if r[0] == FAIL]
    if args.json:
        print(json.dumps([dict(zip(('level', 'gate', 'node', 'message'), r)) for r in results], ensure_ascii=False, indent=2))
    else:
        for level, gate, label, msg in results:
            tag = '用户豁免' if level == 'SKIP' else level
            print(f'{tag}\t{gate}\t{label}\t{msg}')
        warns = sum(1 for r in results if r[0] == WARN)
        print(f'\n结论：{"未通过" if fails else "通过"}（FAIL {len(fails)}，WARN {warns}，豁免 {sum(1 for r in results if r[0] == "SKIP")}）')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
