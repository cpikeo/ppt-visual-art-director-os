"""审计样稿：手工艺术指导，不是自动布局模板。数字来自 audit/ 的实际测试。
运行 vao.py plan brief.json 后由本稿明确落元素；不把 ghost 当真实 PowerPoint。
"""
BG, INK, MUTED, ACCENT = '#F4F3EF', '#142C3C', '#576773', '#BD442C'
COLORS = dict(background=BG, ink=INK, muted=MUTED, primary=INK,
              secondary='#73818A', accent=ACCENT)


def text(id, value, x, y, w, h, size=28, color='ink', **kw):
    return dict(id=id, type='text', text=value, x=x, y=y, width=w, height=h,
                size=size, color=color, line_height=1.2, **kw)


def rule(id, x, y, w, color='primary'):
    return dict(id=id, type='shape', shape='line', x=x, y=y, width=w, height=0,
                stroke=color, stroke_width=1)


def page(id, eyebrow, insight, elements, source):
    return dict(id=id, source_zone=dict(x=64, y=660, width=1152, height=48),
                page_intent=dict(insight=insight, focus='title'), elements=[
        text('eyebrow', eyebrow, 64, 32, 960, 28, 18, 'muted', role='eyebrow'),
        text('page_number', id[-2:], 1168, 32, 48, 28, 18, 'muted', role='page_number', align='right'),
        *elements, text('source', source, 64, 672, 1152, 28, 17, 'muted', role='source')])


SPEC = dict(canvas=dict(width=1280, height=720),
    theme=dict(colors=COLORS, fonts=dict(cn='Noto Sans CJK SC', latin='Arial')),
    slides=[
    page('s01', 'ENGINEERING × ART DIRECTION / 2026.10', '架构简单，判断不能简单', [
        text('title', '架构简单，\n判断不能简单。', 64, 152, 1088, 216, 76, bold=True),
        rule('rule', 64, 428, 128, 'accent'),
        text('sub', '删掉重复劳动，保留真实证据。', 64, 472, 1000, 56, 34),
        text('boundary', '仓库审计样稿 · 可编辑对象 · 目标 PowerPoint 尚待验收', 64, 564, 1100, 40, 23, 'muted'),
    ], '来源：2ec0b0e 基线与本工作区改动；本文是审计展示，不是商业预测。'),
    page('s02', '01 / 关系先于图形', '相加为100不是共同分母', [
        text('title', '相加为 100，\n不等于同一个整体。', 64, 112, 1100, 132, 48, bold=True),
        text('a', '60%', 64, 304, 448, 120, 92, bold=True),
        text('al', '缓解率', 64, 440, 448, 44, 30),
        text('b', '40%', 704, 304, 448, 120, 92, bold=True),
        text('bl', '不良反应发生率', 704, 440, 448, 44, 30),
        rule('sep', 64, 520, 1152),
        text('note', '同一患者可同时满足两者。先问事件是否互斥，再决定能否画饼图。', 64, 556, 1152, 64, 28),
    ], '来源：benchmark/holdout.json · H01；60% / 40% 为合成语义案例，非临床结果。'),
    page('s03', '02 / 方向只来自明确关系', '职责并列不是时间线', [
        text('title', '职责并列，\n不是先后顺序。', 64, 112, 1100, 132, 48, bold=True),
        text('subject_a', '青禾组', 64, 312, 288, 64, 40, bold=True),
        text('rel_a', '负责', 420, 324, 176, 44, 26, 'muted'),
        text('object_a', '质量测试', 736, 312, 480, 64, 40),
        rule('row', 64, 404, 1152),
        text('subject_b', '澄海组', 64, 440, 288, 64, 40, bold=True),
        text('rel_b', '负责', 420, 452, 176, 44, 26, 'muted'),
        text('object_b', '项目交付', 736, 440, 480, 64, 40),
        text('note', '没有已知上下级，就不补汇报线；没有时间轴，就不造流程。', 64, 560, 1152, 60, 28, 'muted'),
    ], '来源：显式关系回归测试；此页为合成组织关系示例，不代表实际组织。'),
    page('s04', '03 / 判断基准，不是视觉评分', '新边界案例通过由7增至12', [
        text('title', '五个误判被消除。\n视觉质量仍需另验。', 64, 112, 1100, 132, 48, bold=True),
        dict(id='evidence_chart', type='chart', chart_kind='column', x=64, y=284,
             width=720, height=332, role='focus',
             data=[dict(label='修改前', value=7), dict(label='修改后', value=12)],
             show_values=True, label_size=28, value_size=32, highlight=1,
             metric='固定边界案例通过数', source='audit/holdout-before.json 与 holdout-after.json',
             unit='例', period='本次审计', basis='同一组12个固定案例'),
        text('score', '12/12', 852, 312, 364, 104, 64, 'accent', bold=True),
        text('qualifier', '固定关系不变式\n不是独立盲评\n不是跨行业质量证明', 852, 440, 364, 152, 27, 'muted'),
    ], '来源：audit/holdout-{before,after}.json；案例预先写定，修复后转为回归集。'),
    page('s05', '04 / 一次判断，下游复用', '调用链不增加模型或新模块', [
        text('title', '保持一条生产链。', 64, 112, 1100, 76, 48, bold=True),
        text('think', 'THINK', 64, 280, 320, 72, 48, bold=True),
        text('build', 'BUILD', 464, 280, 320, 72, 48, bold=True),
        text('verify', 'VERIFY', 864, 280, 352, 72, 48, bold=True),
        text('think_body', '主张与证据\n保留未知关系', 64, 376, 320, 112, 30),
        text('build_body', '原生文字与图表\n作者决定几何', 464, 376, 320, 112, 30),
        text('verify_body', '硬门与字节凭证\n不代替视觉签署', 864, 376, 352, 112, 30),
        text('close', '删除不可靠的隐式缓存；复用显式快照与已验摘要。', 64, 564, 1152, 56, 30, 'accent'),
    ], '来源：scripts/vao.py · plan / check；架构与判断原则见 SKILL.md。'),
    page('s06', '05 / 中文排版必须落到成品', '数字与单位绑定不等于真实排版通过', [
        text('title', '186 公里，\n不能在单位前断开。', 64, 112, 1100, 132, 48, bold=True),
        text('specimen', '186\u00a0公里', 64, 316, 1152, 132, 96, bold=True),
        text('note', '不断行空格已写入原生文字；中文字体角色已绑定。', 64, 500, 1152, 52, 30),
        text('limit', '真实断行、字体回退与投影可读性，须在目标 PowerPoint 检查。', 64, 568, 1152, 48, 26, 'muted'),
    ], '来源：混排回归测试与 PPTX XML；本页 ghost 只提供结构预览。'),
    page('s07', '06 / 交付不能越过证据', '保留目标软件验收', [
        text('title', '代码可以通过。\n作品必须被看见。', 64, 144, 1100, 180, 64, bold=True),
        rule('rule', 64, 388, 128, 'accent'),
        text('action', '下一步：打开、编辑、另存，再重开。', 64, 440, 1152, 64, 36, bold=True),
        text('pending', '目标 PowerPoint 未验证 · 独立视觉盲评未开展', 64, 548, 1152, 48, 28, 'muted'),
    ], '交付边界：结构 PASS 不等于视觉终验；没有真实评审，不填写虚构评分。'),
])
