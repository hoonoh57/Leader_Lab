# -*- coding: utf-8 -*-
"""Generate SuperTrend Regime Discovery dashboard v6.

v6 keeps v5 rendering and fixes the left-list click flow.
It also adds an explanation layer so the user can immediately understand that:
    - this is not a buy recommendation screen
    - one row means one SuperTrend uptrend segment
    - GREAT / GOOD / BAD are regime-quality labels
    - the immediate task is chart-consistency verification
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.review import generate_supertrend_regime_discovery_dashboard_v2 as v2
from src.review import generate_supertrend_regime_discovery_dashboard_v5 as v5


CLARITY_PATCH = r"""
<style>
  .mission-box-v6{
    border:1px solid #475569;
    background:#111827;
    border-radius:10px;
    padding:12px;
    margin:0 0 10px 0;
    line-height:1.55;
    font-size:13px;
    color:#dbeafe;
  }
  .mission-box-v6 b{color:#fbbf24;}
  .quality-badge-v6{
    display:inline-block;
    min-width:62px;
    text-align:center;
    padding:2px 8px;
    border-radius:999px;
    font-size:11px;
    font-weight:700;
    margin-right:6px;
    background:#1e293b;
  }
  .quality-GREAT{color:#fbbf24;border:1px solid #f59e0b;}
  .quality-GOOD{color:#86efac;border:1px solid #22c55e;}
  .quality-BAD{color:#fca5a5;border:1px solid #ef4444;}
  .quality-NEUTRAL{color:#93c5fd;border:1px solid #3b82f6;}
  .purpose-card-v6 .v{font-size:14px !important;line-height:1.45;}
</style>
<script>
(function(){
  if (window.__leaderLabDashboardV6ClarityApplied) return;
  window.__leaderLabDashboardV6ClarityApplied = true;

  function qualityOf(seg){
    if (Number(seg.label_st_gain_10pct) === 1) return 'GREAT';
    if (Number(seg.label_st_gain_5pct) === 1) return 'GOOD';
    if (Number(seg.label_st_fail_1pct) === 1 || Number(seg.label_st_end_negative) === 1) return 'BAD';
    return 'NEUTRAL';
  }
  window.v6QualityOf = qualityOf;

  function insertMissionBox(){
    const main = document.querySelector('.main') || document.querySelector('main');
    if (!main || document.getElementById('missionBoxV6')) return;
    const box = document.createElement('div');
    box.id = 'missionBoxV6';
    box.className = 'mission-box-v6';
    box.innerHTML = '<b>분석 목적:</b> 이 화면은 매수추천 화면이 아닙니다. <b>한 행 = 한 종목의 하루가 아니라, 특정 ST 파라미터의 상승구간 1개</b>입니다. 현재 목표는 GREAT/GOOD/BAD ST 상승구간의 차이를 찾고, DB 음영이 실제 ST Up 선과 일치하는지 검증하는 것입니다. 기본 화면은 일부러 <b>Great >= 10%</b>부터 보여줍니다.';
    main.insertBefore(box, main.firstChild);
  }

  function patchDefaultView(){
    const view = document.getElementById('viewSelect');
    if (!view || view.__v6DefaultPatched) return;
    view.__v6DefaultPatched = true;
    const options = Array.from(view.options || []);
    const great = options.find(function(o){ return String(o.value).toLowerCase().includes('great') || String(o.text).toLowerCase().includes('great'); });
    if (great) view.value = great.value;
  }

  function patchHeader(){
    const header = document.querySelector('header h1');
    if (header) {
      header.textContent = 'SuperTrend Regime Discovery v6 — ST 상승구간 품질분류 / 차트 정합성 검증';
    }
  }

  function decorateListRows(){
    if (typeof segments === 'undefined' || typeof segmentList === 'undefined') return;
    const rows = Array.from(segmentList.querySelectorAll('.seg'));
    rows.forEach(function(el){
      if (el.__v6QualityDecorated) return;
      const idAttr = el.getAttribute('data-segment-id');
      let seg = null;
      if (idAttr) seg = segments.find(function(s){ return Number(s.id) === Number(idAttr); });
      if (!seg) {
        const text = el.textContent || '';
        seg = segments.find(function(s){ return text.indexOf(String(s.code)) >= 0 && text.indexOf(String(s.trade_date)) >= 0; });
      }
      if (!seg) return;
      const q = qualityOf(seg);
      const title = el.querySelector('.title') || el.firstElementChild;
      if (title && !title.querySelector('.quality-badge-v6')) {
        const badge = document.createElement('span');
        badge.className = 'quality-badge-v6 quality-' + q;
        badge.textContent = q;
        title.insertBefore(badge, title.firstChild);
      }
      el.__v6QualityDecorated = true;
    });
  }

  function addPurposeCards(seg){
    const panel = document.getElementById('infoPanel');
    if (!panel || !seg) return;
    const q = qualityOf(seg);
    const cards = document.createElement('div');
    cards.className = 'card purpose-card-v6';
    cards.innerHTML = '<div class="k">현재 선택 구간의 의미</div><div class="v"><span class="quality-badge-v6 quality-' + q + '">' + q + '</span> 매수추천이 아니라 과거 ST 상승구간 샘플입니다. 이 샘플이 왜 GREAT/GOOD/BAD인지 차트와 feature로 확인합니다.</div>';
    const old = document.getElementById('purposeCardV6');
    if (old) old.remove();
    cards.id = 'purposeCardV6';
    panel.insertBefore(cards, panel.firstChild);
  }

  function patchSelectSegment(){
    if (typeof selectSegment !== 'function' || typeof segments === 'undefined') return false;
    if (window.__leaderLabDashboardV6SelectClarityPatched) return true;
    window.__leaderLabDashboardV6SelectClarityPatched = true;
    const originalSelect = selectSegment;
    selectSegment = function(id, rerender=true){
      originalSelect(id, rerender);
      const seg = segments.find(function(s){ return Number(s.id) === Number(id); });
      addPurposeCards(seg);
      window.setTimeout(decorateListRows, 50);
    };
    window.selectSegment = selectSegment;
    return true;
  }

  function tick(){
    insertMissionBox();
    patchHeader();
    patchDefaultView();
    patchSelectSegment();
    decorateListRows();
    window.setTimeout(tick, 300);
  }
  tick();
})();
</script>
"""


CLICK_PATCH = r"""
<script>
(function(){
  if (window.__leaderLabDashboardV6ClickPatchApplied) return;
  window.__leaderLabDashboardV6ClickPatchApplied = true;

  function patchWhenReady(){
    if (typeof segments === 'undefined' || typeof candles === 'undefined' || typeof candleMeta === 'undefined') {
      window.setTimeout(patchWhenReady, 100);
      return;
    }
    if (typeof filteredSegments !== 'function' || typeof paramOf !== 'function' || typeof keyOf !== 'function' || typeof fmt !== 'function') {
      window.setTimeout(patchWhenReady, 100);
      return;
    }

    function hasPrevSessionDisplay(seg){
      const arr = candles[keyOf(seg)] || [];
      return arr.some(function(r){ return Number(r.is_prev_session_display) === 1; });
    }

    function firstPrevDateForParam(paramKey){
      for (let i = 0; i < segments.length; i++) {
        const s = segments[i];
        if (paramOf(s) !== paramKey) continue;
        if (hasPrevSessionDisplay(s)) return s.trade_date;
      }
      return 'ALL';
    }

    function segmentCssClass(s){
      return s.id === selectedId ? 'seg active' : 'seg';
    }

    function renderSegmentRow(s){
      const q = (window.v6QualityOf ? window.v6QualityOf(s) : '');
      const retCls = Number(s.st_up_max_return_pct) >= 5 ? 'good' : ((Number(s.label_st_fail_1pct)===1 || Number(s.label_st_end_negative)===1) ? 'bad' : 'warn');
      const prevBadge = hasPrevSessionDisplay(s) ? '<span class="pill">prev</span>' : '<span class="pill">no-prev</span>';
      const qualityBadge = q ? '<span class="quality-badge-v6 quality-' + q + '">' + q + '</span>' : '';
      return `<div class="${segmentCssClass(s)}" data-segment-id="${s.id}"><div class="title">${qualityBadge}${s.trade_date} ${s.code} ${s.name||''} <span class="pill">#${s.segment_no}</span><span class="pill">ST ${paramOf(s)}</span>${prevBadge}</div><div class="meta">max <span class="${retCls}">${fmt(s.st_up_max_return_pct)}%</span> / end ${fmt(s.st_up_end_return_pct)}% / bars ${s.st_up_bars} / startOpen ${fmt(s.start_from_day_open_pct)}% / segAmt ${fmt(Number(s.segment_amount)/100000000)}억</div></div>`;
    }

    selectSegment = function(id, rerender=true){
      selectedId = Number(id);
      const s = segments.find(function(x){ return Number(x.id) === Number(id); });
      if (!s) return;
      renderInfo(s);
      renderChart(s);
      if (rerender) renderList();
      if (window.__leaderLabDashboardV6ClarityApplied && typeof window.v6QualityOf === 'function') {
        const panel = document.getElementById('infoPanel');
        const old = document.getElementById('purposeCardV6');
        if (old) old.remove();
        if (panel) {
          const q = window.v6QualityOf(s);
          const card = document.createElement('div');
          card.id = 'purposeCardV6';
          card.className = 'card purpose-card-v6';
          card.innerHTML = '<div class="k">현재 선택 구간의 의미</div><div class="v"><span class="quality-badge-v6 quality-' + q + '">' + q + '</span> 매수추천이 아니라 과거 ST 상승구간 샘플입니다. 이 샘플이 왜 GREAT/GOOD/BAD인지 차트와 feature로 확인합니다.</div>';
          panel.insertBefore(card, panel.firstChild);
        }
      }
    };
    window.selectSegment = selectSegment;

    renderList = function(){
      const dateValue = document.getElementById('dateSelect') ? document.getElementById('dateSelect').value : 'ALL';
      let list = filteredSegments();
      if (dateValue === 'ALL') {
        list = list.filter(hasPrevSessionDisplay);
      }
      segmentList.innerHTML = list.map(renderSegmentRow).join('');
      const rows = Array.from(segmentList.querySelectorAll('[data-segment-id]'));
      rows.forEach(function(el){
        el.addEventListener('click', function(){
          const id = Number(el.getAttribute('data-segment-id'));
          selectSegment(id, true);
        });
      });
      if (list.length && !list.some(function(s){ return Number(s.id) === Number(selectedId); })) {
        selectSegment(list[0].id, false);
      }
    };
    window.renderList = renderList;

    const paramSelectEl = document.getElementById('paramSelect');
    const dateSelectEl = document.getElementById('dateSelect');
    const viewSelectEl = document.getElementById('viewSelect');
    if (viewSelectEl) {
      const opt = Array.from(viewSelectEl.options).find(function(o){ return String(o.value).toLowerCase().includes('great') || String(o.text).toLowerCase().includes('great'); });
      if (opt) viewSelectEl.value = opt.value;
    }
    if (paramSelectEl && dateSelectEl) {
      const wantedDate = firstPrevDateForParam(paramSelectEl.value);
      if (wantedDate !== 'ALL') {
        dateSelectEl.value = wantedDate;
      }
    }
    renderList();
  }
  patchWhenReady();
})();
</script>
"""


def inject_patch(html: str, patch: str) -> str:
    marker = "</body>"
    if marker not in html:
        return html + patch
    return html.replace(marker, patch + "\n" + marker)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", default="reports/supertrend_regime_discovery_dashboard.html")
    parser.add_argument("--limit", type=int, default=12000)
    parser.add_argument("--warmup-bars", type=int, default=v2.DEFAULT_WARMUP_BARS)
    parser.add_argument("--prev-display-start", default=v2.DEFAULT_PREV_DISPLAY_START)
    args = parser.parse_args()

    v2.load_env(args.env)
    prev_display_start = v2.parse_hhmm(args.prev_display_start)
    conn = v2.open_conn()
    try:
        segments = v2.load_segments(conn, args.limit)
        summary = v2.load_summary(conn)
        feature_summary = v2.load_feature_summary(conn)
        candles, candle_meta = v2.load_candles_for_segments(conn, segments, args.warmup_bars, prev_display_start)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        html = v2.build_html(segments, candles, candle_meta, summary, feature_summary, args.warmup_bars, args.prev_display_start)
        html = v5.compact_base_axis(html)
        html = v5.inject_patch(html)
        html = inject_patch(html, CLARITY_PATCH)
        html = inject_patch(html, CLICK_PATCH)
        out.write_text(html, encoding="utf-8")
        print("=== DONE generate_supertrend_regime_discovery_dashboard_v6 ===")
        print("warmup_bars=" + str(args.warmup_bars))
        print("prev_display_start=" + str(args.prev_display_start))
        print("xaxis_mode=category_compact_readable_ticks")
        print("selection_mode=exact_click_same_previous_current_bundle")
        print("clarity_layer=mission_quality_badges_default_great")
        print("output=" + str(out.resolve()))
        v5.build_report(segments, candles, candle_meta, summary, feature_summary)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
