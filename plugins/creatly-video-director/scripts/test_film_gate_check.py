import json
import tempfile
import unittest
from pathlib import Path
from film_gate_check import Checker, load_nodes, main


def node(id, type, label, **kw):
    return dict(id=id, type=type, label=label, **kw)


def canvas(video_prompt, duration=6, refs=None, card_files=True, art_views=('正视图', '侧视图', '背视图')):
    views = [node(f'art-{i}', 'frame', f'亚瑟{v}', parentNode='art', frameFiles=[{'id': 'f'}])
             for i, v in enumerate(art_views)]
    return views + [
        node('card', 'element', '色卡', subType='custom'),
        node('card-img', 'frame', '色卡图', parentNode='card', frameFiles=[{'id': 'f'}] if card_files else []),
        node('tom', 'element', '汤米', subType='character'),
        node('tom-tri', 'frame', '汤米三视图', subType='tri_view', parentNode='tom', frameFiles=[{'id': 'f'}]),
        node('art', 'element', '亚瑟', subType='character'),
        node('shot', 'shot', 'S01'),
        node('g', 'group', '组｜S01'),
        node('frame', 'frame', 'F01', parentNode='g', parentIds=['shot'], content='画面 [@色卡]'),
        node('blk', 'frame', '站位｜酒吧｜入座', frameFiles=[{'id': 'f'}]),
        node('a1', 'audio', 'A01', parentNode='g', content='TOMMY: Just straw.'),
        node('v', 'video', 'V01', parentNode='g', parentIds=['frame', 'a1'], content=video_prompt,
             generationParams={'prompt': video_prompt, 'duration': duration,
                               'referenceResources': refs if refs is not None else [
                                   {'mediaType': 'IMAGE', 'sourceNodeId': 'blk'},
                                   {'mediaType': 'AUDIO', 'sourceNodeId': 'a1'}]}),
    ]


GOOD = ('[@汤米] 在画右、[@亚瑟] 在画左，保持轴线。【色卡】[@色卡]。【图1】站位。\n'
        '0—2秒｜中景：亚瑟坐下。\nHARD CUT\n2—6秒｜近景：汤米说【音频1】“Just straw.”')


def gates(nodes, **kw):
    args = dict(max_images=30, max_audios=10, max_duration=30, skip=set())
    args.update(kw)
    return {(level, gate) for level, gate, _, _ in Checker(nodes, **args).run()}


class GateTests(unittest.TestCase):
    def test_clean_video_passes(self):
        self.assertFalse({g for g in gates(canvas(GOOD)) if g[0] == 'FAIL'})

    def test_missing_color_card_mention_fails(self):
        self.assertIn(('FAIL', 'color-card-mention'), gates(canvas(GOOD.replace('[@色卡]', ''))))

    def test_id_style_mention_is_accepted(self):
        self.assertNotIn(('FAIL', 'unknown-subject'), gates(canvas(GOOD.replace('[@汤米]', '[@tom]'))))

    def test_subject_library_alias_is_accepted(self):
        nodes = canvas(GOOD.replace('[@汤米]', '[@6971856900043]'))
        subjects = {'subjectTypes': [{'subjects': [{'id': '6971856900043', 'elementId': '7245778825357', 'label': '汤米'}]}]}
        result = {(l, g) for l, g, _, _ in Checker(nodes, 30, 10, 30, set(), subjects).run()}
        self.assertNotIn(('FAIL', 'unknown-subject'), result)

    def test_formal_subject_id_resolves_from_node_detail(self):
        nodes = canvas(GOOD.replace('[@汤米]', '[@501]'))
        next(n for n in nodes if n['id'] == 'tom')['subjects'] = {'subject': {'elementId': '501'}}
        self.assertNotIn(('FAIL', 'unknown-subject'), gates(nodes))
        self.assertNotIn(('FAIL', 'subject-link'), gates(nodes))

    def test_explicit_unlinked_subject_is_rejected_even_with_picture(self):
        for detail in ({'subjects': {'subject': None}}, {'elementId': '0'}, {'elementId': None}):
            with self.subTest(detail=detail):
                nodes = canvas(GOOD)
                next(n for n in nodes if n['id'] == 'tom').update(detail)
                self.assertIn(('FAIL', 'subject-link'), gates(nodes))

    def test_unlinked_color_card_cannot_pass_with_child_picture(self):
        nodes = canvas(GOOD)
        next(n for n in nodes if n['id'] == 'card')['elementId'] = 0
        self.assertIn(('FAIL', 'subject-link'), gates(nodes))

    def test_empty_color_card_container_is_rejected(self):
        nodes = [n for n in canvas(GOOD) if n['id'] != 'card-img']
        self.assertIn(('FAIL', 'color-card'), gates(nodes))

    def test_encoded_mention_warns_and_card_line_counts(self):
        token = 'dXmax4a7kW1Q1JdaDxIoE56ln0id1gAJ3NCrJsJE1z9FOdq6wokweKg'
        result = gates(canvas(GOOD.replace('[@色卡]', f'[@{token}]')))
        self.assertIn(('WARN', 'unverified-mention'), result)
        self.assertNotIn(('FAIL', 'unknown-subject'), result)
        self.assertNotIn(('FAIL', 'color-card-mention'), result)

    def test_unknown_subject_fails(self):
        self.assertIn(('FAIL', 'unknown-subject'), gates(canvas(GOOD + '[@波莉]')))

    def test_empty_color_card_fails(self):
        self.assertIn(('FAIL', 'color-card'), gates(canvas(GOOD, card_files=False)))

    def test_character_needs_three_views(self):
        self.assertIn(('FAIL', 'character-views'), gates(canvas(GOOD, art_views=('正视图',))))

    def test_reference_index_beyond_inputs_fails(self):
        self.assertIn(('FAIL', 'ref-index'), gates(canvas(GOOD + '【图2】')))

    def test_image_limit(self):
        refs = [{'mediaType': 'IMAGE', 'sourceNodeId': 'blk'}] * 3
        self.assertIn(('FAIL', 'ref-limit'), gates(canvas(GOOD, refs=refs), max_images=2))

    def test_timing_gap_and_overrun_fail(self):
        self.assertIn(('FAIL', 'timing'), gates(canvas(GOOD.replace('2—6秒', '3—6秒'))))
        self.assertIn(('FAIL', 'duration-limit'), gates(canvas(GOOD, duration=40)))

    def test_equal_durations_and_missing_cut_warn(self):
        prompt = '[@色卡] 0—3秒 a\n3—6秒 b\n6—9秒 c'
        result = gates(canvas(prompt, duration=9))
        self.assertIn(('WARN', 'equal-durations'), result)
        self.assertIn(('WARN', 'hard-cut'), result)

    def test_shot_frame_reference_and_missing_blocking_warn(self):
        refs = [{'mediaType': 'IMAGE', 'sourceNodeId': 'frame'}, {'mediaType': 'AUDIO', 'sourceNodeId': 'a1'}]
        result = gates(canvas(GOOD, refs=refs))
        self.assertIn(('WARN', 'shot-frame-ref'), result)
        self.assertIn(('WARN', 'blocking'), result)

    def test_dialogue_must_be_verbatim(self):
        self.assertIn(('WARN', 'dialogue'), gates(canvas(GOOD.replace('Just straw.', 'Only straw.'))))

    def test_subject_edge_and_path_fail(self):
        nodes = canvas(GOOD + ' /Users/me/ref.png')
        nodes[-1]['parentIds'].append('tom')
        result = gates(nodes)
        self.assertIn(('FAIL', 'subject-edge'), result)
        self.assertIn(('FAIL', 'prompt-hygiene'), result)

    def test_skip_marks_gate_as_waived(self):
        result = gates(canvas(GOOD, art_views=('正视图',)), skip={'character-views'})
        self.assertIn(('SKIP', 'character-views'), result)
        self.assertNotIn(('FAIL', 'character-views'), result)

    def test_loads_tool_result_wrapper_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'canvas.json'
            nodes = canvas(GOOD, art_views=('正视图',))
            wrapped = [{'type': 'text', 'text': '[Resource link] ...'},
                       {'type': 'text', 'text': json.dumps({'output': {'nodes': nodes}})}]
            path.write_text(json.dumps(wrapped), encoding='utf-8')
            self.assertEqual(len(load_nodes(str(path))), len(nodes))
            self.assertEqual(main([str(path), '--skip', 'character-views']), 0)
            self.assertEqual(main([str(path)]), 1)

    def test_context_pagination_requires_full_same_version_and_all_nodes(self):
        page1 = {'project': {'id': '101', 'currentVersion': 9}, 'scope': {'kind': 'FULL'},
                 'detail': 'full', 'complete': False, 'nextCursor': 'cursor', 'totalNodes': 2,
                 'nodes': [{'id': '1', 'type': 'video', 'label': 'A'}]}
        page2 = dict(page1, complete=True, nextCursor=None, nodes=[{'id': '2', 'type': 'video', 'label': 'B'}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'canvas.json'
            path.write_text(json.dumps({'pages': [page1, page2]}), encoding='utf-8')
            self.assertEqual([n['id'] for n in load_nodes(str(path))], ['1', '2'])
            for bad in [page1, dict(page1, detail='brief', complete=True)]:
                path.write_text(json.dumps(bad), encoding='utf-8')
                with self.assertRaises(ValueError): load_nodes(str(path))
                self.assertEqual(main([str(path)]), 2)
            for change in [dict(page2, project={'id': '101', 'currentVersion': 10}),
                           dict(page2, nodes=page1['nodes']), dict(page2, totalNodes=3),
                           dict(page2, scope={'kind': 'FILTERED', 'nodeType': 'video'}),
                           dict(page2, detail='compact')]:
                path.write_text(json.dumps({'pages': [page1, change]}), encoding='utf-8')
                with self.assertRaises(ValueError): load_nodes(str(path))


if __name__ == '__main__':
    unittest.main()
